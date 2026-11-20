# Contexto

O backend NutriIA já possui serviços Python para perfis, consulta de produtos por EAN, análise, histórico e persistência. A aplicação FastAPI e suas rotas HTTP ainda não foram implementadas.

# Objetivo

Implementar uma API HTTP que conecte os serviços existentes a contratos Pydantic, sem duplicar regras de negócio. Incluir health check, operações de perfil, captura de EAN/análise e leitura de histórico, além de testes isolados com serviços simulados. Não executar comandos, instalar dependências, iniciar servidor ou aplicar migrações nesta tarefa.

# Prompt utilizado

Crie a camada FastAPI do NutriIA sem reimplementar a lógica dos serviços existentes. Use validação de payload e UUID, respostas tipadas, CORS configurável e tratamento de erros sem expor detalhes sensíveis. Inclua testes para a API usando dependências substituídas por fakes. Não implemente autenticação inexistente no modelo atual e indique que as rotas com dados de perfil precisam de autenticação/autorização antes de exposição pública. Não execute testes ou comandos.
