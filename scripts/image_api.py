#!/usr/bin/env python3
"""Generate and edit images through OpenAI-compatible Images APIs."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import struct
import sys
import tempfile
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_to_bytes, urljoin
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-1"
MAX_ERROR_TEXT = 4000
MAX_INPUT_IMAGES = 16
MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_MASK_BYTES = 4 * 1024 * 1024
MAX_ALPHA_SCAN_BYTES = 64 * 1024 * 1024
SIZE_PATTERN = re.compile(r"^(?P<width>\d+)x(?P<height>\d+)$", re.IGNORECASE)
FORMAT_ALIASES = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "webp": "webp",
    "gif": "gif",
}
MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}


class ImageApiError(RuntimeError):
    """A user-facing API, response, or output error."""


@dataclass(frozen=True)
class ParsedImage:
    data: bytes
    image_format: str
    width: int | None
    height: int | None
    response_fields: tuple[str, ...]


@dataclass(frozen=True)
class InputImage:
    path: Path
    byte_count: int
    sha256: str
    image_format: str
    width: int | None
    height: int | None
    has_alpha: bool
    alpha_status: str
    transparency_chunk: bool


@dataclass(frozen=True)
class AlphaInfo:
    has_alpha: bool
    status: str
    transparency_chunk: bool = False


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def load_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt_file:
        try:
            value = prompt_file.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise ImageApiError(f"cannot read prompt file: {prompt_file}: {exc}") from exc
    else:
        value = (prompt or "").strip()
    if not value:
        raise ImageApiError("prompt is empty")
    return value


def apply_image_roles(prompt: str, roles: list[str] | None) -> str:
    if not roles:
        return prompt
    lines = ["", "Input images:"]
    for index, role in enumerate(roles, start=1):
        normalized = " ".join(role.split())
        if not normalized:
            raise ImageApiError(f"image role {index} is empty")
        lines.append(f"Image {index}: {normalized}")
    return prompt.rstrip() + "\n" + "\n".join(lines)


def validate_image_roles(image_paths: list[Path], roles: list[str] | None) -> None:
    if roles and len(roles) != len(image_paths):
        raise ImageApiError(
            f"received {len(roles)} image role(s) for {len(image_paths)} image(s); "
            "provide one --image-role per --image or omit all roles"
        )


def endpoint_url(base_url: str, resource: str, override: str | None) -> str:
    if override:
        return override.rstrip("/")
    return f"{base_url.rstrip('/')}/{resource.lstrip('/')}"


def generation_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
    }
    for key in ("size", "quality", "output_format", "response_format", "background"):
        value = getattr(args, key)
        if value is not None:
            payload[key] = value
    return payload


def effective_output_format(args: argparse.Namespace) -> str | None:
    if args.output_format:
        return FORMAT_ALIASES.get(args.output_format.lower(), args.output_format.lower())
    suffix = args.output.suffix.lstrip(".").lower()
    return FORMAT_ALIASES.get(suffix)


def validate_request_options(args: argparse.Namespace) -> None:
    if args.background == "transparent" and effective_output_format(args) == "jpeg":
        raise ImageApiError(
            "transparent backgrounds require PNG or WebP output, not JPEG"
        )


def data_url_for_file(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ImageApiError(f"cannot read image file: {path}: {exc}") from exc
    image_format = detect_image_format(data)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{MIME_BY_FORMAT[image_format]};base64,{encoded}"


def json_edit_payload(
    args: argparse.Namespace,
    prompt: str,
    image_paths: Iterable[Path],
    mask_path: Path | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "images": [{"image_url": data_url_for_file(path)} for path in image_paths],
        "n": args.n,
    }
    for key in ("size", "quality", "output_format", "response_format", "background"):
        value = getattr(args, key)
        if value is not None:
            payload[key] = value
    if mask_path:
        payload["mask"] = {"image_url": data_url_for_file(mask_path)}
    return payload


def multipart_body(
    fields: dict[str, Any],
    image_paths: list[Path],
    mask_path: Path | None,
) -> tuple[bytes, str]:
    boundary = f"----image-generation-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        if value is None:
            continue
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii")
        )
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    image_field = "image" if len(image_paths) == 1 else "image[]"
    for path in image_paths:
        chunks.append(_file_part(boundary, image_field, path))
    if mask_path:
        chunks.append(_file_part(boundary, "mask", mask_path))

    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _file_part(boundary: str, field_name: str, path: Path) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ImageApiError(f"cannot read image file: {path}: {exc}") from exc
    image_format = detect_image_format(data)
    content_type = MIME_BY_FORMAT[image_format]
    filename = path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    headers = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    )
    return headers.encode("utf-8") + data + b"\r\n"


def post_request(
    url: str,
    key: str,
    body: bytes,
    content_type: str,
    timeout: float,
) -> dict[str, Any]:
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "image-generation-skill/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read()
        detail = decode_error_body(raw, exc.reason)
        raise ImageApiError(f"image API returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ImageApiError(f"image API request failed: {exc}") from exc
    return decode_json_response(raw)


def decode_json_response(raw: bytes) -> dict[str, Any]:
    if not raw:
        raise ImageApiError("image API returned an empty response")
    try:
        body = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        excerpt = raw[:MAX_ERROR_TEXT].decode("utf-8", errors="replace")
        raise ImageApiError(f"image API returned non-JSON content: {excerpt}") from exc
    if not isinstance(body, dict):
        raise ImageApiError("image API response must be a JSON object")
    return body


def decode_error_body(raw: bytes, fallback: Any) -> str:
    text = raw[:MAX_ERROR_TEXT].decode("utf-8", errors="replace").strip()
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return text or str(fallback)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str):
            return error
    return text or str(fallback)


def extract_image_candidates(body: dict[str, Any]) -> list[Any]:
    error = body.get("error")
    if error:
        if isinstance(error, dict):
            message = error.get("message") or json.dumps(error, ensure_ascii=False)
        else:
            message = str(error)
        raise ImageApiError(f"image API error: {message}")

    for key in ("data", "images"):
        value = body.get(key)
        if isinstance(value, list) and value:
            return value
    if "image" in body:
        value = body["image"]
        return value if isinstance(value, list) else [value]
    if any(
        key in body
        for key in (
            "b64_json",
            "b64",
            "url",
            "image_url",
        )
    ):
        return [body]
    return []


def parse_image_item(item: Any, endpoint: str, timeout: float) -> ParsedImage:
    response_fields = tuple(sorted(item.keys())) if isinstance(item, dict) else ("<string>",)
    data = image_bytes_from_item(item, endpoint, timeout)
    if not data:
        raise ImageApiError("image API returned an empty image")
    image_format = detect_image_format(data)
    width, height = image_dimensions(data, image_format)
    return ParsedImage(data, image_format, width, height, response_fields)


def image_bytes_from_item(item: Any, endpoint: str, timeout: float) -> bytes:
    if isinstance(item, str):
        return decode_image_string(item, endpoint, timeout)
    if not isinstance(item, dict):
        raise ImageApiError(f"unsupported image item type: {type(item).__name__}")

    for key in ("b64_json", "b64"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return decode_base64(value)

    for key in ("url", "image_url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return decode_image_string(value, endpoint, timeout)

    nested = item.get("image")
    if isinstance(nested, (dict, str)):
        return image_bytes_from_item(nested, endpoint, timeout)
    if isinstance(nested, list) and nested:
        return image_bytes_from_item(nested[0], endpoint, timeout)

    raise ImageApiError(
        "no recognized image field; item keys: " + ", ".join(sorted(item.keys()))
    )


def decode_image_string(value: str, endpoint: str, timeout: float) -> bytes:
    stripped = value.strip()
    if stripped.startswith("data:"):
        return decode_data_url(stripped)
    if stripped.startswith(("http://", "https://")):
        return download_image(stripped, timeout)
    if stripped.startswith("//"):
        return download_image("https:" + stripped, timeout)
    if stripped.startswith("/"):
        return download_image(urljoin(endpoint, stripped), timeout)
    return decode_base64(stripped)


def decode_data_url(value: str) -> bytes:
    header, separator, payload = value.partition(",")
    if not separator:
        raise ImageApiError("invalid data URL")
    if ";base64" in header.lower():
        return decode_base64(payload)
    return unquote_to_bytes(payload)


def decode_base64(value: str) -> bytes:
    normalized = "".join(value.split())
    normalized += "=" * (-len(normalized) % 4)
    try:
        data = base64.b64decode(normalized, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ImageApiError("image response contains invalid base64 data") from exc
    if not data:
        raise ImageApiError("image response contains empty base64 data")
    return data


def download_image(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        method="GET",
        headers={"User-Agent": "image-generation-skill/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
    except HTTPError as exc:
        raise ImageApiError(f"image download returned HTTP {exc.code}: {url}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ImageApiError(f"image download failed: {exc}") from exc
    if not data:
        raise ImageApiError("image download returned no data")
    return data


def detect_image_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    raise ImageApiError("returned data is not a supported raster image (PNG, JPEG, WebP, GIF)")


def inspect_input_image(path: Path) -> InputImage:
    if not path.is_file():
        raise ImageApiError(f"input image does not exist: {path}")
    try:
        byte_count = path.stat().st_size
    except OSError as exc:
        raise ImageApiError(f"cannot inspect input image: {path}: {exc}") from exc
    if byte_count < 1:
        raise ImageApiError(f"input image is empty: {path}")
    if byte_count > MAX_INPUT_BYTES:
        raise ImageApiError(
            f"input image exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MB limit: {path}"
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ImageApiError(f"cannot read input image: {path}: {exc}") from exc
    image_format = detect_image_format(data)
    width, height = image_dimensions(data, image_format)
    alpha = image_alpha_info(data, image_format)
    return InputImage(
        path=path,
        byte_count=byte_count,
        sha256=hashlib.sha256(data).hexdigest(),
        image_format=image_format,
        width=width,
        height=height,
        has_alpha=alpha.has_alpha,
        alpha_status=alpha.status,
        transparency_chunk=alpha.transparency_chunk,
    )


def validate_edit_inputs(
    image_paths: list[Path],
    mask_path: Path | None,
    transport: str,
) -> tuple[list[InputImage], InputImage | None, list[str]]:
    if not image_paths:
        raise ImageApiError("edit requests require at least one input image")
    if len(image_paths) > MAX_INPUT_IMAGES:
        raise ImageApiError(
            f"edit supports at most {MAX_INPUT_IMAGES} input images; received {len(image_paths)}"
        )
    images = [inspect_input_image(path) for path in image_paths]
    mask = inspect_input_image(mask_path) if mask_path else None
    if mask is None:
        return images, None, []

    warnings: list[str] = []
    if mask.byte_count > MAX_MASK_BYTES:
        raise ImageApiError(
            f"image mask exceeds the {MAX_MASK_BYTES // (1024 * 1024)} MB limit: "
            f"{mask.path}"
        )
    source = images[0]
    if transport == "multipart":
        if mask.image_format != "png":
            raise ImageApiError("multipart image masks must be PNG files")
        if not mask.has_alpha:
            if mask.transparency_chunk:
                raise ImageApiError(
                    "multipart image masks require an alpha channel; PNG tRNS "
                    "transparency metadata is not an alpha channel. Save the mask "
                    "as an RGBA PNG."
                )
            raise ImageApiError("multipart image masks must contain an alpha channel")
        if mask.alpha_status == "opaque":
            raise ImageApiError(
                "multipart image masks must contain at least one transparent pixel; "
                "this mask's alpha channel is fully opaque"
            )
        if mask.alpha_status == "unknown":
            raise ImageApiError(
                "cannot verify transparent pixels in the multipart image mask; "
                "use a non-interlaced 8-bit or 16-bit PNG with an alpha channel"
            )
    elif mask.transparency_chunk and not mask.has_alpha:
        warnings.append(
            f"{mask.path}: mask uses PNG tRNS transparency metadata rather than "
            "an alpha channel; some providers may reject it"
        )
    if (
        source.width is not None
        and source.height is not None
        and mask.width is not None
        and mask.height is not None
        and (source.width, source.height) != (mask.width, mask.height)
    ):
        raise ImageApiError(
            "mask dimensions must match the first input image "
            f"({source.width}x{source.height}); got {mask.width}x{mask.height}"
        )
    return images, mask, warnings


def image_has_alpha(data: bytes, image_format: str) -> bool:
    return image_alpha_info(data, image_format).has_alpha


def image_alpha_info(data: bytes, image_format: str) -> AlphaInfo:
    if image_format == "png":
        return png_alpha_info(data)
    if image_format == "webp":
        offset = 12
        while offset + 8 <= len(data):
            chunk_type = data[offset : offset + 4]
            chunk_size = int.from_bytes(data[offset + 4 : offset + 8], "little")
            payload = offset + 8
            if payload + chunk_size > len(data):
                return AlphaInfo(False, "unknown")
            if chunk_type == b"VP8X" and chunk_size >= 1:
                has_alpha = bool(data[payload] & 0x10)
                return AlphaInfo(has_alpha, "unknown" if has_alpha else "none")
            if chunk_type == b"VP8L" and chunk_size >= 5:
                bits = int.from_bytes(data[payload + 1 : payload + 5], "little")
                has_alpha = bool((bits >> 28) & 0x01)
                return AlphaInfo(has_alpha, "unknown" if has_alpha else "none")
            offset = payload + chunk_size + (chunk_size % 2)
    return AlphaInfo(False, "none")


def png_alpha_info(data: bytes) -> AlphaInfo:
    if len(data) < 29 or data[12:16] != b"IHDR":
        return AlphaInfo(False, "unknown")

    width, height = struct.unpack(">II", data[16:24])
    bit_depth = data[24]
    color_type = data[25]
    compression = data[26]
    filter_method = data[27]
    interlace = data[28]
    has_channel = color_type in {4, 6}
    idat_parts: list[bytes] = []
    transparency_chunk = False

    offset = 8
    while offset + 8 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            return AlphaInfo(
                has_channel,
                "unknown" if has_channel else "none",
                transparency_chunk,
            )
        if chunk_type == b"tRNS":
            transparency_chunk = True
        elif chunk_type == b"IDAT":
            idat_parts.append(data[payload_start:payload_end])
        elif chunk_type == b"IEND":
            break
        offset += 12 + length

    if not has_channel:
        return AlphaInfo(
            False,
            "chunk_only" if transparency_chunk else "none",
            transparency_chunk,
        )
    if (
        bit_depth not in {8, 16}
        or compression != 0
        or filter_method != 0
        or interlace != 0
        or not idat_parts
        or width < 1
        or height < 1
    ):
        return AlphaInfo(True, "unknown", transparency_chunk)

    channels = 2 if color_type == 4 else 4
    sample_bytes = bit_depth // 8
    bytes_per_pixel = channels * sample_bytes
    row_bytes = width * bytes_per_pixel
    expected_size = height * (row_bytes + 1)
    if expected_size > MAX_ALPHA_SCAN_BYTES:
        return AlphaInfo(True, "unknown", transparency_chunk)

    try:
        decompressor = zlib.decompressobj()
        decompressed = decompressor.decompress(
            b"".join(idat_parts),
            expected_size + 1,
        )
    except zlib.error:
        return AlphaInfo(True, "unknown", transparency_chunk)
    if len(decompressed) < expected_size:
        return AlphaInfo(True, "unknown", transparency_chunk)
    decompressed = decompressed[:expected_size]

    maximum = (1 << (bit_depth)) - 1
    minimum_alpha = maximum
    maximum_alpha = 0
    previous = bytearray(row_bytes)
    position = 0
    try:
        for _ in range(height):
            filter_type = decompressed[position]
            position += 1
            row = bytearray(decompressed[position : position + row_bytes])
            position += row_bytes
            unfilter_png_row(row, previous, bytes_per_pixel, filter_type)
            alpha_offset = (channels - 1) * sample_bytes
            for pixel in range(width):
                start = pixel * bytes_per_pixel + alpha_offset
                alpha = int.from_bytes(row[start : start + sample_bytes], "big")
                minimum_alpha = min(minimum_alpha, alpha)
                maximum_alpha = max(maximum_alpha, alpha)
            previous = row
    except (IndexError, ValueError):
        return AlphaInfo(True, "unknown", transparency_chunk)

    if maximum_alpha == 0:
        status = "transparent"
    elif minimum_alpha == maximum and maximum_alpha == maximum:
        status = "opaque"
    else:
        status = "partial"
    return AlphaInfo(True, status, transparency_chunk)


def unfilter_png_row(
    row: bytearray,
    previous: bytearray,
    bytes_per_pixel: int,
    filter_type: int,
) -> None:
    if filter_type == 0:
        return
    if filter_type not in {1, 2, 3, 4}:
        raise ValueError(f"unsupported PNG filter type: {filter_type}")
    for index in range(len(row)):
        left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index]
        upper_left = (
            previous[index - bytes_per_pixel]
            if index >= bytes_per_pixel
            else 0
        )
        if filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        else:
            predictor = paeth_predictor(left, up, upper_left)
        row[index] = (row[index] + predictor) & 0xFF


def paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def input_image_record(image: InputImage) -> dict[str, Any]:
    return {
        "path": str(image.path.resolve()),
        "bytes": image.byte_count,
        "sha256": image.sha256,
        "format": image.image_format,
        "width": image.width,
        "height": image.height,
        "has_alpha": image.has_alpha,
        "alpha_status": image.alpha_status,
        "has_transparent_pixels": image.alpha_status
        in {"transparent", "partial"},
        "transparency_chunk": image.transparency_chunk,
    }


def image_dimensions(data: bytes, image_format: str) -> tuple[int | None, int | None]:
    try:
        if image_format == "png":
            return png_dimensions(data)
        if image_format == "jpeg":
            return jpeg_dimensions(data)
        if image_format == "webp":
            return webp_dimensions(data)
        if image_format == "gif":
            return struct.unpack("<HH", data[6:10])
    except (IndexError, struct.error, ValueError):
        return None, None
    return None, None


def png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    return struct.unpack(">II", data[16:24])


def jpeg_dimensions(data: bytes) -> tuple[int | None, int | None]:
    index = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0xD8, 0xD9):
            continue
        if marker == 0xDA or marker == 0xD2:
            break
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in sof_markers:
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += segment_length
    return None, None


def webp_dimensions(data: bytes) -> tuple[int | None, int | None]:
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        start = data.find(b"\x9d\x01\x2a", 20, 30)
        if start >= 0 and start + 7 <= len(data):
            width = int.from_bytes(data[start + 3 : start + 5], "little") & 0x3FFF
            height = int.from_bytes(data[start + 5 : start + 7], "little") & 0x3FFF
            return width, height
    return None, None


def compatible_extension(extension: str, image_format: str) -> bool:
    return FORMAT_ALIASES.get(extension.lower().lstrip(".")) == image_format


def path_identity(path: Path) -> str:
    return os.path.normcase(str(path.absolute())).casefold()


def output_path_for(output: Path, index: int, image_format: str) -> Path:
    candidate = output
    if index:
        suffix = candidate.suffix
        stem = candidate.stem if suffix else candidate.name
        candidate = candidate.with_name(f"{stem}-{index + 1}{suffix}")

    suffix = candidate.suffix.lstrip(".")
    canonical_extension = "jpg" if image_format == "jpeg" else image_format
    if suffix:
        if not compatible_extension(suffix, image_format):
            candidate = candidate.with_suffix(f".{canonical_extension}")
    else:
        candidate = candidate.with_name(f"{candidate.name}.{canonical_extension}")
    return candidate


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str) and value.startswith("data:"):
        header = value.partition(",")[0]
        return f"{header},<base64 omitted>"
    return value


def stage_output_file(target: Path, data: bytes) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ImageApiError(f"cannot stage output file: {target}: {exc}") from exc
    return temporary


def publish_staged_file(staged: Path, target: Path) -> None:
    try:
        os.link(staged, target)
    except FileExistsError as exc:
        raise ImageApiError(f"output already exists: {target}") from exc
    except OSError as exc:
        raise ImageApiError(f"cannot publish output file: {target}: {exc}") from exc


def publish_output_set(
    image_outputs: list[tuple[Path, bytes]],
    sidecar: Path,
    metadata: dict[str, Any],
) -> None:
    staged_images: list[tuple[Path, Path]] = []
    staged_sidecar: Path | None = None
    published: list[Path] = []
    try:
        for target, data in image_outputs:
            staged = stage_output_file(target, data)
            staged_images.append((staged, target))
        sidecar_data = (
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        staged_sidecar = stage_output_file(sidecar, sidecar_data)
        for staged, target in staged_images:
            publish_staged_file(staged, target)
            published.append(target)
        publish_staged_file(staged_sidecar, sidecar)
        published.append(sidecar)
    except Exception:
        for target in reversed(published):
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        for staged, _ in staged_images:
            staged.unlink(missing_ok=True)
        if staged_sidecar is not None:
            staged_sidecar.unlink(missing_ok=True)


def parse_and_save_images(
    response: dict[str, Any],
    output: Path,
    endpoint: str,
    timeout: float,
    metadata_path: Path | None,
    request_info: dict[str, Any],
    expected_count: int | None = None,
    expected_size: str | None = None,
    expected_transparency: bool = False,
) -> dict[str, Any]:
    candidates = extract_image_candidates(response)
    if not candidates:
        raise ImageApiError(
            "no image candidates in response; top-level keys: "
            + ", ".join(sorted(response.keys()))
        )

    parsed: list[tuple[int, ParsedImage]] = []
    errors: list[str] = []
    for index, item in enumerate(candidates):
        try:
            parsed.append((index, parse_image_item(item, endpoint, timeout)))
        except ImageApiError as exc:
            errors.append(f"candidate {index + 1}: {exc}")
    if not parsed:
        detail = "; ".join(errors) if errors else "no decodable image candidates"
        raise ImageApiError(f"no valid images in response; {detail}")

    targets = [
        output_path_for(output, index, image.image_format)
        for index, image in parsed
    ]
    if len({path_identity(target) for target in targets}) != len(targets):
        raise ImageApiError("multiple response images resolve to the same output path")

    sidecar = metadata_path or targets[0].with_name(targets[0].name + ".json")
    for target in targets:
        if target.exists():
            raise ImageApiError(f"output already exists: {target}")
    if sidecar.exists():
        raise ImageApiError(f"metadata already exists: {sidecar}")
    if path_identity(sidecar) in {path_identity(target) for target in targets}:
        raise ImageApiError("metadata path cannot equal an image output path")

    records: list[dict[str, Any]] = []
    for target, (_, image) in zip(targets, parsed):
        alpha = image_alpha_info(image.data, image.image_format)
        records.append(
            {
                "path": str(target.resolve()),
                "bytes": len(image.data),
                "sha256": hashlib.sha256(image.data).hexdigest(),
                "format": image.image_format,
                "width": image.width,
                "height": image.height,
                "has_alpha": alpha.has_alpha,
                "alpha_status": alpha.status,
                "response_fields": list(image.response_fields),
            }
        )

    warnings: list[str] = []
    if expected_count is not None and len(records) != expected_count:
        warnings.append(
            f"requested {expected_count} image(s), decoded {len(records)} valid image(s)"
        )

    size_match = SIZE_PATTERN.fullmatch(expected_size or "")
    if size_match:
        expected_width = int(size_match.group("width"))
        expected_height = int(size_match.group("height"))
        for record in records:
            actual = (record["width"], record["height"])
            expected = (expected_width, expected_height)
            if actual != expected:
                actual_text = (
                    f"{actual[0]}x{actual[1]}"
                    if actual[0] is not None and actual[1] is not None
                    else "unknown"
                )
                warnings.append(
                    f"{record['path']}: expected {expected_width}x{expected_height}, "
                    f"got {actual_text}"
                )

    if expected_transparency:
        for record in records:
            if not record["has_alpha"]:
                warnings.append(
                    f"{record['path']}: transparent background requested, "
                    "but no alpha channel was detected"
                )
            elif record["alpha_status"] == "opaque":
                warnings.append(
                    f"{record['path']}: transparent background requested, "
                    "but the alpha channel is fully opaque"
                )
            elif record["alpha_status"] == "unknown":
                warnings.append(
                    f"{record['path']}: transparent background requested, "
                    "but transparent pixels could not be verified"
                )

    delivery_ready = not errors and not warnings
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": redact_payload(request_info),
        "outputs": records,
        "returned_count": len(candidates),
        "published_count": len(records),
        "requested_count": expected_count,
        "delivery_ready": delivery_ready,
        "warnings": warnings,
        "errors": errors,
    }
    publish_output_set(
        [(target, image.data) for target, (_, image) in zip(targets, parsed)],
        sidecar,
        metadata,
    )

    return {
        "outputs": records,
        "metadata": str(sidecar.resolve()),
        "returned_count": len(candidates),
        "published_count": len(records),
        "delivery_ready": delivery_ready,
        "warnings": warnings,
        "errors": errors,
    }


def require_key(api_key_env: str) -> str:
    key = os.environ.get(api_key_env, "").strip()
    if not key:
        raise ImageApiError(
            f"missing API key; set environment variable {api_key_env} "
            "or pass --api-key-env with a different variable name"
        )
    return key


def run_generate(args: argparse.Namespace) -> dict[str, Any]:
    prompt = load_prompt(args.prompt, args.prompt_file)
    validate_request_options(args)
    payload = generation_payload(args, prompt)
    endpoint = endpoint_url(
        args.base_url or DEFAULT_BASE_URL,
        "images/generations",
        args.endpoint,
    )
    request_info = {
        "method": "POST",
        "url": endpoint,
        "transport": "json",
        "payload": payload,
    }
    if args.dry_run:
        return {"dry_run": True, **request_info}

    key = require_key(args.api_key_env)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response = post_request(endpoint, key, body, "application/json", args.timeout)
    return parse_and_save_images(
        response,
        args.output,
        endpoint,
        args.timeout,
        args.metadata,
        request_info,
        expected_count=args.n,
        expected_size=args.size,
        expected_transparency=args.background == "transparent",
    )


def run_edit(args: argparse.Namespace) -> dict[str, Any]:
    prompt = load_prompt(args.prompt, args.prompt_file)
    validate_request_options(args)
    image_paths = [path.expanduser() for path in args.image]
    mask_path = args.mask.expanduser() if args.mask else None
    roles = getattr(args, "image_role", None)
    validate_image_roles(image_paths, roles)
    prompt = apply_image_roles(prompt, roles)
    input_images, mask_image, input_warnings = validate_edit_inputs(
        image_paths,
        mask_path,
        args.transport,
    )

    endpoint = endpoint_url(
        args.base_url or DEFAULT_BASE_URL,
        "images/edits",
        args.endpoint,
    )
    if args.transport == "json":
        payload = json_edit_payload(args, prompt, image_paths, mask_path)
        request_info = {
            "method": "POST",
            "url": endpoint,
            "transport": "json",
            "payload": redact_payload(payload),
            "image_roles": roles,
            "inputs": [input_image_record(image) for image in input_images],
            "mask": input_image_record(mask_image) if mask_image else None,
            "input_warnings": input_warnings,
        }
        if args.dry_run:
            return {"dry_run": True, **request_info}
        key = require_key(args.api_key_env)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        content_type = "application/json"
    else:
        fields = {
            "model": args.model,
            "prompt": prompt,
            "n": args.n,
            "size": args.size,
            "quality": args.quality,
            "output_format": args.output_format,
            "response_format": args.response_format,
            "background": args.background,
        }
        request_info = {
            "method": "POST",
            "url": endpoint,
            "transport": "multipart",
            "fields": {key: value for key, value in fields.items() if value is not None},
            "image_roles": roles,
            "inputs": [input_image_record(image) for image in input_images],
            "mask": input_image_record(mask_image) if mask_image else None,
            "input_warnings": input_warnings,
        }
        if args.dry_run:
            return {"dry_run": True, **request_info}
        key = require_key(args.api_key_env)
        body, content_type = multipart_body(fields, image_paths, mask_path)

    response = post_request(endpoint, key, body, content_type, args.timeout)
    return parse_and_save_images(
        response,
        args.output,
        endpoint,
        args.timeout,
        args.metadata,
        request_info,
        expected_count=args.n,
        expected_size=args.size,
        expected_transparency=args.background == "transparent",
    )


def add_request_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt", help="image prompt")
    parser.add_argument("--prompt-file", type=Path, help="UTF-8 prompt file")
    parser.add_argument("--output", type=Path, required=True, help="output image path")
    parser.add_argument("--metadata", type=Path, help="JSON sidecar path")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("IMAGE_API_BASE_URL", DEFAULT_BASE_URL),
        help=f"API root (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--endpoint", help="full endpoint URL; overrides --base-url")
    parser.add_argument(
        "--api-key-env",
        default="IMAGE_API_KEY",
        help="environment variable containing the API key",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("IMAGE_MODEL", DEFAULT_MODEL),
        help=f"model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--size", help="provider image size, for example 1024x1024")
    parser.add_argument("--quality", help="provider quality value")
    parser.add_argument("--n", type=positive_int, default=1, help="requested image count")
    parser.add_argument(
        "--output-format",
        choices=("png", "jpeg", "webp"),
        help="requested output format",
    )
    parser.add_argument(
        "--response-format",
        choices=("b64_json", "url"),
        help="requested response format",
    )
    parser.add_argument(
        "--background",
        choices=("transparent", "opaque", "auto"),
        help="requested background handling",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=360.0,
        help="request timeout in seconds",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned request without reading the API key or calling the network",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and edit images through OpenAI-compatible Images APIs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="generate an image")
    add_request_options(generate_parser)
    generate_parser.set_defaults(handler=run_generate)

    edit_parser = subparsers.add_parser("edit", help="edit one or more images")
    add_request_options(edit_parser)
    edit_parser.add_argument(
        "--image",
        type=Path,
        action="append",
        required=True,
        help="source image; repeat for multiple inputs",
    )
    edit_parser.add_argument(
        "--image-role",
        action="append",
        help="role for the matching --image, in order; repeat once per input image",
    )
    edit_parser.add_argument("--mask", type=Path, help="optional mask image")
    edit_parser.add_argument(
        "--transport",
        choices=("multipart", "json"),
        default="multipart",
        help="edit request shape (default: multipart)",
    )
    edit_parser.set_defaults(handler=run_edit)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except ImageApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
