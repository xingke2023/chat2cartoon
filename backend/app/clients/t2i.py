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

import base64
import io
import json
import uuid
from json import JSONDecodeError
from typing import Optional, List

import requests
from pydantic import BaseModel
from volcengine.visual.VisualService import VisualService
from volcenginesdkarkruntime import Ark

from app.constants import ARK_ACCESS_KEY, ARK_SECRET_KEY, ARTIFACT_TOS_BUCKET
from app.logger import INFO, ERROR


def url_to_base64(url: str) -> Optional[str]:
    """Download an image URL and return its base64-encoded content."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        ERROR(f"failed to download image from url {url}: {e}")
        return None

_DEFAULT_REQ_KEY = "high_aes_general_v20_L"
_DEFAULT_MODEL_VERSION = "general_v2.0_L"

POST_IMG_RISK_NOT_PASS_ERROR_CODE = 50511
POST_IMG_RISK_NOT_PASS_MESSAGE = "Post Img Risk Not Pass"
TEXT_RISK_NOT_PASS_ERROR_CODE = 50412
TEXT_RISK_NOT_PASS_MESSAGE = "Text Risk Not Pass"


class T2IException(Exception):
    def __init__(self, code, message):
        super().__init__(message)  # Pass the message to the base class
        self.code = code  # Additional attribute for error code
        self.message = message

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.code})"


_ARK_IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"


class T2IClient:
    t2i_client: Ark

    def __init__(self, t2i_api_key: str) -> None:
        self.t2i_client = Ark(api_key=t2i_api_key, region="cn-beijing")
        self.api_key = t2i_api_key

    def image_generation(self, prompt: str, model: str, size: Optional[str] = None,
                         reference_image: Optional[str] = None) -> List[str]:
        """
        API Docs: https://www.volcengine.com/docs/82379/1541523
        size: e.g. "768x1344" for 9:16 portrait, "1344x768" for 16:9 landscape (default)
        reference_image: base64-encoded image string for image-to-image generation
        """
        kwargs = dict(model=model, prompt=prompt)
        if size:
            kwargs["size"] = size
        if reference_image:
            kwargs["extra_body"] = {"reference_image": reference_image}
        images = self.t2i_client.images.generate(**kwargs)
        return [item.url for item in images.data]

    def upload_base64_to_tos(self, base64_str: str) -> Optional[str]:
        """Upload a base64-encoded image to TOS and return a pre-signed URL."""
        try:
            from app.clients.tos import TOSClient
            image_bytes = base64.b64decode(base64_str)
            object_key = f"reference_images/{uuid.uuid4().hex}.jpg"
            tos_client = TOSClient()
            tos_client.put_object(ARTIFACT_TOS_BUCKET, object_key, io.BytesIO(image_bytes))
            url_output = tos_client.pre_signed_url(ARTIFACT_TOS_BUCKET, object_key)
            return url_output.signed_url
        except Exception as e:
            ERROR(f"failed to upload reference image to TOS: {e}")
            return None

    def image_generation_with_reference_url(self, prompt: str, model: str, image_url: str,
                                             size: Optional[str] = None) -> List[str]:
        """
        Image-to-image generation using doubao-seedream API.
        Uses direct HTTP call with 'image' parameter (URL) instead of base64 reference_image.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "image": image_url,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "stream": False,
            "watermark": False,
        }
        if size:
            payload["size"] = size
        resp = requests.post(
            _ARK_IMAGE_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["url"] for item in data.get("data", [])]


class LogoInfo(BaseModel):
    add_logo: Optional[bool] = None
    position: Optional[int] = None
    language: Optional[int] = None
    opacity: Optional[float] = None


class T2ICreateTextToImageRequest(BaseModel):
    req_key: str
    prompt: str
    model_version: str
    seed: Optional[int] = None
    scale: Optional[float] = None
    ddim_steps: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    use_rephraser: Optional[bool] = None
    use_sr: Optional[bool] = None
    sr_seed: Optional[int] = None
    double_sr_strength: Optional[bool] = None
    double_sr_scale: Optional[float] = None
    i32_sr_steps: Optional[int] = None
    is_only_sr: Optional[bool] = None
    return_url: Optional[bool] = None
    logo_info: Optional[LogoInfo] = None


class T2ICreateTextToImageResponse(BaseModel):
    binary_data_base64: Optional[List[str]]
    image_urls: Optional[List[str]]
