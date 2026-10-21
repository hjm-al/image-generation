# Prompt Quality Loop

Use this reference when a prompt will be reused, compared across models, or changed after reviewing outputs. The goal is to keep prompt iteration traceable without turning every random artifact into a permanent rule.

## Separate Facts From Review

Keep two records:

| Record | Purpose | Source of truth |
|---|---|---|
| API sidecar and batch manifest | Objective request/result facts: endpoint, model, request options, hashes, dimensions, errors, delivery status | Written by `image_api.py` or `image_batch.py` |
| Quality event JSONL | Subjective review: usable verdict, observable defects, positive features, likely prompt clause | Append-only local file managed by `quality_log.py` |

Do not rewrite a sidecar with subjective opinions. Do not put provider secrets, authenticated URLs, or private source-image contents into quality events.

All validation, digest, and due-date commands are offline. Generating the samples used for review remains billable and needs a separate request plan and approval.

## Quality Event Schema

Write one JSON object per line. Every generated image should get at least one event; an API failure also gets an event.

```json
{"id":"QE-20261022-001","timestamp":"2026-10-22T14:05:00+08:00","theme":"ceramic-cup","prompt_file":"prompts/ceramic-cup.txt","prompt_version":1,"prompt_sha256_12":"0123456789ab","model":"image-model","mode":"generate","request":{"size":"1024x1024","quality":"high","output_format":"png","n":1},"result":{"http_status":200,"output":"outputs/cup.png","delivery_ready":true},"verdict":"needs-rework","defects":[{"code":"C5","severity":"S1","detail":"The cup touches the bottom edge and leaves no title area","evidence":"bottom third","suspect_clause":"composition"}],"positives":["Handle and rim geometry are readable","Ceramic glaze has consistent highlights"],"action":"prompt-edit","notes":"Candidate change only; do not edit the default yet"}
```

Required fields:

| Field | Contract |
|---|---|
| `id` | Unique `QE-YYYYMMDD-NNN` |
| `timestamp` | ISO 8601 with a timezone |
| `theme` | Reused visual topic or campaign key |
| `prompt_key` | Optional registry key; defaults to `theme`; use `__template__` for the shared template |
| `prompt_file` | Path matching the registered prompt file |
| `prompt_version` | Positive integer registered in the version file |
| `prompt_sha256_12` | First 12 lowercase hex characters of the normalized prompt hash |
| `model` | Exact requested model ID |
| `mode` | `generate`, `edit`, or `compare` |
| `request` | Non-secret request options object |
| `result` | Local result facts object |
| `verdict` | `usable`, `needs-rework`, `unusable`, or `failed` |
| `defects` | Array of coded defects; use `[]` only when the review found none |
| `positives` | Non-empty for successful results; preserves regression checks |
| `action` | `prompt-edit`, `param-change`, `post-edit`, `retry`, `accept`, or `reject` |

Optional fields include `run_id`, `cost`, and a one-line `notes`.

## Defect Codes

Use observable evidence. "Ugly" is not a defect code.

| Code | Category | Observable failure |
|---|---|---|
| `C1` | Subject | Wrong subject, object class, quantity, action, or cultural function |
| `C2` | Structure | Broken anatomy, joints, connections, perspective, or duplicated subject |
| `C3` | Fact/culture | Wrong material, construction, clothing, period, or object use |
| `C4` | Text contamination | Garbled text, unintended logo, watermark, signature, or marking |
| `C5` | Composition | Cropping, scale, placement, sight line, or reserved-area failure |
| `C6` | Detail/material | Missing fibers, texture, contact shadow, or other required detail |
| `C7` | Style conflict | Mixed incompatible media or a style that does not fit the deliverable |
| `C8` | Light/color | Wrong direction, clipping, crushed shadows, or unwanted cast/saturation |
| `C9` | Specification | Actual dimensions, format, alpha, or file contract differs from the request |
| `C10` | Infrastructure | 502, 404, timeout, auth failure, no image field, or download failure |

Severity is `S0` (blocked, immediate review), `S1` (major rework), `S2` (minor repair), or `S3` (observation).

### C10 Boundary

`C10` means the platform or request path failed; it does not describe the prompt.

- Record `C10` alone.
- Use `suspect_clause: "unknown"`.
- Use action `retry` or `reject`.
- Keep the original redacted error in the API sidecar or run record.
- Do not rewrite a prompt because of one 502.
- A group-specific 404 means the current credential cannot access that model. It does not prove the model does not exist.

## Prompt Versions

Store a registry next to the event log. The helper supports this shape:

```json
{
  "schema": 1,
  "hash_rule": "sha256(UTF-8 without BOM, LF normalized, trimmed), first 12 hex characters",
  "themes": {
    "ceramic-cup": {
      "file": "prompts/ceramic-cup.txt",
      "versions": [
        {
          "version": 1,
          "date": "2026-10-22",
          "sha256_12": "0123456789ab",
          "summary": "Initial concrete product brief",
          "evidence": []
        }
      ]
    }
  },
  "template": {
    "file": "prompts/general-template.txt",
    "versions": [
      {
        "version": 1,
        "date": "2026-10-22",
        "sha256_12": "abcdef123456",
        "summary": "Initial reusable template",
        "evidence": []
      }
    ]
  }
}
```

Before accepting a revision:

1. archive the old prompt body;
2. increment the version;
3. record the new hash and a concise change summary;
4. list the quality-event IDs used as evidence;
5. keep the old version retrievable for A/B comparison.

A prompt edit without a new registered version invalidates quality attribution.

## Review Thresholds

Do not change a default prompt from one observation.

- Review a theme after 5 new events, after the same theme/code combination reaches 3 events, after any `S0`, or after 14 days without a global review.
- Change a theme prompt after the same code appears at least 3 times in that theme.
- Change the shared template only after the same code appears in at least 2 themes and at least 4 times overall.
- If a prompt body grows beyond 2,000 characters, delete lower-value guidance or document why the extra length is needed.

These are minimum gates, not proof that a change caused improvement.

## Controlled Verification

To compare prompt versions:

- hold model, `n`, size, quality, output format, and theme fixed;
- change only the prompt version;
- run at least two images per version, or one image on each of two models;
- compare defect recurrence, new regressions, and preserved positive features;
- require at least two aligned samples before treating a change as evidence.

To compare models:

- hold the exact prompt and every request option fixed;
- change only the model;
- preserve each sidecar;
- do not rank models from a single image.

Run two or more direct generation requests only after stating the billable request count and receiving confirmation.

## Offline Commands

From the skill directory:

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\ceramic-cup.txt

python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .

Get-Content .\quality\draft.jsonl -Raw |
  python .\scripts\quality_log.py append `
    --events .\quality\events.jsonl `
    --versions .\quality\prompt-versions.json `
    --input -

python .\scripts\quality_log.py digest --events .\quality\events.jsonl

python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

The review ledger is optional until a time-based review history exists:

```json
{"reviews":[{"id":"RV-20261022-001","date":"2026-10-22","scope":["all"]}]}
```

`append` validates the entire draft before writing anything. The event log remains append-only.
