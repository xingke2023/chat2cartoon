# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# Licensed under the 【火山方舟】原型应用软件自用许可协议
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.volcengine.com/docs/82379/1433703
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterable, Optional, List

from arkitect.types.llm.model import ArkChatRequest, ArkChatResponse, ArkChatCompletionChunk
from arkitect.core.errors import InvalidParameter, InternalServiceError
from arkitect.utils.context import get_reqid, get_resource_id
from volcenginesdkarkruntime.types.chat.chat_completion_chunk import Choice, ChoiceDelta, ChoiceDeltaToolCall, \
    ChoiceDeltaToolCallFunction

from app.clients.downloader import DownloaderClient
from app.clients.tos import TOSClient
from app.constants import ARTIFACT_TOS_BUCKET, MAX_STORY_BOARD_NUMBER, MAX_STORY_BOARD_NUMBER_EXTENDED, API_KEY, SUBTITLE_CN_FONT_SIZE, SUBTITLE_EN_FONT_SIZE, SUBTITLE_ENABLE_TRANSLATION, MODE_TEXT_TO_STORYBOARD
from app.generators.base import Generator
from app.generators.phase import PhaseFinder, Phase
import re
from app.logger import ERROR, INFO
from app.mode import Mode
from app.models.audio import Audio
from app.models.film import Film
from app.models.first_frame_image import FirstFrameImage
from app.models.tone import Tone

_current_dir = os.path.dirname(os.path.abspath(__file__))
_font = os.path.join(_current_dir, "../../../media/DouyinSansBold.otf")


def _strip_trailing_punct_cn(text: str) -> str:
    return text.rstrip('。！？，、；：')


def _strip_trailing_punct_en(text: str) -> str:
    return text.rstrip('.!?,;:')


def _split_subtitle_by_sentences_cn(line: str, start: float, end: float) -> List[tuple]:
    parts = re.split(r'(?<=[。！？，、；：])', line)
    parts = [p for p in parts if p.strip()]
    if not parts:
        return [((start, end), _strip_trailing_punct_cn(line))]

    total_len = sum(len(p) for p in parts)
    subtitles = []
    t = start
    for p in parts:
        duration = (end - start) * len(p) / total_len
        subtitles.append(((t, t + duration), _strip_trailing_punct_cn(p)))
        t += duration
    return subtitles


def _split_subtitle_by_sentences_en(line: str, start: float, end: float) -> List[tuple]:
    parts = re.split(r'(?<=[.!?,;:])\s+', line)
    parts = [p for p in parts if p.strip()]
    if not parts:
        return [((start, end), _strip_trailing_punct_en(line))]

    total_words = sum(len(p.split()) for p in parts)
    if total_words == 0:
        return [((start, end), _strip_trailing_punct_en(line))]

    subtitles = []
    t = start
    for p in parts:
        duration = (end - start) * len(p.split()) / total_words
        subtitles.append(((t, t + duration), _strip_trailing_punct_en(p)))
        t += duration
    return subtitles


def _get_tool_resp(index: int, content: Optional[str] = None) -> ArkChatCompletionChunk:
    return ArkChatCompletionChunk(
        id=get_reqid(),
        choices=[Choice(
            index=index,
            finish_reason=None if content else "stop",
            delta=ChoiceDelta(
                role="tool",
                content=f"{content}\n\n" if content else "",
                tool_calls=[
                    ChoiceDeltaToolCall(
                        index=index,
                        id="tool_call_id",
                        function=ChoiceDeltaToolCallFunction(
                            name="",
                            arguments="",
                        ),
                        type="function",
                    )
                ]
            )
        )],
        created=int(time.time()),
        model=get_resource_id(),
        object="chat.completion.chunk"
    )


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert float seconds to ASS timestamp format: H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _wrap_text(text: str, max_chars_per_line: int) -> str:
    """Insert ASS line breaks (\\N) so each line stays within max_chars_per_line."""
    if len(text) <= max_chars_per_line:
        return text
    lines = []
    while len(text) > max_chars_per_line:
        lines.append(text[:max_chars_per_line])
        text = text[max_chars_per_line:]
    if text:
        lines.append(text)
    return "\\N".join(lines)


def _build_ass_content(subtitles: List, style_name: str, font_name: str, font_size: int,
                        margin_v: int, video_width: int, video_height: int,
                        max_chars_per_line: int = 14) -> str:
    """Build ASS subtitle file content for one subtitle track."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, Outline, Shadow
Style: {style_name},{font_name},{font_size},&H00FFFFFF,&H00021526,-1,0,2,10,10,{margin_v},2,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for (start, end), text in subtitles:
        escaped = text.replace(",", "，")
        wrapped = _wrap_text(escaped, max_chars_per_line)
        lines.append(
            f"Dialogue: 0,{_seconds_to_ass_time(start)},{_seconds_to_ass_time(end)},{style_name},,0,0,0,,{wrapped}"
        )
    return header + "\n".join(lines) + "\n"


def _make_panel_video(args):
    """
    Generate a single silent panel video (static image looped for audio duration).
    Runs in a process pool to allow parallelism.
    Returns (index, panel_video_path, audio_duration).
    """
    index, image_path, audio_path, output_path, width, height = args

    # Get audio duration via ffprobe
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True, text=True, check=True,
    )
    audio_duration = float(probe.stdout.strip())

    # Create silent video from static image, scale to fill then crop to target size (no black bars)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(audio_duration),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                   f"crop={width}:{height}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            output_path,
        ],
        capture_output=True, check=True,
    )

    return index, output_path, audio_duration


def _generate_storybook_film(
    req_id: str,
    tones: List[Tone],
    first_frame_images: List[FirstFrameImage],
    audios: List[Audio],
):
    """
    Compose a storybook-style MP4 using ffmpeg:
    - Each panel = one static image displayed for the duration of its audio.
    - Audio segments are concatenated into a continuous soundtrack.
    - Bilingual ASS subtitles are burned in via ffmpeg subtitle filter.
    """
    audios.sort(key=lambda a: a.index)
    first_frame_images.sort(key=lambda f: f.index)

    VIDEO_WIDTH = 720
    VIDEO_HEIGHT = 1280

    tos_client = TOSClient()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write all image and audio bytes to temp files
        image_paths = []
        audio_paths = []
        for i, (ffi, a) in enumerate(zip(first_frame_images, audios)):
            img_path = os.path.join(tmp_dir, f"image_{i}.jpg")
            with open(img_path, "wb") as f:
                f.write(ffi.image_data)
            image_paths.append(img_path)

            aud_path = os.path.join(tmp_dir, f"audio_{i}.mp3")
            with open(aud_path, "wb") as f:
                f.write(a.audio_data)
            audio_paths.append(aud_path)

        # Generate panel videos in parallel (each static image → silent mp4)
        panel_args = [
            (
                i,
                image_paths[i],
                audio_paths[i],
                os.path.join(tmp_dir, f"panel_{i}.mp4"),
                VIDEO_WIDTH,
                VIDEO_HEIGHT,
            )
            for i in range(len(first_frame_images))
        ]

        with ThreadPoolExecutor(max_workers=min(len(panel_args), 4)) as pool:
            panel_results = list(pool.map(_make_panel_video, panel_args))

        # Sort results by index
        panel_results.sort(key=lambda r: r[0])
        panel_video_paths = [r[1] for r in panel_results]
        audio_durations = [r[2] for r in panel_results]

        # Build subtitle timing — split by sentence-ending punctuation so each sentence
        # appears as a separate subtitle entry timed proportionally to its length.
        # A panel with multiple sentences will show them one by one in sync with the audio.
        cn_subtitles = []
        en_subtitles = []
        clip_start = 0.0
        for i, (t, duration) in enumerate(zip(tones, audio_durations)):
            clip_end = clip_start + duration
            if t.line:
                cn_subtitles.extend(_split_subtitle_by_sentences_cn(t.line, clip_start, clip_end))
            if SUBTITLE_ENABLE_TRANSLATION and t.line_en:
                en_subtitles.extend(_split_subtitle_by_sentences_en(t.line_en, clip_start, clip_end))
            clip_start = clip_end

        # Write ASS subtitle files
        cn_ass_path = os.path.join(tmp_dir, "cn.ass")
        font_name = "Douyin Sans"

        with open(cn_ass_path, "w", encoding="utf-8") as f:
            f.write(_build_ass_content(
                cn_subtitles, "CN", font_name,
                font_size=SUBTITLE_CN_FONT_SIZE, margin_v=60,
                video_width=VIDEO_WIDTH, video_height=VIDEO_HEIGHT,
                max_chars_per_line=14,
            ))

        if SUBTITLE_ENABLE_TRANSLATION:
            en_ass_path = os.path.join(tmp_dir, "en.ass")
            with open(en_ass_path, "w", encoding="utf-8") as f:
                f.write(_build_ass_content(
                    en_subtitles, "EN", font_name,
                    font_size=SUBTITLE_EN_FONT_SIZE, margin_v=25,
                    video_width=VIDEO_WIDTH, video_height=VIDEO_HEIGHT,
                    max_chars_per_line=28,
                ))

        # Concat panel videos (copy, no re-encode)
        concat_list_path = os.path.join(tmp_dir, "concat_video.txt")
        with open(concat_list_path, "w") as f:
            for p in panel_video_paths:
                f.write(f"file '{p}'\n")

        concat_video_path = os.path.join(tmp_dir, "concat_video.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                concat_video_path,
            ],
            capture_output=True, check=True,
        )

        # Concat audio segments (copy, no re-encode)
        concat_audio_list_path = os.path.join(tmp_dir, "concat_audio.txt")
        with open(concat_audio_list_path, "w") as f:
            for p in audio_paths:
                f.write(f"file '{p}'\n")

        merged_audio_path = os.path.join(tmp_dir, "merged_audio.mp3")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_audio_list_path,
                "-c", "copy",
                merged_audio_path,
            ],
            capture_output=True, check=True,
        )

        # Final: merge video + audio + burn subtitles (one encode pass)
        tmp_film_path = os.path.join(tmp_dir, f"{req_id}.mp4")
        # Escape paths for ffmpeg filter (backslash and colon need escaping on Linux)
        def _esc(path: str) -> str:
            return path.replace("\\", "/").replace(":", "\\:")

        fontsdir = _esc(os.path.dirname(_font))
        vf = f"subtitles={_esc(cn_ass_path)}:fontsdir={fontsdir}"
        if SUBTITLE_ENABLE_TRANSLATION:
            vf += f",subtitles={_esc(en_ass_path)}:fontsdir={fontsdir}"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", concat_video_path,
                "-i", merged_audio_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-shortest",
                tmp_film_path,
            ],
            capture_output=True, check=True,
        )
        INFO("generated storybook film via ffmpeg")

        tos_bucket_name = ARTIFACT_TOS_BUCKET
        tos_object_key = f"{req_id}/{Phase.FILM.value}_storybook.mp4"
        try:
            tos_client.put_object_from_file(tos_bucket_name, tos_object_key, tmp_film_path)
            INFO("put storybook film to TOS")
        except Exception as e:
            ERROR(f"failed to put storybook film to TOS, error: {e}")
            raise InternalServiceError("failed to upload storybook film")

    output = tos_client.pre_signed_url(tos_bucket_name, tos_object_key)
    return output.signed_url


class StorybookFilmGenerator(Generator):
    phase_finder: PhaseFinder
    request: ArkChatRequest
    tos_client: TOSClient
    downloader_client: DownloaderClient
    mode: Mode

    def __init__(self, request: ArkChatRequest, mode: Mode):
        super().__init__(request, mode)
        self.tos_client = TOSClient()
        self.downloader_client = DownloaderClient()
        self.phase_finder = PhaseFinder(request)
        self.request = request
        self.mode = mode
        content_mode = request.metadata.get("mode", "") if request.metadata else ""
        self.max_storyboard_num = MAX_STORY_BOARD_NUMBER_EXTENDED if content_mode == MODE_TEXT_TO_STORYBOARD else MAX_STORY_BOARD_NUMBER

    async def generate(self) -> AsyncIterable[ArkChatResponse]:
        tones = self.phase_finder.get_tones()
        first_frame_images = self.phase_finder.get_first_frame_images()
        audios = self.phase_finder.get_audios()

        if not tones:
            ERROR("tones not found")
            raise InvalidParameter("messages", "tones not found")

        if not first_frame_images:
            ERROR("first_frame_images not found")
            raise InvalidParameter("messages", "first_frame_images not found")

        if not audios:
            ERROR("audios not found")
            raise InvalidParameter("messages", "audios not found")

        if len(tones) != len(first_frame_images) or len(tones) != len(audios):
            ERROR(
                f"count mismatch: tones={len(tones)}, first_frame_images={len(first_frame_images)}, audios={len(audios)}"
            )
            raise InvalidParameter("messages", "number of tones, first_frame_images and audios do not match")

        if len(tones) > self.max_storyboard_num:
            ERROR(f"tones count: {len(tones)} exceed limit")
            raise InvalidParameter("messages", "tones count exceed limit")

        INFO(f"StorybookFilm: tones={len(tones)}, images={len(first_frame_images)}, audios={len(audios)}")

        # Signal start
        yield ArkChatCompletionChunk(
            id=get_reqid(),
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(
                        content=f"phase={Phase.FILM.value}\n\n",
                    ),
                ),
            ],
            created=int(time.time()),
            model=get_resource_id(),
            object="chat.completion.chunk"
        )

        # Download images and audios in parallel
        audio_download_tasks = [asyncio.create_task(self._download_audio(a)) for a in audios]
        image_download_tasks = [asyncio.create_task(self._download_image(ffi)) for ffi in first_frame_images]
        await asyncio.gather(*(audio_download_tasks + image_download_tasks))

        # Run ffmpeg composition in a separate thread to avoid blocking the event loop.
        # While waiting, yield keepalive chunks every 20s to prevent proxy timeout.
        loop = asyncio.get_event_loop()
        film_future = loop.run_in_executor(
            ThreadPoolExecutor(max_workers=1),
            _generate_storybook_film,
            get_reqid(),
            tones,
            first_frame_images,
            audios,
        )

        while not film_future.done():
            try:
                await asyncio.wait_for(asyncio.shield(film_future), timeout=20)
                break
            except asyncio.TimeoutError:
                # Send a keepalive empty chunk so the SSE connection stays alive
                yield ArkChatCompletionChunk(
                    id=get_reqid(),
                    choices=[Choice(index=0, delta=ChoiceDelta(content=""))],
                    created=int(time.time()),
                    model=get_resource_id(),
                    object="chat.completion.chunk",
                )

        film_presigned_url = await film_future

        content = {"film": Film(url=film_presigned_url).model_dump()}
        yield _get_tool_resp(0, json.dumps(content))
        yield _get_tool_resp(1)

    async def _download_audio(self, a: Audio):
        if not a.url.startswith("http"):
            raise InvalidParameter("message", "invalid audio url")
        audio_data, _ = self.downloader_client.download_to_memory(a.url)
        a.audio_data = audio_data.read()
        INFO(f"downloaded audio, index: {a.index}")

    async def _download_image(self, ffi: FirstFrameImage):
        if not ffi.images:
            raise InvalidParameter("message", "first_frame_image has no urls")
        image_url = ffi.images[0]
        if not image_url.startswith("http"):
            raise InvalidParameter("message", "invalid image url")
        image_data, _ = self.downloader_client.download_to_memory(image_url)
        ffi.image_data = image_data.read()
        INFO(f"downloaded first_frame_image, index: {ffi.index}")
