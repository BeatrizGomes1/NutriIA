# Personalizacao nutricional e seguranca alimentar

A decisao de seguranca continua independente e deterministica. Conflitos confirmados
sempre prevalecem (not_recommended). Dados de ingredientes insuficientes permanecem
insufficient_information, salvo conflito confirmado. Nao e necessario chamar Gemini
para manter essas protecoes; observacoes nutricionais verificadas podem coexistir.

## Personalizacao verificada

nutrition_observations.py produz um catalogo de fatos a partir de produto e perfil:
objetivo, declaracoes explicitas de variedade, preferencias, ingredientes e valores
com referencia confirmada. O adaptador envia esse catalogo ao Gemini, que pode
selecionar IDs e reutilizar seus textos. O parser conserva textos/IDs validos e
completa o contexto com os demais fatos verificados. Respostas antigas sem IDs
continuam aceitas, com a mesma contextualizacao construida pelo backend.

Texto livre fora do catalogo nao e publicado como conclusao. Isso e uma restricao
intencional: citar um ingrediente nao valida uma promessa clinica ou uma conclusao
quantitativa. O catalogo nao calcula metas, nao promete ganho muscular e nao define
limiares para baixo sodio. Lactase isolada nao confirma zero lactose. Uma declaracao
zero lactose e citada como declaracao da fonte, sem garantir seguranca para alergias.

Com basis unknown, os numeros nutricionais sao preservados no produto original,
mas nao sao usados em quantificacao, comparacao ou classificacao de teores nas
justificativas. Ainda e possivel informar que existe proteina declarada e citar
ingredientes/variedade. Com base conhecida, reproduz os valores originais sem
conversoes. Baixo sodio e uma preferencia avaliada por dados nutricionais, nunca
um conflito com um ingrediente generico como leite integral.

## Classificacao e contrato

O resultado deterministico prevalece e mantem seus conflitos, motivos e evidencias.
Sem conflito conhecido, perfis com alergias/restricoes permanecem attention, sem
promessa de seguranca. Insuficiencia nutricional do provedor nao apaga os fatos
qualitativos disponiveis. Um conflito de seguranca nao confirmado do provedor
continua insuficiente, mesmo que existam observacoes nutricionais aproveitaveis.

Status, summary, reasons, conflicts e evidence continuam nos mesmos DTOs publicos.
A separacao de responsabilidades e interna; nenhum novo campo publico e exigido.
nutrition_observation_ids e apenas parte do contrato interno do provedor.

A tela Android agora mostra conflitos e reasons simultaneamente, sem repetir
explicacoes identicas. Exige recompilar/reinstalar o aplicativo para essa alteracao
de exibicao; a personalizacao recebida em reasons ja funciona em clientes antigos
quando nao ha conflitos.

## Persistencia e cache

PERSONALIZATION_VERSION participa do hash, junto com versao de seguranca e perfil.
Novas capturas ignoram o cache anterior e persistem as observacoes validadas nas
colunas ja existentes. O historico da nova analise preserva reasons e conflicts.
Registros historicos antigos nao sao reescritos nem recalculados em GET: e preciso
reanalisar/recapturar para obter um resultado da nova politica. Nao ha migracao.

A integracao PostgreSQL usa apenas nutriIA_test, com verificacao de identidade e
rollback. Agora tambem valida o EAN 7896048706126 com alergia a gluten, preferencias
sem lactose/baixo sodio, cache e historico personalizados. OFF/Gemini sao simulados.


A avaliacao quantitativa por objetivo agora e definida em NUTRITION_GOAL_CRITERIA.md.
O catalogo inclui os calculos deterministas e dados faltantes dessa avaliacao, sem
sobrescrever as quantidades originais. Porcoes compativeis podem gerar valores
derivados identificados como tais; fibras sao um campo opcional adicional.
