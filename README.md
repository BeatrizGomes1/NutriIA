# NutriIA

Assistente nutricional para leitura de rótulos, análise de ingredientes e
orientações personalizadas com apoio de inteligência artificial.

## Estrutura do projeto

```text
NutriIA/
├── frontend/      # Aplicativo Android
├── backend/       # API e serviços de análise
├── prompts/       # Histórico de prompts e decisões
├── apresentacao/  # Kit para demonstração do aplicativo
└── README.md
```

### Frontend

Aplicativo Android em Kotlin, com telas em XML e ViewBinding. Permite cadastro,
login, configuração do perfil, leitura de código de barras, captura de foto do
rótulo e consulta ao histórico. Para instalação e configuração, consulte
[frontend/README.md](frontend/README.md) e [COMO_RODAR.md](COMO_RODAR.md).

### Backend

API HTTP em FastAPI com autenticação, perfis, captura de produtos por EAN ou
foto de rótulo, análise nutricional e histórico. Os dados são persistidos em
PostgreSQL por serviços Python com SQLAlchemy. A análise pode usar o provedor
mock ou o Gemini; a leitura de rótulos por foto requer uma chave Gemini.

Consulte [backend/README.md](backend/README.md) para configuração, execução e
detalhes dos serviços.

### Prompts

A pasta `prompts/` registra versões de prompts e decisões relevantes do
projeto. Versões existentes são preservadas e o índice acompanha novas
versões. Consulte [prompts/README.md](prompts/README.md) e
[prompts/INDEX.md](prompts/INDEX.md).

## Objetivo

Analisar informações de produtos alimentícios considerando o perfil, as metas
e as restrições alimentares declaradas por cada usuário, oferecendo
orientações informativas e personalizadas.

## Execução local

Siga o [guia COMO_RODAR.md](COMO_RODAR.md) para configurar o backend e executar
o aplicativo Android.

## Status

O repositório contém um aplicativo Android integrado à API FastAPI, com
autenticação, persistência de perfis, capturas e análises, consulta por EAN,
leitura de rótulo por foto e histórico. A análise nutricional oferece modo
mock e integração com Gemini. Consulte os guias específicos para requisitos de
ambiente e configuração de serviços externos.
