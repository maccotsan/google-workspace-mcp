# Google Workspace MCP Server

Google Sheets / Docs / Drive を読み取るMCPサーバー（OAuth認証、読み取り専用）。

## セットアップ

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 認証情報

機密情報はリポジトリに含めず、環境変数 `GOOGLE_CREDENTIALS_DIR` で指定したディレクトリに配置する。

```
$GOOGLE_CREDENTIALS_DIR/
  client_secret.json   # GCP OAuth クライアントID
  token.json           # 認証済みトークン（自動生成）
```

デフォルトは `~/Library/Mobile Documents/com~apple~CloudDocs/claude-memory/google/`。

## 初回認証

```bash
.venv/bin/python3 -c "from server import get_credentials; get_credentials()"
```

ブラウザが開くのでGoogleアカウントでログインする。

## Claude Code に登録

```bash
claude mcp add -s user google-workspace .venv/bin/python3 server.py
```

## ツール

- `read_sheet` - スプレッドシート読み取り
- `list_sheets` - シート/タブ一覧
- `read_document` - Googleドキュメント読み取り
- `search_drive` - ドライブ検索
