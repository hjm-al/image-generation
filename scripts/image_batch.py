#!/usr/bin/env python3
"""Run a preflighted JSONL batch through the image API helper."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import image_api


COMMON_KEYS = {
    "id",
    "operation",
    "mode",
    "prompt",
    "prompt_file",
    "output",
    "metadata",
    "base_url",
    "endpoint",
    "api_key_env",
    "model",
    "size",
    "quality",
    "n",
    "output_format",
    "response_format",
    "background",
    "timeout",
}
EDIT_KEYS = {"images", "image", "mask", "transport", "image_roles", "image_role"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


@dataclass
class BatchPlan:
    line_number: int
    item_id: str
    operation: str
    args: argparse.Namespace
    output: Path
    metadata: Path | None
    expected_format: str
    planned_outputs: list[Path]
    sidecar: Path


def resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise image_api.ImageApiError(f"cannot read batch file: {path}: {exc}") from exc

    records: list[tuple[int, dict[str, Any]]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise image_api.ImageApiError(
                f"invalid JSON on line {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise image_api.ImageApiError(
                f"line {line_number} must contain a JSON object"
            )
        records.append((line_number, value))
    if not records:
        raise image_api.ImageApiError("batch file contains no jobs")
    return records


def require_string(
    record: dict[str, Any],
    key: str,
    line_number: int,
    *,
    optional: bool = False,
) -> str | None:
    value = record.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise image_api.ImageApiError(
            f"line {line_number}: {key} must be a non-empty string"
        )
    return value.strip()


def optional_string(
    record: dict[str, Any],
    key: str,
    line_number: int,
) -> str | None:
    return require_string(record, key, line_number, optional=True)


def item_paths(
    record: dict[str, Any],
    key: str,
    line_number: int,
    base_dir: Path,
) -> list[Path]:
    value = record.get(key)
    if value is None:
        return []
    values: list[Any]
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise image_api.ImageApiError(
            f"line {line_number}: {key} must be a path string or a list of path strings"
        )
    paths: list[Path] = []
    for entry in values:
        if not isinstance(entry, str) or not entry.strip():
            raise image_api.ImageApiError(
                f"line {line_number}: {key} contains an invalid path"
            )
        paths.append(resolve_path(entry, base_dir))
    return paths


def optional_roles(
    record: dict[str, Any],
    line_number: int,
) -> list[str] | None:
    value = record.get("image_roles", record.get("image_role"))
    if value is None:
        return None
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or any(
        not isinstance(role, str) or not role.strip() for role in values
    ):
        raise image_api.ImageApiError(
            f"line {line_number}: image_roles must be a string or list of strings"
        )
    return [role.strip() for role in values]


def parse_positive_int(
    record: dict[str, Any],
    line_number: int,
) -> int:
    value = record.get("n", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise image_api.ImageApiError(
            f"line {line_number}: n must be a positive integer"
        )
    return value


def parse_timeout(
    record: dict[str, Any],
    line_number: int,
) -> float:
    value = record.get("timeout", 360.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise image_api.ImageApiError(
            f"line {line_number}: timeout must be a positive number"
        )
    return float(value)


def validate_choice(
    value: str | None,
    key: str,
    choices: set[str],
    line_number: int,
) -> str | None:
    if value is not None and value not in choices:
        allowed = ", ".join(sorted(choices))
        raise image_api.ImageApiError(
            f"line {line_number}: {key} must be one of {allowed}"
        )
    return value


def expected_format_for(args: argparse.Namespace) -> str:
    if args.output_format:
        return args.output_format
    suffix = args.output.suffix.lower().lstrip(".")
    if suffix in IMAGE_EXTENSIONS:
        return "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    raise image_api.ImageApiError(
        "batch outputs need a PNG/JPEG/WebP/GIF extension or an output_format value"
    )


def build_plan(
    line_number: int,
    record: dict[str, Any],
    base_dir: Path,
) -> BatchPlan:
    operation_value = record.get("operation", record.get("mode", "generate"))
    if not isinstance(operation_value, str):
        raise image_api.ImageApiError(
            f"line {line_number}: operation must be a string"
        )
    operation = {"generate": "generate", "edit": "edit"}.get(
        operation_value.strip().lower()
    )
    if operation is None:
        raise image_api.ImageApiError(
            f"line {line_number}: operation must be generate or edit"
        )

    allowed_keys = COMMON_KEYS | (EDIT_KEYS if operation == "edit" else set())
    unknown_keys = sorted(set(record) - allowed_keys)
    if unknown_keys:
        raise image_api.ImageApiError(
            f"line {line_number}: unknown field(s): {', '.join(unknown_keys)}"
        )

    output_value = require_string(record, "output", line_number, optional=False)
    assert output_value is not None
    output = resolve_path(output_value, base_dir)
    metadata_value = optional_string(record, "metadata", line_number)
    metadata = resolve_path(metadata_value, base_dir) if metadata_value else None

    prompt = optional_string(record, "prompt", line_number)
    prompt_file_value = optional_string(record, "prompt_file", line_number)
    if bool(prompt) == bool(prompt_file_value):
        raise image_api.ImageApiError(
            f"line {line_number}: provide exactly one of prompt or prompt_file"
        )
    prompt_file = (
        resolve_path(prompt_file_value, base_dir) if prompt_file_value else None
    )

    output_format = validate_choice(
        optional_string(record, "output_format", line_number),
        "output_format",
        {"png", "jpeg", "webp"},
        line_number,
    )
    response_format = validate_choice(
        optional_string(record, "response_format", line_number),
        "response_format",
        {"b64_json", "url"},
        line_number,
    )
    background = validate_choice(
        optional_string(record, "background", line_number),
        "background",
        {"transparent", "opaque", "auto"},
        line_number,
    )
    transport = validate_choice(
        optional_string(record, "transport", line_number) if operation == "edit" else None,
        "transport",
        {"multipart", "json"},
        line_number,
    ) or "multipart"

    base_url = optional_string(record, "base_url", line_number)
    endpoint = optional_string(record, "endpoint", line_number)
    model = optional_string(record, "model", line_number)
    api_key_env = optional_string(record, "api_key_env", line_number) or "IMAGE_API_KEY"
    size = optional_string(record, "size", line_number)
    quality = optional_string(record, "quality", line_number)
    n = parse_positive_int(record, line_number)
    timeout = parse_timeout(record, line_number)

    args = argparse.Namespace(
        command=operation,
        prompt=prompt,
        prompt_file=prompt_file,
        output=output,
        metadata=metadata,
        base_url=base_url or os.environ.get("IMAGE_API_BASE_URL", image_api.DEFAULT_BASE_URL),
        endpoint=endpoint,
        api_key_env=api_key_env,
        model=model or os.environ.get("IMAGE_MODEL", image_api.DEFAULT_MODEL),
        size=size,
        quality=quality,
        n=n,
        output_format=output_format,
        response_format=response_format,
        background=background,
        timeout=timeout,
        dry_run=False,
    )
    image_api.validate_request_options(args)

    item_id = optional_string(record, "id", line_number) or f"item-{line_number}"
    if operation == "edit":
        images_value = item_paths(record, "images", line_number, base_dir)
        if not images_value:
            images_value = item_paths(record, "image", line_number, base_dir)
        if not images_value:
            raise image_api.ImageApiError(
                f"line {line_number}: edit jobs require images"
            )
        mask_values = item_paths(record, "mask", line_number, base_dir)
        if len(mask_values) > 1:
            raise image_api.ImageApiError(
                f"line {line_number}: mask must contain one path"
            )
        args.image = images_value
        args.mask = mask_values[0] if mask_values else None
        args.transport = transport
        args.image_role = optional_roles(record, line_number)
        args.handler = image_api.run_edit
    else:
        args.handler = image_api.run_generate

    image_api.load_prompt(args.prompt, args.prompt_file)
    if operation == "edit":
        image_api.validate_image_roles(args.image, args.image_role)
        image_api.validate_edit_inputs(args.image, args.mask, args.transport)

    expected_format = expected_format_for(args)
    planned_outputs = [
        image_api.output_path_for(output, index, expected_format)
        for index in range(n)
    ]
    sidecar = metadata or planned_outputs[0].with_name(
        planned_outputs[0].name + ".json"
    )
    if sidecar in planned_outputs:
        raise image_api.ImageApiError(
            f"line {line_number}: metadata path cannot equal an image output path"
        )

    return BatchPlan(
        line_number=line_number,
        item_id=item_id,
        operation=operation,
        args=args,
        output=output,
        metadata=metadata,
        expected_format=expected_format,
        planned_outputs=planned_outputs,
        sidecar=sidecar,
    )


def path_variants(path: Path) -> list[Path]:
    suffix = path.suffix.lower()
    if suffix == ".gif":
        return [path]
    stem = path.stem
    return [
        path.with_name(f"{stem}.png"),
        path.with_name(f"{stem}.jpg"),
        path.with_name(f"{stem}.jpeg"),
        path.with_name(f"{stem}.webp"),
        path.with_name(f"{stem}.gif"),
    ]


def sidecar_variants(path: Path) -> list[Path]:
    variants = [path]
    name = path.name
    for suffix in (".png.json", ".jpg.json", ".jpeg.json", ".webp.json", ".gif.json"):
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            variants.extend(
                path.with_name(stem + candidate)
                for candidate in (
                    ".png.json",
                    ".jpg.json",
                    ".jpeg.json",
                    ".webp.json",
                    ".gif.json",
                )
            )
            break
    return list(dict.fromkeys(variants))


def claim_stem(path: Path) -> tuple[str, str]:
    return (str(path.parent).casefold(), path.stem.casefold())


def preflight_batch(
    batch_path: Path,
    manifest_path: Path,
    *,
    dry_run: bool,
) -> list[BatchPlan]:
    base_dir = batch_path.parent.resolve()
    records = read_jsonl(batch_path)
    plans = [build_plan(line, record, base_dir) for line, record in records]

    item_ids: set[str] = set()
    output_stems: dict[tuple[str, str], str] = {}
    output_paths: set[str] = set()
    sidecars: dict[str, str] = {}
    for plan in plans:
        if plan.item_id in item_ids:
            raise image_api.ImageApiError(
                f"line {plan.line_number}: duplicate id {plan.item_id}"
            )
        item_ids.add(plan.item_id)

        for target in plan.planned_outputs:
            stem = claim_stem(target)
            previous = output_stems.get(stem)
            if previous and previous != plan.item_id:
                raise image_api.ImageApiError(
                    f"line {plan.line_number}: output stem conflicts with {previous}: "
                    f"{target}"
                )
            output_stems[stem] = plan.item_id
            for variant in path_variants(target):
                variant_key = str(variant).casefold()
                if variant_key in sidecars:
                    raise image_api.ImageApiError(
                        f"line {plan.line_number}: image output conflicts with "
                        f"{sidecars[variant_key]} metadata: {variant}"
                    )
                output_paths.add(variant_key)
                if variant.exists():
                    raise image_api.ImageApiError(
                        f"line {plan.line_number}: output already exists: {variant}"
                    )

        for sidecar in sidecar_variants(plan.sidecar):
            key = str(sidecar).casefold()
            if key in output_paths:
                raise image_api.ImageApiError(
                    f"line {plan.line_number}: metadata path conflicts with an "
                    f"image output: {sidecar}"
                )
            previous = sidecars.get(key)
            if previous and previous != plan.item_id:
                raise image_api.ImageApiError(
                    f"line {plan.line_number}: metadata path conflicts with {previous}: "
                    f"{sidecar}"
                )
            sidecars[key] = plan.item_id
            if sidecar.exists():
                raise image_api.ImageApiError(
                    f"line {plan.line_number}: metadata already exists: {sidecar}"
                )

    manifest_key = str(manifest_path.resolve())
    if any(stem == claim_stem(manifest_path) for stem in output_stems):
        raise image_api.ImageApiError(
            f"manifest path conflicts with an image output: {manifest_key}"
        )
    if manifest_key.casefold() in sidecars:
        raise image_api.ImageApiError(
            f"manifest path conflicts with an image sidecar: {manifest_key}"
        )

    if not dry_run:
        for plan in plans:
            image_api.require_key(plan.args.api_key_env)
    return plans


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def initial_manifest(batch_path: Path, plans: list[BatchPlan]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch": str(batch_path.resolve()),
        "status": "running",
        "total": len(plans),
        "succeeded": 0,
        "contract_warnings": 0,
        "failed": 0,
        "items": [],
    }


def dry_run_plan(plans: list[BatchPlan]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for plan in plans:
        plan.args.dry_run = True
        request = plan.args.handler(plan.args)
        items.append(
            {
                "id": plan.item_id,
                "line": plan.line_number,
                "operation": plan.operation,
                "planned_outputs": [
                    str(path.resolve()) for path in plan.planned_outputs
                ],
                "metadata": str(plan.sidecar.resolve()),
                "request": request,
            }
        )
    return {"dry_run": True, "total": len(plans), "items": items}


def run_plans(
    batch_path: Path,
    manifest_path: Path,
    plans: list[BatchPlan],
) -> tuple[dict[str, Any], int]:
    manifest = initial_manifest(batch_path, plans)
    write_manifest(manifest_path, manifest)

    for plan in plans:
        item: dict[str, Any] = {
            "id": plan.item_id,
            "line": plan.line_number,
            "operation": plan.operation,
            "planned_outputs": [str(path.resolve()) for path in plan.planned_outputs],
        }
        try:
            result = plan.args.handler(plan.args)
            item["result"] = result
            if result.get("delivery_ready", True):
                item["status"] = "succeeded"
                manifest["succeeded"] += 1
            else:
                item["status"] = "succeeded_with_contract_warnings"
                manifest["contract_warnings"] += 1
        except (image_api.ImageApiError, OSError) as exc:
            item["status"] = "failed"
            item["error"] = str(exc)[: image_api.MAX_ERROR_TEXT]
            manifest["failed"] += 1
            manifest["items"].append(item)
            write_manifest(manifest_path, manifest)
            continue
        manifest["items"].append(item)
        write_manifest(manifest_path, manifest)

    if manifest["failed"]:
        manifest["status"] = "failed" if manifest["failed"] == len(plans) else "partial"
    elif manifest["contract_warnings"]:
        manifest["status"] = "contract_warnings"
    else:
        manifest["status"] = "completed"
    write_manifest(manifest_path, manifest)
    exit_code = 0 if manifest["status"] == "completed" else 1
    return manifest, exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and run a JSONL image batch without automatic retries."
    )
    parser.add_argument("batch", type=Path, help="UTF-8 JSONL batch file")
    parser.add_argument(
        "--manifest",
        type=Path,
        help="manifest path (default: <batch>.manifest.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preflight every job and print the request plan without keys or network calls",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    image_api.configure_stdio()
    args = build_parser().parse_args(argv)
    batch_path = args.batch.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else batch_path.with_name(batch_path.name + ".manifest.json")
    )
    try:
        plans = preflight_batch(batch_path, manifest_path, dry_run=args.dry_run)
        if args.dry_run:
            output = dry_run_plan(plans)
            exit_code = 0
        else:
            output, exit_code = run_plans(batch_path, manifest_path, plans)
    except image_api.ImageApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
