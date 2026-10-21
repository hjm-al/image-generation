# JSONL Batch Format

Use `scripts/image_batch.py` for a preflighted sequence of independent generate and edit jobs. Paths in the JSONL file are resolved relative to the JSONL file's directory unless they are absolute.

## Example

```jsonl
{"id":"hero","prompt":"Editorial product photo of a steel kettle on pale stone, side light, no text","output":"outputs/hero.png","output_format":"png","size":"1024x1536","quality":"high","n":1}
{"id":"room-edit","operation":"edit","prompt":"Keep the subject and framing; replace the background with warm plaster","images":["inputs/source.png"],"image_roles":["product and framing reference"],"output":"outputs/room-edit.png","output_format":"png","size":"1024x1024"}
```

Preview every request and run all local checks without a key or network call:

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --dry-run
```

Execute the batch:

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --manifest .\outputs\manifest.json
```

## Fields

| Field | Required | Meaning |
|---|---:|---|
| `id` | No | Unique job ID; defaults to `item-<line number>` |
| `operation` | No | `generate` or `edit`; defaults to `generate` |
| `prompt` / `prompt_file` | One | Inline UTF-8 prompt or prompt file |
| `output` | Yes | Image path; a supported extension or `output_format` is required |
| `metadata` | No | Explicit sidecar path |
| `model` | No | Model ID; otherwise uses `IMAGE_MODEL` or the helper default |
| `base_url` / `endpoint` | No | API root or a full endpoint override |
| `api_key_env` | No | Environment variable name; defaults to `IMAGE_API_KEY` |
| `size`, `quality`, `n` | No | Provider request options |
| `output_format` | No | `png`, `jpeg`, or `webp` |
| `response_format` | No | `b64_json` or `url` |
| `background` | No | `transparent`, `opaque`, or `auto` |
| `timeout` | No | Request timeout in seconds |
| `images` | Edit only | One path or a list of up to 16 source paths |
| `image_roles` | Edit only | One role per source image, in the same order |
| `mask` | Edit only | One mask path |
| `transport` | Edit only | `multipart` or `json` |

## Preflight Contract

Before the first billable request, the batch runner:

- parses every JSONL line and rejects unknown fields;
- reads prompts and validates all input images;
- checks role counts, mask size, dimensions, alpha semantics, and transparent pixels;
- requires predictable output formats;
- rejects duplicate IDs, image stems, sidecars, manifest paths, and existing files;
- checks every required API key environment variable when not using `--dry-run`.

Image stems are reserved across all jobs, even if requested extensions differ. This prevents a provider's actual returned format from turning two planned paths into one.

## Execution Contract

- Jobs run sequentially in file order.
- No job is retried automatically, and the runner never switches models.
- A failed job does not stop later jobs.
- A response can contain both valid and invalid candidates; valid images are published and invalid candidates are recorded.
- The manifest is atomically updated after every job so completed work is recoverable after interruption.
- The manifest distinguishes API success from technical delivery. Check each result's `delivery_ready`, `warnings`, and `errors`.
- The process exits `0` only when every job completes without delivery warnings or failures.

## Mask Rules

Multipart masks must be PNG files no larger than 4 MB, contain a real alpha channel with at least one transparent pixel, and match the first source image's dimensions. A PNG `tRNS` chunk is not treated as an alpha channel.

JSON transport can accept another supported raster format when the provider allows it. A JSON mask that relies only on `tRNS` produces an input warning in the request plan and sidecar instead of a claim that transparency was verified.
