# v0008 — Integração Python com PostgreSQL

As últimas etapas criaram a consulta Open Food Facts e o core de análise, além
do schema PostgreSQL gerenciado por Prisma. O backend Python ainda não persiste
perfis, produtos, capturas ou análises.

Implemente os serviços e a camada de persistência Python necessários para que a
futura API FastAPI possa criar/atualizar perfis, registrar consultas EAN,
analisar produtos e consultar histórico. Preserve o schema Prisma e adapte os
modelos de domínio aos campos e enums do banco. Use SQLAlchemy e psycopg,
transações curtas, cache de análise isolado por usuário e versão de provedor,
modelo e prompt. Não implemente rotas HTTP, autenticação ou OCR.

Registre testes para os mapeamentos, estados de captura, persistência/cache e
isolamento por usuário. Documente a configuração do banco e os serviços
disponíveis para o futuro adaptador HTTP.
