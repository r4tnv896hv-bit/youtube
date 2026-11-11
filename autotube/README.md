# autotube — 「30秒サイエンス」自動投稿パイプライン

科学の雑学 Shorts(縦 1080x1920・約25秒)を **毎日 18:07 (JST) に 1 本**、GitHub Actions が自動で生成して YouTube に投稿します。

```
episodes.json  →  make_video.py (音声合成 + 字幕カード + ffmpeg)  →  upload.py (YouTube Data API)  →  published.json
```

| ファイル | 役割 |
| --- | --- |
| `episodes.json` | 台本キュー。上から順に 1 日 1 本消化 |
| `published.json` | 投稿済みの記録(ワークフローが自動コミット) |
| `make_video.py` | 動画生成。音声は VOICEVOX(ずんだもん)、落ちていれば Open JTalk |
| `upload.py` | YouTube へのアップロード |
| `run.py` | 上記をつなぐエントリポイント |
| `get_refresh_token.py` | 初回だけ手元の PC で実行する認証ヘルパー |
| `../.github/workflows/daily-short.yml` | 毎日の定期実行 |

## 初回セットアップ(人間の操作が必要な部分)

Google アカウントの本人確認と API の同意は代行できないため、ここだけ手作業です。

1. **チャンネルを作る** — YouTube にログインし、チャンネルを作成(名前の例: 「30秒サイエンス」)。
2. **API を有効化** — [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作り、「YouTube Data API v3」を有効化。
3. **OAuth 同意画面** — User type「外部」で作成し、**公開ステータスを「本番環境」にする**(「テスト」のままだとトークンが 7 日で失効します)。
4. **OAuth クライアント** — 種類「デスクトップアプリ」で作成し、クライアント ID とシークレットを控える。
5. **リフレッシュトークン取得** — 手元の PC で `python autotube/get_refresh_token.py` を実行し、チャンネルの持ち主のアカウントでログイン。
6. **Secrets 登録** — リポジトリの Settings → Secrets and variables → Actions に
   `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN` を登録。
7. **このブランチをデフォルトブランチにマージ** — 定期実行(schedule)はデフォルトブランチ上のワークフローでしか動きません。

Secrets が未設定の間は、動画を生成して Actions の Artifacts に保存するだけで、投稿も消化もしません。

## 知っておくべき制約

- **未監査の API プロジェクトからの投稿は「非公開」に固定されます。** YouTube の仕様で、2020/7/28 以降に作られた API プロジェクトは
  [コンプライアンス監査](https://support.google.com/youtube/contact/yt_api_form)に通るまで、API 経由の動画が非公開にロックされます。
  監査が通るまでは、Artifacts の mp4 を YouTube Studio から手動で上げるか、監査を申請してください。
- **収益化** — テンプレート的な量産動画は YouTube パートナープログラムの「量産型/繰り返しの多いコンテンツ」に該当し、収益化審査で落ちる可能性があります。
- **音声クレジット** — VOICEVOX 使用時は説明欄に「VOICEVOX:ずんだもん」を自動で記載します(利用規約上必須)。
- 公開範囲を変えたい場合はリポジトリ変数 `YT_PRIVACY` に `private` / `unlisted` / `public` を設定(既定は `public`)。

## 台本の追加

`episodes.json` の末尾に追記するだけです。残り 5 本以下になるとワークフローが警告を出します。

```json
{"id": "031", "hook": "最初に出す一言(タイトルにもなる)", "lines": ["1文ずつ。", "4文前後が目安。"], "tags": ["タグ"]}
```

事実関係は必ず確認してから追加してください。

## ローカルで試す

```bash
sudo apt-get install -y ffmpeg fonts-noto-cjk
pip install -r autotube/requirements.txt
cd autotube && python run.py     # out/<id>.mp4 ができる(Secrets なしなら投稿しない)
```
