# 画像生成スキル

[English](README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [Español](README.es.md)

[![validate](https://github.com/hjm-al/image-generation/actions/workflows/validate.yml/badge.svg)](https://github.com/hjm-al/image-generation/actions/workflows/validate.yml)

OpenAI 互換の Images API を通じて画像を生成・編集するための独立した Codex スキルです。プロンプトの準備、認証情報の安全な読み込み、レスポンスの正規化、ローカルファイルへの書き込み、形式の検出、寸法の取得、メタデータの記録を担当します。

## 機能

- `POST /images/generations` で画像を生成します。
- 公式の multipart または中継サービス形式の JSON で画像を編集します。
- 曖昧な形容詞を並べるのではなく、レイヤー化したスタイル規約からアートディレクションを構築します。
- 複数の参照画像に、順序付きの `Image 1`、`Image 2` などの役割を付けます。
- 元画像のハッシュ、形式、寸法、Alpha チャンネルの有無を記録します。
- マスクのサイズ、PNG Alpha チャンネルの意味、透明ピクセル、寸法を検証します。
- PNG Alpha チャンネルを、完全不透明、完全透明、部分的に透明、解析不能の四状態に分類します。
- JPEG 出力と `background=transparent` の組み合わせを、リクエスト前に拒否します。
- `b64_json`、`b64`、`url`、および一般的なネストされた画像フィールドを受け付けます。
- 各画像セットと JSON sidecar をまとめて公開し、既存ファイルを上書きしません。
- PNG、JPEG、WebP、GIF のシグネチャを検出し、実際の寸法を記録します。
- 同じレスポンス内の他の候補が壊れていても、有効な画像は保持します。
- JSONL ジョブを事前検証し、パスの競合を拒否し、各ジョブの後に復旧マニフェストを更新します。
- リクエストの詳細、ファイルハッシュ、納品時の警告、レスポンス構造を含む JSON sidecar を書き出します。
- コード化された品質イベント、プロンプトハッシュ、回帰チェックで再利用可能なプロンプト改訂を追跡します。
- ネットワークリクエストを行わずにオフラインテストを実行します。

## 要件

- Python 3.10 以降。
- サードパーティ製パッケージは不要です。ヘルパー、バッチランナー、品質ログ、テストは Python 標準ライブラリのみを使用します。
- ネットワークアクセスとプロバイダーの認証情報は、課金対象の生成または編集リクエストにのみ必要です。

## 費用とネットワーク動作

- `--dry-run` は計画したリクエストを表示するだけで、API キーの読み込み、ネットワーク利用、費用の発生はありません。
- テストスイートとすべての `quality_log.py` コマンドはオフラインです。
- `generate`、`edit`、および `--dry-run` なしのバッチは、設定したプロバイダーを呼び出し、費用が発生する場合があります。
- バッチの各項目は 1 回の API リクエストを行います。`n` はそのリクエスト内で要求する画像数です。ヘルパーが自動で再試行したりモデルを切り替えたりすることはありません。

## インストール

リポジトリをクローンしてから、Codex のスキルディレクトリへコピーします。

```powershell
git clone https://github.com/hjm-al/image-generation.git
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

Codex では `$image-generation` を指定して明示的に呼び出します。これはスキル参照であり、PowerShell の変数展開ではありません。Codex が説明から自動選択することもあります。

## 更新と削除

クローンしたリポジトリとインストール済みスキルを更新します。

```powershell
git -C .\image-generation pull --ff-only
$source = Join-Path $PWD "image-generation"
$target = Join-Path $HOME ".codex\skills\image-generation"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
```

この操作は現在のファイルをコピーしますが、上流で削除されたファイルは削除しません。クリーンインストールが必要な場合は、ローカルの変更を確認してバックアップしてから、インストール先ディレクトリを置き換えてください。スキルを削除するには次を実行します。

```powershell
$target = Join-Path $HOME ".codex\skills\image-generation"
Remove-Item -LiteralPath $target -Recurse -Force
```

## 設定

キーは現在のプロセス環境にのみ設定します。

```powershell
$env:IMAGE_API_KEY = "your-key"
$env:IMAGE_API_BASE_URL = "https://api.openai.com/v1"
$env:IMAGE_MODEL = "gpt-image-1"
```

対応する環境変数：

| 変数 | 必須 | 用途 |
|---|---:|---|
| `IMAGE_API_KEY` | はい | Bearer トークン、または `--api-key-env` で指定した変数 |
| `IMAGE_API_BASE_URL` | いいえ | API ルート。既定値は `https://api.openai.com/v1` |
| `IMAGE_MODEL` | いいえ | 既定モデル。フォールバックは `gpt-image-1` |

使用後はキーを削除します。

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

キーを読み込まず、ネットワークリクエストも行わずにリクエストをプレビューします。

```powershell
python .\scripts\image_api.py generate `
  --prompt "A minimal studio portrait with a warm gray background" `
  --output .\outputs\portrait.png `
  --dry-run
```

## アートディレクション

スタイルがブリーフの中心である場合は、主要な媒体を一つ定め、エッジ、レンダリング、表面、配色、光、構図、任意のグラフィックシステムを制御する観察可能な属性を指定します。画像から画像への編集では、保持する内容の規約とスタイル変更の規約を分けて記述します。

ガイドには写真、イラスト、印刷、ポスター、UI、3D、テクニカル、混合スタイルの方向性と、曖昧なスタイル語の置き換え例があります。[references/art-directions.md](references/art-directions.md) を参照してください。

## 編集

公式 multipart 転送：

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png
```

一部の互換中継サービスで使用される JSON 転送：

```powershell
python .\scripts\image_api.py edit `
  --image .\inputs\source.png `
  --image-role "product and framing reference" `
  --prompt "Keep the subject unchanged; replace the background with pale sand-colored plaster." `
  --output .\outputs\edited.png `
  --transport json
```

複数の参照画像を使う場合は、`--image` と `--image-role` を組にして繰り返します。役割の数は画像の数と一致している必要があります。multipart のマスクは 4 MB 以下で、最初の元画像と同じ寸法を持ち、実際の Alpha チャンネルを含み、少なくとも 1 つの透明ピクセルが必要です。PNG の `tRNS` メタデータは別途報告され、Alpha チャンネルとしては扱われません。

## バッチ処理

1 行に 1 ジョブを記述した JSONL ファイルを作成します。相対パスは JSONL ファイルのディレクトリを基準に解決されます。

```jsonl
{"id":"hero","prompt":"Editorial product photo of a steel kettle, side light, no text","output":"outputs/hero.png","output_format":"png","size":"1024x1536"}
{"id":"room-edit","operation":"edit","prompt":"Keep the product; replace the room with warm plaster","images":["inputs/source.png"],"image_roles":["product and framing reference"],"output":"outputs/room-edit.png","output_format":"png"}
```

API キーを読み込まず、ネットワークリクエストも行わずに事前検証します。

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --dry-run
```

ジョブ数とリクエスト計画を確認した後で実行します。

```powershell
python .\scripts\image_batch.py .\jobs.jsonl --manifest .\outputs\manifest.json
```

バッチジョブは順番に実行され、自動的な再試行やモデルの切り替えは行いません。失敗したジョブがあっても後続のジョブは停止しません。マニフェストは各項目の処理後にアトミックに更新されます。フィールドの完全な規約は [references/batch-jsonl.md](references/batch-jsonl.md) を参照してください。

## プロンプト品質ループ

このスキルは、再利用可能なプロンプト用にローカルの追記専用レビューログを保持できます。リクエストと納品の事実については API sidecar が引き続き正本です。品質イベントには主観的なレビューを記録します。成功した各イベントでは、良い特徴と `C1` から `C9` までの観察可能な欠陥を記録します。インフラストラクチャの障害には `C10` を使用し、プロンプト編集の根拠には決してしません。

正規化したプロンプトハッシュを生成します。

```powershell
python .\scripts\quality_log.py hash --prompt .\prompts\theme.txt
```

イベントと登録済みプロンプトバージョンを検証します。

```powershell
python .\scripts\quality_log.py validate `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --root .
```

欠陥を集計し、レビュー時期に達したか確認します。

```powershell
python .\scripts\quality_log.py digest --events .\quality\events.jsonl
python .\scripts\quality_log.py due `
  --events .\quality\events.jsonl `
  --versions .\quality\prompt-versions.json `
  --ledger .\quality\reviews.json
```

既定プロンプトを変更するのは、証拠が繰り返し現れた後だけです。同じテーマで同じ欠陥が 3 回以上発生した場合、または 2 つ以上のテーマで合計 4 回発生した場合に、共有テンプレートの変更を検討します。イベントスキーマ、バージョン登録、統制された比較ルール、レビュー台帳は [references/quality-loop.md](references/quality-loop.md) を参照してください。

品質ログのコマンドはすべてオフラインです。プロンプトバージョンの比較のために追加の画像生成を行う場合は課金が発生するため、リクエスト数を明示し、確認を得る必要があります。

## 出力規約

`outputs\result.png` に対して、ヘルパーは `outputs\result.png.json` も書き出します。sidecar には次が含まれます。

- エンドポイントとモデル
- 完全なプロンプト
- 秘密情報を含まないリクエストオプション
- 入力画像のパス、バイト数、SHA-256 ハッシュ、形式、寸法
- 最終画像のパス、バイト数、SHA-256 ハッシュ、形式、Alpha 検出結果、寸法
- Alpha 状態（`opaque`、`transparent`、`partial`、`unknown`、`chunk_only`、`none` のいずれか）
- 返却、公開、要求された画像数
- `delivery_ready`、`warnings`、候補ごとの `errors`
- レスポンスのフィールド名とタイムスタンプ

プロバイダーが要求と異なる形式を返した場合、ヘルパーは誤ったラベルのバイトを書き込む代わりに、出力拡張子を検出した形式へ変更します。

`delivery_ready` はプロバイダーの成功より厳格です。候補のいずれかが失敗した場合、画像数が `n` と異なる場合、要求した固定サイズを満たさない場合、透明背景に Alpha チャンネルがない場合、Alpha チャンネルが完全不透明の場合、または透明度を検証できない場合に false になります。画像ファイルと sidecar は先にステージングされ、セットとして公開されます。sidecar の書き込みに失敗した場合、画像が部分的に納品されることはありません。

## 互換性に関する注意

- 公式 OpenAI 編集エンドポイントは multipart フォームデータを使用します。
- 一部の中継サービスは `images[].image_url` で JSON 編集を実装しています。そのようなサービスに限り `--transport json` を使用してください。
- 署名付き画像 URL は API キーなしでダウンロードされます。プロバイダーが認証付きダウンロードを要求する場合は、base64 レスポンスを要求してください。
- プロバイダー固有のモデル名、サイズ、品質値、レスポンス形式はプロバイダーの責任です。

## 開発と検証

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

テストは外部サービスを呼び出さず、費用も発生しません。CI は Python 3.10 と 3.12 を確認します。開発手順と Pull Request の要件は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## コントリビューション

Issue と Pull Request のテンプレートを使用し、実際のプロバイダー確認を自動テストに含めず、Pull Request を作成する前に上記のオフライン検証コマンドを実行してください。参加時は [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) に従ってください。

## セキュリティ

- `.env`、API キー、非公開の参照画像、クライアントの生成物をコミットしないでください。
- `--api-key` で秘密情報を渡さないでください。環境変数を使用してください。
- 機密資料を第三者の API に送信する前に、プロンプトを確認してください。
- 脆弱性は公開 Issue ではなく [SECURITY.md](SECURITY.md) の手順で報告してください。

## ライセンス

MIT。確認済みの上流設計元と正確なリビジョンは [ATTRIBUTIONS.md](ATTRIBUTIONS.md) に記載されています。
