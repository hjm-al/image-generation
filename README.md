# Image Generation Skill

[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Español](README.es.md)

An independent Codex skill for generating and editing images through OpenAI-compatible Images APIs. It handles prompt preparation, safe credential loading, response normalization, local file writing, format detection, dimensions, and metadata.

## Features

- Generate with `POST /images/generations`.
- Edit with official multipart or relay-style JSON.
- Build art direction from a layered style contract instead of vague adjectives.
- Label multiple references with ordered `Image 1`, `Image 2`, ... roles.
- Record source-image hashes, formats, dimensions, and alpha-channel presence.
- Validate mask size, PNG alpha-channel semantics, transparent pixels, and dimensions.
- Distinguish fully opaque, fully transparent, partially transparent, and unparseable PNG alpha channels.
- Reject `background=transparent` with JPEG output before making a request.
- Accept `b64_json`, `b64`, `url`, and common nested image fields.
- Publish each image set and JSON sidecar together without overwriting existing files.
- Detect PNG, JPEG, WebP, and GIF signatures and record real dimensions.
- Keep valid images when other candidates in the same response are malformed.
- Preflight JSONL jobs, reject path conflicts, and update a recovery manifest after every job.
- Write a JSON sidecar with request details, file hashes, delivery warnings, and response shape.
- Track reusable prompt revisions with coded quality events, prompt hashes, and regression checks.
- Run offline tests without making network requests.

## Install

Clone the repository, then copy it to the Codex skills directory:

```powershell
git clone https://github.com/hjm-al/image-generation.git
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

In Codex, invoke it explicitly with `$image-generation`; this is a skill reference, not PowerShell variable expansion. Codex can also select it from the description.

## Configure

Set the key only in the current process environment:

```powershell
$env:IMAGE_API_KEY = "your-key"
$env:IMAGE_API_BASE_URL = "https://api.openai.com/v1"
$env:IMAGE_MODEL = "gpt-image-1"
```

Supported environment variables:

| Variable | Required | Purpose |
|---|---:|---|
| `IMAGE_API_KEY` | Yes | Bearer token, or the variable named by `--api-key-env` |
| `IMAGE_API_BASE_URL` | No | API root, default `https://api.openai.com/v1` |
| `IMAGE_MODEL` | No | Default model, fallback `gpt-image-1` |

Remove the key after use:

```powershell
Remove-Item Env:IMAGE_API_KEY -ErrorAction SilentlyContinue
```

## Generate

```powershell
python .\scripts\image_api.py generate `
  --prompt "A quiet editorial photo of a ceramic cup on a windowsill, overcast daylight, no text or watermark" `
  --output .\outputs\cup.png `
  --size 1024x1024 `
  --quality high
```

Preview the request without a key or network call:

```powershell
python .\scripts\image_api.py generate `
  --prompt "A minimal studio portrait with a warm gray background" `
  --output .\outputs\portrait.png `
  --dry-run
```

## Art Direction

When style is central to the brief, define one primary medium plus the observable properties that control edges, rendering, surface, palette, light, composition, and optional graphic systems. For image-to-image work, keep the preservation contract separate from the restyling contract.

The guide includes photographic, illustration, print, poster, UI, 3D, technical, and mixed-style directions, along with replacements for vague style words. See [references/art-directions.md](references/art-directions.md).

## Edit

Official multipart transport:

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png
```

JSON transport used by some compatible relays:

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png `
  --transport json
```

Repeat `--image` and `--image-role` together for multiple references. The role count must match the image count. Multipart masks must be 4 MB or smaller, match the first source image's dimensions, contain a real alpha channel, and include at least one transparent pixel. PNG `tRNS` metadata is reported separately and is not treated as an alpha channel.

## Batch

Create a JSONL file with one job per line. Relative paths resolve from the JSONL file's directory:

```jsonl
{"id":"hero","prompt":"Editorial product photo of a steel kettle, side light, no text","output":"outputs/hero.png","output_format":"png","size":"1024x1536"}
{"id":"room-edit","operation":"edit","prompt":"Keep the product; replace the room with warm plaster","images":["inputs/source.png"],"image_roles":["product and framing reference"],"output":"outputs/room-edit.png","output_format":"png"}
```

Preflight without reading the API key or making a network call:

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --dry-run
```

After reviewing the job count and request plan:

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --manifest .\outputs\manifest.json
```

Batch jobs run sequentially and never retry or switch models automatically. A failed job does not stop later jobs. The manifest is updated atomically after each item. See [references/batch-jsonl.md](references/batch-jsonl.md) for the full field contract.

## Prompt Quality Loop

The skill can keep a local, append-only review log for reusable prompts. API sidecars remain the source of truth for request and delivery facts; quality events capture the subjective review. Each successful event records positive features and any observable defects from `C1` through `C9`. Infrastructure failures use `C10` and never become prompt-editing evidence.

Generate a normalized prompt hash:

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\theme.txt
```

Validate events and registered prompt versions:

```powershell
python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .
```

Summarize defects and check whether a review is due:

```powershell
python .\scripts\quality_log.py digest --events .\quality\events.jsonl
python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

The default prompt changes only after repeated evidence: at least 3 occurrences of the same defect in a theme, or 4 occurrences across at least 2 themes to change the shared template. See [references/quality-loop.md](references/quality-loop.md) for the event schema, version registry, controlled comparison rules, and review ledger.

All quality-log commands are offline. Any additional image generation used to compare prompt versions is billable and requires a stated request count and confirmation.

## Output Contract

For `outputs\result.png`, the helper also writes `outputs\result.png.json`. The sidecar includes:

- endpoint and model;
- exact prompt;
- non-secret request options;
- input-image paths, byte sizes, SHA-256 hashes, formats, and dimensions;
- final image paths, byte sizes, SHA-256 hashes, formats, alpha detection, and dimensions;
- alpha status (`opaque`, `transparent`, `partial`, `unknown`, `chunk_only`, or `none`);
- returned, published, and requested counts;
- `delivery_ready`, `warnings`, and per-candidate `errors`;
- response field names and timestamps.

If the provider returns a different format, the helper changes the output extension to the detected format instead of writing mislabeled bytes.

`delivery_ready` is stricter than provider success: it becomes false when any candidate fails, the image count differs from `n`, a requested fixed size is not met, a transparent background has no alpha channel, the alpha channel is fully opaque, or transparency cannot be verified. Image files and their sidecar are staged first and published as a set; a sidecar failure leaves no partial image delivery.

## Compatibility Notes

- The official OpenAI edit endpoint uses multipart form data.
- Some relay services implement JSON edits with `images[].image_url`; use `--transport json` only for those services.
- Signed image URLs are downloaded without the API key. If a provider requires authenticated downloads, request a base64 response instead.
- Provider-specific model names, sizes, quality values, and response formats remain the provider's responsibility.

## Test

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

The tests do not call external services and incur no cost.

## Security

- Do not commit `.env`, API keys, private reference images, or generated client work.
- Do not pass secrets with `--api-key`; use environment variables.
- Review the prompt before sending confidential material to a third-party API.

## License

MIT. Reviewed upstream design sources and exact revisions are listed in [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
