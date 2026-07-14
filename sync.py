"""Sincronizacao incremental do Drive usando a Changes API.

A primeira execucao pega um "startPageToken" (marco atual) e faz um
inventario inicial. As execucoes seguintes buscam APENAS o que mudou
desde a ultima vez - muito mais barato que relistar tudo.

Uso:
    python sync.py init     # inventario inicial + salva o token
    python sync.py run      # aplica as mudancas desde a ultima sincronizacao
"""
import sys

import db
from auth import drive_service

TOKEN_KEY = "drive_changes_page_token"
FIELDS = "id, name, mimeType, modifiedTime, size, trashed"


def initial_inventory():
    svc = drive_service()
    db.init_schema()

    # Marca o ponto de partida ANTES de listar, para nao perder mudancas.
    start = svc.changes().getStartPageToken().execute()["startPageToken"]

    page_token = None
    total = 0
    with db.get_conn() as conn, conn.cursor() as cur:
        while True:
            resp = svc.files().list(
                pageSize=100,
                fields=f"nextPageToken, files({FIELDS})",
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                db.upsert_file(cur, f)
                total += 1
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    db.set_sync_state(TOKEN_KEY, start)
    print(f"Inventario inicial: {total} arquivos. Token de sync salvo.")


def apply_changes():
    svc = drive_service()
    page_token = db.get_sync_state(TOKEN_KEY)
    if not page_token:
        print("Sem token. Rode 'python sync.py init' primeiro.")
        return

    changed = 0
    with db.get_conn() as conn, conn.cursor() as cur:
        while page_token:
            resp = svc.changes().list(
                pageToken=page_token,
                fields=f"newStartPageToken, nextPageToken, changes(removed, fileId, file({FIELDS}))",
            ).execute()

            for change in resp.get("changes", []):
                if change.get("removed"):
                    # NAO apagamos o dado migrado. Apenas sinalizamos que o
                    # arquivo saiu do Drive - o conteudo permanece no banco.
                    cur.execute(
                        "UPDATE drive_files SET removed_from_drive = TRUE, last_seen = now() "
                        "WHERE id = %s",
                        (change["fileId"],),
                    )
                    changed += 1
                    continue
                # Arquivos enviados para a lixeira chegam como um change normal
                # com file.trashed = TRUE; o upsert atualiza a flag e preserva tudo.
                f = change.get("file")
                if f:
                    db.upsert_file(cur, f)
                    changed += 1

            if "newStartPageToken" in resp:
                # Fim das mudancas: guarda o novo token para a proxima rodada.
                db.set_sync_state(TOKEN_KEY, resp["newStartPageToken"])
                break
            page_token = resp.get("nextPageToken")

    print(f"Sincronizacao concluida: {changed} mudanca(s) aplicada(s).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "init":
        initial_inventory()
    elif cmd == "run":
        apply_changes()
    else:
        print(__doc__)
