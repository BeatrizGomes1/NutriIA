## API HTTP

A aplicação é inicializada por `app.main:app`, com prefixo configurável por
`API_V1_PREFIX` (padrão `/api/v1`). O FastAPI gera documentação interativa em
`/docs`.

### Autenticação

- `POST /auth/register`: cria perfil e credenciais; retorna bearer JWT.
- `POST /auth/login`: valida credenciais e retorna bearer JWT.
- `GET /auth/me`: retorna o perfil associado ao token.

Senhas são armazenadas com Argon2. `JWT_SECRET_KEY` precisa ser um segredo
aleatório local com pelo menos 32 caracteres. Tokens expiram conforme
`ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutos por padrão).

### Perfis e produtos

- `GET /profiles/{user_id}` e `PUT /profiles/{user_id}`;
- `POST /profiles/{user_id}/captures/ean`;
- `POST /profiles/{user_id}/products/{product_id}/analysis`;
- `GET /profiles/{user_id}/history/analyses`;
- `GET /profiles/{user_id}/history/captures`.

Todas essas rotas exigem `Authorization: Bearer <access_token>` e verificam
que o `user_id` da URL corresponde ao usuário do token. Não há autenticação
por papéis, refresh token, logout revogável, recuperação de senha ou OCR.
