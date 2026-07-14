"""Lista e baixa arquivos do Google Drive.

Uso:
    python drive_download.py list                 # lista os 20 arquivos mais recentes
    python drive_download.py list "name contains 'relatorio'"
    python drive_download.py download <FILE_ID>   # baixa um arquivo pelo id
"""
import io
import os
import sys

from googleapiclient.http import MediaIoBaseDownload

import config
from auth import drive_service

# Google Docs/Sheets/Slides sao "nativos" e precisam ser EXPORTADOS,
# nao podem ser baixados direto. Mapeamos para um formato de saida.
EXPORT_MAP = {
    "application/vnd.google-apps.document": (
        "application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": (
        "application/pdf", ".pdf"),
}


def list_files(query: str | None = None, page_size: int = 20):
    svc = drive_service()
    params = {
        "pageSize": page_size,
        "fields": "files(id, name, mimeType, modifiedTime, size)",
        "orderBy": "modifiedTime desc",
    }
    if query:
        params["q"] = query
    result = svc.files().list(**params).execute()
    files = result.get("files", [])
    for f in files:
        size = f.get("size", "-")
        print(f"{f['id']}  {f['mimeType']:<45}  {size:>10}  {f['name']}")
    return files


def download_file(file_id: str):
    svc = drive_service()
    meta = svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    name, mime = meta["name"], meta["mimeType"]

    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

    if mime in EXPORT_MAP:
        export_mime, ext = EXPORT_MAP[mime]
        request = svc.files().export_media(fileId=file_id, mimeType=export_mime)
        out_path = os.path.join(config.DOWNLOAD_DIR, name + ext)
    else:
        request = svc.files().get_media(fileId=file_id)
        out_path = os.path.join(config.DOWNLOAD_DIR, name)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"  baixando... {int(status.progress() * 100)}%")

    with open(out_path, "wb") as f:
        f.write(buffer.getvalue())
    print(f"Salvo em: {out_path}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        list_files(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "download":
        download_file(sys.argv[2])
    else:
        print(__doc__)
