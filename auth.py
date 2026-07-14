"""Autenticacao OAuth 2.0 com a sua conta Google.

No primeiro uso abre o navegador para voce autorizar o app.
O token fica salvo em token.json e e renovado automaticamente depois.
"""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists(config.TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.SCOPES)

    # Se nao ha credencial valida, faz o fluxo de login.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Arquivo '{config.CREDENTIALS_FILE}' nao encontrado. "
                    "Baixe o OAuth client (Desktop app) do Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CREDENTIALS_FILE, config.SCOPES
            )
            # Abre servidor local temporario para receber o callback do OAuth.
            creds = flow.run_local_server(port=0)

        with open(config.TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


def drive_service():
    """Cliente da Drive API v3."""
    return build("drive", "v3", credentials=get_credentials())


def sheets_service():
    """Cliente da Sheets API v4."""
    return build("sheets", "v4", credentials=get_credentials())


if __name__ == "__main__":
    # Teste rapido de login.
    svc = drive_service()
    about = svc.about().get(fields="user").execute()
    print("Autenticado como:", about["user"]["emailAddress"])
