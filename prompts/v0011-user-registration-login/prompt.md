# Contexto

A API FastAPI possui cadastro simples de perfil, mas não possui conta, senha ou autenticação. As rotas aceitam `user_id` fornecido pelo cliente, o que não é adequado para proteger dados pessoais.

# Objetivo

Implementar registro com senha armazenada como hash, login com token JWT e rotas privadas que identifiquem o perfil pelo token autenticado. Atualizar Prisma/SQLAlchemy com uma coluna compatível para hashes de senha e fornecer uma migração versionada. Não executar migrações nesta implementação.

# Prompt utilizado

Implemente cadastro/login usando Argon2 por meio de pwdlib e tokens JWT de curta duração com PyJWT. Crie `/auth/register`, `/auth/login`, `/auth/me`; proteja perfil, captura, análise e histórico usando o usuário do token em vez de aceitar ID livre. Normalize e valide e-mail, rejeite credenciais inválidas com resposta genérica, não exponha hashes e configure segredo JWT via ambiente. Atualize schema Prisma, ORM, migração e testes. Não implemente refresh token, logout persistente ou recuperação de senha.
