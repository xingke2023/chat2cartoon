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
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterable, Optional, List, Tuple

from arkitect.types.llm.model import ArkChatRequest, ArkChatResponse, ArkChatCompletionChunk
from arkitect.core.errors import InvalidParameter, InternalServiceError
from arkitect.utils.context import get_reqid, get_resource_id
from volcenginesdkarkruntime import Ark
from volcenginesdkarkruntime.types.chat.chat_completion_chunk import Choice, ChoiceDelta, ChoiceDeltaToolCall, \
    ChoiceDeltaToolCallFunction

from app.clients.downloader import DownloaderClient
from app.clients.tos import TOSClient
from app.constants import ARTIFACT_TOS_BUCKET, MAX_STORY_BOARD_NUMBER, MAX_STORY_BOARD_NUMBER_EXTENDED, API_KEY, \
    MODE_TEXT_TO_STORYBOARD, SUBTITLE_CN_FONT_SIZE, SUBTITLE_EN_FONT_SIZE, SUBTITLE_ENABLE_TRANSLATION
from app.generators.base import Generator
from app.generators.phase import PhaseFinder, Phase
from app.logger import ERROR, INFO
from app.mode import Mode
from app.models.audio import Audio
from app.models.film import Film
from app.models.tone import Tone
from app.models.video import Video

_current_dir = os.path.dirname(os.path.abspath(__file__))
_font = os.path.join(_current_dir, "../../../media/DouyinSansBold.otf")


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


def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(probe.stdout.strip())


def _get_video_size(video_path: str) -> Tuple[int, int]:
    """Get video width and height via ffprobe."""
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    parts = probe.stdout.strip().split("x")
    return int(parts[0]), int(parts[1])


def _prepare_panel(args):
    """
    Normalize a single video clip: re-encode with audio trimmed/replaced by the TTS audio.
    Returns (index, panel_video_path, duration).
    """
    index, video_path, audio_path, output_path = args

    video_duration = _get_video_duration(video_path)
    audio_duration = _get_video_duration(audio_path)

    # Use the video duration; trim audio if longer, pad silence if shorter
    duration = video_duration

    if audio_duration >= video_duration:
        # Trim audio to video length
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-t", str(duration),
                "-c:v", "copy",
                "-c:a", "aac",
                output_path,
            ],
            capture_output=True, check=True,
        )
    else:
        # Pad audio with silence to reach video duration
        pad_duration = video_duration - audio_duration
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={pad_duration}",
                "-filter_complex", "[1:a][2:a]concat=n=2:v=0:a=1[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
                "-t", str(duration),
                "-c:v", "copy",
                "-c:a", "aac",
                output_path,
            ],
            capture_output=True, check=True,
        )

    return index, output_path, duration


def _generate_film(req_id: str, tones: List[Tone], videos: List[Video], audios: List[Audio]):
    """
    Compose final MP4 using ffmpeg:
    - Each clip = one video with its TTS audio.
    - Clips are concatenated (re-encode for consistent stream).
    - Bilingual ASS subtitles burned in.
    - Uploaded to TOS, returns presigned URL.
    """
    videos.sort(key=lambda v: v.index)
    audios.sort(key=lambda a: a.index)

    tos_client = TOSClient()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write video and audio bytes to temp files
        video_paths = []
        audio_paths = []
        for i, (v, a) in enumerate(zip(videos, audios)):
            vid_path = os.path.join(tmp_dir, f"video_{i}.mp4")
            with open(vid_path, "wb") as f:
                f.write(v.video_data)
            video_paths.append(vid_path)

            aud_path = os.path.join(tmp_dir, f"audio_{i}.mp3")
            with open(aud_path, "wb") as f:
                f.write(a.audio_data)
            audio_paths.append(aud_path)

        # Get video size from first clip
        video_width, video_height = _get_video_size(video_paths[0])

        # Prepare panel clips in parallel (merge video + tts audio)
        panel_args = [
            (i, video_paths[i], audio_paths[i], os.path.join(tmp_dir, f"panel_{i}.mp4"))
            for i in range(len(videos))
        ]
        with ThreadPoolExecutor(max_workers=min(len(panel_args), 4)) as pool:
            panel_results = list(pool.map(_prepare_panel, panel_args))

        panel_results.sort(key=lambda r: r[0])
        panel_video_paths = [r[1] for r in panel_results]
        panel_durations = [r[2] for r in panel_results]

        # Build subtitle timing
        cn_subtitles = []
        en_subtitles = []
        clip_start = 0.0
        for t, duration in zip(tones, panel_durations):
            clip_end = clip_start + duration
            if t.line:
                cn_subtitles.extend(_split_subtitle_by_sentences_cn(t.line, clip_start, clip_end))
            if SUBTITLE_ENABLE_TRANSLATION and t.line_en:
                en_subtitles.extend(_split_subtitle_by_sentences_en(t.line_en, clip_start, clip_end))
            clip_start = clip_end

        # Write ASS subtitle files
        font_name = "Douyin Sans"
        cn_ass_path = os.path.join(tmp_dir, "cn.ass")
        with open(cn_ass_path, "w", encoding="utf-8") as f:
            f.write(_build_ass_content(
                cn_subtitles, "CN", font_name,
                font_size=SUBTITLE_CN_FONT_SIZE, margin_v=60,
                video_width=video_width, video_height=video_height,
                max_chars_per_line=14,
            ))

        if SUBTITLE_ENABLE_TRANSLATION:
            en_ass_path = os.path.join(tmp_dir, "en.ass")
            with open(en_ass_path, "w", encoding="utf-8") as f:
                f.write(_build_ass_content(
                    en_subtitles, "EN", font_name,
                    font_size=SUBTITLE_EN_FONT_SIZE, margin_v=25,
                    video_width=video_width, video_height=video_height,
                    max_chars_per_line=28,
                ))

        # Concat panel clips
        concat_list_path = os.path.join(tmp_dir, "concat.txt")
        with open(concat_list_path, "w") as f:
            for p in panel_video_paths:
                f.write(f"file '{p}'\n")

        concat_path = os.path.join(tmp_dir, "concat.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                concat_path,
            ],
            capture_output=True, check=True,
        )

        # Burn subtitles (one final encode pass)
        def _esc(path: str) -> str:
            return path.replace("\\", "/").replace(":", "\\:")

        fontsdir = _esc(os.path.dirname(_font))
        vf = f"subtitles={_esc(cn_ass_path)}:fontsdir={fontsdir}"
        if SUBTITLE_ENABLE_TRANSLATION:
            vf += f",subtitles={_esc(en_ass_path)}:fontsdir={fontsdir}"

        tmp_film_path = os.path.join(tmp_dir, f"{req_id}.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", concat_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                tmp_film_path,
            ],
            capture_output=True, check=True,
        )
        INFO("generated final film via ffmpeg")

        tos_bucket_name = ARTIFACT_TOS_BUCKET
        tos_object_key = f"{req_id}/{Phase.FILM.value}.mp4"
        try:
            tos_client.put_object_from_file(tos_bucket_name, tos_object_key, tmp_film_path)
            INFO("put final film to TOS")
        except Exception as e:
            ERROR(f"failed to put film to TOS, error: {e}")
            raise InternalServiceError("failed to upload film")

    output = tos_client.pre_signed_url(tos_bucket_name, tos_object_key)
    return output.signed_url


class FilmGenerator(Generator):
    phase_finder: PhaseFinder
    request: ArkChatRequest
    tos_client: TOSClient
    content_generation_client: Ark
    downloader_client: DownloaderClient
    mode: Mode

    def __init__(self, request: ArkChatRequest, mode: Mode.NORMAL):
        super().__init__(request, mode)
        self.tos_client = TOSClient()
        self.content_generation_client = Ark(api_key=API_KEY)
        self.downloader_client = DownloaderClient()
        self.phase_finder = PhaseFinder(request)
        self.request = request
        self.mode = mode
        content_mode = request.metadata.get("mode", "") if request.metadata else ""
        self.max_storyboard_num = MAX_STORY_BOARD_NUMBER_EXTENDED if content_mode == MODE_TEXT_TO_STORYBOARD else MAX_STORY_BOARD_NUMBER

    async def generate(self) -> AsyncIterable[ArkChatResponse]:
        tones = self.phase_finder.get_tones()
        videos = self.phase_finder.get_videos()
        audios = self.phase_finder.get_audios()

        if not tones:
            ERROR("tones not found")
            raise InvalidParameter("messages", "tones not found")

        if not videos:
            ERROR("videos not found")
            raise InvalidParameter("messages", "videos not found")

        if not audios:
            ERROR("audios not found")
            raise InvalidParameter("messages", "audios not found")

        if len(tones) != len(videos) or len(tones) != len(audios):
            ERROR(
                f"number of tones: {len(tones)}, num of videos: {len(videos)} and num of audios: {len(audios)} do not match")
            raise InvalidParameter("messages", "number of tones videos and audios do not match")

        if len(tones) > self.max_storyboard_num:
            ERROR(f"tones count: {len(tones)} exceed limit")
            raise InvalidParameter("messages", "tones count exceed limit")

        INFO(f"len(tones) = {len(tones)}, len(videos) = {len(videos)}, len(audios) = {len(audios)}")

        # Return first
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

        video_download_tasks = [asyncio.create_task(self._download_video(v)) for v in videos]
        audio_download_tasks = [asyncio.create_task(self._download_audio(a)) for a in audios]
        await asyncio.gather(*(video_download_tasks + audio_download_tasks))

        loop = asyncio.get_event_loop()
        film_presigned_url = await loop.run_in_executor(
            ThreadPoolExecutor(max_workers=1),
            _generate_film,
            get_reqid(), tones, videos, audios,
        )

        content = {"film": Film(url=film_presigned_url).model_dump()}
        yield _get_tool_resp(0, json.dumps(content))
        yield _get_tool_resp(1)

    async def _download_video(self, v: Video):
        video_gen_task = self.content_generation_client.content_generation.tasks.get(task_id=v.video_gen_task_id)
        if video_gen_task.status != "succeeded":
            ERROR(f"video is not ready, index: {v.index}")
            raise InvalidParameter("messages", "video is not ready")

        video_url = video_gen_task.content.video_url
        if video_url is None:
            ERROR(f"video_url is empty, index: {v.index}")
            raise InvalidParameter("messages", "video_url is empty")

        video_data, _ = self.downloader_client.download_to_memory(video_url)
        v.video_data = video_data.read()
        INFO(f"downloaded video, index: {v.index}")

    async def _download_audio(self, a: Audio):
        if not a.url.startswith("http"):
            raise InvalidParameter("message", "invalid audio url")
        audio_data, _ = self.downloader_client.download_to_memory(a.url)
        a.audio_data = audio_data.read()
        INFO(f"downloaded audio, index: {a.index}")
