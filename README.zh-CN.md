# 图片生成技能

[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Español](README.es.md)

[![validate](https://github.com/hjm-al/image-generation/actions/workflows/validate.yml/badge.svg)](https://github.com/hjm-al/image-generation/actions/workflows/validate.yml)

一个独立的 Codex 技能，通过兼容 OpenAI 的 Images API 生成和编辑图片。它负责提示词准备、密钥安全加载、响应标准化、本地文件写入、格式检测、尺寸读取和元数据记录。

## 功能

- 通过 `POST /images/generations` 生成图片。
- 通过官方 multipart 或中转服务常用的 JSON 方式编辑图片。
- 使用分层风格约定构建艺术方向，而不是堆砌模糊形容词。
- 用有序的 `Image 1`、`Image 2` 等角色标注多张参考图。
- 记录源图片哈希、格式、尺寸和 Alpha 通道状态。
- 校验蒙版大小、PNG Alpha 通道语义、透明像素和尺寸。
- 区分完全不透明、完全透明、部分透明和无法解析的 PNG Alpha 通道。
- 在发起请求前拒绝同时使用 JPEG 输出和 `background=transparent`。
- 接受 `b64_json`、`b64`、`url` 及常见的嵌套图片字段。
- 将每组图片和 JSON sidecar 作为一个集合发布，不覆盖已有文件。
- 检测 PNG、JPEG、WebP 和 GIF 文件签名，并记录真实尺寸。
- 同一响应中的其他候选损坏时，保留仍然有效的图片。
- 预检 JSONL 任务，拒绝路径冲突，并在每个任务后更新恢复清单。
- 写出包含请求详情、文件哈希、交付警告和响应结构的 JSON sidecar。
- 通过编码质量事件、提示词哈希和回归检查跟踪可复用提示词版本。
- 运行离线测试，不发起网络请求。

## 环境要求

- Python 3.10 或更高版本。
- 无需第三方包；辅助脚本、批处理器、质量日志工具和测试均只使用 Python 标准库。
- 只有实际生成或编辑请求才需要网络连接和服务商凭据。

## 费用与网络行为

- `--dry-run` 只打印计划请求，不读取 API Key、不使用网络，也不会产生费用。
- 测试套件和所有 `quality_log.py` 命令均为离线操作。
- `generate`、`edit` 以及未使用 `--dry-run` 的批处理会调用配置的服务商，并可能产生费用。
- 批处理中的每个条目会发起一次 API 请求；`n` 是该请求内要求的图片数量。脚本不会自动重试或切换模型。

## 安装

克隆仓库后，将其复制到 Codex 技能目录：

```powershell
git clone https://github.com/hjm-al/image-generation.git
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

在 Codex 中可使用 `$image-generation` 显式调用；这是技能引用，不是 PowerShell 变量展开。Codex 也可以根据描述自动选择该技能。

## 更新或卸载

更新已克隆的仓库和已安装技能：

```powershell
git -C .\image-generation pull --ff-only
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

这会复制当前文件，但不会删除上游已移除的文件。若需全新安装，请先检查并备份本地修改，再替换已安装目录。卸载技能：

```powershell
$target = Join-Path $HOME ".codex\skills\image-generation"
Remove-Item -LiteralPath $target -Recurse -Force
```

## 配置

仅在当前进程环境中设置密钥：

```powershell
$env:IMAGE_API_KEY = "your-key"
$env:IMAGE_API_BASE_URL = "https://api.openai.com/v1"
$env:IMAGE_MODEL = "gpt-image-1"
```

支持的环境变量：

| 变量 | 必需 | 用途 |
|---|---:|---|
| `IMAGE_API_KEY` | 是 | Bearer Token，或 `--api-key-env` 指定的变量 |
| `IMAGE_API_BASE_URL` | 否 | API 根地址，默认 `https://api.openai.com/v1` |
| `IMAGE_MODEL` | 否 | 默认模型，回退值为 `gpt-image-1` |

使用后移除密钥：

```powershell
Remove-Item Env:IMAGE_API_KEY -ErrorAction SilentlyContinue
```

## 生成

```powershell
python .\scripts\image_api.py generate `
  --prompt "A quiet editorial photo of a ceramic cup on a windowsill, overcast daylight, no text or watermark" `
  --output .\outputs\cup.png `
  --size 1024x1024 `
  --quality high
```

不读取密钥、也不发起网络请求地预览请求：

```powershell
python .\scripts\image_api.py generate `
  --prompt "A minimal studio portrait with a warm gray background" `
  --output .\outputs\portrait.png `
  --dry-run
```

## 艺术方向

当风格是简报的核心时，应定义一个主要媒介，并说明边缘、渲染、表面、配色、光线、构图和可选图形系统的可观察属性。对于图生图，应把内容保留约定与风格改写约定分开。

指南涵盖摄影、插画、印刷、海报、UI、3D、技术图和混合风格，并提供模糊风格词的替换方法。参见 [references/art-directions.md](references/art-directions.md)。

## 编辑

官方 multipart 传输：

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png
```

部分兼容中转服务使用的 JSON 传输：

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png `
  --transport json
```

多参考图使用时，成对重复 `--image` 和 `--image-role`。角色数量必须与图片数量一致。Multipart 蒙版必须不超过 4 MB、与第一张源图尺寸一致、包含真实 Alpha 通道，并至少有一个透明像素。PNG 的 `tRNS` 元数据会单独报告，不会被当作 Alpha 通道。

## 批处理

创建每行一个任务的 JSONL 文件。相对路径以 JSONL 文件所在目录为基准：

```jsonl
{"id":"hero","prompt":"Editorial product photo of a steel kettle, side light, no text","output":"outputs/hero.png","output_format":"png","size":"1024x1536"}
{"id":"room-edit","operation":"edit","prompt":"Keep the product; replace the room with warm plaster","images":["inputs/source.png"],"image_roles":["product and framing reference"],"output":"outputs/room-edit.png","output_format":"png"}
```

不读取 API Key、也不发起网络请求地预检：

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --dry-run
```

确认任务数量和请求计划后运行：

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --manifest .\outputs\manifest.json
```

批处理任务按顺序运行，不会自动重试或切换模型。单个任务失败不会阻止后续任务。清单会在每个条目的处理完成后原子更新。完整字段约定参见 [references/batch-jsonl.md](references/batch-jsonl.md)。

## 提示词质量循环

该技能可为可复用提示词维护本地、只追加的审查日志。API sidecar 仍是请求和交付事实的来源；质量事件记录主观审查。每个成功事件都应记录优点和 `C1` 至 `C9` 中可观察的缺陷。基础设施故障使用 `C10`，并且永远不会成为提示词编辑依据。

生成规范化提示词哈希：

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\theme.txt
```

校验事件和已登记提示词版本：

```powershell
python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .
```

汇总缺陷并检查是否到期需要审查：

```powershell
python .\scripts\quality_log.py digest --events .\quality\events.jsonl
python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

只有重复出现证据后，才修改默认提示词：同一主题中同一缺陷至少出现 3 次，或在至少 2 个主题中累计出现 4 次，才考虑修改共享模板。事件结构、版本登记、受控比较规则和审查台账参见 [references/quality-loop.md](references/quality-loop.md)。

所有质量日志命令均为离线操作。为比较提示词版本而额外生成图片会产生费用，必须说明请求数量并获得确认。

## 输出约定

对于 `outputs\result.png`，脚本还会写入 `outputs\result.png.json`。Sidecar 包含：

- 端点与模型；
- 完整提示词；
- 不含密钥的请求选项；
- 输入图片路径、字节数、SHA-256 哈希、格式和尺寸；
- 最终图片路径、字节数、SHA-256 哈希、格式、Alpha 检测结果和尺寸；
- Alpha 状态（`opaque`、`transparent`、`partial`、`unknown`、`chunk_only` 或 `none`）；
- 返回、发布和请求的图片数量；
- `delivery_ready`、`warnings` 和每个候选的错误；
- 响应字段名称和时间戳。

如果服务商返回的实际格式与请求不同，脚本会把输出扩展名改为检测到的格式，不会写入扩展名错误的字节。

`delivery_ready` 比服务商返回成功更严格：只要任一候选失败、图片数量与 `n` 不一致、请求的固定尺寸未满足、透明背景没有 Alpha 通道、Alpha 通道完全不透明或透明度无法验证，就会变为 false。图片文件和 sidecar 会先暂存，再作为一个集合发布；sidecar 失败时不会留下部分图片交付。

## 兼容性说明

- 官方 OpenAI 编辑端点使用 multipart 表单数据。
- 一些中转服务使用 `images[].image_url` 实现 JSON 编辑；仅对这类服务使用 `--transport json`。
- 签名图片 URL 下载时不带 API Key。如果服务商要求鉴权下载，应改用 base64 响应。
- 服务商特定的模型名称、尺寸、质量值和响应格式由服务商负责。

## 开发与验证

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

测试不会调用外部服务，也不会产生费用。CI 会检查 Python 3.10 和 3.12。开发流程和 Pull Request 要求参见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 贡献

请使用 Issue 和 Pull Request 模板，不要把真实服务商检查放进自动测试，并在提交 Pull Request 前运行上面的离线验证命令。参与项目时请遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 安全

- 不要提交 `.env`、API 密钥、私有参考图或客户生成物。
- 不要通过 `--api-key` 传递密钥；请使用环境变量。
- 向第三方 API 发送机密材料前，先审查提示词。
- 安全问题请按 [SECURITY.md](SECURITY.md) 私密报告，不要发到公开 Issue。

## 许可证

MIT。已审查的上游设计来源和精确版本列于 [ATTRIBUTIONS.md](ATTRIBUTIONS.md)。
