"""Embed local images as base64 data URIs.

`st.image` serves files through Streamlit's in-memory media manager, whose
`/media/...` URLs can 404 after a restart/hibernation. A data URI has no
server-side dependency, so it can't expire.
"""

import base64
import io
import os
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=32)
def image_to_data_uri(path: str, max_width: int = 500) -> str | None:
    """Return a PNG data URI for `path`, downscaled to `max_width`; None on failure."""
    if not os.path.isfile(path):
        return None
    try:
        with Image.open(path) as img:
            if img.width > max_width:
                height = round(img.height * max_width / img.width)
                img = img.resize((max_width, height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
    except Exception as e:
        print(f"Error embedding {path}: {e}")
        return None
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
