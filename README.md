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

Backend planejado em Python. A comunicação com o frontend será feita por uma
API HTTP, com FastAPI planejado para a próxima etapa.

O backend ainda está somente estruturado, sem implementação funcional:

```text
backend/
├── app/
│   ├── config/
│   ├── api/
│   ├── integrations/
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

## Status

Projeto em fase inicial de organização do monorepo. A estrutura atual não
possui implementação funcional; decisões de provedor, persistência, OCR,
autenticação e versões mínimas do Android ainda serão registradas conforme o
desenvolvimento começar.
