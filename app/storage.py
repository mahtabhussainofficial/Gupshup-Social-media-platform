"""Where uploaded files live.

Today: the local disk (MEDIA_DIR). The routers only call save_profile_image() and
delete_profile_image(), so moving to cloud storage later (Azure Blob Storage, S3, ...)
means replacing this one file, not touching the routers.

Important for Azure: the disk inside a container is wiped on every redeploy/restart, so
for a real deployment either mount persistent storage on MEDIA_DIR or switch to blob storage.
"""
import uuid
from pathlib import Path

from .config import settings

PROFILE_PICS = "profile_pics"


def media_root() -> Path:
    root = Path(settings.media_dir)
    (root / PROFILE_PICS).mkdir(parents=True, exist_ok=True)
    return root


def save_profile_image(data: bytes) -> str:
    """Store the bytes under a random name and return that name."""
    filename = f"{uuid.uuid4().hex}.jpg"
    (media_root() / PROFILE_PICS / filename).write_bytes(data)
    return filename


def delete_profile_image(filename: str | None) -> None:
    if not filename:
        return
    # Path(...).name drops any folder parts, so a bad value can never escape the folder.
    path = media_root() / PROFILE_PICS / Path(filename).name
    path.unlink(missing_ok=True)
