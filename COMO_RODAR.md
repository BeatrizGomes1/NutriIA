# Como rodar o NutriIA (backend + app)

Guia para rodar o projeto do zero no Windows. São duas partes que rodam ao
mesmo tempo:

- **Backend** (Python/FastAPI + PostgreSQL): `backend/`
- **App Android** (Kotlin + XML): `frontend/`

O app conversa com o backend em `http://<máquina>:8000/api/v1/`.

---

## 1. Instalar as ferramentas (uma vez só)

| Ferramenta | Para quê | Instalação (PowerShell) |
|---|---|---|
| Git | baixar o código | `winget install Git.Git` |
| Python 3.12 | backend | `winget install Python.Python.3.12` |
| Node.js LTS | migrações do banco (Prisma) | `winget install OpenJS.NodeJS.LTS` |
| PostgreSQL 17 | banco de dados | `winget install PostgreSQL.PostgreSQL.17` |
| Android Studio | app | https://developer.android.com/studio |

Durante a instalação do PostgreSQL, **anote a senha do usuário `postgres`**.
Feche e abra o terminal depois de instalar, para o PATH ser atualizado.

## 2. Baixar o código

```powershell
git clone https://github.com/BeatrizGomes1/NutriIA.git
cd NutriIA
git checkout issueTeste
```

## 3. Backend (uma vez só)

Todos os comandos abaixo são na pasta `backend`:

```powershell
cd backend
```

### 3.1 Criar o banco

```powershell
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres -h localhost nutriia
```

(Pede a senha do `postgres` que você anotou.)

### 3.2 Criar o arquivo `.env`

```powershell
copy .env.example .env
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Abra o `.env` e ajuste:

```env
NUTRITION_PROVIDER=mock
DATABASE_URL="postgresql://postgres:SUA_SENHA@localhost:5432/nutriia?schema=public"
JWT_SECRET_KEY=<cole aqui o valor gerado pelo comando acima>
```

- `NUTRITION_PROVIDER=mock` roda a análise sem IA real. Para usar o Gemini,
  troque para `gemini` e preencha `GEMINI_API_KEY`.
- A **análise por foto do rótulo** sempre usa o Gemini para ler a imagem: sem
  `GEMINI_API_KEY`, o app mostra que não foi possível ler o rótulo.
- **Recuperação de senha** (opcional): preencha `PASSWORD_RESET_URL=nutriia://redefinir-senha`
  (o link do e-mail abre direto o app) e os dados de SMTP (`SMTP_HOST`,
  `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER`). Com Gmail:
  `smtp.gmail.com`, porta `587` e uma "senha de app" da conta Google. Sem SMTP,
  o app avisa que a recuperação não está configurada.
- O `.env` **nunca** vai para o Git (já está no `.gitignore`).

### 3.3 Instalar dependências e aplicar as migrações

```powershell
npm ci
npm run db:deploy
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Opcional, para conferir: `.\.venv\Scripts\python.exe -m pytest -q` (os testes
não precisam do banco nem do Gemini).

## 4. Rodar o backend (toda vez)

Na pasta `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Deixe esse terminal aberto. Para conferir, abra
http://127.0.0.1:8000/api/v1/health (deve mostrar `{"status":"ok"}`) ou a
documentação em http://127.0.0.1:8000/docs.

> Erro `[Errno 10048] ... 8000`: já existe um backend rodando nessa porta.
> Use o que já está aberto ou feche-o (Ctrl+C no terminal dele).

## 5. Rodar o app (toda vez)

1. Abra a pasta **`frontend`** no Android Studio (não a raiz do repositório) e
   espere o Gradle sincronizar.
2. Escolha um emulador (ou conecte o celular) e clique em **Run**.

Por padrão o app procura o backend em `http://10.0.2.2:8000/api/v1/`, que é o
endereço do seu computador visto de dentro do **emulador**.

### Se o app disser "Não foi possível conectar ao servidor"

Isso acontece em **celular físico** e em algumas máquinas também com o
emulador. A solução que funciona nos dois casos é o `adb reverse`:

1. Crie (ou edite) o arquivo `C:\Users\<seu usuário>\.gradle\gradle.properties`
   com a linha abaixo. Ele fica **fora do repositório**, então só vale para a
   sua máquina:

   ```properties
   nutriia.apiBaseUrl=http://127.0.0.1:8000/api/v1/
   ```

2. Rode o app de novo pelo Android Studio (ele precisa recompilar).
3. **Toda vez** que ligar o emulador ou conectar o celular por USB, rode:

   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
   ```

   O `adb reverse` some quando o emulador reinicia ou o cabo é desconectado.

No celular, ative a **Depuração USB** nas opções do desenvolvedor.

## 6. Testando o fluxo

1. Toque em **Criar meu cadastro**, preencha e siga as duas etapas do perfil
   (marque, por exemplo, alergia a **Leite**).
2. Na aba **Escanear**:
   - **Usar câmera** lê o código de barras de um produto de verdade;
   - **Fotografar rótulo** tira uma foto da lista de ingredientes (precisa do Gemini);
   - **Sem acesso à câmera?** permite digitar um código ou escolher uma foto da galeria.
3. Códigos úteis para teste:

| EAN | Produto | Observação |
|---|---|---|
| `7891000100103` | Leite condensado | "Não recomendado" para quem marcou Leite |
| `3017624010701` | Nutella | Rótulo em inglês: "sugar" é reconhecido como açúcar |
| `0000000000000` | — | Produto não encontrado |

4. O resultado fica salvo no **Histórico** (cada produto aparece uma vez, com a
   leitura mais recente); tocar em um item abre a análise sem escanear de novo.

## 7. Bom saber

- O login fica salvo por até 30 dias: o app renova a sessão sozinho
  (`/auth/refresh`). Trocar a senha encerra as sessões abertas.
- A tela "Analisando produto" avança os passos por tempo: o backend responde a
  análise de uma vez só.
- Se o Gradle reclamar de JDK, use o JDK embutido do Android Studio
  (*Settings > Build > Gradle > Gradle JDK*).
