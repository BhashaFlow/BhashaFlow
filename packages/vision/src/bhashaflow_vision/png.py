"""RGB bytes to a PNG data URL. No third-party image library."""

import base64
import math
import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def rgb_to_png(width: int, height: int, rgb: bytes) -> bytes:
    """Encode tightly packed RGB as an 8-bit PNG."""
    expected = width * height * 3
    if width <= 0 or height <= 0 or len(rgb) != expected:
        raise ValueError("rgb buffer does not match the frame size")
    stride = width * 3
    rows = [b"\x00" + rgb[y * stride : (y + 1) * stride] for y in range(height)]
    compressed = zlib.compress(b"".join(rows), level=9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return _SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")


def frame_image(
    width: int,
    height: int,
    pixels: bytes,
    *,
    max_edge: int = 480,
) -> tuple[str, float] | None:
    """Return a PNG data URL and the scale from preview pixels back to the frame.

    The scale is ``original / preview``. A 2x2 frame is not reduced. A frame
    whose buffer does not match ``width * height * 3`` returns None.
    """
    if width <= 0 or height <= 0 or len(pixels) != width * height * 3:
        return None
    step = max(1, math.ceil(max(width, height) / max_edge))
    if step == 1:
        preview = pixels
        preview_w, preview_h = width, height
    else:
        preview_w = width // step
        preview_h = height // step
        if preview_w <= 0 or preview_h <= 0:
            return None
        rows: list[bytes] = []
        for y in range(preview_h):
            src_y = y * step
            row = bytearray()
            for x in range(preview_w):
                start = (src_y * width + x * step) * 3
                row.extend(pixels[start : start + 3])
            rows.append(bytes(row))
        preview = b"".join(rows)
    png = rgb_to_png(preview_w, preview_h, preview)
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}", float(step)


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)
