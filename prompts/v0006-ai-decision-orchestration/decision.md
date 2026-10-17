# Decisão

`NutritionService` será um orquestrador de dados e não o decisor final da
análise.

## Responsabilidades do serviço

- detectar dados mínimos ausentes;
- montar um `AnalysisContext` serializável;
- enviar ao provedor os dados estruturados originais do produto e do perfil;
- validar a estrutura da resposta e conferir citações de evidência contra os dados recebidos;
- retornar `insufficient_information` se as evidências de conflitos ou da análise não puderem ser confirmadas;
- chamar um provedor de análise injetável;
- converter o retorno estruturado do provedor em `AnalysisResult`.

## Responsabilidades da IA

- decidir entre recomendado, atenção, não recomendado e informações
  insuficientes quando houver dados para análise;
- produzir motivos, evidências e explicação contextualizada;
- interpretar ingredientes, perfil, objetivo e preferências sem conflitos
  pré-calculados pelo serviço;
- citar trechos literais dos dados que sustentem evidências e conflitos, incluindo
  a declaração correspondente do perfil.

Um provedor mockado simulará a resposta do Gemini sem chamada externa. A
resposta esperada do provedor é estruturada e deve conter `status`, `summary`,
`reasons`, `conflicts` e `evidence`. Cada conflito interno inclui também
`source_excerpt`, removido ao converter para o resultado público.

## Status

Implementado.
