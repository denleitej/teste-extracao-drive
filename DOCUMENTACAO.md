# Documentação — Teste de Extração Google Drive → PostgreSQL

Este documento explica o que foi construído e testado: o objetivo, o passo a passo
do processo, o que cada script faz, para onde vão os arquivos, como o banco está
estruturado e como usar/recuperar as ferramentas (incluindo o setup no Google).

---

## 1. Objetivo do projeto

Testar, num ambiente local, a **extração de dados e arquivos do Google Drive** e o
seu armazenamento num **banco de dados estruturado e seguro (PostgreSQL)**. A ideia
é validar a base de uma futura ferramenta de **migração/arquivamento**: tirar
arquivos de um Drive e guardá-los no banco de forma que continuem íntegros e
recuperáveis, mesmo que sejam removidos do Drive depois.

Foram exercitados três fluxos:
- **Extração de arquivos** (bytes) para o banco, com verificação de integridade.
- **Extração de planilhas** (dados tabulares) para linhas no banco.
- **Sincronização incremental** (detectar só o que mudou no Drive).

---

## 2. APIs do Google utilizadas

| API | Para quê serve aqui |
|-----|---------------------|
| **Google Drive API v3** | listar, baixar e exportar arquivos; detectar mudanças (Changes API) |
| **Google Sheets API v4** | ler planilhas de forma estruturada (linha a linha) |
| **OAuth 2.0** | autorizar o acesso à conta Google usada no teste |

---

## 3. Setup no Google Cloud (feito uma vez)

1. Criado um **projeto** em <https://console.cloud.google.com> (nome: `teste-drive`).
2. Ativadas as APIs em **APIs e serviços → Biblioteca**:
   - Google Drive API
   - Google Sheets API
3. Configurada a **tela de consentimento OAuth** (Google Auth Platform):
   - Tipo de público: **Externo**.
   - Adicionado o email da conta de teste em **Test users** (obrigatório enquanto
     o app está "em teste"; sem isso o login retorna `403 access_denied`).
4. Criada a credencial em **Credenciais → Criar → ID do cliente OAuth**:
   - Tipo: **App para computador (Desktop app)**.
   - Baixado o JSON e salvo como **`credentials.json`** na pasta do projeto.

> Para recuperar o JSON depois: **Google Auth Platform → Clients →** ícone de
> download na linha do cliente.

---

## 4. Setup do ambiente local (Windows)

1. **Python 3.12** instalado (via `winget install Python.Python.3.12`).
2. **Ambiente virtual** e dependências:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **PostgreSQL 17** instalado (via winget). Serviço `postgresql-x64-17` rodando.
   - Usuário: `postgres` · Senha: `postgres` · Porta: `5432`
   - Banco criado: **`drive_teste`**
   - Acompanha o **pgAdmin 4** (interface gráfica) para explorar o banco.
4. Arquivo **`.env`** preenchido com os dados do Postgres e caminhos do Google.
5. **Login** feito uma vez com `python auth.py` (gera o `token.json`).

---

## 5. Estrutura do projeto — o que cada arquivo faz

| Arquivo | Papel |
|---------|-------|
| `config.py` | Lê o `.env` e define os escopos OAuth (hoje: somente leitura). |
| `auth.py` | Faz o login OAuth 2.0; cria os clientes das APIs Drive e Sheets. Guarda/renova o `token.json`. |
| `db.py` | Conexão com o PostgreSQL, criação do schema (tabelas) e funções de inserção. |
| `drive_download.py` | Lista e baixa/exporta arquivos do Drive **para disco**. |
| `sheets_to_db.py` | Extrai os **dados** de uma planilha (linhas) para a tabela `sheet_rows`. |
| `files_to_db.py` | Extrai **arquivos** (bytes) do Drive para a tabela `file_contents`; também lista e recupera (restore) com verificação de integridade. |
| `sync.py` | Sincronização incremental via Changes API: aplica no banco só o que mudou. |
| `requirements.txt` | Lista de dependências Python. |
| `.env` | Configurações e segredos (senha do banco, caminhos). **Não versionar.** |
| `credentials.json` / `token.json` | Credencial do Google e token de acesso. **Não versionar.** |

---

## 6. Para onde vão os arquivos

- **Conteúdo dos arquivos migrados:** vai para **dentro do PostgreSQL** (tabela
  `file_contents`, coluna binária `content`). O banco é a fonte segura.
- **Downloads avulsos** (`drive_download.py`): vão para a pasta **`downloads/`**.
- **Arquivos recuperados do banco** (`files_to_db.py restore`): por padrão vão para
  **`downloads/`**, ou para a pasta que você indicar (nos testes usamos
  **`recuperados/`**).
- Google Docs/Sheets/Slides são **nativos** e não podem ser baixados direto: são
  **exportados** antes de armazenar (Docs → PDF, Sheets → XLSX).

---

## 7. Estrutura do banco de dados

Banco: **`drive_teste`**. Quatro tabelas:

**`drive_files`** — catálogo de metadados de cada arquivo visto no Drive.
| Coluna | Descrição |
|--------|-----------|
| `id` | ID do arquivo no Drive (chave primária) |
| `name`, `mime_type`, `modified_time`, `size_bytes` | metadados |
| `trashed` | `true` se o arquivo está na lixeira do Drive |
| `removed_from_drive` | `true` se o arquivo saiu de vez do Drive |
| `last_seen` | quando o sync viu o arquivo pela última vez |

**`file_contents`** — o conteúdo binário dos arquivos migrados.
| Coluna | Descrição |
|--------|-----------|
| `file_id` | referência a `drive_files` (chave primária) |
| `stored_name`, `content_type` | nome e tipo do que foi armazenado |
| `content` | **os bytes do arquivo** (BYTEA) |
| `byte_size`, `sha256` | tamanho e hash para verificar integridade |
| `extracted_at` | data/hora da extração |

**`sheet_rows`** — dados tabulares extraídos de planilhas.
| Coluna | Descrição |
|--------|-----------|
| `file_id` | referência à planilha em `drive_files` |
| `sheet_name`, `row_index` | aba e número da linha |
| `data` | a linha como **JSONB** (chave = cabeçalho da coluna) |

**`sync_state`** — guarda o "marco" (page token) da sincronização incremental.

> **Decisão de projeto importante:** remoções no Drive **não apagam** o dado no
> banco. Lixeira marca `trashed=true`; exclusão marca `removed_from_drive=true`.
> O conteúdo em `file_contents` é sempre preservado — o banco funciona como
> arquivo histórico confiável.

---

## 8. Como usar as ferramentas

Sempre dentro da pasta do projeto, usando o Python do ambiente virtual
(`.\.venv\Scripts\python.exe`, ou `python` com o venv ativado).

**Login (uma vez):**
```powershell
python auth.py
```

**Listar arquivos do Drive:**
```powershell
python drive_download.py list
python drive_download.py list "name contains 'relatorio'"
```

**Extrair arquivos (bytes) para o banco:**
```powershell
python files_to_db.py extract <FILE_ID>   # um arquivo
python files_to_db.py extract-all         # todos (exceto pastas)
python files_to_db.py list                # ver o que já está guardado
```

**Extrair dados de uma planilha:**
```powershell
python sheets_to_db.py <SPREADSHEET_ID>
```

**Sincronização incremental:**
```powershell
python sync.py init   # inventário inicial + salva o marco
python sync.py run    # aplica só o que mudou desde a última vez
```

> O `<FILE_ID>` / `<SPREADSHEET_ID>` está na URL do arquivo no Drive.

---

## 9. Como recuperar os dados armazenados

Há três formas de acessar/recuperar o que está no banco:

1. **Pelo app (recupera o arquivo inteiro):**
   ```powershell
   python files_to_db.py restore <FILE_ID> <pasta>
   ```
   Reconstrói o arquivo original a partir dos bytes no banco e **confere o hash**
   (relendo o arquivo gravado no disco).

2. **Pelo pgAdmin 4** (interface gráfica): conectar no servidor local (senha
   `postgres`) → `drive_teste` → Tables → visualizar `file_contents`, `drive_files`
   e `sheet_rows`, rodar consultas SQL.

3. **Via SQL** (psql ou pgAdmin), por exemplo:
   ```sql
   SELECT stored_name, content_type, byte_size, sha256 FROM file_contents;
   SELECT data FROM sheet_rows ORDER BY row_index;
   ```

---

## 10. O que foi testado (resultados)

- ✅ Login OAuth com a conta de teste (`token.json` gerado).
- ✅ Listagem de arquivos do Drive.
- ✅ Extração de um **PDF** e de um **Google Doc** (exportado para PDF) para o banco.
- ✅ Extração de uma pasta ("Teste de Extração com Python") com **Doc + PDF + Sheet**.
- ✅ Extração dos **dados tabulares** da Sheet (4 linhas em `sheet_rows`).
- ✅ **Recuperação (restore)** dos arquivos a partir do banco, com integridade OK.
- ✅ **Sincronização incremental**: inventário inicial (15 arquivos), depois detecção
  correta de **apenas** 2 mudanças (1 arquivo novo + 1 enviado para a lixeira), sem
  reprocessar os demais.
- ✅ Confirmado que um arquivo enviado para a lixeira é **marcado** no banco, mas seu
  **conteúdo é preservado** e continua recuperável.

Um bug foi encontrado e corrigido durante os testes: nomes de arquivo com
caracteres inválidos no Windows (ex.: `:`) quebravam a gravação em disco na
recuperação. Corrigido com sanitização do nome e verificação de integridade relendo
o arquivo do disco.

---

## 11. Limitações e próximos passos (testes futuros)

- **Escopo atual é somente leitura.** Modificar/enviar arquivos de volta ao Drive
  exige ampliar o escopo OAuth para `drive` e refazer o login.
- **BYTEA é ideal para arquivos pequenos/médios.** Para arquivos grandes no futuro,
  o padrão seria *Large Objects* do Postgres ou storage externo (S3/MinIO) com o
  banco apenas indexando.
- Testes ainda não feitos (salvos para depois):
  - **Extração em lote** de todo o Drive (`extract-all`).
  - **Escrita/upload** de arquivos no Drive.
  - **Extração recursiva** de uma pasta inteira (subpastas) por nome.

---

## 12. Segurança

- `.env`, `credentials.json` e `token.json` contêm segredos e estão no `.gitignore`
  — **nunca versionar nem compartilhar**.
- Os escopos OAuth começam com o mínimo (somente leitura); ampliar apenas quando
  necessário.
- O hash SHA-256 de cada arquivo permite comprovar, a qualquer momento, que o dado
  guardado é idêntico ao original.
