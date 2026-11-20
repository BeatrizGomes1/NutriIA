# Decisão: camada HTTP FastAPI

## Decisão

Adicionar schemas Pydantic e rotas FastAPI para health, perfis, captura por EAN, análise de produto e histórico. As rotas delegam para `ProfileService`, `NutritionWorkflowService` e `HistoryService`; não contêm acesso direto a SQLAlchemy nem a serviços externos.

## Justificativa

Os serviços do domínio já implementam persistência, Open Food Facts, validação da análise e cache. A camada HTTP deve adaptá-los para contratos JSON e códigos HTTP consistentes, preservando a separação de responsabilidades.

## Impacto e limites

- Não inclui autenticação porque o projeto ainda não possui identidade/sessão/tokens implementados. Rotas que recebem `user_id` não são seguras para exposição pública até existir autenticação e autorização.
- Captura por foto/OCR não é exposta porque não há serviço de OCR ou fluxo de imagem implementado.
- Esta alteração é escrita sem executar testes, comandos, servidores ou migrações, conforme solicitação.

## Status

Código da API implementado; validação automatizada pendente por solicitação do usuário.
