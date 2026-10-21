# Design Attribution

Reviewed on 2026-10-22 against the exact GitHub revisions below. The licenses and commit IDs were checked through the GitHub API. This project independently implements its code, instructions, and tests; no upstream source code, prompt text, or preview image was copied.

## Adopted Designs

| Upstream project and revision | License | Contribution reflected here | Local landing |
|---|---|---|---|
| [yc-duan/api-image](https://github.com/yc-duan/api-image/tree/5d53535e78ab99e17b2aad84d6f01d9e7e6c37cf) `5d53535e78ab99e17b2aad84d6f01d9e7e6c37cf` | MIT | Ordered reference-image roles, mask format checks, and mask/source dimension matching | `apply_image_roles()`, `validate_image_roles()`, `validate_edit_inputs()` |
| [Syh1906/openai-compatible-imagegen](https://github.com/Syh1906/openai-compatible-imagegen/tree/32dba9b384e1b2b40c8711291a27194b30a5c5bf) `32dba9b384e1b2b40c8711291a27194b30a5c5bf` | MIT | JSONL preflight, recovery manifests, path-conflict checks, and delivery QA | `scripts/image_batch.py`, `parse_and_save_images()`, `delivery_ready` |
| [joeseesun/qiaomu-codex-imagegen](https://github.com/joeseesun/qiaomu-codex-imagegen/tree/c03a1ccaf77938257bb93f64e09afa9cd08efe29) `c03a1ccaf77938257bb93f64e09afa9cd08efe29` | MIT | Delivery-focused Codex workflow, environment-only credentials, and per-request approval boundaries | `SKILL.md`, `run_generate()`, `run_edit()` |
| [kingbootoshi/nano-banana-2-skill](https://github.com/kingbootoshi/nano-banana-2-skill/tree/80bab9a921608e701467ba7d03424c10589a233f) `80bab9a921608e701467ba7d03424c10589a233f` | MIT | Numbered reference discipline and explicit transparent-delivery checks | Role prompt block, alpha-status checks |
| [black-forest-labs/skills](https://github.com/black-forest-labs/skills/tree/8907d515b0ac270a988ec7a239add81ee13d6cba) `8907d515b0ac270a988ec7a239add81ee13d6cba` | MIT | Numbered references, exact text handling, and provider troubleshooting structure | `references/prompt-guide.md`, `references/providers.md` |
| [wuyoscar/GPT-Image2-Skill](https://github.com/wuyoscar/GPT-Image2-Skill/tree/9f8aa1a44a4a5c0f5a5d6e45eed564b3e2d5b87f) `9f8aa1a44a4a5c0f5a5d6e45eed564b3e2d5b87f` | MIT | Prompt workflow and reference-image categorization | `references/prompt-guide.md` |
| [guinacio/claude-image-gen](https://github.com/guinacio/claude-image-gen/tree/9ae689d2f1163ccba1900fa58a75436ef4d8d75b) `9ae689d2f1163ccba1900fa58a75436ef4d8d75b` | MIT | Mask preflight ideas: 4 MB limit, PNG alpha semantics, fully opaque mask rejection, and transparent-background/JPEG conflict | `MAX_MASK_BYTES`, `png_alpha_info()`, `validate_edit_inputs()`, `validate_request_options()` |
| [AgriciDaniel/banana-claude](https://github.com/AgriciDaniel/banana-claude/tree/08e329b37dae396fc869c10d3494c5950d1d61c2) `08e329b37dae396fc869c10d3494c5950d1d61c2` | MIT | Atomic artifact release, input hash revalidation, recovery manifests, and single-approval budget discipline | `publish_output_set()`, SHA-256 records, batch manifest, `SKILL.md` |
| [nexu-io/open-design](https://github.com/nexu-io/open-design/tree/8d820a698908dc279ef3d5aeb4ce6d156211a499) `8d820a698908dc279ef3d5aeb4ce6d156211a499` | Apache-2.0 at repository root; image prompt catalog uses mixed licenses | Content/style separation, layered art-direction stacks, and explicit anti-drift review concepts, independently rewritten | `references/art-directions.md`, `references/prompt-guide.md` |

### OpenDesign Prompt-Template Boundary

At the reviewed revision, `prompt-templates/image/` contains 48 JSON image-prompt entries with mixed source licenses: 36 `CC-BY-4.0`, 9 `Apache-2.0`, 2 marked `Original X post`, and 1 `MIT`. The repository-root LICENSE is Apache-2.0, but that root license does not erase the per-entry source metadata.

The catalog was reviewed only for recurring organizational ideas: separating what must be preserved from what may be restyled, describing style through observable visual layers, and limiting conflicting media. The local art-direction guide is an independent rewrite. It does not reproduce prompt strings, preview images, model recommendations, access claims, or source-specific creative content.

## Gateway Design References

These gateway projects informed error and routing boundaries. They were not copied or vendored, and this skill intentionally keeps one small HTTP client instead of adding a second proxy layer.

| Upstream project and revision | License | Contribution reflected here |
|---|---|---|
| [QuantumNous/new-api](https://github.com/QuantumNous/new-api/tree/7d8b91268dab69d7150f345c448b5e250163146a) `7d8b91268dab69d7150f345c448b5e250163146a` | AGPL-3.0 | Unified endpoint configuration, explicit provider/transport selection, and structured upstream error reporting |
| [songquanpeng/one-api](https://github.com/songquanpeng/one-api/tree/8df4a2670b98266bd287c698243fff327d9748cf) `8df4a2670b98266bd287c698243fff327d9748cf` | MIT | Separation between endpoint configuration and model selection; no blind model switching |
| [Portkey-AI/gateway](https://github.com/Portkey-AI/gateway/tree/669825cbe89ee51569918b8f78a9db486fd69dd4) `669825cbe89ee51569918b8f78a9db486fd69dd4` | MIT | Distinguishing auth, permission, request-shape, rate-limit, upstream, and ambiguous-timeout failures |

## Reviewed but Not Adopted

| Upstream project and revision | License | Decision |
|---|---|---|
| [ic0n311/codex-image-skill](https://github.com/ic0n311/codex-image-skill/tree/c237651e7898632c118a808412568987c35f39f3) `c237651e7898632c118a808412568987c35f39f3` | No license reported by GitHub | Its automatic `/images/generations` to `/responses` fallback was explicitly rejected because it can create a second billable request. No code or prompt text was copied. |
| [kkoppenhaver/cc-nano-banana](https://github.com/kkoppenhaver/cc-nano-banana/tree/3b136993b1218c3f3bb5d1489b3c1ecb441dc842) `3b136993b1218c3f3bb5d1489b3c1ecb441dc842` | MIT | Reviewed as a lower-priority workflow reference; no distinct implementation was adopted. |
| [ZeroLu/Ultimate-AI-Media-Generator-Skill](https://github.com/ZeroLu/Ultimate-AI-Media-Generator-Skill/tree/f28e58f2b9814b2056417377c46f34fd35219702) `f28e58f2b9814b2056417377c46f34fd35219702` | MIT | Reviewed for prompt and multi-media workflow ideas; its broader scope was not merged into this focused image API skill, and no prompt text was copied. |

## Local Workspace Design Source

The local workspace `图片生成/` directory was reviewed on 2026-10-22 as an additional design source. It is not a Git checkout, so no upstream revision or third-party license is asserted for it.

Its observable prompt-quality practices informed `references/prompt-guide.md`, `references/quality-loop.md`, and the independent implementation in `scripts/quality_log.py`: observable prompt language, cultural-object disambiguation, reserved text space, append-only quality events, defect codes, prompt-version hashes, review thresholds, and controlled comparison. The implementation was rewritten for this skill and is provider-neutral.

No sample images, API credentials, local model availability claims, prices, group-specific access results, or raw review records from that workspace are included here.

The local reference snapshots under the parent workspace are not Git checkouts. They may differ from the exact revisions above, so the commit links are the authoritative attribution points.

This project is licensed under the MIT License. See [LICENSE](LICENSE).
