# Provider Notes

## Generation

The helper sends JSON to:

```text
POST {base_url}/images/generations
```

Core fields are `model`, `prompt`, and optional `n`, `size`, `quality`, `output_format`, and `response_format`. Providers differ in which optional fields they accept, so the helper sends only values supplied by the caller.

## Editing

Official OpenAI-compatible editing uses multipart:

```text
POST {base_url}/images/edits
Content-Type: multipart/form-data
```

Fields include `model`, `prompt`, one or more image files, and an optional mask.

Some relay services implement JSON editing:

```json
{
  "model": "gpt-image-1",
  "prompt": "Keep the subject and framing.",
  "images": [
    {
      "image_url": "data:image/png;base64,..."
    }
  ]
}
```

Use `--transport json` only when the provider documents or demonstrates this shape. Do not assume JSON support from an OpenAI-compatible generation endpoint.

## Mask Preflight

For the official multipart shape, the helper requires:

- a PNG file no larger than 4 MB;
- dimensions matching the first source image;
- a real alpha channel, not only a `tRNS` transparency chunk;
- at least one pixel whose alpha value is below full opacity.

An RGBA file whose alpha channel is entirely opaque is rejected because it does not identify an editable region. Interlaced PNGs and images too large to inspect safely are also rejected when their transparent pixels cannot be verified.

JSON relay transports may accept other raster formats and mask semantics. If a JSON mask is a PNG with `tRNS` metadata but no alpha channel, the request plan records a warning; it does not claim that transparency was verified.

## Common Response Shapes

Recognized image item fields:

- `b64_json`
- `b64`
- `image.b64_json`
- `image.b64`
- `url`
- `image_url`
- `image.url`

Remote URLs are fetched without the API key. Prefer base64 output when the provider returns a private or authenticated image URL.

## Troubleshooting

- **401**: the key is missing, expired, or sent to the wrong service.
- **403**: the key lacks the model or group permission.
- **404 on a model**: confirm the exact model ID and account permission before changing the prompt.
- **404 on edits**: confirm whether the provider supports multipart, JSON, or neither.
- **400**: inspect the provider's `error.message`; invalid masks and optional fields are common causes.
- **429**: rate or quota limit. Do not automatically retry a billable request without confirmation.
- **5xx**: preserve the response body. Do not describe an upstream failure as proof that a model does not exist.

Do not retry after an ambiguous timeout until checking whether the provider may already have charged or created the image.
