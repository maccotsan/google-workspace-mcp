# Google Workspace MCP Server

Google Sheets / Docs / Drive を読み取るMCPサーバー（OAuth認証、読み取り専用）。

## ツール

- `read_sheet` - スプレッドシート読み取り
- `filter_sheet` - キーワードでシート内行検索
- `list_sheets` - シート/タブ一覧
- `read_document` - Googleドキュメント読み取り
- `search_drive` - ドライブ検索

## 新規セットアップ（初めて導入する場合）

### 1. GCPプロジェクト作成

1. [console.cloud.google.com](https://console.cloud.google.com) にGoogleアカウントでログイン
2. プロジェクトを作成（名前は任意、組織は「組織なし」でOK）
3. 「APIとサービス」→「ライブラリ」から以下を有効化：
   - Google Sheets API
   - Google Docs API
   - Google Drive API

※ これらのAPIは無料。課金設定・クレジットカード登録は不要。

### 2. OAuth同意画面の設定

1. 「APIとサービス」→「OAuth同意画面」
2. ユーザータイプ: 外部 → 作成
3. アプリ名: 任意（例: `google-workspace-mcp`）
4. ユーザーサポートメール / デベロッパー連絡先: 自分のメールアドレス
5. スコープは追加不要 → 保存して続行
6. テストユーザーに**自分のGoogleアカウント**を追加 → 保存

### 3. OAuthクライアントIDの作成

1. 「APIとサービス」→「認証情報」→「＋認証情報を作成」→「OAuthクライアントID」
2. アプリケーションの種類: **デスクトップアプリ**
3. 名前: 任意 → 作成
4. JSONをダウンロード → `client_secret.json` としてリネーム

### 4. リポジトリのクローンと依存パッケージのインストール

```bash
git clone git@github.com:maccotsan/google-workspace-mcp.git ~/.claude/mcp-servers/google-workspace
cd ~/.claude/mcp-servers/google-workspace
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 5. 認証情報の配置

`client_secret.json` を任意のディレクトリに配置し、環境変数で指定する。

```bash
# 例: ~/.config/google/ に配置する場合
mkdir -p ~/.config/google
mv ~/Downloads/client_secret.json ~/.config/google/
```

デフォルトの認証情報ディレクトリは `~/Library/Mobile Documents/com~apple~CloudDocs/claude-memory/google/`（macOS iCloud）。
変更する場合は Claude Code の MCP 設定で環境変数 `GOOGLE_CREDENTIALS_DIR` を指定する。

### 6. 初回認証

```bash
# GOOGLE_CREDENTIALS_DIR がデフォルトでない場合は指定する
export GOOGLE_CREDENTIALS_DIR=~/.config/google
.venv/bin/python3 -c "from server import get_credentials; get_credentials()"
```

ブラウザが開くのでGoogleアカウントでログインし、アクセスを許可する。
「このアプリは Google で確認されていません」と表示されるが、自分で作成したアプリなので「続行」で問題ない。

認証成功すると `$GOOGLE_CREDENTIALS_DIR/token.json` が自動生成される。

### 7. Claude Code に登録

```bash
# GOOGLE_CREDENTIALS_DIR がデフォルトの場合
claude mcp add -s user google-workspace -- ~/.claude/mcp-servers/google-workspace/.venv/bin/python3 ~/.claude/mcp-servers/google-workspace/server.py

# GOOGLE_CREDENTIALS_DIR を変更する場合
claude mcp add -s user google-workspace -e GOOGLE_CREDENTIALS_DIR=~/.config/google -- ~/.claude/mcp-servers/google-workspace/.venv/bin/python3 ~/.claude/mcp-servers/google-workspace/server.py
```

Claude Code を再起動すると使えるようになる。

## 認証情報

機密情報はリポジトリに含めず、環境変数 `GOOGLE_CREDENTIALS_DIR` で指定したディレクトリに配置する。

```
$GOOGLE_CREDENTIALS_DIR/
  client_secret.json   # GCP OAuthクライアントID（手動配置）
  token.json           # 認証済みトークン（自動生成・自動更新）
```

## iCloudを共有している別Macでの導入

同じApple IDでiCloudを同期している場合、GCPプロジェクト作成・OAuth設定・初回認証は不要。
`client_secret.json` と `token.json` がiCloud経由で自動同期されるため、リポジトリのクローンとClaude Codeへの登録のみ行う。

```bash
# 1. リポジトリのクローンと依存パッケージのインストール
git clone git@github.com:maccotsan/google-workspace-mcp.git ~/.claude/mcp-servers/google-workspace
cd ~/.claude/mcp-servers/google-workspace
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Claude Code に登録（デフォルトでiCloudの認証情報を参照する）
claude mcp add -s user google-workspace -- ~/.claude/mcp-servers/google-workspace/.venv/bin/python3 ~/.claude/mcp-servers/google-workspace/server.py
```

Claude Code を再起動すれば使える。

## 再認証（トークンが無効化された場合）

`invalid_grant: Bad Request` 等のエラーでAPI呼び出しが失敗する場合、`reauth.sh` を実行する。

```bash
~/.claude/mcp-servers/google-workspace/reauth.sh
```

ブラウザが開くのでGoogleアカウントでログインし、アクセスを許可する。認証完了後、Claude Code を再起動すれば使えるようになる。

`GOOGLE_CREDENTIALS_DIR` をデフォルトから変更している場合は、環境変数を設定してから実行する。

```bash
GOOGLE_CREDENTIALS_DIR=~/.config/google ~/.claude/mcp-servers/google-workspace/reauth.sh
```

## 別のGoogleアカウントを追加する場合

1. GCPコンソール →「OAuth同意画面」→ テストユーザーにそのアカウントを追加
2. `token.json` を削除
3. 初回認証を再実行（ブラウザで新しいアカウントでログイン）
