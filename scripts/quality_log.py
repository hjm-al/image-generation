#!/usr/bin/env python3
"""Validate and summarize offline image-quality records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


EVENT_ID_PATTERN = re.compile(r"^QE-\d{8}-\d{3}$")
SHA12_PATTERN = re.compile(r"^[0-9a-f]{12}$")
VERDICTS = {"usable", "needs-rework", "unusable", "failed"}
MODES = {"generate", "edit", "compare"}
ACTIONS = {"prompt-edit", "param-change", "post-edit", "retry", "accept", "reject"}
SEVERITIES = {"S0", "S1", "S2", "S3"}
DEFECT_CODES = {f"C{number}" for number in range(1, 11)}
CLAUSES = {
    "use-case",
    "asset-type",
    "primary-request",
    "scene",
    "subject-details",
    "composition",
    "style-medium",
    "lighting-mood",
    "color-palette",
    "text-layout",
    "constraints",
    "unknown",
}
REQUIRED_EVENT_FIELDS = (
    "id",
    "timestamp",
    "theme",
    "prompt_file",
    "prompt_version",
    "prompt_sha256_12",
    "model",
    "mode",
    "request",
    "result",
    "verdict",
    "defects",
    "positives",
    "action",
)
RULES = {
    "review_interval_days": 14,
    "events_per_theme": 5,
    "same_code_per_theme": 3,
    "immediate_severity": "S0",
    "template_min_themes": 2,
    "template_min_total": 4,
}


class QualityLogError(ValueError):
    """A user-facing quality-record error."""


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def normalized_prompt_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise QualityLogError(f"cannot read prompt file: {path}: {exc}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def prompt_hash(path: Path) -> dict[str, Any]:
    text = normalized_prompt_text(path)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"sha256_12": digest[:12], "chars": len(text)}


def canonical_path_text(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise QualityLogError(f"cannot read {label}: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise QualityLogError(f"{label} is not valid JSON: {path}: {exc}") from exc


def load_jsonl(path: Path) -> tuple[list[tuple[int, Any]], list[str]]:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise QualityLogError(f"cannot read event log: {path}: {exc}") from exc
    records: list[tuple[int, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append((line_number, json.loads(line)))
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
    return records, errors


def validate_versions(versions: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(versions, dict):
        return index, ["prompt version registry must be a JSON object"]
    if versions.get("schema") != 1:
        errors.append("prompt version registry schema must be 1")
    groups: dict[str, Any] = {}
    themes = versions.get("themes")
    if themes is not None:
        if not isinstance(themes, dict):
            errors.append("prompt version registry themes must be an object")
        else:
            groups.update(themes)
    template = versions.get("template")
    if template is not None:
        groups["__template__"] = template
    if not groups:
        errors.append("prompt version registry must define themes or template")
    for key, group in groups.items():
        label = f"prompt registry {key}"
        if not isinstance(group, dict):
            errors.append(f"{label}: must be an object")
            continue
        prompt_file = group.get("file")
        if not isinstance(prompt_file, str) or not prompt_file.strip():
            errors.append(f"{label}: missing file")
            prompt_file = ""
        versions_list = group.get("versions")
        if not isinstance(versions_list, list) or not versions_list:
            errors.append(f"{label}: versions must be a non-empty array")
            continue
        seen_versions: set[int] = set()
        for item_index, item in enumerate(versions_list):
            item_label = f"{label} versions[{item_index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label}: must be an object")
                continue
            version = item.get("version")
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                errors.append(f"{item_label}: version must be a positive integer")
                continue
            if version in seen_versions:
                errors.append(f"{item_label}: duplicate version {version}")
            seen_versions.add(version)
            sha = item.get("sha256_12")
            if not isinstance(sha, str) or not SHA12_PATTERN.fullmatch(sha):
                errors.append(f"{item_label}: sha256_12 must be 12 lowercase hex characters")
            if not isinstance(item.get("summary"), str) or not item["summary"].strip():
                errors.append(f"{item_label}: summary is required")
            if "evidence" in item and not isinstance(item["evidence"], list):
                errors.append(f"{item_label}: evidence must be an array")
            index[f"{key}#{version}"] = {
                **item,
                "prompt_key": key,
                "file": prompt_file,
            }
    return index, errors


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def validate_event(
    event: Any,
    line_number: int,
    version_index: dict[str, dict[str, Any]],
    seen_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    prefix = f"line {line_number}"
    if not isinstance(event, dict):
        return [f"{prefix}: event must be a JSON object"]

    for field in REQUIRED_EVENT_FIELDS:
        if field not in event or event[field] is None:
            errors.append(f"{prefix}: missing required field {field}")

    event_id = event.get("id")
    if isinstance(event_id, str):
        if not EVENT_ID_PATTERN.fullmatch(event_id):
            errors.append(f"{prefix}: id must match QE-YYYYMMDD-NNN")
        if event_id in seen_ids:
            errors.append(f"{prefix}: duplicate id {event_id}")
        seen_ids.add(event_id)
    elif event_id is not None:
        errors.append(f"{prefix}: id must be a string")

    timestamp = parse_timestamp(event.get("timestamp"))
    if timestamp is None:
        errors.append(f"{prefix}: timestamp must be ISO 8601 with a timezone")

    for field in ("theme", "prompt_file", "model"):
        value = event.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}: {field} must be a non-empty string")

    version = event.get("prompt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append(f"{prefix}: prompt_version must be a positive integer")

    sha = event.get("prompt_sha256_12")
    if not isinstance(sha, str) or not SHA12_PATTERN.fullmatch(sha):
        errors.append(f"{prefix}: prompt_sha256_12 must be 12 lowercase hex characters")

    for field, allowed in (
        ("mode", MODES),
        ("verdict", VERDICTS),
        ("action", ACTIONS),
    ):
        value = event.get(field)
        if value not in allowed:
            errors.append(
                f"{prefix}: {field} must be one of {', '.join(sorted(allowed))}"
            )

    if not isinstance(event.get("request"), dict):
        errors.append(f"{prefix}: request must be an object")
    if not isinstance(event.get("result"), dict):
        errors.append(f"{prefix}: result must be an object")

    positives = event.get("positives")
    if not isinstance(positives, list):
        errors.append(f"{prefix}: positives must be an array")
        positives = []
    elif any(not isinstance(value, str) or not value.strip() for value in positives):
        errors.append(f"{prefix}: every positive must be a non-empty string")

    defects = event.get("defects")
    if not isinstance(defects, list):
        errors.append(f"{prefix}: defects must be an array, including when empty")
        defects = []
    for defect_index, defect in enumerate(defects):
        tag = f"{prefix} defects[{defect_index}]"
        if not isinstance(defect, dict):
            errors.append(f"{tag}: must be an object")
            continue
        if defect.get("code") not in DEFECT_CODES:
            errors.append(f"{tag}: code must be C1 through C10")
        if defect.get("severity") not in SEVERITIES:
            errors.append(f"{tag}: severity must be S0 through S3")
        if not isinstance(defect.get("detail"), str) or not defect["detail"].strip():
            errors.append(f"{tag}: detail must be observable and non-empty")
        if defect.get("suspect_clause") not in CLAUSES:
            errors.append(f"{tag}: suspect_clause is not recognized")

    codes = {
        defect.get("code")
        for defect in defects
        if isinstance(defect, dict) and defect.get("code")
    }
    has_c10 = "C10" in codes
    verdict = event.get("verdict")
    action = event.get("action")
    if verdict == "failed" and not has_c10:
        errors.append(f"{prefix}: failed results must include a C10 defect")
    if has_c10:
        if codes != {"C10"}:
            errors.append(f"{prefix}: C10 infrastructure failure must be recorded alone")
        if action not in {"retry", "reject"}:
            errors.append(f"{prefix}: C10 requires action retry or reject")
        if verdict != "failed":
            errors.append(f"{prefix}: C10 requires verdict failed")
        for defect in defects:
            if isinstance(defect, dict) and defect.get("suspect_clause") != "unknown":
                errors.append(
                    f"{prefix}: C10 cannot attribute a platform failure to a prompt clause"
                )
    elif verdict in {"usable", "needs-rework"} and not positives:
        errors.append(
            f"{prefix}: successful results must record at least one positive feature"
        )
    if action == "prompt-edit" and not (codes & {f"C{number}" for number in range(1, 9)}):
        errors.append(
            f"{prefix}: prompt-edit requires a prompt-related C1-C8 defect"
        )

    prompt_key = event.get("prompt_key") or event.get("theme")
    if isinstance(prompt_key, str) and isinstance(version, int):
        registered = version_index.get(f"{prompt_key}#{version}")
        if registered is None:
            errors.append(
                f"{prefix}: no registered prompt version {prompt_key} v{version}"
            )
        else:
            if isinstance(sha, str) and sha != registered.get("sha256_12"):
                errors.append(
                    f"{prefix}: prompt hash does not match the registered version"
                )
            prompt_file = event.get("prompt_file")
            if isinstance(prompt_file, str) and canonical_path_text(prompt_file) != (
                canonical_path_text(str(registered.get("file", "")))
            ):
                errors.append(
                    f"{prefix}: prompt_file does not match the registered prompt file"
                )
    return errors


def validate_records(
    records: Iterable[tuple[int, Any]],
    version_index: dict[str, dict[str, Any]],
    seen_ids: set[str] | None = None,
) -> list[str]:
    ids = seen_ids if seen_ids is not None else set()
    errors: list[str] = []
    for line_number, event in records:
        errors.extend(validate_event(event, line_number, version_index, ids))
    return errors


def event_counts(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    themes: Counter[str] = Counter()
    codes: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    models: Counter[str] = Counter()
    verdicts: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    code_themes: dict[str, set[str]] = {}
    clause_total = 0
    clause_unknown = 0
    blockers: list[str] = []
    total = 0

    for event in events:
        total += 1
        themes[str(event.get("theme"))] += 1
        models[f"{event.get('model')} @ {event.get('theme')}"] += 1
        verdicts[str(event.get("verdict"))] += 1
        actions[str(event.get("action"))] += 1
        for defect in event.get("defects", []):
            code = str(defect.get("code"))
            severity = str(defect.get("severity"))
            codes[code] += 1
            severities[severity] += 1
            code_themes.setdefault(code, set()).add(str(event.get("theme")))
            clause_total += 1
            if defect.get("suspect_clause") == "unknown":
                clause_unknown += 1
            if severity == RULES["immediate_severity"]:
                blockers.append(
                    f"{event.get('id')} ({event.get('theme')}/"
                    f"{event.get('model')}) {code} {defect.get('detail')}"
                )
    return {
        "total": total,
        "themes": themes,
        "codes": codes,
        "severities": severities,
        "models": models,
        "verdicts": verdicts,
        "actions": actions,
        "code_themes": code_themes,
        "clause_total": clause_total,
        "clause_unknown": clause_unknown,
        "blockers": blockers,
    }


def parse_review_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def latest_review_date(
    reviews: list[dict[str, Any]],
    scope_item: str,
) -> date | None:
    latest: date | None = None
    for review in reviews:
        scope = review.get("scope", [])
        if not isinstance(scope, list):
            continue
        if "all" not in scope and scope_item not in scope:
            continue
        review_date = parse_review_date(review.get("date"))
        if review_date is not None and (latest is None or review_date > latest):
            latest = review_date
    return latest


def due_report(
    events: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    themes = sorted({str(event.get("theme")) for event in events})
    theme_results: dict[str, Any] = {}
    reasons: list[str] = []
    for theme in themes:
        last = latest_review_date(reviews, theme)
        fresh = []
        for event in events:
            if event.get("theme") != theme:
                continue
            timestamp = parse_timestamp(event.get("timestamp"))
            if last is None or (timestamp is not None and timestamp.date() > last):
                fresh.append(event)
        code_counts: Counter[str] = Counter()
        for event in fresh:
            for code in {
                defect.get("code")
                for defect in event.get("defects", [])
                if defect.get("code")
            }:
                code_counts[str(code)] += 1
        highest = code_counts.most_common(1)
        highest_code, highest_count = highest[0] if highest else (None, 0)
        triggers: list[str] = []
        if len(fresh) >= RULES["events_per_theme"]:
            triggers.append(f"events>={RULES['events_per_theme']}")
        if highest_count >= RULES["same_code_per_theme"]:
            triggers.append(f"{highest_code}x{highest_count}")
        if any(
            defect.get("severity") == RULES["immediate_severity"]
            for event in fresh
            for defect in event.get("defects", [])
        ):
            triggers.append("S0")
        theme_results[theme] = {
            "last_review": last.isoformat() if last else None,
            "fresh_events": len(fresh),
            "highest_code": highest_code,
            "highest_count": highest_count,
            "triggers": triggers,
        }
        if triggers:
            reasons.append(f"{theme}: {', '.join(triggers)}")

    global_last = latest_review_date(reviews, "all")
    days_since = (today - global_last).days if global_last else None
    if days_since is None:
        reasons.append("no global review recorded")
    elif days_since >= RULES["review_interval_days"]:
        reasons.append(f"{days_since} days since the last global review")

    counts = event_counts(events)
    candidates = []
    for code, themes_for_code in sorted(counts["code_themes"].items()):
        total = counts["codes"][code]
        if (
            len(themes_for_code) >= RULES["template_min_themes"]
            and total >= RULES["template_min_total"]
        ):
            candidates.append(
                {
                    "code": code,
                    "total": total,
                    "themes": sorted(themes_for_code),
                }
            )
    return {
        "due": bool(reasons),
        "reasons": reasons,
        "themes": theme_results,
        "global_last_review": global_last.isoformat() if global_last else None,
        "days_since_global_review": days_since,
        "template_candidates": candidates,
    }


def check_registered_files(
    versions: Any,
    root: Path,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(versions, dict):
        return ["prompt version registry must be a JSON object"]
    groups: dict[str, Any] = {}
    if isinstance(versions.get("themes"), dict):
        groups.update(versions["themes"])
    if isinstance(versions.get("template"), dict):
        groups["__template__"] = versions["template"]
    for key, group in groups.items():
        if not isinstance(group, dict):
            continue
        prompt_file = group.get("file")
        versions_list = group.get("versions")
        if not isinstance(prompt_file, str) or not isinstance(versions_list, list):
            continue
        latest = versions_list[-1] if versions_list else None
        if not isinstance(latest, dict):
            continue
        actual_path = (root / prompt_file).resolve()
        try:
            actual = prompt_hash(actual_path)
        except QualityLogError as exc:
            errors.append(f"{key}: {exc}")
            continue
        if actual["sha256_12"] != latest.get("sha256_12"):
            errors.append(
                f"{key}: prompt changed without a new registered version "
                f"(registered {latest.get('sha256_12')}, actual {actual['sha256_12']})"
            )
    return errors


def append_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("append wrote zero bytes")
            offset += written
    finally:
        os.close(descriptor)


def print_counter(title: str, counter: Counter[str]) -> None:
    print(f"\n{title}")
    if not counter:
        print("  none")
        return
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {key}: {count}")


def cmd_validate(args: argparse.Namespace) -> int:
    versions = load_json(args.versions, "prompt version registry")
    version_index, errors = validate_versions(versions)
    records, parse_errors = load_jsonl(args.events)
    errors.extend(parse_errors)
    errors.extend(validate_records(records, version_index))
    if args.root:
        errors.extend(check_registered_files(versions, args.root.resolve()))
    print(
        f"events: {len(records)} parsed, {len(parse_errors)} parse errors; "
        f"registered prompt versions: {len(version_index)}"
    )
    if errors:
        print(f"validation failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("validation passed")
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    versions = load_json(args.versions, "prompt version registry")
    version_index, registry_errors = validate_versions(versions)
    existing, parse_errors = load_jsonl(args.events)
    errors = list(registry_errors) + list(parse_errors)
    existing_ids: set[str] = set()
    errors.extend(validate_records(existing, version_index, existing_ids))
    seen_ids = set(existing_ids)

    if args.input == "-":
        draft_text = sys.stdin.read()
    else:
        try:
            draft_text = Path(args.input).read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise QualityLogError(f"cannot read draft event file: {exc}") from exc
    drafts: list[tuple[int, Any]] = []
    for line_number, line in enumerate(draft_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            drafts.append((line_number, json.loads(line)))
        except json.JSONDecodeError as exc:
            errors.append(f"draft line {line_number}: invalid JSON: {exc}")
    if not drafts:
        errors.append("draft input is empty")
    errors.extend(validate_records(drafts, version_index, seen_ids))
    if errors:
        print(f"append rejected with {len(errors)} issue(s); no data was written:")
        for error in errors:
            print(f"  - {error}")
        return 1

    payload = "\n".join(json.dumps(event, ensure_ascii=False) for _, event in drafts)
    try:
        existing_bytes = args.events.read_bytes() if args.events.exists() else b""
    except OSError as exc:
        raise QualityLogError(f"cannot inspect event log before append: {exc}") from exc
    prefix = b"\n" if existing_bytes and not existing_bytes.endswith(b"\n") else b""
    append_bytes(args.events, prefix + payload.encode("utf-8") + b"\n")
    print(f"appended {len(drafts)} quality event(s) to {args.events}")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    records, parse_errors = load_jsonl(args.events)
    if parse_errors:
        for error in parse_errors:
            print(error, file=sys.stderr)
        return 1
    events = [event for _, event in records if isinstance(event, dict)]
    counts = event_counts(events)
    print(f"events: {counts['total']}")
    print_counter("by theme", counts["themes"])
    print_counter("by defect code", counts["codes"])
    print_counter("by severity", counts["severities"])
    print_counter("by model and theme", counts["models"])
    print_counter("by verdict", counts["verdicts"])
    print_counter("by action", counts["actions"])
    ratio = (
        counts["clause_unknown"] / counts["clause_total"] * 100
        if counts["clause_total"]
        else 0
    )
    print(f"\nunknown prompt-clause attribution: {ratio:.0f}%")
    print("\nS0 blockers")
    if counts["blockers"]:
        for blocker in counts["blockers"]:
            print(f"  - {blocker}")
    else:
        print("  none")
    return 0


def cmd_due(args: argparse.Namespace) -> int:
    versions = load_json(args.versions, "prompt version registry")
    version_index, errors = validate_versions(versions)
    records, parse_errors = load_jsonl(args.events)
    errors.extend(parse_errors)
    errors.extend(validate_records(records, version_index))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    events = [event for _, event in records if isinstance(event, dict)]
    reviews: list[dict[str, Any]] = []
    if args.ledger:
        ledger = load_json(args.ledger, "review ledger")
        if not isinstance(ledger, dict) or not isinstance(ledger.get("reviews"), list):
            raise QualityLogError("review ledger must contain a reviews array")
        reviews = [item for item in ledger["reviews"] if isinstance(item, dict)]
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError as exc:
        raise QualityLogError("--today must use YYYY-MM-DD") from exc
    report = due_report(events, reviews, today)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_versions(args: argparse.Namespace) -> int:
    versions = load_json(args.versions, "prompt version registry")
    _, errors = validate_versions(versions)
    errors.extend(check_registered_files(versions, args.root.resolve()))
    if errors:
        print(f"prompt version check failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("all current prompt files match their latest registered versions")
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    result = prompt_hash(args.prompt.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize offline image-quality records."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--events", type=Path, required=True)
    validate_parser.add_argument("--versions", type=Path, required=True)
    validate_parser.add_argument(
        "--root",
        type=Path,
        help="also verify current prompt files relative to this project root",
    )
    validate_parser.set_defaults(handler=cmd_validate)

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--events", type=Path, required=True)
    append_parser.add_argument("--versions", type=Path, required=True)
    append_parser.add_argument(
        "--input",
        default="-",
        help="JSONL draft path, or - to read standard input",
    )
    append_parser.set_defaults(handler=cmd_append)

    digest_parser = subparsers.add_parser("digest")
    digest_parser.add_argument("--events", type=Path, required=True)
    digest_parser.set_defaults(handler=cmd_digest)

    due_parser = subparsers.add_parser("due")
    due_parser.add_argument("--events", type=Path, required=True)
    due_parser.add_argument("--versions", type=Path, required=True)
    due_parser.add_argument("--ledger", type=Path)
    due_parser.add_argument("--today", help="override today's date as YYYY-MM-DD")
    due_parser.set_defaults(handler=cmd_due)

    versions_parser = subparsers.add_parser("versions")
    versions_parser.add_argument("--versions", type=Path, required=True)
    versions_parser.add_argument("--root", type=Path, default=Path("."))
    versions_parser.set_defaults(handler=cmd_versions)

    hash_parser = subparsers.add_parser("hash")
    hash_parser.add_argument("--prompt", type=Path, required=True)
    hash_parser.set_defaults(handler=cmd_hash)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except QualityLogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
