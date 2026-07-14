# Teste: Google Drive API → PostgreSQL

Ambiente local para testar **download**, **extração de planilhas para banco** e
**sincronização incremental** do Google Drive, usando sua própria conta.

---

## 🚀 Início rápido

Roteiro mínimo do zero ao primeiro uso. O passo a passo detalhado (incl. o setup
do Google Cloud) está em **[SETUP.md](SETUP.md)**.

```bash
# 1. Pré-requisitos: Python 3.10+, PostgreSQL e as credenciais do Google
#    (crie o projeto no Google Cloud e baixe o credentials.json - ver SETUP.md, Passo 2)

# 2. Ambiente Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# 3. Banco de dados
psql -U postgres -c "CREATE DATABASE drive_teste;"
copy .env.example .env              # depois edite o .env com a senha do PostgreSQL

# 4. Login no Google (abre o navegador uma vez)
python auth.py

# 5. Criar as tabelas
python db.py

# 6. Usar!
python drive_download.py list             # lista arquivos e mostra os FILE_IDs
python files_to_db.py extract <FILE_ID>   # guarda um arquivo no PostgreSQL
python files_to_db.py restore <FILE_ID>   # recupera o arquivo do banco para o disco
```

> Cada script rodado **sem argumentos** mostra sua própria ajuda de uso.
> Veja todos os comandos e exemplos na seção **[5. Rodar os testes](#5-rodar-os-testes)**.

---

## APIs usadas

| API | Para quê |
|-----|----------|
| **Google Drive API v3** | listar, baixar e exportar arquivos; detectar mudanças (Changes API) |
| **Google Sheets API v4** | ler células/linhas de planilhas de forma estruturada |
| **OAuth 2.0** | autorizar o acesso à sua conta |

---

## 1. Configurar o Google Cloud (uma vez)

1. Acesse <https://console.cloud.google.com> e crie um **projeto** (ex: `teste-drive`).
2. Menu **APIs e serviços → Biblioteca**. Ative:
   - **Google Drive API**
   - **Google Sheets API**
3. **APIs e serviços → Tela de consentimento OAuth**:
   - Tipo de usuário: **Externo** → Criar.
   - Preencha nome do app e email.
   - Em **Usuários de teste**, adicione o seu próprio email (`ti@inovconsultoria.com`).
     Sem isso o login é bloqueado enquanto o app está "em teste".
4. **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo de aplicativo: **App para computador (Desktop app)**.
   - Baixe o JSON e salve como **`credentials.json`** nesta pasta.

> Os escopos ficam em `config.py`. Começamos com **somente leitura**
> (`drive.readonly` + `spreadsheets.readonly`). Para *modificar/upload* depois,
> troque para `https://www.googleapis.com/auth/drive` e apague `token.json`.

## 2. Preparar o ambiente Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Configurar o PostgreSQL

Tenha um PostgreSQL rodando localmente e crie o banco:

```powershell
# exemplo (ajuste usuario/senha conforme sua instalacao)
psql -U postgres -c "CREATE DATABASE drive_teste;"
```

Copie `.env.example` para `.env` e preencha a senha do Postgres:

```powershell
Copy-Item .env.example .env
```

## 4. Primeiro login (autenticação)

```powershell
python auth.py
```

Abre o navegador para você autorizar. Ao concluir, cria `token.json`
e imprime o email autenticado.

---

## 5. Rodar os testes

### Baixar arquivos
```powershell
python drive_download.py list                       # 20 arquivos recentes
python drive_download.py list "name contains 'nota'"  # filtro
python drive_download.py download <FILE_ID>         # baixa (exporta Docs/Sheets p/ pdf/xlsx)
```

### Extrair planilha para o PostgreSQL
```powershell
python db.py                              # cria as tabelas
python sheets_to_db.py <SPREADSHEET_ID>   # le a 1a aba e grava em sheet_rows (JSONB)
```
O `<SPREADSHEET_ID>` é o trecho da URL da planilha:
`docs.google.com/spreadsheets/d/`**`SPREADSHEET_ID`**`/edit`

### Extrair arquivos (conteúdo binário → PostgreSQL)
Guarda os **bytes** do arquivo dentro do banco (tabela `file_contents`), com
metadados e hash SHA-256 para verificar integridade. Google Docs/Sheets/Slides
são exportados para PDF/XLSX antes de armazenar.
```powershell
python files_to_db.py extract <FILE_ID>   # extrai um arquivo para o banco
python files_to_db.py extract-all         # extrai todos (exceto pastas)
python files_to_db.py list                # lista o que já está guardado
python files_to_db.py restore <FILE_ID>   # puxa do banco p/ disco e confere o hash
```

### Sincronização incremental
```powershell
python sync.py init   # inventario inicial + guarda o ponto de partida
python sync.py run    # aplica só o que mudou desde a última vez
```

Consulte os dados:
```sql
SELECT name, mime_type, modified_time FROM drive_files ORDER BY modified_time DESC;
SELECT data FROM sheet_rows LIMIT 20;
```

---

## Estrutura

| Arquivo | Papel |
|---------|-------|
| `config.py` | lê o `.env` e define escopos OAuth |
| `auth.py` | fluxo OAuth 2.0; cria clientes Drive/Sheets |
| `db.py` | conexão + schema PostgreSQL + upserts |
| `drive_download.py` | listar e baixar/exportar arquivos |
| `sheets_to_db.py` | extrair planilha → tabela `sheet_rows` |
| `files_to_db.py` | extrair arquivos (bytes) → tabela `file_contents` + hash |
| `sync.py` | sincronização incremental via Changes API |

## Segurança
- `.env`, `credentials.json` e `token.json` estão no `.gitignore` — **nunca versione**.
- Escopos mínimos por padrão (somente leitura). Amplie só quando for testar escrita.
