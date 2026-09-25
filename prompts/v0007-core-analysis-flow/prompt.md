# v0007 — Fluxo automatizado da análise com IA

**Status:** implementado.

## Objetivo

Executar o fluxo principal do core sem depender da camada FastAPI: receber
dados mockados, tratá-los no `NutritionService`, enviá-los a um provedor de
análise, validar o resultado estruturado e gravá-lo em arquivo.

## Prompt utilizado

Implemente um fluxo automatizado de análise nutricional com dois modos de
provedor: `mock` como padrão, sem chamada externa, e `gemini` como modo
opcional usando a chave configurada no ambiente.

O `NutritionService` deve preparar o contexto, normalizar dados, identificar
informações críticas ausentes e delegar a decisão ao provedor. O Gemini deve
receber o contexto em JSON e retornar exclusivamente um resultado estruturado
em JSON com status, resumo, motivos, conflitos e evidências.

Crie um comando local que use um produto e um perfil mockados, execute o fluxo
completo e grave o resultado em `result.json` dentro desta versão. Não
implemente FastAPI e não altere os testes existentes.

## Execução

Na pasta `backend`, execute:

```bash
python -m app.run_core_flow
```

O provedor padrão é `mock`. Para usar o Gemini real, configure no `.env`:

```env
NUTRITION_PROVIDER=gemini
GEMINI_API_KEY=sua-chave
```

O resultado é salvo em
`prompts/v0007-core-analysis-flow/result.json`.
