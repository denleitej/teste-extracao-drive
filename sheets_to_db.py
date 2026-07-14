"""Extrai dados de uma Google Sheet e grava no PostgreSQL.

Le a primeira aba, usa a primeira linha como cabecalho e grava
cada linha como um JSONB na tabela sheet_rows.

Uso:
    python sheets_to_db.py <SPREADSHEET_ID> [NomeDaAba]
"""
import json
import sys

import psycopg2.extras

import db
from auth import drive_service, sheets_service


def _file_meta(spreadsheet_id: str) -> dict:
    svc = drive_service()
    return svc.files().get(
        fileId=spreadsheet_id,
        fields="id, name, mimeType, modifiedTime, size, trashed",
    ).execute()


def extract_sheet(spreadsheet_id: str, sheet_name: str | None = None):
    sheets = sheets_service()

    # Descobre o nome da aba se nao foi passado.
    if not sheet_name:
        info = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_name = info["sheets"][0]["properties"]["title"]

    resp = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=sheet_name
    ).execute()
    values = resp.get("values", [])
    if not values:
        print("Planilha vazia.")
        return

    header = values[0]
    rows = values[1:]

    db.init_schema()
    meta = _file_meta(spreadsheet_id)

    with db.get_conn() as conn, conn.cursor() as cur:
        db.upsert_file(cur, meta)
        for i, row in enumerate(rows):
            # Alinha a linha ao cabecalho (preenche faltantes com None).
            record = {header[j]: (row[j] if j < len(row) else None)
                      for j in range(len(header))}
            cur.execute(
                """
                INSERT INTO sheet_rows (file_id, sheet_name, row_index, data)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (file_id, sheet_name, row_index)
                DO UPDATE SET data = EXCLUDED.data;
                """,
                (spreadsheet_id, sheet_name, i, json.dumps(record, ensure_ascii=False)),
            )

    print(f"Gravadas {len(rows)} linhas da aba '{sheet_name}' no PostgreSQL.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sheet = sys.argv[2] if len(sys.argv) > 2 else None
    extract_sheet(sys.argv[1], sheet)
