# v0006 — Orquestração da decisão pela IA

**Status:** definido para implementação.

## Contexto

O incremento anterior colocou a classificação dentro de
`NutritionService`. Após a revisão da arquitetura, a decisão contextualizada
deve ser produzida pelo provedor de IA, enquanto o serviço prepara e protege
os dados enviados para esse provedor.

## Objetivo

Refatorar o core para que `NutritionService` normalize os dados, identifique
informações críticas ausentes e monte um contexto estruturado. O resultado
final deve ser produzido por um provedor injetável, com um provedor mockado
representando o Gemini durante o desenvolvimento.

## Prompt utilizado

Implemente a orquestração da análise nutricional sem colocar o veredito no
`NutritionService`. O serviço deve receber produto e perfil, normalizar os
ingredientes, reunir evidências e conflitos objetivos e produzir um contexto
estruturado para a IA.

O serviço só deve interromper a análise quando faltarem dados críticos para
uma análise confiável. Nos demais casos, delegue a classificação, os motivos,
as evidências e a linguagem da recomendação ao provedor de IA.

Crie um provedor mockado com o mesmo contrato do provedor real, sem alterar
`backend/app/gemini/`, `backend/tests/`, a API ou o frontend. O provedor real
de Gemini poderá substituir o mock por injeção de dependência.
