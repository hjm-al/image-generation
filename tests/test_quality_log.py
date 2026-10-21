from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "quality_log.py"
SPEC = importlib.util.spec_from_file_location("quality_log", MODULE_PATH)
assert SPEC and SPEC.loader
quality_log = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = quality_log
SPEC.loader.exec_module(quality_log)


def prompt_registry(
    theme: str = "ceramic-cup",
    prompt_file: str = "prompts/ceramic-cup.txt",
    sha256_12: str = "0123456789ab",
) -> dict[str, object]:
    return {
        "schema": 1,
        "themes": {
            theme: {
                "file": prompt_file,
                "versions": [
                    {
                        "version": 1,
                        "date": "2026-10-22",
                        "sha256_12": sha256_12,
                        "summary": "Initial prompt",
                        "evidence": [],
                    }
                ],
            }
        },
    }


def quality_event(
    event_id: str = "QE-20261022-001",
    theme: str = "ceramic-cup",
    timestamp: str = "2026-10-22T14:05:00+08:00",
    code: str = "C5",
    severity: str = "S1",
    verdict: str = "needs-rework",
    action: str = "prompt-edit",
    positives: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": event_id,
        "timestamp": timestamp,
        "theme": theme,
        "prompt_file": "prompts/ceramic-cup.txt",
        "prompt_version": 1,
        "prompt_sha256_12": "0123456789ab",
        "model": "image-model",
        "mode": "generate",
        "request": {
            "size": "1024x1024",
            "quality": "high",
            "output_format": "png",
            "n": 1,
        },
        "result": {"http_status": 200, "delivery_ready": True},
        "verdict": verdict,
        "defects": [
            {
                "code": code,
                "severity": severity,
                "detail": "The cup touches the bottom edge and leaves no title area",
                "evidence": "bottom third",
                "suspect_clause": "unknown" if code == "C10" else "composition",
            }
        ],
        "positives": (
            ["Handle and rim geometry are readable"]
            if positives is None
            else positives
        ),
        "action": action,
    }


class PromptHashTests(unittest.TestCase):
    def test_hash_ignores_bom_line_endings_and_outer_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "prompt.txt"
            prompt.write_bytes(b"\xef\xbb\xbf  first\r\nsecond\r\n  ")
            result = quality_log.prompt_hash(prompt)
        normalized = "first\nsecond"
        expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        self.assertEqual(result["sha256_12"], expected)
        self.assertEqual(result["chars"], len(normalized))


class EventValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.versions = prompt_registry()
        self.index, errors = quality_log.validate_versions(self.versions)
        self.assertEqual(errors, [])

    def validate(self, event: dict[str, object]) -> list[str]:
        return quality_log.validate_event(event, 1, self.index, set())

    def test_accepts_complete_quality_event(self) -> None:
        self.assertEqual(self.validate(quality_event()), [])

    def test_c10_must_be_unknown_failed_and_alone(self) -> None:
        event = quality_event(
            code="C10",
            verdict="failed",
            action="retry",
            positives=[],
        )
        event["defects"][0]["suspect_clause"] = "composition"
        errors = self.validate(event)
        self.assertTrue(any("prompt clause" in error for error in errors))

    def test_failed_result_requires_c10(self) -> None:
        event = quality_event(verdict="failed", action="retry", positives=[])
        errors = self.validate(event)
        self.assertTrue(any("must include a C10" in error for error in errors))

    def test_prompt_edit_requires_prompt_defect(self) -> None:
        event = quality_event(code="C10", verdict="failed", action="prompt-edit", positives=[])
        errors = self.validate(event)
        self.assertTrue(any("C10 requires action retry or reject" in error for error in errors))

    def test_successful_result_requires_positive_feature(self) -> None:
        event = quality_event(positives=[])
        errors = self.validate(event)
        self.assertTrue(any("at least one positive" in error for error in errors))


class AppendTests(unittest.TestCase):
    def test_appends_validated_event_to_append_only_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events_path = root / "events.jsonl"
            versions_path = root / "versions.json"
            draft_path = root / "draft.jsonl"
            first = quality_event()
            second = quality_event("QE-20261022-002")
            events_path.write_text(json.dumps(first) + "\n", encoding="utf-8")
            versions_path.write_text(json.dumps(prompt_registry()), encoding="utf-8")
            draft_path.write_text(json.dumps(second) + "\n", encoding="utf-8")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = quality_log.main(
                    [
                        "append",
                        "--events",
                        str(events_path),
                        "--versions",
                        str(versions_path),
                        "--input",
                        str(draft_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("appended 1 quality event", output.getvalue())
            self.assertEqual(len(events_path.read_text(encoding="utf-8").splitlines()), 2)

    def test_duplicate_draft_does_not_modify_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events_path = root / "events.jsonl"
            versions_path = root / "versions.json"
            draft_path = root / "draft.jsonl"
            original = quality_event()
            events_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
            versions_path.write_text(json.dumps(prompt_registry()), encoding="utf-8")
            draft_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
            before = events_path.read_bytes()

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = quality_log.main(
                    [
                        "append",
                        "--events",
                        str(events_path),
                        "--versions",
                        str(versions_path),
                        "--input",
                        str(draft_path),
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("append rejected", output.getvalue())
            self.assertEqual(events_path.read_bytes(), before)


class DueTests(unittest.TestCase):
    def test_repeated_code_and_cross_theme_template_candidate(self) -> None:
        events = [
            quality_event("QE-20261020-001", theme="cup", timestamp="2026-10-20T10:00:00+08:00"),
            quality_event("QE-20261020-002", theme="cup", timestamp="2026-10-20T11:00:00+08:00"),
            quality_event("QE-20261021-001", theme="cup", timestamp="2026-10-21T10:00:00+08:00"),
            quality_event("QE-20261021-002", theme="kettle", timestamp="2026-10-21T11:00:00+08:00"),
        ]
        reviews = [{"id": "RV-20261018-001", "date": "2026-10-18", "scope": ["all"]}]

        report = quality_log.due_report(events, reviews, date(2026, 10, 22))

        self.assertIn("cup: C5x3", "\n".join(report["reasons"]))
        self.assertEqual(
            report["template_candidates"],
            [{"code": "C5", "total": 4, "themes": ["cup", "kettle"]}],
        )

    def test_s0_immediately_triggers_theme_review(self) -> None:
        event = quality_event(severity="S0")
        report = quality_log.due_report([event], [], date(2026, 10, 22))
        self.assertIn("S0", report["themes"]["ceramic-cup"]["triggers"])


class VersionFileTests(unittest.TestCase):
    def test_detects_prompt_changed_without_a_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompts" / "ceramic-cup.txt"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("Initial prompt", encoding="utf-8")
            digest = quality_log.prompt_hash(prompt)["sha256_12"]
            versions = prompt_registry(sha256_12=digest)
            self.assertEqual(quality_log.check_registered_files(versions, root), [])

            prompt.write_text("Changed prompt", encoding="utf-8")
            errors = quality_log.check_registered_files(versions, root)
            self.assertTrue(any("without a new registered version" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
