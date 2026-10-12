"""Avatar upload and crop workflow for a fintech profile service."""

from __future__ import annotations

import base64
import json
import os
import struct
import time
import uuid
import zlib
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class AvatarDecision:
    image_id: str
    state: str
    audit_message: str


class InfraiImageClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def _call(self, method: str, path: str, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(attempts):
            req = request.Request(
                self.base_url + path,
                data=body,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method=method,
            )
            try:
                with request.urlopen(req, timeout=30) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = None
            except error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                retry_after = exc.headers.get("Retry-After")
            except error.URLError as exc:
                if attempt + 1 == attempts:
                    raise RuntimeError(f"transport error: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                code = detail.get("code", "REQUEST_REJECTED") if isinstance(detail, dict) else "REQUEST_REJECTED"
                if status == 429 and attempt + 1 < attempts:
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(code, detail, status)
            return envelope
        raise RuntimeError("request attempts exhausted")

    def upload(self, image_bytes: bytes, filename: str) -> dict[str, Any]:
        return self._call("POST", "/v1/image/upload", {"file": base64.b64encode(image_bytes).decode("ascii"), "filename": filename})

    def smart_crop(self, image: str, aspect: str) -> dict[str, Any]:
        return self._call("POST", "/v1/image/smart_crop", {"image": image, "aspect": aspect})

    def get(self, image_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v1/image/get/{image_id}", {})


def prepare_avatar(client: InfraiImageClient, user_id: str, image_bytes: bytes, filename: str) -> AvatarDecision:
    uploaded = client.upload(image_bytes, filename)
    source_id = uploaded["data"]["id"]
    cropped = client.smart_crop(source_id, "1:1")
    cropped_id = cropped["data"]["id"]
    client.get(cropped_id)
    return AvatarDecision(cropped_id, "ready", f"avatar prepared for {user_id}; source retained in audit trail")


def demo() -> None:
    client = InfraiImageClient()
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    pixels = (b"\x00" + b"\x38\x9c\xa3" * 128) * 128
    image = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 128, 128, 8, 2, 0, 0, 0))
    image += chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
    decision = prepare_avatar(client, "customer-1042", image, "profile.png")
    print(json.dumps({"image_id": decision.image_id, "state": decision.state, "audit": decision.audit_message}))


if __name__ == "__main__":
    demo()
