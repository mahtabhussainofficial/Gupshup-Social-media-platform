"""Validating and processing uploaded profile pictures.

We never trust the file name or the Content-Type sent by the browser. Instead we open the
bytes with Pillow, check the real format and size, then re-encode a clean 400x400 JPEG.
Re-encoding also strips metadata such as GPS location from phone photos.
"""
import io

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 25_000_000  # protects the server from "decompression bomb" images
OUTPUT_SIZE = (400, 400)


class InvalidImage(ValueError):
    pass


def process_profile_image(data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
        # .size and .format are known without decoding all pixels, so check them first.
        if img.format not in ALLOWED_FORMATS:
            raise InvalidImage("Only JPEG, PNG or WEBP images are allowed")
        width, height = img.size
        if width * height > MAX_PIXELS:
            raise InvalidImage("Image dimensions are too large")
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise InvalidImage("File is not a valid image")

    img = ImageOps.exif_transpose(img)  # respect phone rotation
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    img = ImageOps.fit(img, OUTPUT_SIZE, Image.LANCZOS)  # centre-crop to a square
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()
