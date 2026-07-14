"""Carrega configuracoes do .env em um unico lugar."""
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL
PG_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5432"),
    "dbname": os.getenv("PGDATABASE", "drive_teste"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
}

# Google
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

# Escopos: comece com o minimo necessario.
#   drive.readonly  -> listar/baixar (nao permite modificar)
#   drive           -> acesso total (necessario para modificar/upload)
#   spreadsheets.readonly -> ler planilhas via Sheets API
# Se voce mudar os escopos, apague token.json para reautenticar.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
