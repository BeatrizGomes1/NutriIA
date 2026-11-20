## API HTTP

A aplicação é inicializada por `app.main:app`, com prefixo configurável por
`API_V1_PREFIX` (padrão `/api/v1`). O FastAPI gera documentação interativa em
`/docs`.

### Autenticação

- `POST /auth/register`: cria perfil e credenciais; retorna bearer JWT.
- `POST /auth/login`: valida credenciais e retorna bearer JWT.
- `POST /auth/refresh`: rotaciona refresh token opaco; reutilização revoga a família.
- `POST /auth/password-reset/request`: envia link SMTP genérico se a conta existir.
- `POST /auth/password-reset/confirm`: consome token único e atualiza senha.
- `GET /auth/me`: retorna o perfil associado ao token.

Senhas são armazenadas com Argon2. `JWT_SECRET_KEY` precisa ser um segredo
aleatório local com pelo menos 32 caracteres. Tokens expiram conforme
`ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutos por padrão).
Refresh tokens são aleatórios, persistidos apenas como hash e rotacionados; o
prazo padrão é 30 dias. Reset usa token hash-only de uso único, válido por 20
minutos. A rota de solicitação exige SMTP e `PASSWORD_RESET_URL`.

### Perfis e produtos

- `GET /profiles/{user_id}` e `PUT /profiles/{user_id}`;
- `POST /profiles/{user_id}/captures/ean`;
- `POST /profiles/{user_id}/captures/label-photo` com multipart field `file`
	(JPEG, PNG ou WEBP, até 8 MB); extrai o rótulo pelo Gemini;
- `POST /profiles/{user_id}/products/{product_id}/analysis`;
- `GET /profiles/{user_id}/history/analyses`;
- `GET /profiles/{user_id}/history/captures`.

Todas essas rotas exigem `Authorization: Bearer <access_token>` e verificam
que o `user_id` da URL corresponde ao usuário do token. Não há autenticação
por papéis, logout explícito, verificação de e-mail ou OCR local; a extração
da foto é feita pelo Gemini.

O histórico de capturas conserva os eventos no banco, mas retorna somente a
leitura mais recente por produto encontrado. EANs sem produto continuam sendo
exibidos individualmente.
