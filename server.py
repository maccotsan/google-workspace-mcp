"""Google Workspace MCP Server - Sheets & Docs reader using OAuth."""

import os
import re
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


@mcp.tool()
def read_sheet(spreadsheet_id: str, range: str = "", sheet_name: str = "") -> str:
    """Read data from a Google Spreadsheet.

    Args:
        spreadsheet_id: Spreadsheet URL or ID
        range: Cell range like "A1:Z100". If empty, reads entire sheet.
        sheet_name: Sheet/tab name. If empty, reads the first sheet.
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
    if not rows:
        return "No data found."

    lines = []
    for i, row in enumerate(rows):
        line = "| " + " | ".join(str(cell) for cell in row) + " |"
        lines.append(line)
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


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
