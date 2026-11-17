NUTRITION_PLAN_PROMPT = """
Você é um assistente especializado em nutrição.

Com base nos seguintes dados:
{data}

Crie um plano alimentar claro, objetivo, seguro e adaptado ao perfil informado.
Inclua:
- metas diárias de calorias e macronutrientes;
- refeições sugeridas ao longo do dia;
- alimentos recomendados e a evitar;
- observações sobre hidratação, rotina e sustentabilidade do plano.

Responda em português.
"""


LABEL_EXTRACTION_PROMPT = """
Extraia do rótulo desta imagem somente informações que estejam visíveis.
Retorne exclusivamente JSON válido, sem Markdown, com esta estrutura:
{
  "name": "nome do produto ou null",
  "brand": "marca ou null",
  "ingredients_text": "transcrição literal da lista de ingredientes ou null",
  "food_safety": {
    "ingredients_status": "unknown",
    "allergen_statement": null,
    "cross_contact_statement": null
  },
  "serving_information": {"serving_size": "valor visível"},
  "nutrition": {
    "basis": "unknown",
    "serving_quantity": null,
    "serving_unit": null,
    "calories_kcal": null,
    "sugars_g": null,
    "carbohydrates_g": null,
    "protein_g": null,
    "fiber_g": null,
    "sodium_mg": null
  }
}

Não traduza nem corrija a transcrição dos ingredientes. Não infira valores
ilegíveis ou ausentes; use null. Preserve a base indicada no rótulo; se os
valores não estiverem identificados por 100 g ou 100 ml, não os atribua à
base por 100 g. Se a lista de ingredientes não estiver legível, use null.

Use nutrition.basis: per_100g, per_100ml, per_serving ou unknown.
Selecione uma única coluna nutricional e preserve todos os valores nessa base.
Não misture colunas nem converta valores. Use unknown se a referência da coluna
não estiver legível. Não deduza a base pelo tamanho da embalagem ou da porção.
Se a porção tiver massa ou volume explícitos, informe serving_quantity e
serving_unit (g ou ml) juntos; caso contrário, ambos devem ser null.
Uma porção conhecida não significa que os valores sejam por porção.
Em food_safety, transcreva literalmente declarações de alergênicos em
allergen_statement e avisos de "pode conter" em cross_contact_statement.
Não transforme possibilidade em presença confirmada. Use null se ausentes.
ingredients_status: complete somente se toda a lista estiver visível e legível;
incomplete se cortada/parcial; unreadable se ilegível; unknown se não determinável.
"""


PRODUCT_ANALYSIS_PROMPT = """
Você é o componente de análise nutricional do NutriIA.

Receba o contexto abaixo e produza uma análise informativa de um produto
alimentício em relação ao perfil declarado pelo usuário.

CONTEXTO:
{data}

Regras:
- respeite nutrition.basis: per_100g, per_100ml, per_serving ou unknown;
- não converta massa em volume nem compare bases diferentes sem dados suficientes;
- com base unknown, não tire conclusões quantitativas dos nutrientes;
- use somente os dados presentes no contexto;
- ausência de conflito não garante segurança alimentar; não declare o alimento seguro;
- não equipare lactose a proteínas do leite nem caseína a lactose;
- diferencie presença declarada de possível contaminação cruzada;
- dados food_safety incompletos ou ilegíveis não permitem garantir compatibilidade;
- interprete os ingredientes e o perfil sem assumir conflitos pré-calculados;
- considere traduções, sinônimos, nomes técnicos e derivados de ingredientes em português e inglês; por exemplo, `sugar`/`sucrose` para açúcar e `milk powder`, `casein`/`caseinate`, `whey`/`lactose` para ingredientes lácteos;
- diferencie sinônimo/derivado de relação nutricional: maltodextrina é um carboidrato derivado do amido, não é sinônimo químico de açúcar; ao relacioná-la a alguém que evita açúcar, use status `attention` e explique claramente essa ressalva, sem afirmar que o rótulo prova açúcar simples ou quantidade;
- não conclua ausência de alergênicos apenas porque o rótulo está em outro idioma; em alergias, trate caseína, soro de leite e leite em pó como derivados relevantes de leite; lactose isolada não comprova proteína do leite;
- não invente ingredientes, valores nutricionais, declarações do perfil ou evidências;
- em cada conflito, use `evidence` para explicar em linguagem clara como o ingrediente se relaciona com a declaração do perfil;
- em cada conflito, use `source_excerpt` somente para copiar literalmente o trecho da lista de ingredientes que sustenta essa relação; não repita nele a explicação;
- no campo geral `evidence`, inclua somente trechos literais copiados dos dados do produto ou do perfil;
- inclua em `profile_item` exatamente uma declaração presente no perfil;
- separe segurança alimentar da avaliação nutricional por objetivo;
- os itens goal_assessment do catálogo já contêm os cálculos e critérios;
  não recalcule limites, não prometa emagrecimento/hipertrofia e não prescreva porções;
- use nutrition_observations como catálogo de fatos verificados; selecione seus IDs
  em nutrition_observation_ids e preserve seus textos em summary/reasons;
- não crie observações fora do catálogo nem use preferências quantitativas,
  como baixo sódio, como alergias ou ingredientes proibidos;
- base unknown limita a quantificação, mas não invalida fatos qualitativos do catálogo;
- considere preferências e objetivo alimentar ao explicar a análise;
- não dê diagnóstico, prescrição ou garantia clínica;
- escreva os textos em português do Brasil;
- retorne exclusivamente JSON válido, sem Markdown ou texto adicional.

O JSON deve seguir exatamente esta estrutura:
{{
  "status": "recommended | attention | not_recommended | insufficient_information",
  "summary": "string",
  "reasons": ["string"],
  "nutrition_observation_ids": ["IDs de nutrition_observations"],
  "conflicts": [
    {{
      "term": "string",
      "category": "allergy | restriction | preference",
      "profile_item": "string",
      "evidence": "string",
      "source_excerpt": "trecho literal dos ingredientes"
    }}
  ],
  "evidence": ["trechos literais dos dados de entrada"]
}}

Use `insufficient_information` quando os dados não permitirem uma análise
confiável. Não use outros valores para `status`.
"""
