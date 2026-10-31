# Decisão

A integração do backend Python com o PostgreSQL existente será feita com
SQLAlchemy 2.x e psycopg 3. O schema Prisma e suas migrações permanecem como
fonte da verdade; a aplicação Python mapeia explicitamente seus enums e
colunas, sem criar ou alterar tabelas automaticamente.

O fluxo de serviços cobre criação/consulta/atualização de perfil, consulta de
produto Open Food Facts por EAN com captura por usuário, upsert de catálogo,
análise contextualizada, persistência de conflitos e consulta de histórico.
Uma ausência confirmada na fonte registra `not_found`; falhas transitórias são
propagadas e não classificadas como ausência. Produtos retornados pela fonte
com dados insuficientes continuam sendo capturas `found`, enquanto a análise
pode persistir o veredito `insufficient`.

O cache é calculado por SHA-256 a partir do usuário, produto/dados, perfil e
versões do provedor/modelo/prompt. Os valores do core são convertidos para os
enums do banco (`not_recommended` para `avoid`). Operações externas ocorrem
fora das transações. Rotas FastAPI, autenticação, OCR e captura por foto ficam
fora deste incremento.

## Status

Implementado.
