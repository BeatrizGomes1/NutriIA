# Decisão: refresh, password reset, foto de rótulo e aliases

## Decisão

- Refresh tokens opacos aleatórios serão armazenados apenas como SHA-256 e rotacionados a cada uso; reutilização revoga a família.
- Reset de senha usa token aleatório de uso único, armazenado por hash e enviado por SMTP; respostas de solicitação não revelam se o e-mail existe.
- Foto será validada e enviada inline via `ImageContentParam` da Interactions API. A extração retorna campos estruturados e segue para o serviço comum de análise/persistência.
- Mock e prompt do Gemini reconhecem traduções e sinônimos de ingredientes. Derivados correlatos, como maltodextrina para uma preferência por evitar açúcar, serão marcados como relacionados, não como equivalência química; evidência sempre cita literalmente o rótulo.

## Impacto e limites

- Nova migração adiciona tabelas de refresh sessions e password reset tokens.
- SMTP deve ser configurado para efetivamente entregar e-mails de recuperação.
- Foto exige multipart, tamanho limitado e Gemini configurado; imagem não será persistida nem enviada por URL.
- Refresh e reset precisam de testes de integração ao banco; esses testes podem usar dependências/sessões isoladas.
- Nenhuma chave real ou banco externo será usado nesta implementação.

## Status

Implementado. Schema Prisma validado e testes offline sem dependência de upload passaram; aplicação da migração e execução dos testes das rotas multipart dependem da instalação/ambiente do usuário.
