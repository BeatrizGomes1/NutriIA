# Decisão

`NutritionService` será um orquestrador de dados e não o decisor final da
análise.

## Responsabilidades do serviço

- normalizar texto e dados do produto e do perfil;
- detectar dados mínimos ausentes;
- identificar conflitos objetivos conhecidos e enviá-los como evidência;
- montar um `AnalysisContext` serializável;
- chamar um provedor de análise injetável;
- converter o retorno estruturado do provedor em `AnalysisResult`.

## Responsabilidades da IA

- decidir entre recomendado, atenção, não recomendado e informações
  insuficientes quando houver dados para análise;
- produzir motivos, evidências e explicação contextualizada;
- considerar objetivo, preferências e conflitos apresentados no contexto.

Um provedor mockado simulará a resposta do Gemini sem chamada externa. A
resposta esperada do provedor é estruturada e deve conter `status`, `summary`,
`reasons`, `conflicts` e `evidence`.

## Status

Implementado.
