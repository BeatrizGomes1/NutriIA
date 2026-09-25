# Backend NutriIA

Backend inicial do NutriIA, com a camada de integração preparada para o
Gemini.

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

## Configuração do Gemini

1. Copie `.env.example` para `.env`.
2. Preencha `GEMINI_API_KEY` com uma chave criada no Google AI Studio.
3. Mantenha o arquivo `.env` fora do Git. Ele já está no `.gitignore`.
4. Confira `GEMINI_MODEL` e altere-o se necessário.

A chave não é necessária para executar os testes unitários. Sem ela, uma
chamada real falha explicitamente com `GEMINI_API_KEY is not configured`.

## Instalação

Na pasta `backend`, execute:

```powershell
py -m pip install -r requirements.txt
```

## Testes automatizados

Execute:

```powershell
py -m pytest -q
```

Os testes não chamam a API real e não consomem cota do Gemini.

## Teste manual da API

Depois de configurar o `.env`, execute na pasta `backend`:

```powershell
py -c "from app.gemini.client import generate_response; print(generate_response('Responda apenas: conexão funcionando'))"
```

Se a configuração estiver correta, o terminal exibirá a resposta gerada pelo
Gemini. Esse comando usa a chave local e pode consumir cota da API.

Também é possível testar o fluxo nutricional:

```powershell
py -c "from app.gemini.nutrition_ai import generate_nutrition_plan; print(generate_nutrition_plan({'goal': 'emagrecimento', 'daily_kcal': 1800, 'restrictions': ['sem glúten']}))"
```
