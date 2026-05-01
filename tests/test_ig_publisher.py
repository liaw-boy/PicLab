"""Unit tests for src/core/ig_publisher.py."""
from __future__ import annotations

import io
import os
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_publisher(
    ig_user_id: str = "user123",
    fb_page_token: str = "tok456",
    upload_url: str = "https://upload.example.com",
):
    """Return an IGPublisher pre-configured via environment variables."""
    env = {
        "IG_USER_ID": ig_user_id,
        "FB_PAGE_TOKEN": fb_page_token,
        "UPLOAD_SERVER_URL": upload_url,
    }
    with patch("src.core.ig_publisher._load_env", return_value=env):
        from src.core.ig_publisher import IGPublisher
        return IGPublisher()


def _make_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(
            f"{status_code} Error", response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# IGPublisher — configuration loading
# ---------------------------------------------------------------------------

class TestIGPublisherConfig:
    def test_loads_ig_user_id_from_env(self):
        pub = _make_publisher(ig_user_id="MY_USER")
        assert pub.ig_user_id == "MY_USER"

    def test_loads_page_token_from_env(self):
        pub = _make_publisher(fb_page_token="MY_TOKEN")
        assert pub.page_token == "MY_TOKEN"

    def test_loads_upload_url_from_env(self):
        pub = _make_publisher(upload_url="https://relay.example.com/")
        # trailing slash is stripped
        assert pub.upload_url == "https://relay.example.com"

    def test_is_configured_true_when_all_values_present(self):
        pub = _make_publisher()
        assert pub.is_configured() is True

    def test_is_configured_false_when_user_id_missing(self):
        pub = _make_publisher(ig_user_id="")
        assert pub.is_configured() is False

    def test_is_configured_false_when_token_missing(self):
        pub = _make_publisher(fb_page_token="")
        assert pub.is_configured() is False

    def test_is_configured_false_when_upload_url_missing(self):
        pub = _make_publisher(upload_url="")
        assert pub.is_configured() is False


# ---------------------------------------------------------------------------
# upload_image()
# ---------------------------------------------------------------------------

class TestUploadImage:
    def test_calls_post_with_correct_url(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        resp = _make_response(200, {"url": "https://cdn.example.com/photo.jpg", "filename": "photo.jpg"})

        with patch("src.core.ig_publisher.requests.post", return_value=resp) as mock_post:
            result = pub.upload_image(str(image))

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "https://upload.example.com/upload"

    def test_returns_url_string_on_success(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        expected_url = "https://cdn.example.com/uploaded.jpg"
        resp = _make_response(200, {"url": expected_url, "filename": "uploaded.jpg"})

        with patch("src.core.ig_publisher.requests.post", return_value=resp):
            result = pub.upload_image(str(image))

        assert result == expected_url

    def test_stores_uploaded_filename(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        resp = _make_response(200, {"url": "https://cdn.example.com/x.jpg", "filename": "x.jpg"})

        with patch("src.core.ig_publisher.requests.post", return_value=resp):
            pub.upload_image(str(image))

        assert pub._uploaded_filename == "x.jpg"

    def test_raises_on_server_500(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        resp = _make_response(500, {})

        with patch("src.core.ig_publisher.requests.post", return_value=resp):
            with pytest.raises(Exception):
                pub.upload_image(str(image))

    def test_raises_on_server_400(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\x00" * 8)

        resp = _make_response(400, {})

        with patch("src.core.ig_publisher.requests.post", return_value=resp):
            with pytest.raises(Exception):
                pub.upload_image(str(image))

    def test_raises_file_not_found_for_missing_image(self):
        pub = _make_publisher()
        with pytest.raises(FileNotFoundError):
            pub.upload_image("/nonexistent/path/photo.jpg")


# ---------------------------------------------------------------------------
# publish() — orchestration sequence
# ---------------------------------------------------------------------------

class TestPublish:
    def test_calls_steps_in_sequence(self, tmp_path):
        """publish() must call _create_container → _wait_container_ready → _publish_container."""
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        call_order: list[str] = []

        def fake_upload(path):
            call_order.append("upload")
            return "https://cdn.example.com/photo.jpg"

        def fake_create(image_url, caption):
            call_order.append("create")
            return "container_abc"

        def fake_wait(container_id, timeout=60):
            call_order.append("wait")

        def fake_publish(container_id):
            call_order.append("publish")
            return "post_xyz"

        pub.upload_image = fake_upload
        pub._create_container = fake_create
        pub._wait_container_ready = fake_wait
        pub._publish_container = fake_publish
        pub._delete_uploaded = MagicMock()

        result = pub.publish(str(image), caption="Test caption")

        assert call_order == ["upload", "create", "wait", "publish"]
        assert result.success is True
        assert result.post_id == "post_xyz"

    def test_returns_failure_result_on_exception(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        pub.upload_image = MagicMock(side_effect=RuntimeError("network failure"))
        pub._delete_uploaded = MagicMock()

        result = pub.publish(str(image), caption="Test")

        assert result.success is False
        assert "network failure" in result.error

    def test_calls_delete_uploaded_on_success(self, tmp_path):
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        pub.upload_image = MagicMock(return_value="https://cdn.example.com/x.jpg")
        pub._create_container = MagicMock(return_value="cid")
        pub._wait_container_ready = MagicMock()
        pub._publish_container = MagicMock(return_value="post_id")
        pub._delete_uploaded = MagicMock()

        pub.publish(str(image), "caption")

        pub._delete_uploaded.assert_called_once()

    def test_calls_delete_uploaded_on_failure(self, tmp_path):
        """Cleanup must run even when an exception is raised mid-flow."""
        pub = _make_publisher()
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

        pub.upload_image = MagicMock(return_value="https://cdn.example.com/x.jpg")
        pub._create_container = MagicMock(side_effect=RuntimeError("API error"))
        pub._delete_uploaded = MagicMock()

        result = pub.publish(str(image), "caption")

        assert result.success is False
        pub._delete_uploaded.assert_called_once()


# ---------------------------------------------------------------------------
# _create_container() — error handling
# ---------------------------------------------------------------------------

class TestCreateContainer:
    def test_raises_runtime_error_on_api_error_json(self):
        pub = _make_publisher()

        error_resp = _make_response(200, {
            "error": {
                "message": "Invalid OAuth access token",
                "type": "OAuthException",
                "code": 190,
            }
        })

        with patch("src.core.ig_publisher.requests.post", return_value=error_resp):
            with pytest.raises(RuntimeError, match="Invalid OAuth access token"):
                pub._create_container("https://cdn.example.com/photo.jpg", "caption")

    def test_returns_container_id_on_success(self):
        pub = _make_publisher()

        ok_resp = _make_response(200, {"id": "container_999"})

        with patch("src.core.ig_publisher.requests.post", return_value=ok_resp):
            container_id = pub._create_container("https://cdn.example.com/photo.jpg", "caption")

        assert container_id == "container_999"

    def test_passes_image_url_and_caption_as_params(self):
        pub = _make_publisher()

        ok_resp = _make_response(200, {"id": "cid"})

        with patch("src.core.ig_publisher.requests.post", return_value=ok_resp) as mock_post:
            pub._create_container("https://cdn.example.com/img.jpg", "My caption")

        _, kwargs = mock_post.call_args
        params = kwargs.get("params", {})
        assert params["image_url"] == "https://cdn.example.com/img.jpg"
        assert params["caption"] == "My caption"
        assert params["access_token"] == pub.page_token

    def test_raises_runtime_error_with_unknown_message_when_error_has_no_message(self):
        pub = _make_publisher()

        error_resp = _make_response(200, {"error": {}})

        with patch("src.core.ig_publisher.requests.post", return_value=error_resp):
            with pytest.raises(RuntimeError, match="Unknown error"):
                pub._create_container("https://cdn.example.com/photo.jpg", "")
