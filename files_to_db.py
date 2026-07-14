"""Extrai ARQUIVOS do Google Drive e guarda o conteudo no PostgreSQL.

Os bytes de cada arquivo ficam DENTRO do banco (tabela file_contents),
junto com metadados e um hash SHA-256 para verificar integridade.

Google Docs/Sheets/Slides sao nativos e nao podem ser baixados direto:
sao EXPORTADOS para um formato concreto (pdf/xlsx) antes de armazenar.

Uso:
    python files_to_db.py extract <FILE_ID>     # extrai um arquivo para o banco
    python files_to_db.py extract-all           # extrai todos os arquivos (nao-pastas)
    python files_to_db.py list                  # lista o que ja esta guardado no banco
    python files_to_db.py restore <FILE_ID> [pasta]   # puxa o arquivo do banco p/ disco e confere o hash
"""
import hashlib
import io
import os
import re
import sys

from googleapiclient.http import MediaIoBaseDownload

import config
import db
from auth import drive_service

# Tipos nativos do Google -> (mime de exportacao, extensao)
EXPORT_MAP = {
    "application/vnd.google-apps.document": (
        "application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": (
        "application/pdf", ".pdf"),
}
FOLDER_MIME = "application/vnd.google-apps.folder"


def _fetch_bytes(svc, file_id: str, mime: str, name: str):
    """Baixa (ou exporta) um arquivo e devolve (bytes, nome_armazenado, mime_armazenado)."""
    if mime in EXPORT_MAP:
        export_mime, ext = EXPORT_MAP[mime]
        request = svc.files().export_media(fileId=file_id, mimeType=export_mime)
        stored_name = name + ext
        stored_mime = export_mime
    else:
        request = svc.files().get_media(fileId=file_id)
        stored_name = name
        stored_mime = mime

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue(), stored_name, stored_mime


def extract_one(file_id: str):
    svc = drive_service()
    meta = svc.files().get(
        fileId=file_id,
        fields="id, name, mimeType, modifiedTime, size, trashed",
    ).execute()

    if meta["mimeType"] == FOLDER_MIME:
        print(f"'{meta['name']}' e uma pasta - ignorado.")
        return

    content, stored_name, stored_mime = _fetch_bytes(
        svc, file_id, meta["mimeType"], meta["name"])
    sha = hashlib.sha256(content).hexdigest()

    db.init_schema()
    with db.get_conn() as conn, conn.cursor() as cur:
        db.upsert_file(cur, meta)
        db.upsert_file_content(cur, file_id, stored_name, stored_mime, content, sha)

    print(f"OK  {stored_name}  ({len(content)} bytes)  sha256={sha[:12]}...")


def extract_all():
    svc = drive_service()
    db.init_schema()
    page_token = None
    total = 0
    while True:
        resp = svc.files().list(
            pageSize=100,
            q=f"mimeType != '{FOLDER_MIME}' and trashed = false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            try:
                extract_one(f["id"])
                total += 1
            except Exception as e:
                print(f"FALHA em '{f['name']}': {e}")
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    print(f"\nConcluido: {total} arquivo(s) armazenado(s) no PostgreSQL.")


def list_stored():
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT fc.stored_name, fc.content_type, fc.byte_size,
                   fc.sha256, fc.extracted_at
            FROM file_contents fc
            ORDER BY fc.extracted_at DESC;
            """
        )
        rows = cur.fetchall()
    if not rows:
        print("Nenhum arquivo armazenado ainda.")
        return
    print(f"{'TAMANHO':>10}  {'SHA256':<14}  NOME")
    for name, ctype, size, sha, _ in rows:
        print(f"{size:>10}  {sha[:12]}..  {name}")
    print(f"\nTotal: {len(rows)} arquivo(s).")


# Caracteres proibidos em nomes de arquivo no Windows: < > : " / \ | ? *
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def _safe_filename(name: str) -> str:
    """Troca caracteres invalidos no Windows por '_' para gravar em disco.

    Ex: 'Anotacoes: ClickUP.pdf' -> 'Anotacoes_ ClickUP.pdf'
    (o nome ORIGINAL continua preservado no banco, isto e so para o disco).
    """
    safe = _INVALID_CHARS.sub("_", name)
    return safe.strip().rstrip(".") or "arquivo"


def restore(file_id: str, out_dir: str | None = None):
    """Puxa o arquivo do banco de volta para o disco e confere o hash."""
    out_dir = out_dir or config.DOWNLOAD_DIR
    os.makedirs(out_dir, exist_ok=True)
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT stored_name, content, sha256 FROM file_contents WHERE file_id = %s",
            (file_id,),
        )
        row = cur.fetchone()
    if not row:
        print(f"Nada guardado para o id {file_id}.")
        return
    stored_name, content, sha = row
    content = bytes(content)  # memoryview -> bytes

    out_path = os.path.join(out_dir, _safe_filename(stored_name))
    with open(out_path, "wb") as f:
        f.write(content)

    # Verificacao honesta: releia o arquivo GRAVADO no disco e confira o hash.
    with open(out_path, "rb") as f:
        disk_bytes = f.read()
    recomputed = hashlib.sha256(disk_bytes).hexdigest()
    ok = "OK - integro" if recomputed == sha else "FALHA - hash divergente!"
    print(f"Restaurado em: {out_path}  ({len(disk_bytes)} bytes)")
    print(f"Verificacao de integridade: {ok}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "extract" and len(sys.argv) > 2:
        extract_one(sys.argv[2])
    elif cmd == "extract-all":
        extract_all()
    elif cmd == "list":
        list_stored()
    elif cmd == "restore" and len(sys.argv) > 2:
        restore(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        print(__doc__)
