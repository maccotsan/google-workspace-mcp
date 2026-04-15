#!/bin/bash
# Google Workspace MCP 再認証スクリプト
# invalid_grant 等でトークンが失効した場合に実行する

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDENTIALS_DIR="${GOOGLE_CREDENTIALS_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-memory/google}"

echo "既存のtoken.jsonを削除: $CREDENTIALS_DIR/token.json"
rm -f "$CREDENTIALS_DIR/token.json"

echo "再認証を開始します（ブラウザが開きます）..."
cd "$SCRIPT_DIR"
.venv/bin/python3 -c "from server import get_credentials; get_credentials()"

echo ""
echo "再認証完了。Claude Code を再起動してください。"
