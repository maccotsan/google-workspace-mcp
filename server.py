"""Google Workspace MCP Server - Sheets & Docs reader using OAuth."""

import io
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_DIR = Path(os.environ.get(
    "GOOGLE_CREDENTIALS_DIR",
    Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/claude-memory/google",
))
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

IMAGE_DIR = Path.home() / "Library/Caches/google-workspace-mcp"

mcp = FastMCP("google-workspace")


def get_credentials() -> Credentials:
    """Get valid OAuth credentials, refreshing or re-authenticating as needed."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from URL or return as-is."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_id)
    return match.group(1) if match else url_or_id


def extract_document_id(url_or_id: str) -> str:
    """Extract document ID from URL or return as-is."""
    match = re.search(r"/document/d/([a-zA-Z0-9-_]+)", url_or_id)
    return match.group(1) if match else url_or_id


def _extract_images(creds: Credentials, sid: str) -> list[Path]:
    """Download the xlsx export and extract embedded images. Always fetches fresh
    (no caching). Returns the list of extracted image paths, empty if the sheet
    has no embedded images.
    """
    if not creds.token:
        creds.refresh(Request())
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {creds.token}"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()

    out_dir = IMAGE_DIR / sid
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        media = [n for n in zf.namelist() if n.startswith("xl/media/")]
        for n in media:
            target = out_dir / Path(n).name
            with zf.open(n) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return sorted(out_dir.iterdir())


@mcp.tool()
def read_sheet(
    spreadsheet_id: str,
    range: str = "",
    sheet_name: str = "",
    include_images: bool = False,
) -> str:
    """Read data from a Google Spreadsheet.

    Args:
        spreadsheet_id: Spreadsheet URL or ID
        range: Cell range like "A1:Z100". If empty, reads entire sheet.
        sheet_name: Sheet/tab name. If empty, reads the first sheet.
        include_images: When True, downloads the spreadsheet as xlsx, extracts
            embedded images (those pasted on top of cells, not =IMAGE() URLs)
            to ~/Library/Caches/google-workspace-mcp/<fileId>/, and appends
            their paths to the response. Every True call performs a fresh
            download (no caching). Defaults to False — behavior is then
            identical to the original tool.
    """
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    sid = extract_spreadsheet_id(spreadsheet_id)

    if not range and not sheet_name:
        meta = service.spreadsheets().get(spreadsheetId=sid).execute()
        sheet_name = meta["sheets"][0]["properties"]["title"]

    full_range = f"'{sheet_name}'!{range}" if sheet_name and range else sheet_name or range

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=full_range)
        .execute()
    )
    rows = result.get("values", [])

    lines: list[str] = []
    if rows:
        for i, row in enumerate(rows):
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in row) + " |")
    else:
        lines.append("No data found.")

    if include_images:
        try:
            images = _extract_images(creds, sid)
        except Exception as e:
            lines.append(f"\n---\n(画像抽出に失敗: {type(e).__name__}: {e})")
            return "\n".join(lines)
        if images:
            lines.append(f"\n---\n画像 ({len(images)} 枚):")
            for p in images:
                lines.append(f"- {p}")
        else:
            lines.append("\n---\n画像なし")
    return "\n".join(lines)


@mcp.tool()
def filter_sheet(spreadsheet_id: str, keyword: str, column: str = "", sheet_name: str = "") -> str:
    """Search rows in a Google Spreadsheet by keyword. Returns header + matching rows.

    Args:
        spreadsheet_id: Spreadsheet URL or ID
        keyword: Search keyword (case-insensitive, partial match)
        column: Column letter to search in (e.g. "D"). If empty, searches all columns.
        sheet_name: Sheet/tab name. If empty, reads the first sheet.
    """
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)
    sid = extract_spreadsheet_id(spreadsheet_id)

    if not sheet_name:
        meta = service.spreadsheets().get(spreadsheetId=sid).execute()
        sheet_name = meta["sheets"][0]["properties"]["title"]

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=f"'{sheet_name}'")
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return "No data found."

    # Determine column index if specified
    col_idx = None
    if column:
        col_idx = 0
        for ch in column.upper():
            col_idx = col_idx * 26 + (ord(ch) - ord("A") + 1)
        col_idx -= 1  # 0-based

    keyword_lower = keyword.lower()
    matched = []
    for i, row in enumerate(rows):
        if i < 3:  # Keep header rows
            matched.append(row)
            continue
        if col_idx is not None:
            if col_idx < len(row) and keyword_lower in str(row[col_idx]).lower():
                matched.append(row)
        else:
            if any(keyword_lower in str(cell).lower() for cell in row):
                matched.append(row)

    if len(matched) <= 3:
        return f"No rows matching '{keyword}' found."

    lines = []
    for i, row in enumerate(matched):
        line = "| " + " | ".join(str(cell) for cell in row) + " |"
        lines.append(line)
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return f"Found {len(matched) - 3} matching row(s).\n\n" + "\n".join(lines)


@mcp.tool()
def list_sheets(spreadsheet_id: str) -> str:
    """List all sheet/tab names in a Google Spreadsheet.

    Args:
        spreadsheet_id: Spreadsheet URL or ID
    """
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)
    sid = extract_spreadsheet_id(spreadsheet_id)
    meta = service.spreadsheets().get(spreadsheetId=sid).execute()
    sheets = meta.get("sheets", [])
    lines = [f"- {s['properties']['title']} ({s['properties']['sheetId']})" for s in sheets]
    return "\n".join(lines)


@mcp.tool()
def read_document(document_id: str) -> str:
    """Read content from a Google Document.

    Args:
        document_id: Document URL or ID
    """
    creds = get_credentials()
    service = build("docs", "v1", credentials=creds)
    did = extract_document_id(document_id)
    doc = service.documents().get(documentId=did).execute()

    content = []
    for element in doc.get("body", {}).get("content", []):
        if "paragraph" in element:
            paragraph = element["paragraph"]
            text = ""
            for elem in paragraph.get("elements", []):
                if "textRun" in elem:
                    text += elem["textRun"]["content"]
            if text.strip():
                style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
                if style.startswith("HEADING_"):
                    level = int(style[-1])
                    text = "#" * level + " " + text.strip()
                content.append(text)
        elif "table" in element:
            table = element["table"]
            for row in table.get("tableRows", []):
                cells = []
                for cell in row.get("tableCells", []):
                    cell_text = ""
                    for p in cell.get("content", []):
                        if "paragraph" in p:
                            for elem in p["paragraph"].get("elements", []):
                                if "textRun" in elem:
                                    cell_text += elem["textRun"]["content"].strip()
                    cells.append(cell_text)
                content.append("| " + " | ".join(cells) + " |")

    return "\n".join(content) if content else "Empty document."


@mcp.tool()
def search_drive(query: str, max_results: int = 10) -> str:
    """Search Google Drive for files.

    Args:
        query: Search query (file name, content, etc.)
        max_results: Maximum number of results (default 10)
    """
    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)
    results = (
        service.files()
        .list(q=f"name contains '{query}'", pageSize=max_results, fields="files(id, name, mimeType, webViewLink)")
        .execute()
    )
    files = results.get("files", [])
    if not files:
        return "No files found."
    lines = []
    for f in files:
        mime = f.get("mimeType", "")
        type_label = "Sheet" if "spreadsheet" in mime else "Doc" if "document" in mime else "File"
        lines.append(f"- [{type_label}] {f['name']}\n  URL: {f.get('webViewLink', 'N/A')}\n  ID: {f['id']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
