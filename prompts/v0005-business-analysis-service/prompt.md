# v0005 — Serviço de análise contextualizada

**Status:** definido para implementação.

## Contexto

O documento de requisitos define o NutriIA como um apoio à decisão para
produtos industrializados, comparando dados disponíveis do produto com o
perfil alimentar declarado pelo usuário. A API, a integração com o Gemini e
a pasta `tests/` são mantidas sob responsabilidade de outros colaboradores.

## Objetivo

Implementar o primeiro núcleo de regra de negócio do backend, com modelos de
domínio, configuração, normalização simples e um serviço de análise que possa
usar dados mockados sem depender de uma integração externa.

## Prompt utilizado

Implemente somente a camada de negócio da análise nutricional do NutriIA.

Respeite as regras do documento de requisitos: classifique o produto como
`recommended`, `attention`, `not_recommended` ou `insufficient_information`;
compare ingredientes, dados nutricionais e perfil alimentar; registre motivos,
conflitos e evidências; não invente dados ausentes; e trate a análise como
apoio informativo, nunca como diagnóstico ou garantia clínica.

Não altere `frontend/`, `backend/app/gemini/`, `backend/tests/` ou a camada de
API. Use mocks quando a integração externa não for necessária e aplique
somente validações críticas. Preserve uma fronteira clara para que a API e o
Gemini possam consumir ou substituir o serviço futuramente.
