# P0: validacao deterministica de alergias e restricoes

## Fluxo e precedencia

NutritionService prepara o contexto e aplica food_safety antes do provedor.
Com conflito conhecido ou informacao insuficiente, nao chama o Gemini.
parse_provider_result reaplica a protecao, inclusive para respostas contraditorias,
JSON invalido ou conflitos omitidos. Regras deterministicas nao dependem do prompt.

- Presenca confirmada de alvo declarado: not_recommended, mesmo com dados
  incompletos. Motivos de insuficiencia e todas as evidencias sao preservados.
- Sem conflito confirmado, lista ausente, ilegivel, explicitamente parcial ou com
  marcadores de truncamento: insufficient_information. Avisos conhecidos de
  contaminacao cruzada continuam nos conflitos.
- Somente possivel contaminacao cruzada: attention, com explicacao de possibilidade.
- Nenhum conflito conhecido, perfil com alergias/restricoes: attention, nunca
  garantia de seguranca. Observacoes nutricionais verificadas sao preservadas,
  inclusive junto de alertas. Ver NUTRITION_PERSONALIZATION.md para o catalogo
  de fatos, as regras de referencia nutricional e a composicao do resultado.

## Correspondencias

Normalizacao de caixa/acentos e limites de palavras; nao usa substrings arbitrarias.
Dicionario limitado PT/EN: leite/proteinas e derivados (caseina, caseinatos, whey),
lactose em conceito separado, amendoim, soja, trigo, gluten e acucares.
Alvos especificos (caseina, whey) nao sao expandidos a todos os derivados do leite.
Outros itens recebem apenas correspondencia literal, sem inventar sinonimos.
Preferencias nao sao promovidas a alergias ou restricoes.

Lactose nao comprova proteina do leite; caseina/whey nao comprovam quantidade ou
presenca de lactose. Zero lactose nao remove um conflito comprovado com leite.
Negacoes comuns e nomes de bebidas vegetais sao tratados conservadoramente.
"Pode conter", "may contain", tracos e instalacoes compartilhadas sao possibilidade,
nao ingredientes confirmados. Sua fonte e transcrita em source_excerpt, e a
explicacao distingue presenca de possivel contaminacao. O contrato de Conflict
continua igual; a distincao fica no trecho literal e no texto da explicacao.

## Captura e persistencia

Product.food_safety adiciona ingredients_status (unknown/complete/incomplete/unreadable),
allergen_statement e cross_contact_statement. Foto solicita transcricao literal
separada; OFF fornece allergens e traces sem inferir ausencias de tags vazias.

Os metadados sao um sidecar food_safety no JSONB nutrition_table existente.
Os valores e a referencia nutricional continuam no formato schema_version=2/values
introduzido pelo P0 anterior. Campos ausentes em registros antigos assumem unknown.
Nao ha nova coluna, DDL, migracao ou backfill. Em atualizacoes OFF que trazem apenas
metadados de seguranca, a expressao JSONB preserva a tabela nutricional existente.
Conflitos e evidencias usam a persistencia ja existente de ingredient_matches.

## Cache, API e limites

Chaves incluem RULES_VERSION, metadados de seguranca e perfil. Qualquer alteracao
semantica do dicionario/politica exige nova versao. Chaves anteriores nao sao
reutilizadas para novas analises. Historico antigo nao e revalidado automaticamente.

Rotas, statuses e campos de Conflict sao preservados; food_safety e adicional no
produto. Android nao foi alterado. Nenhum valor/base nutricional e convertido.

Cobertura nao e exaustiva: outras linguas, negacoes complexas, OCR incorreto,
truncamento sem indicios e derivados nao catalogados podem escapar. Nao ha
avaliacao de dose, limiares clinicos, excecoes regulatorias de ingredientes
processados nem garantia de ausencia de contaminacao. Algumas correspondencias
conservadoras precisam de revisao especializada antes de ampliar o dicionario.

Referencia para exemplos de derivados e avisos de contaminacao:
https://www.fda.gov/consumers/consumer-updates/have-food-allergies-read-label

## Verificacao

`backend/.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider`

Testes usam provedores/HTTP/sessoes simulados. Nao abrem banco real nem executam
migracoes. A execucao de SQL em PostgreSQL real e qualidade de OCR/LLM nao sao
comprovadas por esses testes.
