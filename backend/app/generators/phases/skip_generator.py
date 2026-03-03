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

import json
import time
from typing import AsyncIterable, Optional

from arkitect.types.llm.model import ArkChatRequest, ArkChatResponse, ArkChatCompletionChunk
from arkitect.utils.context import get_reqid, get_resource_id
from volcenginesdkarkruntime.types.chat.chat_completion_chunk import Choice, ChoiceDelta, ChoiceDeltaToolCall, \
    ChoiceDeltaToolCallFunction

from app.generators.base import Generator
from app.generators.phase import Phase
from app.mode import Mode


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


class SkipVideoDescriptionGenerator(Generator):
    """
    In story_narration mode, VideoDescription phase is skipped.
    Outputs an empty phase marker so the frontend can advance automatically.
    """

    def __init__(self, request: ArkChatRequest, mode: Mode):
        super().__init__(request, mode)

    async def generate(self) -> AsyncIterable[ArkChatResponse]:
        yield ArkChatCompletionChunk(
            id=get_reqid(),
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(
                        content=f"phase={Phase.VIDEO_DESCRIPTION.value}\n\n",
                    ),
                ),
            ],
            created=int(time.time()),
            model=get_resource_id(),
            object="chat.completion.chunk"
        )
        # Empty video_descriptions so downstream phases won't look for them
        yield _get_tool_resp(0, json.dumps({"video_descriptions": ""}))
        yield _get_tool_resp(1)


class SkipVideoGenerator(Generator):
    """
    In story_narration mode, Video phase is skipped.
    Outputs an empty videos list so the frontend can advance automatically.
    """

    def __init__(self, request: ArkChatRequest, mode: Mode):
        super().__init__(request, mode)

    async def generate(self) -> AsyncIterable[ArkChatResponse]:
        yield ArkChatCompletionChunk(
            id=get_reqid(),
            choices=[
                Choice(
                    index=0,
                    delta=ChoiceDelta(
                        content=f"phase={Phase.VIDEO.value}\n\n",
                    ),
                ),
            ],
            created=int(time.time()),
            model=get_resource_id(),
            object="chat.completion.chunk"
        )
        # Empty videos list — StorybookFilmGenerator will use first_frame_images instead
        yield _get_tool_resp(0, json.dumps({"videos": []}))
        yield _get_tool_resp(1)
