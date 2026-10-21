# 圖片生成技能

[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Español](README.es.md)

一個獨立的 Codex 技能，透過相容於 OpenAI 的 Images API 生成與編輯圖片。它負責提示詞準備、金鑰安全載入、回應標準化、本機檔案寫入、格式偵測、尺寸讀取和詮釋資料記錄。

## 功能

- 透過 `POST /images/generations` 生成圖片。
- 透過官方 multipart 或中轉服務常用的 JSON 方式編輯圖片。
- 使用分層風格約定建立藝術方向，而不是堆疊模糊形容詞。
- 以有序的 `Image 1`、`Image 2` 等角色標註多張參考圖。
- 記錄來源圖片雜湊、格式、尺寸和 Alpha 通道狀態。
- 驗證遮罩大小、PNG Alpha 通道語意、透明像素和尺寸。
- 區分完全不透明、完全透明、部分透明和無法解析的 PNG Alpha 通道。
- 在發起請求前拒絕同時使用 JPEG 輸出和 `background=transparent`。
- 接受 `b64_json`、`b64`、`url` 及常見的巢狀圖片欄位。
- 將每組圖片和 JSON sidecar 作為一個集合發布，不覆寫既有檔案。
- 偵測 PNG、JPEG、WebP 和 GIF 檔案簽章，並記錄真實尺寸。
- 同一回應中的其他候選損壞時，保留仍然有效的圖片。
- 預檢 JSONL 任務，拒絕路徑衝突，並在每個任務後更新復原清單。
- 寫出包含請求詳情、檔案雜湊、交付警告和回應結構的 JSON sidecar。
- 透過編碼品質事件、提示詞雜湊和回歸檢查追蹤可重複使用的提示詞版本。
- 執行離線測試，不發起網路請求。

## 安裝

複製倉庫後，將其複製到 Codex 技能目錄：

```powershell
git clone https://github.com/hjm-al/image-generation.git
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

在 Codex 中可使用 `$image-generation` 明確呼叫；這是技能參照，不是 PowerShell 變數展開。Codex 也可以根據描述自動選擇此技能。

## 設定

僅在目前處理序環境中設定金鑰：

```powershell
$env:IMAGE_API_KEY = "your-key"
$env:IMAGE_API_BASE_URL = "https://api.openai.com/v1"
$env:IMAGE_MODEL = "gpt-image-1"
```

支援的環境變數：

| 變數 | 必需 | 用途 |
|---|---:|---|
| `IMAGE_API_KEY` | 是 | Bearer Token，或 `--api-key-env` 指定的變數 |
| `IMAGE_API_BASE_URL` | 否 | API 根位址，預設 `https://api.openai.com/v1` |
| `IMAGE_MODEL` | 否 | 預設模型，回退值為 `gpt-image-1` |

使用後移除金鑰：

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

在不讀取金鑰、也不發起網路請求的情況下預覽請求：

```powershell
python .\scripts\image_api.py generate `
  --prompt "A minimal studio portrait with a warm gray background" `
  --output .\outputs\portrait.png `
  --dry-run
```

## 藝術方向

當風格是簡報的核心時，應定義一個主要媒介，並說明邊緣、渲染、表面、配色、光線、構圖和可選圖形系統的可觀察屬性。對於圖生圖，應把內容保留約定與風格改寫約定分開。

指南涵蓋攝影、插畫、印刷、海報、UI、3D、技術圖和混合風格，並提供模糊風格詞的替換方法。參見 [references/art-directions.md](references/art-directions.md)。

## 編輯

官方 multipart 傳輸：

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png
```

部分相容中轉服務使用的 JSON 傳輸：

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png `
  --transport json
```

多參考圖使用時，成對重複 `--image` 和 `--image-role`。角色數量必須與圖片數量一致。Multipart 遮罩必須不超過 4 MB、與第一張來源圖片尺寸一致、包含真實 Alpha 通道，並至少有一個透明像素。PNG 的 `tRNS` 詮釋資料會單獨報告，不會被當作 Alpha 通道。

## 批次處理

建立每行一個任務的 JSONL 檔案。相對路徑以 JSONL 檔案所在目錄為基準：

```jsonl
{"id":"hero","prompt":"Editorial product photo of a steel kettle, side light, no text","output":"outputs/hero.png","output_format":"png","size":"1024x1536"}
{"id":"room-edit","operation":"edit","prompt":"Keep the product; replace the room with warm plaster","images":["inputs/source.png"],"image_roles":["product and framing reference"],"output":"outputs/room-edit.png","output_format":"png"}
```

在不讀取 API Key、也不發起網路請求的情況下預檢：

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --dry-run
```

確認任務數量和請求計畫後執行：

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --manifest .\outputs\manifest.json
```

批次任務依序執行，不會自動重試或切換模型。單一任務失敗不會阻止後續任務。清單會在每個項目處理完成後原子更新。完整欄位約定參見 [references/batch-jsonl.md](references/batch-jsonl.md)。

## 提示詞品質循環

此技能可為可重複使用的提示詞維護本機、僅追加的審查日誌。API sidecar 仍是請求和交付事實的來源；品質事件記錄主觀審查。每個成功事件都應記錄優點和 `C1` 至 `C9` 中可觀察的缺陷。基礎設施故障使用 `C10`，而且永遠不會成為提示詞編輯依據。

產生標準化提示詞雜湊：

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\theme.txt
```

驗證事件和已登記提示詞版本：

```powershell
python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .
```

彙總缺陷並檢查是否到期需要審查：

```powershell
python .\scripts\quality_log.py digest --events .\quality\events.jsonl
python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

只有重複出現證據後，才修改預設提示詞：同一主題中同一缺陷至少出現 3 次，或在至少 2 個主題中累計出現 4 次，才考慮修改共用模板。事件結構、版本登記、受控比較規則和審查台帳參見 [references/quality-loop.md](references/quality-loop.md)。

所有品質日誌命令均為離線操作。為比較提示詞版本而額外生成圖片會產生費用，必須說明請求數量並取得確認。

## 輸出約定

對於 `outputs\result.png`，腳本還會寫入 `outputs\result.png.json`。Sidecar 包含：

- 端點與模型；
- 完整提示詞；
- 不含金鑰的請求選項；
- 輸入圖片路徑、位元組數、SHA-256 雜湊、格式和尺寸；
- 最終圖片路徑、位元組數、SHA-256 雜湊、格式、Alpha 偵測結果和尺寸；
- Alpha 狀態（`opaque`、`transparent`、`partial`、`unknown`、`chunk_only` 或 `none`）；
- 傳回、發布和請求的圖片數量；
- `delivery_ready`、`warnings` 和每個候選的錯誤；
- 回應欄位名稱和時間戳記。

如果服務商傳回的實際格式與請求不同，腳本會把輸出副檔名改為偵測到的格式，不會寫入副檔名錯誤的位元組。

`delivery_ready` 比服務商傳回成功更嚴格：只要任一候選失敗、圖片數量與 `n` 不一致、請求的固定尺寸未滿足、透明背景沒有 Alpha 通道、Alpha 通道完全不透明或透明度無法驗證，就會變成 false。圖片檔案和 sidecar 會先暫存，再作為一個集合發布；sidecar 失敗時不會留下部分圖片交付。

## 相容性說明

- 官方 OpenAI 編輯端點使用 multipart 表單資料。
- 一些中轉服務使用 `images[].image_url` 實作 JSON 編輯；僅對這類服務使用 `--transport json`。
- 簽章圖片 URL 下載時不帶 API Key。如果服務商要求鑑權下載，應改用 base64 回應。
- 服務商特定的模型名稱、尺寸、品質值和回應格式由服務商負責。

## 測試

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

測試不會呼叫外部服務，也不會產生費用。

## 安全

- 不要提交 `.env`、API 金鑰、私有參考圖或客戶生成物。
- 不要透過 `--api-key` 傳遞金鑰；請使用環境變數。
- 向第三方 API 傳送機密材料前，先審查提示詞。

## 授權條款

MIT。已審查的上游設計來源和精確版本列於 [ATTRIBUTIONS.md](ATTRIBUTIONS.md)。
