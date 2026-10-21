from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
import zlib
from argparse import Namespace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "image_api.py"
SPEC = importlib.util.spec_from_file_location("image_api", MODULE_PATH)
assert SPEC and SPEC.loader
image_api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = image_api
SPEC.loader.exec_module(image_api)

BATCH_MODULE_PATH = ROOT / "scripts" / "image_batch.py"
BATCH_SPEC = importlib.util.spec_from_file_location("image_batch", BATCH_MODULE_PATH)
assert BATCH_SPEC and BATCH_SPEC.loader
image_batch = importlib.util.module_from_spec(BATCH_SPEC)
sys.modules[BATCH_SPEC.name] = image_batch
BATCH_SPEC.loader.exec_module(image_batch)


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", checksum)
    )


def png_bytes(
    width: int = 3,
    height: int = 2,
    color_type: int = 6,
    pixels: bytes | None = None,
    transparency_chunk: bytes | None = None,
) -> bytes:
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    row_bytes = width * channels
    if pixels is None:
        pixels = b"\xff" * (row_bytes * height)
    if len(pixels) != row_bytes * height:
        raise ValueError("pixel payload does not match image dimensions")
    scanlines = b"".join(
        b"\x00" + pixels[row * row_bytes : (row + 1) * row_bytes]
        for row in range(height)
    )
    ihdr = struct.pack(">II", width, height) + bytes((8, color_type, 0, 0, 0))
    chunks = [png_chunk(b"IHDR", ihdr)]
    if transparency_chunk is not None:
        chunks.append(png_chunk(b"tRNS", transparency_chunk))
    chunks.extend((png_chunk(b"IDAT", zlib.compress(scanlines)), png_chunk(b"IEND", b"")))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def jpeg_bytes(width: int = 3, height: int = 2) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x10"
        + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xc0\x00\x11\x08"
        + struct.pack(">HH", height, width)
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def request_namespace(**overrides: object) -> Namespace:
    values = {
        "output": Path("result.png"),
        "model": "test-model",
        "n": 1,
        "size": "1024x1024",
        "quality": "high",
        "output_format": "png",
        "response_format": "b64_json",
        "background": "opaque",
    }
    values.update(overrides)
    return Namespace(**values)


class ImageFormatTests(unittest.TestCase):
    def test_detects_png_signature_and_dimensions(self) -> None:
        data = png_bytes(640, 480)
        self.assertEqual(image_api.detect_image_format(data), "png")
        self.assertEqual(image_api.image_dimensions(data, "png"), (640, 480))

    def test_detects_jpeg_signature_and_dimensions(self) -> None:
        data = jpeg_bytes(800, 600)
        self.assertEqual(image_api.detect_image_format(data), "jpeg")
        self.assertEqual(image_api.image_dimensions(data, "jpeg"), (800, 600))

    def test_rejects_unknown_binary(self) -> None:
        with self.assertRaises(image_api.ImageApiError):
            image_api.detect_image_format(b"not an image")

    def test_data_url_decoding(self) -> None:
        raw = b"image-bytes"
        encoded = base64.b64encode(raw).decode("ascii")
        self.assertEqual(
            image_api.decode_data_url(f"data:image/png;base64,{encoded}"),
            raw,
        )


class PayloadTests(unittest.TestCase):
    def test_generation_payload_omits_empty_values(self) -> None:
        args = request_namespace(quality=None, background=None)
        payload = image_api.generation_payload(args, "prompt")
        self.assertEqual(
            payload,
            {
                "model": "test-model",
                "prompt": "prompt",
                "n": 1,
                "size": "1024x1024",
                "output_format": "png",
                "response_format": "b64_json",
            },
        )

    def test_json_edit_payload_uses_data_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(png_bytes())
            payload = image_api.json_edit_payload(
                request_namespace(),
                "edit prompt",
                [source],
                None,
            )
        self.assertEqual(payload["model"], "test-model")
        self.assertTrue(payload["images"][0]["image_url"].startswith("data:image/png;base64,"))

    def test_redacts_data_urls(self) -> None:
        value = image_api.redact_payload({"image_url": "data:image/png;base64,secret"})
        self.assertEqual(value["image_url"], "data:image/png;base64,<base64 omitted>")

    def test_transparent_background_rejects_jpeg(self) -> None:
        with self.assertRaisesRegex(image_api.ImageApiError, "not JPEG"):
            image_api.validate_request_options(
                request_namespace(background="transparent", output_format="jpeg")
            )

    def test_transparent_background_rejects_jpeg_extension(self) -> None:
        with self.assertRaisesRegex(image_api.ImageApiError, "not JPEG"):
            image_api.validate_request_options(
                request_namespace(
                    background="transparent",
                    output_format=None,
                    output=Path("result.jpg"),
                )
            )


class InputValidationTests(unittest.TestCase):
    def test_roles_are_appended_in_image_order(self) -> None:
        prompt = image_api.apply_image_roles(
            "Keep the person; change the room.",
            ["person reference", "room reference"],
        )
        self.assertIn("Input images:", prompt)
        self.assertIn("Image 1: person reference", prompt)
        self.assertIn("Image 2: room reference", prompt)

    def test_role_count_must_match_image_count(self) -> None:
        with self.assertRaises(image_api.ImageApiError):
            image_api.validate_image_roles(
                [Path("one.png"), Path("two.png")],
                ["subject"],
            )

    def test_input_record_contains_hash_dimensions_and_alpha(self) -> None:
        data = png_bytes(640, 480)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(data)
            record = image_api.inspect_input_image(source)
        self.assertEqual(record.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual((record.width, record.height), (640, 480))
        self.assertTrue(record.has_alpha)
        self.assertEqual(record.alpha_status, "opaque")
        self.assertEqual(record.image_format, "png")

    def test_multipart_mask_requires_png_with_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            source.write_bytes(png_bytes())
            mask.write_bytes(png_bytes(color_type=2))
            with self.assertRaisesRegex(image_api.ImageApiError, "alpha"):
                image_api.validate_edit_inputs([source], mask, "multipart")

    def test_mask_dimensions_must_match_first_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            source.write_bytes(png_bytes(10, 8))
            mask.write_bytes(png_bytes(8, 10))
            with self.assertRaisesRegex(image_api.ImageApiError, "dimensions"):
                image_api.validate_edit_inputs([source], mask, "json")

    def test_multipart_mask_requires_at_least_one_transparent_pixel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            source.write_bytes(png_bytes())
            mask.write_bytes(png_bytes())
            with self.assertRaisesRegex(image_api.ImageApiError, "fully opaque"):
                image_api.validate_edit_inputs([source], mask, "multipart")

    def test_multipart_mask_accepts_partial_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            source.write_bytes(png_bytes())
            pixels = bytearray(b"\xff" * (3 * 2 * 4))
            pixels[3] = 0
            mask.write_bytes(png_bytes(pixels=bytes(pixels)))
            images, mask_image, warnings = image_api.validate_edit_inputs(
                [source], mask, "multipart"
            )
        self.assertEqual(len(images), 1)
        assert mask_image is not None
        self.assertEqual(mask_image.alpha_status, "partial")
        self.assertEqual(warnings, [])

    def test_trns_is_not_treated_as_an_alpha_channel(self) -> None:
        data = png_bytes(
            color_type=2,
            transparency_chunk=b"\x00\x00\x00\x00\x00\x00",
        )
        alpha = image_api.image_alpha_info(data, "png")
        self.assertFalse(alpha.has_alpha)
        self.assertTrue(alpha.transparency_chunk)
        self.assertEqual(alpha.status, "chunk_only")

    def test_json_mask_warns_about_trns_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            source.write_bytes(png_bytes())
            mask.write_bytes(
                png_bytes(
                    color_type=2,
                    transparency_chunk=b"\x00\x00\x00\x00\x00\x00",
                )
            )
            _, _, warnings = image_api.validate_edit_inputs([source], mask, "json")
        self.assertTrue(any("tRNS" in warning for warning in warnings))

    def test_mask_over_four_megabytes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            source.write_bytes(png_bytes())
            mask.write_bytes(png_bytes() + b"\x00" * (4 * 1024 * 1024))
            with self.assertRaisesRegex(image_api.ImageApiError, "4 MB"):
                image_api.validate_edit_inputs([source], mask, "json")

    def test_edit_dry_run_includes_roles_and_input_hash(self) -> None:
        data = png_bytes(40, 30)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(data)
            args = Namespace(
                prompt="Keep the subject.",
                prompt_file=None,
                output=Path(directory) / "edited.png",
                metadata=None,
                base_url="https://example.test/v1",
                endpoint=None,
                api_key_env="IMAGE_API_KEY",
                model="test-model",
                size="1024x1024",
                quality=None,
                n=1,
                output_format="png",
                response_format="b64_json",
                background=None,
                timeout=5,
                dry_run=True,
                image=[source],
                image_role=["subject reference"],
                mask=None,
                transport="multipart",
            )
            result = image_api.run_edit(args)
        self.assertTrue(result["dry_run"])
        self.assertIn("Image 1: subject reference", result["fields"]["prompt"])
        self.assertEqual(result["inputs"][0]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(result["inputs"][0]["width"], 40)


class OutputTests(unittest.TestCase):
    def test_output_extension_follows_actual_format(self) -> None:
        self.assertEqual(
            image_api.output_path_for(Path("result.jpg"), 0, "png"),
            Path("result.png"),
        )

    def test_numbered_outputs_preserve_extension(self) -> None:
        self.assertEqual(
            image_api.output_path_for(Path("result"), 1, "jpeg"),
            Path("result-2.jpg"),
        )

    def test_saves_image_and_sidecar(self) -> None:
        response = {
            "data": [
                {
                    "b64_json": base64.b64encode(png_bytes(20, 10)).decode("ascii"),
                    "revised_prompt": "a test image",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image.png"
            result = image_api.parse_and_save_images(
                response=response,
                output=output,
                endpoint="https://example.test/v1/images/generations",
                timeout=5,
                metadata_path=None,
                request_info={"payload": {"prompt": "test"}},
            )
            self.assertEqual(Path(result["outputs"][0]["path"]), output.resolve())
            self.assertEqual(output.read_bytes(), png_bytes(20, 10))
            sidecar = Path(result["metadata"])
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(metadata["outputs"][0]["width"], 20)
            self.assertEqual(metadata["outputs"][0]["height"], 10)
            self.assertEqual(
                metadata["outputs"][0]["sha256"],
                hashlib.sha256(png_bytes(20, 10)).hexdigest(),
            )
            self.assertEqual(metadata["request"]["payload"]["prompt"], "test")
            self.assertTrue(metadata["delivery_ready"])
            self.assertEqual(metadata["published_count"], 1)

    def test_refuses_to_overwrite_output(self) -> None:
        response = {
            "data": [{"b64_json": base64.b64encode(png_bytes()).decode("ascii")}]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image.png"
            output.write_bytes(b"existing")
            with self.assertRaises(image_api.ImageApiError):
                image_api.parse_and_save_images(
                    response=response,
                    output=output,
                    endpoint="https://example.test/v1/images/generations",
                    timeout=5,
                    metadata_path=None,
                    request_info={},
                )

    def test_multipart_contains_fields_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(png_bytes())
            body, content_type = image_api.multipart_body(
                {"model": "test-model", "prompt": "edit prompt", "size": None},
                [source],
                None,
            )
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="model"', body)
        self.assertIn(b'name="prompt"', body)
        self.assertIn(b'filename="source.png"', body)
        self.assertNotIn(b'name="size"', body)

    def test_bad_candidate_does_not_discard_valid_image(self) -> None:
        response = {
            "data": [
                {"b64_json": base64.b64encode(png_bytes(20, 10)).decode("ascii")},
                {"b64_json": "not-valid-base64!"},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image.png"
            result = image_api.parse_and_save_images(
                response=response,
                output=output,
                endpoint="https://example.test/v1/images/generations",
                timeout=5,
                metadata_path=None,
                request_info={},
                expected_count=2,
            )
            metadata = json.loads(
                Path(result["metadata"]).read_text(encoding="utf-8")
            )
            self.assertEqual(result["published_count"], 1)
            self.assertFalse(result["delivery_ready"])
            self.assertTrue(output.exists())
            self.assertEqual(len(metadata["errors"]), 1)
            self.assertTrue(any("requested 2" in warning for warning in metadata["warnings"]))

    def test_size_and_transparency_contract_warnings(self) -> None:
        response = {
            "data": [
                {"b64_json": base64.b64encode(jpeg_bytes(12, 9)).decode("ascii")}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image.png"
            result = image_api.parse_and_save_images(
                response=response,
                output=output,
                endpoint="https://example.test/v1/images/generations",
                timeout=5,
                metadata_path=None,
                request_info={},
                expected_count=1,
                expected_size="20x10",
                expected_transparency=True,
            )
            self.assertFalse(result["delivery_ready"])
            warnings = "\n".join(result["warnings"])
            self.assertIn("expected 20x10", warnings)
            self.assertIn("no alpha channel", warnings)

    def test_sidecar_staging_failure_leaves_no_partial_output(self) -> None:
        response = {
            "data": [{"b64_json": base64.b64encode(png_bytes(20, 10)).decode("ascii")}]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image.png"
            sidecar = Path(directory) / "metadata.json"
            original_stage = image_api.stage_output_file

            def fail_sidecar(target: Path, data: bytes) -> Path:
                if target == sidecar:
                    raise image_api.ImageApiError("simulated sidecar failure")
                return original_stage(target, data)

            with mock.patch.object(
                image_api, "stage_output_file", side_effect=fail_sidecar
            ):
                with self.assertRaisesRegex(image_api.ImageApiError, "sidecar"):
                    image_api.parse_and_save_images(
                        response=response,
                        output=output,
                        endpoint="https://example.test/v1/images/generations",
                        timeout=5,
                        metadata_path=sidecar,
                        request_info={},
                    )
            self.assertFalse(output.exists())
            self.assertFalse(sidecar.exists())
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])


class BatchTests(unittest.TestCase):
    def write_batch(self, directory: Path, records: list[dict[str, object]]) -> Path:
        batch = directory / "batch.jsonl"
        batch.write_text(
            "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
            + "\n",
            encoding="utf-8",
        )
        return batch

    def test_preflight_accepts_generate_and_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            source.write_bytes(png_bytes())
            batch = self.write_batch(
                root,
                [
                    {
                        "id": "generated",
                        "prompt": "A test image",
                        "output": "outputs/generated.png",
                        "output_format": "png",
                    },
                    {
                        "id": "edited",
                        "operation": "edit",
                        "prompt": "Keep the subject",
                        "images": ["source.png"],
                        "image_roles": ["subject reference"],
                        "output": "outputs/edited.png",
                        "output_format": "png",
                    },
                ],
            )
            plans = image_batch.preflight_batch(
                batch,
                root / "batch.manifest.json",
                dry_run=True,
            )
        self.assertEqual([plan.item_id for plan in plans], ["generated", "edited"])
        self.assertEqual(plans[1].operation, "edit")

    def test_preflight_rejects_output_stem_collision_before_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch = self.write_batch(
                root,
                [
                    {
                        "prompt": "First",
                        "output": "outputs/result.png",
                        "output_format": "png",
                    },
                    {
                        "prompt": "Second",
                        "output": "outputs/result.webp",
                        "output_format": "webp",
                    },
                ],
            )
            with self.assertRaisesRegex(image_api.ImageApiError, "conflicts"):
                image_batch.preflight_batch(
                    batch,
                    root / "batch.manifest.json",
                    dry_run=True,
                )

    def test_dry_run_prints_plan_without_creating_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch = self.write_batch(
                root,
                [
                    {
                        "prompt": "A dry run",
                        "output": "outputs/result.png",
                        "output_format": "png",
                    }
                ],
            )
            manifest = root / "custom.manifest.json"
            import contextlib
            import io

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = image_batch.main(
                    [str(batch), "--manifest", str(manifest), "--dry-run"]
                )
            body = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(body["dry_run"])
            self.assertFalse(manifest.exists())
            self.assertFalse((root / "outputs").exists())

    def test_one_item_failure_does_not_stop_manifest_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch = self.write_batch(
                root,
                [
                    {
                        "id": "ok",
                        "prompt": "First",
                        "output": "outputs/ok.png",
                        "output_format": "png",
                    },
                    {
                        "id": "bad",
                        "prompt": "Second",
                        "output": "outputs/bad.png",
                        "output_format": "png",
                    },
                ],
            )
            manifest_path = root / "batch.manifest.json"
            plans = image_batch.preflight_batch(batch, manifest_path, dry_run=True)

            def succeed(_: Namespace) -> dict[str, object]:
                return {"delivery_ready": True, "outputs": []}

            def fail(_: Namespace) -> dict[str, object]:
                raise image_api.ImageApiError("provider rejected the request")

            plans[0].args.handler = succeed
            plans[1].args.handler = fail
            manifest, exit_code = image_batch.run_plans(batch, manifest_path, plans)
            stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(stored["succeeded"], 1)
        self.assertEqual(stored["failed"], 1)
        self.assertEqual(len(stored["items"]), 2)


if __name__ == "__main__":
    unittest.main()
