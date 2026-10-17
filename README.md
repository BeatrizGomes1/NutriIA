# NutriIA

Assistente nutricional para leitura de rótulos, análise de ingredientes e
orientações personalizadas com apoio de inteligência artificial.

## Estrutura do projeto

Este repositório será organizado como um monorepo:

```text
NutriIA/
├── frontend/
├── backend/
├── prompts/
└── README.md
```

### Frontend

Aplicação mobile Android, planejada com Kotlin e Jetpack Compose. Será
responsável pela interface, captura de imagens, leitura de códigos de barras
e interação com o usuário.

### Backend

Backend em Python. O core de análise já possui modelos, configuração,
serviços e integração preparada para o Gemini. A comunicação com o frontend
será feita por uma API HTTP em FastAPI, que permanece em desenvolvimento
separado.

O fluxo principal pode ser executado localmente sem iniciar o FastAPI:

```text
backend/
├── app/
│   ├── config/
│   ├── api/
│   ├── gemini/
│   ├── models/
│   ├── services/
│   ├── utils/
│   └── main.py
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

### Prompts

A pasta `prompts/` registra prompts e decisões importantes do projeto. Toda
implementação relevante ou decisão arquitetural deve criar uma nova versão
nessa pasta antes da alteração.

```text
prompts/
├── README.md
├── INDEX.md
└── vNNNN-nome-da-decisao/
    ├── prompt.md
    └── decision.md
```

Versões existentes não devem ser sobrescritas. O índice deve ser atualizado a
cada nova versão.

## Objetivo

O NutriIA deverá analisar informações de produtos alimentícios e considerar o
perfil, as metas e as restrições alimentares de cada usuário para produzir
orientações claras e personalizadas.

## Execução local

Consulte [backend/README.md](backend/README.md) para instalar as dependências,
executar o fluxo mockado e alternar para o Gemini real.

O resultado da execução é salvo em
`prompts/v0007-core-analysis-flow/result.json`.

## Status

O core mockado da análise nutricional está funcional. A API FastAPI,
persistência, autenticação, OCR, consulta por EAN e histórico ainda serão
implementados em etapas posteriores.
