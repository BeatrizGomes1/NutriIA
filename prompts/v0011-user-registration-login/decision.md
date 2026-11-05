# Decisão: autenticação com senha Argon2 e JWT

## Decisão

Adicionar `password_hash` opcional em `user_profiles`, com migração aditiva para manter perfis existentes compatíveis. O cadastro de conta cria perfil e hash Argon2. O login verifica o hash e emite JWT HS256 de curta duração. Rotas privadas derivam o usuário autenticado do bearer token e usam caminhos `/profiles/me/...`.

## Justificativa

A tabela de perfil já representa a conta com e-mail único, e o banco não possui tabela de usuários separada. A coluna opcional permite migrar os registros existentes sem apagar dados; perfis antigos sem hash não podem entrar até passarem pelo fluxo de cadastro apropriado.

## Impacto e limites

- Exige `pwdlib[argon2]`, `PyJWT`, `JWT_SECRET_KEY` e aplicação da nova migração Prisma.
- Login usa JSON e retorna bearer token; tokens são stateless, sem refresh/logout revogável.
- Rotas não terão autorização por papel; cada usuário só pode acessar a própria conta.
- Recuperação de senha e verificação de e-mail não fazem parte deste escopo.
- Testes ficam escritos; execução de migrações ou chamadas a serviços externos não faz parte da implementação.

## Status

Código implementado; suíte Python completa passou. A validação do schema Prisma foi cancelada e a migração ainda precisa ser aplicada no banco local.
