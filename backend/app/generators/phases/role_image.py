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

from app.clients.t2i import T2IClient, T2IException
from app.constants import MAX_STORY_BOARD_NUMBER, MAX_STORY_BOARD_NUMBER_EXTENDED, API_KEY, T2V_ENDPOINT_ID, MODE_INSURANCE_CASE, MODE_STORY_NARRATION, MODE_TEXT_TO_STORYBOARD
from app.generators.base import Generator
from app.generators.phase import PhaseFinder, Phase
from app.logger import ERROR, INFO
from app.message_utils import extract_dict_from_message
from app.mode import Mode
from app.models.role_description import RoleDescription
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


class RoleImageGenerator(Generator):
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
        self.t2i_model = T2V_ENDPOINT_ID
        self.phase_finder = PhaseFinder(request)
        self.request = request
        self.mode = mode
        if content_mode == MODE_INSURANCE_CASE:
            self.image_style_suffix = "卡通风格插图，现代都市卡通风格，3D渲染。"
            self.image_size = "1440x2560"
        elif content_mode == MODE_STORY_NARRATION:
            self.image_style_suffix = "卡通插画风格，色彩鲜明，画面感强。"
            self.image_size = "1440x2560"
        elif content_mode == MODE_TEXT_TO_STORYBOARD:
            self.image_style_suffix = "卡通插画风格，色彩鲜明，画面感强。"
            self.image_size = "1440x2560"
        else:
            self.image_style_suffix = "卡通风格插图，3D渲染。"
            self.image_size = "1440x2560"
        self.max_storyboard_num = MAX_STORY_BOARD_NUMBER_EXTENDED if content_mode == MODE_TEXT_TO_STORYBOARD else MAX_STORY_BOARD_NUMBER

    @staticmethod
    def _is_no_role(role_descriptions) -> bool:
        """Return True when the only entry is the virtual '无角色' placeholder."""
        return len(role_descriptions) == 1 and role_descriptions[0].description.startswith("无角色")

    async def generate(self) -> AsyncIterable[ArkChatResponse]:
        role_description_completion = self.phase_finder.get_role_descriptions()
        role_descriptions = parse_role_description(role_description_completion)

        if not role_descriptions:
            ERROR("role descriptions not found")
            raise InvalidParameter("messages", "role descriptions not found")

        if len(role_descriptions) > self.max_storyboard_num:
            ERROR("role description count exceed limit")
            raise InvalidParameter("messages", "role description count exceed limit")

        # No-role mode: skip image generation entirely, emit empty role_images
        if self._is_no_role(role_descriptions):
            INFO("no-role mode: skipping role image generation")
            yield ArkChatCompletionChunk(
                id=get_reqid(),
                choices=[Choice(index=0, delta=ChoiceDelta(content=f"phase={Phase.ROLE_IMAGE.value}\n\n"))],
                created=int(time.time()), model=get_resource_id(), object="chat.completion.chunk"
            )
            yield _get_tool_resp(0, json.dumps({"role_images": []}))
            yield _get_tool_resp(1)
            return

        # handle case when some assets are already provided, only partial set of assets needs to be generated
        generated_role_images: List[RoleImage] = []
        if self.mode == Mode.REGENERATION:
            dict_content = extract_dict_from_message(self.request.messages[-1].content)
            role_images_json = dict_content.get("role_images", [])
            for ri in role_images_json:
                role_image = RoleImage.model_validate(ri)
                if role_image.images:
                    generated_role_images.append(role_image)

        INFO(f"generated_role_images: {generated_role_images}")

        # Return first
        yield ArkChatCompletionChunk(
            id=get_reqid(),
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(
                        content=f"phase={Phase.ROLE_IMAGE.value}\n\n",
                    ),
                ),
            ],
            created=int(time.time()),
            model=get_resource_id(),
            object="chat.completion.chunk"
        )

        tasks = []
        generated_role_image_indexes = set([ri.index for ri in generated_role_images])
        for index, rd in enumerate(role_descriptions):
            if index not in generated_role_image_indexes:
                tasks.append(asyncio.create_task(self._generate_image(index, role_descriptions)))

        pending = set(tasks)
        content = {
            "role_images": [role_image.model_dump() for role_image in generated_role_images],
        }

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                role_image_index, role_images = task.result()
                content["role_images"].append(RoleImage(
                    index=role_image_index,
                    images=role_images
                ).model_dump())

        yield _get_tool_resp(0, json.dumps(content))
        yield _get_tool_resp(1)

    async def _generate_image(self, index: int, role_descriptions: List[RoleDescription]):
        try:
            prompt = f"{role_descriptions[index].description}{self.image_style_suffix}"
            images = self.t2i_client.image_generation(prompt=prompt, model=self.t2i_model, size=self.image_size)
        except T2IException as e:
            ERROR(f"failed to generate image, code: {e.code}, message: {e}")
            return index, [e.message]
        except Exception as e:
            ERROR(f"failed to generate image, error: {e}")
            return index, ["failed to generate image"]

        return index, images
