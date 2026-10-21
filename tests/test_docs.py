from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
README_FILES = (
    "README.md",
    "README.zh-CN.md",
    "README.zh-TW.md",
    "README.ja.md",
    "README.es.md",
)
REQUIRED_FILES = (
    *README_FILES,
    "LICENSE",
    "ATTRIBUTIONS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/pull_request_template.md",
    "examples/jobs.example.jsonl",
)
MARKDOWN_LINK_RE = re.compile(
    r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
)
FENCE_RE = re.compile(r"^```(?P<language>[^\r\n`]*)\s*$")
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+\S")


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    language: str | None = None
    content: list[str] = []
    for line in text.splitlines():
        match = FENCE_RE.fullmatch(line)
        if match:
            if language is None:
                language = match.group("language").strip()
                content = []
            else:
                blocks.append((language, "\n".join(content)))
                language = None
                content = []
            continue
        if language is not None:
            content.append(line)
    if language is not None:
        raise AssertionError("unclosed fenced code block")
    return blocks


def heading_levels(text: str) -> list[int]:
    levels: list[int] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.fullmatch(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            levels.append(len(match.group("marks")))
    return levels


class CommunityFileTests(unittest.TestCase):
    def test_required_open_source_files_exist(self) -> None:
        missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])

    def test_workflow_has_read_only_permissions_and_manual_dispatch(self) -> None:
        workflow = read_text(".github/workflows/validate.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("cancel-in-progress: true", workflow)

    def test_example_batch_is_valid_and_has_unique_paths(self) -> None:
        records = [
            json.loads(line)
            for line in read_text("examples/jobs.example.jsonl").splitlines()
            if line.strip()
        ]
        self.assertGreaterEqual(len(records), 2)
        self.assertEqual(len({record["id"] for record in records}), len(records))
        self.assertEqual(len({record["output"] for record in records}), len(records))
        for record in records:
            self.assertTrue(record["prompt"].strip())
            self.assertTrue(record["output"].endswith(".png"))


class ReadmeContractTests(unittest.TestCase):
    def test_language_switches_link_to_every_readme(self) -> None:
        for readme in README_FILES:
            text = read_text(readme)
            for target in README_FILES:
                self.assertIn(f"]({target})", text, f"{readme} does not link to {target}")

    def test_code_blocks_match_across_languages(self) -> None:
        expected = fenced_blocks(read_text(README_FILES[0]))
        self.assertTrue(expected)
        for readme in README_FILES[1:]:
            self.assertEqual(
                fenced_blocks(read_text(readme)),
                expected,
                f"code blocks differ in {readme}",
            )

    def test_heading_structure_matches_across_languages(self) -> None:
        expected = heading_levels(read_text(README_FILES[0]))
        self.assertGreater(len(expected), 10)
        for readme in README_FILES[1:]:
            self.assertEqual(
                heading_levels(read_text(readme)),
                expected,
                f"heading structure differs in {readme}",
            )

    def test_readmes_link_to_community_guides(self) -> None:
        expected_links = (
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
        )
        for readme in README_FILES:
            text = read_text(readme)
            for target in expected_links:
                self.assertIn(
                    f"]({target})",
                    text,
                    f"{readme} does not link to {target}",
                )

    def test_fenced_blocks_are_balanced(self) -> None:
        for path in sorted(ROOT.rglob("*.md")):
            if ".git" in path.parts:
                continue
            fenced_blocks(path.read_text(encoding="utf-8-sig"))

    def test_relative_markdown_links_resolve_inside_repository(self) -> None:
        failures: list[str] = []
        for path in sorted(ROOT.rglob("*.md")):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8-sig")
            for match in MARKDOWN_LINK_RE.finditer(text):
                target = match.group("target").strip("<>")
                parts = urlsplit(target)
                if parts.scheme or target.startswith("#"):
                    continue
                relative = unquote(parts.path)
                if not relative:
                    continue
                candidate = (path.parent / relative).resolve()
                try:
                    candidate.relative_to(ROOT)
                except ValueError:
                    failures.append(
                        f"{path.relative_to(ROOT)}: link escapes repository: {target}"
                    )
                    continue
                if not candidate.exists():
                    failures.append(
                        f"{path.relative_to(ROOT)}: missing local target: {target}"
                    )
        self.assertEqual(failures, [])


class SecretShapeTests(unittest.TestCase):
    def test_no_long_api_key_shaped_values_in_text_files(self) -> None:
        pattern = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
        failures: list[str] = []
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix.lower() not in {
                "",
                ".md",
                ".py",
                ".jsonl",
                ".yml",
                ".yaml",
                ".txt",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text):
                failures.append(str(path.relative_to(ROOT)))
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
