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
import time
from typing import AsyncIterable, List, Optional

from arkitect.types.llm.model import ArkChatRequest, ArkChatResponse, ArkChatCompletionChunk
from arkitect.utils.context import get_reqid, get_resource_id
from arkitect.core.errors import InvalidParameter
from volcenginesdkarkruntime.types.chat.chat_completion_chunk import ChoiceDelta, Choice, ChoiceDeltaToolCall, \
    ChoiceDeltaToolCallFunction

from app.clients.t2i import T2IClient, T2IException, url_to_base64
from app.constants import MAX_STORY_BOARD_NUMBER, MAX_STORY_BOARD_NUMBER_EXTENDED, API_KEY, T2V_ENDPOINT_ID, REALISTIC_T2I_ENDPOINT_ID, REALISTIC_T2I_MODEL, MODE_INSURANCE_CASE, MODE_STORY_NARRATION, MODE_TEXT_TO_STORYBOARD, MODE_TEXT_TO_VIDEO
from app.generators.base import Generator
from app.generators.phase import PhaseFinder, Phase
from app.logger import ERROR, INFO
from app.message_utils import extract_dict_from_message
from app.mode import Mode
from app.models.first_frame_description import FirstFrameDescription
from app.models.first_frame_image import FirstFrameImage
from app.models.role_image import RoleImage
from app.output_parsers import parse_role_description


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


class FirstFrameImageGenerator(Generator):
    t2i_client: T2IClient
    request: ArkChatRequest
    phase_finder: PhaseFinder
    mode: Mode

    def __init__(self, request: ArkChatRequest, mode: Mode.NORMAL):
        super().__init__(request, mode)

        t2i_api_key = API_KEY
        content_mode = ""
        if request.metadata:
            t2i_api_key = request.metadata.get("t2i_api_key", API_KEY)
            content_mode = request.metadata.get("mode", "")
        self.t2i_client = T2IClient(t2i_api_key)
        self.t2i_model = REALISTIC_T2I_ENDPOINT_ID if content_mode == MODE_TEXT_TO_VIDEO and REALISTIC_T2I_ENDPOINT_ID else T2V_ENDPOINT_ID
        self.phase_finder = PhaseFinder(request)
        self.request = request
        self.mode = mode
        self.content_mode = content_mode
        self.reference_image = request.metadata.get("reference_image") if request.metadata else None
        if content_mode == MODE_INSURANCE_CASE:
            self.image_style_suffix = "卡通风格插图，现代都市卡通风格，3D渲染。"
            self.image_size = "1440x2560"
        elif content_mode == MODE_STORY_NARRATION:
            self.image_style_suffix = "卡通插画风格，色彩鲜明，画面感强。"
            self.image_size = "1440x2560"
        elif content_mode == MODE_TEXT_TO_STORYBOARD:
            self.image_style_suffix = "卡通插画风格，色彩鲜明，画面感强。"
            self.image_size = "1440x2560"
        elif content_mode == MODE_TEXT_TO_VIDEO:
            self.image_style_suffix = "写实摄影风格，真实人物，电影质感，高清细节。"
            self.image_size = "1440x2560"
        else:
            self.image_style_suffix = "卡通风格插图，3D渲染。"
            self.image_size = "1440x2560"
        self.max_storyboard_num = MAX_STORY_BOARD_NUMBER_EXTENDED if content_mode == MODE_TEXT_TO_STORYBOARD else MAX_STORY_BOARD_NUMBER

    async def generate(self) -> AsyncIterable[ArkChatResponse]:
        _, first_frame_descriptions = self.phase_finder.get_first_frame_descriptions()

        if not first_frame_descriptions:
            ERROR("first frame descriptions not found")
            raise InvalidParameter("messages", "first frame descriptions not found")

        if len(first_frame_descriptions) > self.max_storyboard_num:
            ERROR("first frame description count exceed limit")
            raise InvalidParameter("messages", "first frame description count exceed limit")

        # In text_to_video mode, load role images to use as per-storyboard reference
        role_images: List[RoleImage] = []
        role_names: List[str] = []
        if self.content_mode == MODE_TEXT_TO_VIDEO:
            role_images = self.phase_finder.get_role_images()
            role_descriptions = parse_role_description(self.phase_finder.get_role_descriptions())
            role_names = [rd.name for rd in role_descriptions]
            INFO(f"role_images for first_frame: {[ri.index for ri in role_images]}, role_names: {role_names}")

        # handle case when some assets are already provided, only partial set of assets needs to be generated
        generated_first_frame_images: List[FirstFrameImage] = []
        if self.mode == Mode.REGENERATION:
            dict_content = extract_dict_from_message(self.request.messages[-1].content)
            first_frame_images_json = dict_content.get("first_frame_images", [])
            for ri in first_frame_images_json:
                first_frame_image = FirstFrameImage.model_validate(ri)
                if first_frame_image.images:
                    generated_first_frame_images.append(first_frame_image)

        INFO(f"generated_first_frame_images: {generated_first_frame_images}")

        # Return first
        yield ArkChatCompletionChunk(
            id=get_reqid(),
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(
                        content=f"phase={Phase.FIRST_FRAME_IMAGE.value}\n\n",
                    ),
                ),
            ],
            created=int(time.time()),
            model=get_resource_id(),
            object="chat.completion.chunk"
        )

        tasks = []
        generated_first_frame_image_indexes = set([ffi.index for ffi in generated_first_frame_images])
        for index, rd in enumerate(first_frame_descriptions):
            if index not in generated_first_frame_image_indexes:
                tasks.append(asyncio.create_task(self._generate_image(index, first_frame_descriptions, role_images, role_names)))

        pending = set(tasks)
        content = {
            "first_frame_images": [role_image.model_dump() for role_image in generated_first_frame_images],
        }

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                first_frame_image_index, first_frame_images = task.result()
                content["first_frame_images"].append(FirstFrameImage(
                    index=first_frame_image_index,
                    images=first_frame_images,
                ).model_dump())

        yield _get_tool_resp(0, json.dumps(content))
        yield _get_tool_resp(1)

    def _find_role_image_url(self, characters: List[str], role_images: List[RoleImage], role_names: List[str]) -> Optional[str]:
        """Find the best matching role image URL for the given characters."""
        if not role_images:
            return None
        # Try to find a role image matching one of the storyboard's characters
        for char in characters:
            char = char.strip()
            if not char or char == "无角色":
                continue
            for i, name in enumerate(role_names):
                if char in name or name in char:
                    matching = next((ri for ri in role_images if ri.index == i), None)
                    if matching and matching.images:
                        return matching.images[0]
        # Fall back to first available role image
        for ri in sorted(role_images, key=lambda x: x.index):
            if ri.images:
                return ri.images[0]
        return None

    async def _generate_image(self, index: int, first_frame_descriptions: List[FirstFrameDescription],
                               role_images: Optional[List[RoleImage]] = None,
                               role_names: Optional[List[str]] = None):
        try:
            desc = first_frame_descriptions[index]
            if self.content_mode == MODE_TEXT_TO_VIDEO and role_images:
                # Use role image URL as reference via seedream image-to-image API
                role_image_url = self._find_role_image_url(desc.characters, role_images, role_names or [])
                if role_image_url:
                    prompt = f"与参考图人物外貌保持高度一致，{desc.description}{self.image_style_suffix}"
                    images = self.t2i_client.image_generation_with_reference_url(
                        prompt=prompt,
                        model=REALISTIC_T2I_MODEL,
                        image_url=role_image_url,
                        size="2K",
                    )
                    return index, images
            # Fallback: text-to-image
            reference_image = self.reference_image or None
            if reference_image:
                prompt = f"与参考图人物外貌保持高度一致，{desc.description}{self.image_style_suffix}"
            else:
                prompt = f"{desc.description}{self.image_style_suffix}"
            images = self.t2i_client.image_generation(
                prompt=prompt,
                model=self.t2i_model,
                size=self.image_size,
                reference_image=reference_image,
            )
        except T2IException as e:
            ERROR(f"failed to generate image, code: {e.code}, message: {e}")
            return index, [e.message]
        except Exception as e:
            ERROR(f"failed to generate image, error: {e}")
            return index, ["failed to generate image"]

        return index, images
