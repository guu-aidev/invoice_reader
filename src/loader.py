"""アップロードされた画像 / PDF を、Claude へ渡す content ブロックに変換する。

- 画像(JPG/PNG等) → image ブロック(base64)
- PDF            → document ブロック(base64)。Claude はPDFを直接読める（複数ページ可）
"""
from __future__ import annotations

import base64
from pathlib import Path

IMAGE_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def to_content_blocks(data: bytes, filename: str) -> list[dict]:
    """ファイルのバイト列を Claude の content ブロック(list)に変換する。"""
    ext = Path(filename).suffix.lower()
    b64 = base64.standard_b64encode(data).decode("utf-8")

    if ext == ".pdf":
        return [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            }
        ]

    media_type = IMAGE_MEDIA_TYPES.get(ext)
    if media_type is None:
        raise ValueError(f"未対応のファイル形式です: {ext}")

    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64,
            },
        }
    ]
