from avatar_pipeline import AvatarDecision, InfraiImageClient, prepare_avatar


class FakeClient:
    def __init__(self):
        self.calls = []

    def upload(self, image_bytes, filename):
        self.calls.append(("upload", filename, image_bytes))
        return {"ok": True, "data": {"id": "raw-1"}}

    def smart_crop(self, image, aspect):
        self.calls.append(("smart_crop", image, aspect))
        return {"ok": True, "data": {"id": "avatar-1"}}

    def get(self, image_id):
        self.calls.append(("get", image_id))
        return {"ok": True, "data": {"id": image_id}}


def test_avatar_decision_is_ready_after_square_crop():
    client = FakeClient()
    result = prepare_avatar(client, "customer-1042", b"bytes", "selfie.jpg")
    assert isinstance(result, AvatarDecision)
    assert result.state == "ready"
    assert result.image_id == "avatar-1"
    assert client.calls == [
        ("upload", "selfie.jpg", b"bytes"),
        ("smart_crop", "raw-1", "1:1"),
        ("get", "avatar-1"),
    ]


def test_upload_base64_encodes_binary_bytes():
    client = InfraiImageClient(api_key="test")
    calls = []
    client._call = lambda method, path, payload: calls.append((method, path, payload)) or {"ok": True}
    client.upload(b"\x00\xff\x80", "selfie.png")
    assert calls == [("POST", "/v1/image/upload", {"file": "AP+A", "filename": "selfie.png"})]
