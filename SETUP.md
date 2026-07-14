# Guia de Setup — como rodar este projeto na sua máquina

Este guia é para quem clonou o repositório e quer rodar o teste do zero, usando
**a própria conta Google e o próprio Drive**. Ao final, você terá o ambiente
completo funcionando: extrair arquivos/planilhas do Drive e guardá-los num
PostgreSQL local.

> ⚠️ **Importante — não existe "servidor compartilhado".** Cada pessoa cria o
> **seu próprio projeto no Google Cloud** e gera as **suas próprias credenciais**.
> Os arquivos `credentials.json` e `token.json` são **secretos e pessoais**: eles
> dão acesso à sua conta Google e **nunca** devem ser enviados para o GitHub nem
> compartilhados. O `.gitignore` do projeto já bloqueia esses arquivos.

---

## Pré-requisitos

Instale antes de começar:

- **Python 3.10 ou superior** (recomendado 3.12) — <https://www.python.org/downloads/>
  (no Windows, marque **"Add python.exe to PATH"** durante a instalação).
- **PostgreSQL 14+** (recomendado 17) — <https://www.postgresql.org/download/>
  (anote a senha do usuário `postgres` que você definir na instalação).
- **Git** — para clonar o repositório.

Confirme no terminal:
```bash
python --version
psql --version
```

---

## Passo 1 — Clonar o projeto

```bash
git clone <URL-DO-SEU-REPOSITORIO>
cd <pasta-do-projeto>
```

---

## Passo 2 — Criar o projeto no Google Cloud (a parte principal)

Você vai criar um projeto no Google Cloud, ativar as APIs e gerar uma credencial
OAuth. É gratuito (as APIs de Drive/Sheets não cobram e você não cria recursos
pagos).

### 2.1 Criar o projeto
1. Acesse <https://console.cloud.google.com>.
2. No topo da página, clique no **seletor de projeto** → **"Novo projeto"**.
   (ou vá direto em <https://console.cloud.google.com/projectcreate>)
3. Dê um nome (ex: `teste-drive`) e clique em **Criar**.
4. Confirme que o novo projeto está **selecionado** no topo.

### 2.2 Ativar as APIs
Com o projeto selecionado, ative as duas APIs (clique em **Ativar** em cada):
- **Google Drive API** → <https://console.cloud.google.com/apis/library/drive.googleapis.com>
- **Google Sheets API** → <https://console.cloud.google.com/apis/library/sheets.googleapis.com>

### 2.3 Configurar a tela de consentimento OAuth
1. Vá em <https://console.cloud.google.com/apis/credentials/consent>.
2. Se aparecer a tela do **Google Auth Platform**, clique em **"Começar"** e
   preencha:
   - **Informações do app**: nome (ex: `teste-drive`) e um e-mail de suporte.
   - **Público (Audience)**: escolha **Externo**.
   - **Contato**: seu e-mail.
   - Aceite os termos e **Crie**.

### 2.4 Adicionar seu e-mail como usuário de teste  ⚠️ (passo que mais gera erro)
Enquanto o app estiver "em teste", só contas autorizadas conseguem logar.
1. Vá em <https://console.cloud.google.com/auth/audience>.
2. Na seção **Test users**, clique em **Add users**.
3. Adicione **o e-mail da conta Google cujo Drive você vai usar** e salve.

> Se pular este passo, o login retorna **`Error 403: access_denied`**.

### 2.5 Criar a credencial (OAuth client)
1. Vá em <https://console.cloud.google.com/auth/clients> (ou **Credenciais →
   Criar credenciais → ID do cliente OAuth**).
2. Em **Tipo de aplicativo**, escolha **App para computador (Desktop app)**.
3. Dê um nome e clique em **Criar**.
4. Clique em **Download JSON**.
5. **Renomeie o arquivo para `credentials.json`** e coloque-o na **raiz do
   projeto** (a mesma pasta dos scripts).

> Se fechar a janela sem baixar, dá para baixar de novo depois: **Clients** →
> ícone de download na linha do cliente.

---

## Passo 3 — Preparar o ambiente Python

Crie um ambiente virtual e instale as dependências:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Passo 4 — Criar o banco PostgreSQL

Crie um banco vazio chamado `drive_teste` (ajuste usuário/senha conforme sua
instalação):
```bash
psql -U postgres -c "CREATE DATABASE drive_teste;"
```

---

## Passo 5 — Configurar o arquivo `.env`

Copie o modelo e edite com os seus dados:

**Windows:**
```powershell
Copy-Item .env.example .env
```
**Linux / macOS:**
```bash
cp .env.example .env
```

Abra o `.env` e preencha principalmente a **senha do PostgreSQL** (`PGPASSWORD`).
Os demais valores já vêm com padrões que funcionam para uma instalação local.

---

## Passo 6 — Autenticar (primeiro login)

```bash
python auth.py
```

Isso abre o navegador. Faça o login com a conta que você adicionou como usuário
de teste. Você verá um aviso **"O Google não verificou este app"** → clique em
**Avançado → Acessar (não seguro)** (é esperado em apps de teste; o app é seu).
Ao final, um `token.json` é criado e o e-mail autenticado é impresso.

---

## Passo 7 — Rodar os testes

Crie as tabelas e comece a usar:
```bash
python db.py                       # cria as tabelas no PostgreSQL

python drive_download.py list      # lista arquivos do seu Drive
python files_to_db.py extract <FILE_ID>   # guarda um arquivo (bytes) no banco
python files_to_db.py list         # mostra o que já está guardado
python files_to_db.py restore <FILE_ID>   # recupera o arquivo do banco para o disco

python sheets_to_db.py <SPREADSHEET_ID>   # extrai dados de uma planilha
python sync.py init                # inventário inicial (sincronização)
python sync.py run                 # aplica só o que mudou no Drive
```

- O `<FILE_ID>` / `<SPREADSHEET_ID>` está na URL do arquivo no Drive.
- Cada script aceita `sem argumentos` para mostrar sua própria ajuda de uso.
- Detalhes de cada script e da estrutura do banco estão em `DOCUMENTACAO.md`.

---

## Solução de problemas

| Erro / sintoma | Causa provável | Como resolver |
|----------------|----------------|---------------|
| `Error 403: access_denied` no login | seu e-mail não está em **Test users** | adicione-o no Passo 2.4 |
| `FileNotFoundError: credentials.json` | credencial não está na pasta | refaça o Passo 2.5 |
| Erro de conexão com o banco | Postgres parado / senha errada no `.env` | confira o serviço e o `PGPASSWORD` |
| Login pede escopos diferentes / token velho | escopos mudaram em `config.py` | apague `token.json` e rode `login` de novo |
| `psycopg2` não instala | falta wheel para sua versão de Python | use Python 3.12 |

---

## Segurança (leia antes de subir no GitHub)

- **Nunca** faça commit de `.env`, `credentials.json` ou `token.json`. O
  `.gitignore` já os ignora — confirme com `git status` antes de commitar.
- Cada pessoa usa **as próprias credenciais** e o **próprio Drive**.
- Para revogar o acesso de um app à sua conta a qualquer momento:
  <https://myaccount.google.com/permissions>.
- Os escopos OAuth vêm como **somente leitura** por padrão (em `config.py`).
