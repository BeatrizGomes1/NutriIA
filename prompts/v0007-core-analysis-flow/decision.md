# Decisão

O fluxo principal será executável por linha de comando e independente da API
HTTP. A API futura deverá chamar o mesmo `NutritionService` usado pelo runner.

## Provedores

- `mock`: padrão para desenvolvimento local e execução sem chave;
- `gemini`: opcional, selecionado por `NUTRITION_PROVIDER=gemini`.

Os dois provedores compartilham o mesmo contrato e retornam um
`AnalysisResult`. O mock simula a decisão do Gemini para permitir a validação
do fluxo sem consumo de cota.

## Fluxo

1. O runner cria dados mockados de produto e perfil.
2. O `NutritionService` gera um `AnalysisContext`.
3. Dados críticos ausentes encerram o fluxo com
   `insufficient_information`.
4. O provedor recebe o contexto.
5. A resposta do provedor é convertida e validada como `AnalysisResult`.
6. O resultado é salvo em `result.json`.

## Execução

O fluxo é iniciado, a partir da pasta `backend`, com:

```bash
python -m app.run_core_flow
```

O modo padrão é `NUTRITION_PROVIDER=mock`. O modo `gemini` exige
`GEMINI_API_KEY` e grava o resultado real no mesmo arquivo. O arquivo é um
artefato gerado e pode ser sobrescrito a cada execução.

Respostas inválidas do Gemini geram erro explícito. Não haverá fallback
silencioso de `gemini` para `mock`.

## Status

Implementado.
