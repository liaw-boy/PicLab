"""Instagram Content Publishing via Graph API."""
from __future__ import annotations

import os
import time
import requests
from dataclasses import dataclass
from pathlib import Path


def _load_env() -> dict:
    env: dict[str, str] = {}
    env_path = Path(__file__).parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k in env or not env})
    return env


@dataclass
class PublishResult:
    success: bool
    post_id: str = ""
    error: str = ""


class IGPublisher:
    API_BASE = "https://graph.facebook.com/v19.0"

    def __init__(self) -> None:
        cfg = _load_env()
        self.ig_user_id = cfg.get("IG_USER_ID", "")
        self.page_token = cfg.get("FB_PAGE_TOKEN", "")
        self.upload_url = cfg.get("UPLOAD_SERVER_URL", "").rstrip("/")
        self._uploaded_filename: str = ""

    def is_configured(self) -> bool:
        return bool(self.ig_user_id and self.page_token and self.upload_url)

    def upload_image(self, image_path: str) -> str:
        """Upload image to relay server, return public HTTPS URL."""
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"{self.upload_url}/upload",
                files={"image": (Path(image_path).name, f, "image/jpeg")},
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()
        self._uploaded_filename = data.get("filename", "")
        return data["url"]

    def _delete_uploaded(self) -> None:
        if self._uploaded_filename:
            try:
                requests.delete(
                    f"{self.upload_url}/upload/{self._uploaded_filename}",
                    timeout=10,
                )
            except Exception:
                pass
            self._uploaded_filename = ""

    def _create_container(self, image_url: str, caption: str) -> str:
        resp = requests.post(
            f"{self.API_BASE}/{self.ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.page_token,
            },
            timeout=30,
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "Unknown error"))
        return data["id"]

    def _wait_container_ready(self, container_id: str, timeout: int = 60) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(
                f"{self.API_BASE}/{container_id}",
                params={"fields": "status_code", "access_token": self.page_token},
                timeout=15,
            )
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError("Media container processing failed")
            time.sleep(3)
        raise RuntimeError("Media container timed out")

    def _publish_container(self, container_id: str) -> str:
        resp = requests.post(
            f"{self.API_BASE}/{self.ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.page_token,
            },
            timeout=30,
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "Unknown error"))
        return data["id"]

    def publish(self, image_path: str, caption: str) -> PublishResult:
        try:
            image_url = self.upload_image(image_path)
            container_id = self._create_container(image_url, caption)
            self._wait_container_ready(container_id)
            post_id = self._publish_container(container_id)
            self._delete_uploaded()
            return PublishResult(success=True, post_id=post_id)
        except Exception as e:
            self._delete_uploaded()
            return PublishResult(success=False, error=str(e))
