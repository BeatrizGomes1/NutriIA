# Contexto

O backend possui um adaptador Gemini para análise de produto e um cliente SDK baseado em `models.generate_content`. O modelo padrão ainda diverge entre `.env.example`, settings e cliente. O projeto deve usar a API recomendada pela mensagem de erro do Gemini e manter testes sem acesso à rede ou à chave real.

# Objetivo

Implementar a integração do Gemini no backend sem criar rotas HTTP. Centralizar configuração de modelo e credencial, usar a Interactions API, manter falhas explícitas e testar a montagem da requisição/resposta com doubles de teste. A chave real não deve ser lida, pedida, escrita ou usada durante as alterações e testes.

# Prompt utilizado

Atualize a camada de cliente Gemini para a API Interactions indicada pelo SDK, alinhe o modelo padrão com a configuração `gemini-3.6-flash`, garanta que o serviço de análise continue validando o JSON e suas evidências, e adicione testes offline para geração, ausência de configuração, resposta vazia e erro do SDK. Não implemente endpoints HTTP nem execute chamadas reais ao Gemini.
