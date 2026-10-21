# Contributing

Thanks for helping improve Image Generation Skill. This project favors small,
auditable changes that keep image requests explicit, predictable, and easy to
review.

## Before You Start

- Use Python 3.10 or newer. The project has no third-party runtime dependencies.
- Search existing issues before opening a duplicate.
- Keep provider-specific behavior disabled by default and documented when it is
  optional.
- Never include API keys, private reference images, personal data, or client work
  in an issue, pull request, test fixture, or commit.

## Development

There is no build step. Run the scripts directly from the repository root:

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

The test suite is offline and must stay that way. Use `--dry-run` when checking
request construction. Do not call a billable image endpoint from an automated
test. A manual live-provider check needs an explicit request count, user
approval, and a note in the pull request describing what was actually sent.

## Change Guidelines

- Preserve the CLI contracts unless the change explicitly requires a migration.
- Do not add automatic retries, model fallbacks, or hidden second billable
  requests.
- Keep credentials in environment variables and redact them from all output and
  metadata.
- Add focused tests for parsing, validation, file publication, batch recovery, or
  quality-log behavior.
- Keep the five README files aligned: language links, capabilities, safety
  boundaries, and fenced code blocks should remain consistent.
- Update `references/` when a user-facing field, workflow, or provider assumption
  changes.

## Documentation Checks

The documentation tests verify:

- all five README files are present;
- each README links to every supported language;
- relative Markdown links resolve inside the repository;
- fenced code examples stay identical across translations;
- the example JSONL batch is valid;
- required community files and CI safety settings remain present.

Run the normal offline test command after documentation changes.

## Pull Requests

Keep each pull request focused. In the description:

1. State the user-visible problem.
2. Describe the behavior change and compatibility impact.
3. List the exact offline checks you ran.
4. Call out any unverified provider behavior or manual live request.
5. Confirm that no secret, private image, or generated client artifact was
   committed.

Use the pull request template. By submitting a contribution, you agree that it
may be distributed under the repository's [MIT License](LICENSE).

## Conduct and Security

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report
security problems using [SECURITY.md](SECURITY.md), not a public issue.
