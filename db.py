"""Conexao e schema do PostgreSQL para o teste."""
import contextlib

import psycopg2
import psycopg2.extras

import config


@contextlib.contextmanager
def get_conn():
    conn = psycopg2.connect(**config.PG_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema():
    """Cria as tabelas do teste (idempotente)."""
    ddl = """
    -- Metadados dos arquivos vistos no Drive.
    -- trashed / removed_from_drive: sinalizam remocao SEM apagar o dado migrado.
    --   trashed            -> arquivo foi para a lixeira no Drive
    --   removed_from_drive -> arquivo saiu de vez (excluido/perdeu acesso)
    CREATE TABLE IF NOT EXISTS drive_files (
        id                 TEXT PRIMARY KEY,
        name               TEXT,
        mime_type          TEXT,
        modified_time      TIMESTAMPTZ,
        size_bytes         BIGINT,
        trashed            BOOLEAN DEFAULT FALSE,
        removed_from_drive BOOLEAN DEFAULT FALSE,
        last_seen          TIMESTAMPTZ DEFAULT now()
    );
    -- Para bancos criados antes desta coluna existir (idempotente):
    ALTER TABLE drive_files ADD COLUMN IF NOT EXISTS removed_from_drive BOOLEAN DEFAULT FALSE;

    -- Dados extraidos de planilhas (exemplo generico chave/valor por linha)
    CREATE TABLE IF NOT EXISTS sheet_rows (
        id          BIGSERIAL PRIMARY KEY,
        file_id     TEXT REFERENCES drive_files(id) ON DELETE CASCADE,
        sheet_name  TEXT,
        row_index   INT,
        data        JSONB,
        UNIQUE (file_id, sheet_name, row_index)
    );

    -- Conteudo binario dos arquivos baixados/exportados do Drive.
    -- Os bytes ficam DENTRO do banco (armazenamento estruturado e seguro).
    -- sha256 permite verificar integridade (round-trip).
    CREATE TABLE IF NOT EXISTS file_contents (
        file_id      TEXT PRIMARY KEY REFERENCES drive_files(id) ON DELETE CASCADE,
        stored_name  TEXT,        -- nome final (com extensao apos export, se aplicavel)
        content_type TEXT,        -- mime realmente armazenado
        content      BYTEA,       -- os bytes do arquivo
        byte_size    BIGINT,
        sha256       TEXT,
        extracted_at TIMESTAMPTZ DEFAULT now()
    );

    -- Guarda o token de sincronizacao da Changes API do Drive
    CREATE TABLE IF NOT EXISTS sync_state (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(ddl)
    print("Schema criado/atualizado com sucesso.")


def upsert_file(cur, f: dict):
    """Insere ou atualiza um arquivo do Drive."""
    size = f.get("size")
    cur.execute(
        """
        INSERT INTO drive_files (id, name, mime_type, modified_time, size_bytes, trashed, last_seen)
        VALUES (%(id)s, %(name)s, %(mimeType)s, %(modifiedTime)s, %(size)s, %(trashed)s, now())
        ON CONFLICT (id) DO UPDATE SET
            name          = EXCLUDED.name,
            mime_type     = EXCLUDED.mime_type,
            modified_time = EXCLUDED.modified_time,
            size_bytes    = EXCLUDED.size_bytes,
            trashed       = EXCLUDED.trashed,
            last_seen     = now();
        """,
        {
            "id": f["id"],
            "name": f.get("name"),
            "mimeType": f.get("mimeType"),
            "modifiedTime": f.get("modifiedTime"),
            "size": int(size) if size else None,
            "trashed": f.get("trashed", False),
        },
    )


def upsert_file_content(cur, file_id: str, stored_name: str,
                        content_type: str, content: bytes, sha256: str):
    """Grava (ou atualiza) os bytes de um arquivo no banco."""
    cur.execute(
        """
        INSERT INTO file_contents
            (file_id, stored_name, content_type, content, byte_size, sha256, extracted_at)
        VALUES (%s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (file_id) DO UPDATE SET
            stored_name  = EXCLUDED.stored_name,
            content_type = EXCLUDED.content_type,
            content      = EXCLUDED.content,
            byte_size    = EXCLUDED.byte_size,
            sha256       = EXCLUDED.sha256,
            extracted_at = now();
        """,
        (file_id, stored_name, content_type,
         psycopg2.Binary(content), len(content), sha256),
    )


def get_sync_state(key: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT value FROM sync_state WHERE key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else None


def set_sync_state(key: str, value: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_state (key, value, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
            """,
            (key, value),
        )


if __name__ == "__main__":
    init_schema()
