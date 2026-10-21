---
name: image-generation
description: Generate and edit images through OpenAI-compatible Images APIs, including prompt shaping, prompt-quality iteration, safe credential handling, response normalization, local file saving, and output validation; use when the user wants generated or edited image files rather than prompt text alone.
---

# Image Generation

Turn an image brief into a concrete visual specification, generate or edit the image with an OpenAI-compatible Images API, save the result locally, and verify the actual file.

## Workflow

1. Extract the subject, purpose, composition, lighting, style, color direction, text constraints, and output aspect ratio from the request. Infer reasonable details instead of asking about every field. Ask only when a missing choice would materially change the deliverable.
2. Write the prompt as concrete, observable visual language. For substantial prompt work, read [references/prompt-guide.md](references/prompt-guide.md). When style is central, the brief uses a vague or hybrid art direction, or an edit must preserve content while restyling it, also read [references/art-directions.md](references/art-directions.md).
3. Use `scripts/image_api.py` for API-backed work. Read [references/providers.md](references/providers.md) when the endpoint, edit transport, or provider behavior is uncertain.
4. Run `--dry-run` first when the user is reviewing an API request, when the provider is unfamiliar, or when credentials are not yet configured.
5. For an edit, label each reference with one `--image-role` in the same order as `--image`. Keep roles concrete: subject, composition, product, style, or typography reference.
6. For a mask, require a PNG alpha channel, at least one transparent pixel, dimensions matching the first input image, and a file no larger than 4 MB. Treat PNG `tRNS` metadata as distinct from an alpha channel.
7. Treat one direct generation request as authorization for one request. Before a batch, multiple variants, an ambiguous retry, or a model switch, state the request count and obtain confirmation.
8. Never print, persist, or place the API key in a shell command. Read it from an environment variable.
9. After generation, inspect the saved image when image viewing is available. Report the output path, model, dimensions, and any provider-specific limitation.
10. When a prompt will be reused, compared across models, or revised, read [references/quality-loop.md](references/quality-loop.md). Record observable defects and positive features before changing the default prompt.

## Commands

Run from the skill directory:

```powershell
$env:IMAGE_API_KEY = "your-key"
$env:IMAGE_API_BASE_URL = "https://api.openai.com/v1"
$env:IMAGE_MODEL = "gpt-image-1"

python .\scripts\image_api.py generate `
  --prompt "Editorial product photograph of a matte steel kettle on a pale stone counter, side light, no text or watermark" `
  --output .\outputs\kettle.png `
  --size 1024x1536 `
  --quality high
```

Edit with the official multipart shape:

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the product and framing; replace the background with warm sand-colored plaster." `
  --output .\outputs\source-edited.png
```

Some relays expect image edits as JSON with `images[].image_url` instead of multipart:

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "subject reference" `
  --prompt "Keep the subject; change the background to deep forest green." `
  --output .\outputs\source-edited.png `
  --transport json
```

For multiple jobs, read [references/batch-jsonl.md](references/batch-jsonl.md), dry-run the entire batch, and get approval for the billable request count before removing `--dry-run`.

Use `python .\scripts\image_api.py generate --help` or `edit --help` for the full option set.

## Prompt Quality Loop

Keep subjective review separate from API facts:

- use the API sidecar or batch manifest for the exact request, output hashes, dimensions, and provider error;
- append quality events for usable output, rework, and failures;
- classify defects with `C1` through `C10` and point each prompt defect to a concrete prompt clause;
- record positive features so a revision can be checked for regressions;
- register every prompt revision with a new version, hash, summary, and evidence event IDs;
- keep old prompt versions retrievable for controlled comparison.

Do not treat a single bad result as a reason to rewrite the default prompt. Do not mix a `C10` platform failure, such as a 502 or group-specific 404, into prompt feedback.

The quality helper is offline:

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\theme.txt
python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .
python .\scripts\quality_log.py digest --events .\quality\events.jsonl
python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

Read the linked reference for the event schema, defect definitions, review thresholds, and controlled experiment rules.

## Non-Negotiable Output Rules

- Do not overwrite an existing image or metadata file.
- Do not request `background=transparent` with JPEG output.
- Preserve the exact prompt used in the JSON sidecar.
- Detect the real returned format from file signatures; do not trust the requested extension.
- Do not claim an image was generated until a non-empty image file has been written and inspected.
- Treat `delivery_ready` as the technical delivery contract. A provider success with count, size, fully opaque alpha, unverifiable transparency, or candidate errors is not a clean delivery.
- Publish the image files and JSON sidecar as one output set; leave no image behind when sidecar publication fails.
- If no API credential or native image tool is available, deliver the final prompt and the exact dry-run command, and state that no image was generated.
- Do not include secrets, private file contents, or internal host details in prompts, metadata, or chat output.

## Validation

Run the offline test suite after changing the helper:

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

The tests use no network and incur no billing.

Design sources and reviewed upstream revisions are recorded in [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
