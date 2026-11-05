# Backend NutriIA

Backend inicial do NutriIA, com a camada de integração preparada para o
Gemini.

```text
backend/
├── app/
│   ├── config/
│   ├── api/
│   ├── gemini/
│   ├── models/
│   ├── services/
│   ├── utils/
│   └── main.py
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## Configuração do Gemini

1. Copie `.env.example` para `.env`.
2. Preencha `GEMINI_API_KEY` com uma chave criada no Google AI Studio.
3. Mantenha o arquivo `.env` fora do Git. Ele já está no `.gitignore`.
4. Confira `GEMINI_MODEL` e altere-o se necessário.
5. Use `NUTRITION_PROVIDER=mock` para execução local sem chamada externa ou
   `NUTRITION_PROVIDER=gemini` para enviar o contexto ao Gemini.

A chave não é necessária para executar os testes unitários. Sem ela, uma
chamada real falha explicitamente com `GEMINI_API_KEY is not configured`.

## Cadastro, login e API HTTP

O backend usa Argon2 para armazenar senhas como hash e JWT bearer tokens para
autenticar as rotas privadas. Gere um segredo local com:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Adicione o resultado ao `.env` como `JWT_SECRET_KEY` e configure
`ACCESS_TOKEN_EXPIRE_MINUTES` se quiser alterar os 30 minutos padrão. O login e
o cadastro também retornam um refresh token rotativo, com validade padrão de
30 dias. Aplique as migrações Prisma pendentes antes de usar essas operações.

Rotas de autenticação:

- `POST /api/v1/auth/register`: cria o perfil e retorna token;
- `POST /api/v1/auth/login`: valida e-mail/senha e retorna token;
- `POST /api/v1/auth/refresh`: rotaciona o refresh token e emite novos tokens;
- `POST /api/v1/auth/password-reset/request`: solicita instruções de reset;
- `POST /api/v1/auth/password-reset/confirm`: consome o token e troca a senha;
- `GET /api/v1/auth/me`: retorna o perfil autenticado.

A recuperação exige SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_SENDER` e
`PASSWORD_RESET_URL`; autenticação SMTP é opcional). O endpoint sempre retorna
uma mensagem genérica para não revelar se o e-mail existe. O token de reset é
de uso único e expira após 20 minutos por padrão.

As rotas de perfil, captura, análise e histórico exigem
`Authorization: Bearer <access_token>` e só permitem acesso ao próprio perfil.
Consulte `/docs` depois de iniciar o servidor para ver os contratos completos.
Capturas por foto usam `POST /api/v1/profiles/{user_id}/captures/label-photo`
com multipart field `file` e JPEG, PNG ou WEBP até 8 MB; a extração chama o
Gemini e requer chave configurada.

## Instalação

Na pasta `backend`, execute:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

No Bash, a ativação equivalente é:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Testes automatizados

Execute:

```powershell
py -m pytest -q
```

Os testes não chamam a API real e não consomem cota do Gemini.

## Teste direto do cliente Gemini

Depois de configurar o `.env`, execute na pasta `backend`:

```powershell
py -c "from app.gemini.client import generate_response; print(generate_response('Responda apenas: conexão funcionando'))"
```

Se a configuração estiver correta, o terminal exibirá a resposta gerada pelo
Gemini. Esse comando usa a chave local e pode consumir cota da API.

Também é possível testar o fluxo nutricional:

```powershell
py -c "from app.gemini.nutrition_ai import generate_nutrition_plan; print(generate_nutrition_plan({'goal': 'emagrecimento', 'daily_kcal': 1800, 'restrictions': ['sem glúten']}))"
```

## Fluxo automatizado do core

Para executar o fluxo sem iniciar o FastAPI:

```powershell
py -m app.run_core_flow
```

O fluxo consulta o produto de EAN demonstrativo `3017624010701` no Open Food
Facts e usa perfil e provedor de análise mockados. É necessária conexão com a
internet. O resultado é salvo em `../prompts/v0007-core-analysis-flow/result.json`.

O comando deve ser executado a partir da pasta `backend`:

```bash
python -m app.run_core_flow
```

Para enviar o mesmo contexto ao Gemini real, configure no `.env`:

```env
NUTRITION_PROVIDER=gemini
```

Nesse modo, `GEMINI_API_KEY` também deve estar configurada. Não há fallback
automático para o mock quando o Gemini real falha.

O Gemini deve retornar JSON válido com `status`, `summary`, `reasons`,
`conflicts` e `evidence`. Respostas em texto livre ou JSON inválido causam
falha explícita do fluxo.

## Serviços com persistência

O backend usa SQLAlchemy 2 e psycopg 3 para acessar o schema PostgreSQL já
criado pelas migrações Prisma. Configure `DATABASE_URL` no `.env`; URLs Prisma
com `?schema=public` são aceitas. O Python não cria nem altera tabelas: aplique
as migrações pelo fluxo Prisma descrito em `POSTGRESQL_PRISMA.md`.

`AuthService` cria contas e valida credenciais. `ProfileService` consulta e
atualiza perfis. `NutritionWorkflowService` oferece `capture_ean(user_id, ean)`,
que consulta Open Food Facts, registra a
captura e executa ou reutiliza a análise persistida. `analyze_product` analisa
um produto já cadastrado. `HistoryService.list(user_id, limit=20, offset=0)`
consulta análises recentes e `list_captures(...)` inclui capturas sem produto
encontrado. Esses serviços são expostos por rotas FastAPI; os handlers recebem
o perfil autenticado antes de encaminhar o UUID aos serviços.
O histórico mantém cada captura como evento, mas lista apenas a captura mais
recente de cada produto identificado para evitar cartões duplicados. EANs não
encontrados continuam aparecendo individualmente.

O cache considera usuário, conteúdo do produto, perfil, provedor, modelo e
`ANALYSIS_PROMPT_VERSION`. A captura é registrada mesmo quando Open Food Facts
confirma que o EAN não existe; erros transitórios da fonte são propagados.
