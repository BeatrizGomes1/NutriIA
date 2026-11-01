# Decisão: usar a Interactions API do Gemini

## Decisão

Centralizar a configuração do SDK Gemini em `Settings`, usar `client.interactions.create` para geração e alinhar o modelo padrão a `gemini-3.6-flash`. Manter testes do contrato do cliente e do provedor sem rede e sem chave real.

## Justificativa

A API anterior reportou que o modelo `gemini-2.0-flash` não está mais disponível e recomendou a Interactions API. A configuração duplicada entre `.env.example`, Settings e cliente podia causar modelo divergente no cache e na chamada real. A API fica isolada no cliente; a camada superior segue validando JSON e evidências.

## Impacto e limites

- Nenhuma chave real é necessária ou utilizada para implementar e testar a camada.
- A integração real só poderá ser verificada pelo usuário quando configurar sua chave e executar um teste manual.
- Nenhuma rota HTTP será criada nesta alteração.

## Status

Implementado e validado com testes offline. A chamada real depende da chave que o usuário configurará e não foi executada durante esta tarefa.
