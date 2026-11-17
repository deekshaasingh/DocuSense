"""
Step 2 of the Build Manual: keep the uploaded bytes somewhere.

A local folder, not MinIO. The manual's own "if you are short on time, cut in
this order" list puts MinIO first, and nothing else in the project depends on
object storage semantics.
"""
import os
import uuid

from config import settings


def save_upload(filename: str, data: bytes) -> str:
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    ext = os.path.splitext(filename)[1].lower()
    path = os.path.join(settings.STORAGE_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as fh:
        fh.write(data)
    return path
