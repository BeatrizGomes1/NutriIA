package com.uece.nutriia.ui.resultado

import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.model.ConflitoDto
import com.uece.nutriia.data.model.StatusAnalise
import java.text.Normalizer
import java.util.Locale

/** Presentation only: never changes API status, conflicts, evidence or ingredients. */
data class AlertaResultado(
    val titulo: String,
    val descricao: String,
    val originais: List<String>,
    val confirmado: Boolean,
    val possivel: Boolean
)

data class ResultadoPresentation(
    val resumo: String,
    val alertas: List<AlertaResultado>,
    val motivos: List<String>,
    val informacoesNutricionais: List<String>,
    val motivosVisiveis: List<String> = emptyList(),
    val detalhes: List<String> = emptyList(),
    val tabela: TabelaNutricional? = null
)

object ApresentadorResultado {
    private fun normalizar(value: String) = Normalizer.normalize(value, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "").lowercase(Locale.ROOT)
        .replace(Regex("[^a-z0-9]+"), " ").trim()

    private val nomes = mapOf(
        "milk" to "leite", "leite" to "leite", "milk protein" to "leite",
        "proteina do leite" to "leite", "proteinas do leite" to "leite", "aplv" to "leite",
        "soy" to "soja", "soya" to "soja", "soybeans" to "soja", "soja" to "soja",
        "peanut" to "amendoim", "peanuts" to "amendoim", "amendoim" to "amendoim",
        "wheat" to "trigo", "trigo" to "trigo", "gluten" to "gl\u00faten",
        "lactose" to "lactose", "casein" to "case\u00edna", "caseina" to "case\u00edna",
        "whey" to "soro de leite", "soro de leite" to "soro de leite",
        "sugar" to "a\u00e7\u00facar", "acucar" to "a\u00e7\u00facar"
    )

    private fun nome(conflito: ConflitoDto): String {
        val original = conflito.itemPerfil.ifBlank { conflito.term }.trim()
        val alvo = normalizar(original).replace(Regex(
            "^(?:alergia (?:a|ao|as|aos)|intolerancia a|sem|evitar|evito|restricao a) +"), "")
        return nomes[alvo] ?: original
    }

    private fun possivel(conflito: ConflitoDto): Boolean {
        val source = normalizar(conflito.trechoOrigem.orEmpty())
        return normalizar(conflito.evidence).startsWith("possivel contaminacao cruzada") ||
            Regex("\\b(?:pode conter|podem conter|may contain|tracos de|traces of|produzido em|fabricado em|produced in|manufactured in|shared equipment)\\b")
                .containsMatchIn(source)
    }

    // Only known, noncritical nutritional explanations are merged by topic.
    // Allergy alerts and unfamiliar warnings never enter this reducer.
    private fun assunto(texto: String): String? {
        val t = normalizar(texto)
        return when {
            t.startsWith("falta informar se os valores") ||
                t.startsWith("falta confirmar a referencia nutricional") ||
                t.startsWith("a referencia dos valores nutricionais e desconhecida") ||
                t.startsWith("detalhe da avaliacao falta confirmar a referencia") -> "referencia"
            t.startsWith("ha proteina informada") || t.startsWith("o rotulo informa proteina relevante") -> "proteina_generica"
            t.startsWith("o produto declara ser sem lactose") -> "sem_lactose"
            t.startsWith("seu objetivo e perder peso") -> "objetivo_peso"
            t.startsWith("nao identificar conflitos") || t.startsWith("a ausencia de conflito identificado") ||
                t.startsWith("nenhum conflito") || t.startsWith("nao foram identificados conflitos") ||
                t.startsWith("nao ha conflitos") || t.startsWith("a cobertura") -> "ressalva_generica"
            else -> null
        }
    }

    private fun detalhesUteis(candidatos: List<String>, exibidos: List<String>): List<String> {
        val assuntosExibidos = exibidos.mapNotNull(::assunto).toSet()
        val resumoEsclareceProteinasDoLeite = exibidos.any {
            normalizar(it).contains("zero lactose nao significa livre de proteinas do leite")
        }
        val temProteinaQuantificada = (candidatos + exibidos).any {
            val t = normalizar(it)
            Regex("[0-9]").containsMatchIn(it) && (t.contains("g de proteinas") ||
                t.startsWith("avaliacao para ganho de massa") && t.contains("energia") && it.contains("%"))
        }
        val vistos = exibidos.map(::normalizar).toMutableSet()
        val assuntosVistos = assuntosExibidos.toMutableSet()
        val detalhes = mutableListOf<String>()
        val ressalvas = mutableListOf<String>()
        candidatos.forEach { texto ->
            val tema = assunto(texto)
            if (tema == "sem_lactose" && resumoEsclareceProteinasDoLeite) {
                // The critical distinction is already explicit in the summary.
            } else if (tema == "sem_lactose" && tema in assuntosExibidos) {
                val aviso = "Sem lactose n\u00e3o significa livre de prote\u00ednas do leite."
                if (vistos.add(normalizar(aviso))) detalhes.add(aviso)
            } else if (tema == "ressalva_generica") {
                if (!normalizar(texto).startsWith("a cobertura")) ressalvas.add(texto)
            } else if (!(tema == "proteina_generica" && temProteinaQuantificada) &&
                normalizar(texto) !in vistos && (tema == null || tema !in assuntosVistos)) {
                detalhes.add(if (tema == "referencia")
                    "N\u00e3o foi poss\u00edvel confirmar se os valores s\u00e3o por 100 g, por 100 ml ou por por\u00e7\u00e3o." else texto)
                vistos.add(normalizar(texto))
                if (tema != null) assuntosVistos.add(tema)
            }
        }
        // Boilerplate alone does not justify an otherwise empty details section.
        if (detalhes.isNotEmpty()) ressalvas.firstOrNull()?.let { detalhes.add(it) }
        return detalhes
    }

    fun apresentar(analise: Analise): ResultadoPresentation {
        val tabela = TabelaNutricional.de(analise.produto?.nutricao)
        val conflitos = analise.analise?.conflicts.orEmpty()
        val seguranca = conflitos.filter { it.category in setOf("allergy", "restriction") }
        // Group by declared target, not ingredient: lactose and milk protein
        // remain distinct, while milk and leite for the same target coalesce.
        val alertas = seguranca.groupBy { normalizar(nome(it)) }.values.map { grupo ->
            val label = nome(grupo.first())
            val confirmado = grupo.any { !possivel(it) && !it.trechoOrigem.isNullOrBlank() }
            val possivel = grupo.any(::possivel)
            val allergy = grupo.any { it.category == "allergy" }
            val restriction = grupo.any { it.category == "restriction" }
            val descricao = buildList {
                if (confirmado) add(when {
                    allergy && restriction -> "Conflito com a alergia e a restri\u00e7\u00e3o informadas no seu perfil."
                    allergy -> "Conflito com a alergia informada no seu perfil."
                    else -> "Conflito com a restri\u00e7\u00e3o informada no seu perfil."
                })
                if (possivel) add(if (confirmado) "O r\u00f3tulo tamb\u00e9m informa poss\u00edvel contamina\u00e7\u00e3o cruzada."
                                 else "O r\u00f3tulo informa possibilidade de contamina\u00e7\u00e3o, sem confirmar presen\u00e7a.")
                if (!confirmado && !possivel) add("H\u00e1 um alerta relacionado ao seu perfil. Confira as informa\u00e7\u00f5es originais.")
            }.joinToString(" ")
            AlertaResultado(
                titulo = when {
                    confirmado && normalizar(label) in nomes.values.map(::normalizar) -> "Cont\u00e9m $label"
                    confirmado -> "Conflito com: $label"
                    possivel -> "Pode conter $label"
                    else -> "Alerta sobre $label"
                },
                descricao = descricao,
                originais = grupo.flatMap { listOfNotNull(it.trechoOrigem, it.evidence) }
                    .filter { it.isNotBlank() }.distinct(),
                confirmado = confirmado, possivel = possivel
            )
        }
        val confirmado = alertas.any { it.confirmado }
        val motivos = mutableListOf<String>()
        val extras = mutableListOf<String>()
        if (analise.origemAnalise == "cache") extras.add(
            "Resultado reutilizado de uma análise válida para os mesmos dados e perfil.")
        val temIngredientes = !analise.produto?.textoIngredientes.isNullOrBlank() ||
            !analise.produto?.ingredientes.isNullOrEmpty()
        val ingredientesOriginais = analise.produto?.textoIngredientes?.takeIf { it.isNotBlank() }
            ?: analise.produto?.ingredientes.orEmpty().joinToString(", ")
        val ingredientesNormalizados = normalizar(ingredientesOriginais)
        val explicacoes = seguranca.map { normalizar(it.evidence) }.toSet()
        val razoes = analise.analise?.reasons.orEmpty() +
            conflitos.filter { it.category !in setOf("allergy", "restriction") }.map { it.evidence }
        razoes.distinctBy(::normalizar).forEach { original ->
            val text = normalizar(original)
            val fatoNutricional = Regex("^o rotulo informa [0-9]+(?: [0-9]+)?(?:e [0-9]+)? (?:g de (?:proteinas|fibras|acucares|carboidratos)|mg de sodio|kcal de energia) por (?:100 g|100 ml|porcao)$")
                .matches(text)
            when {
                text in explicacoes -> Unit // Already represented by an alert, details remain accessible.
                confirmado && (text.startsWith("nenhum conflito") ||
                    text.startsWith("nao foram identificados conflitos") ||
                    text.startsWith("nao foi identificado conflito") ||
                    text.startsWith("nao ha conflitos")) -> Unit
                text.startsWith("a ausencia de conflito identificado") -> {
                    if (!confirmado && alertas.isEmpty()) motivos.add(
                        "N\u00e3o identificar conflitos n\u00e3o garante que o produto seja seguro para voc\u00ea.")
                }
                text.startsWith("a cobertura das regras e dos dados") -> Unit
                temIngredientes && (text == ingredientesNormalizados ||
                    normalizar(original.substringAfter(":", "")) == ingredientesNormalizados &&
                    (text.startsWith("ingredientes informados") || text.startsWith("trecho disponivel de ingredientes"))) -> Unit
                text.startsWith("para sua restricao de lactose") -> motivos.add(original)
                tabela == null && Regex("[0-9]").containsMatchIn(original) &&
                    (fatoNutricional || text.startsWith("avaliacao para") ||
                        text.startsWith("detalhe da avaliacao")) -> extras.add(
                    "Falta confirmar a refer\u00eancia nutricional.")
                tabela != null && analise.produto?.nutricao?.basis == "per_serving" &&
                    text.startsWith("detalhe da avaliacao na porcao declarada") -> Unit
                text.startsWith("falta confirmar a referencia nutricional") -> extras.add(original)
                text.startsWith("avaliacao para ganho de massa") || text.startsWith("avaliacao para perda de peso") ||
                    text.startsWith("detalhe da avaliacao") -> extras.add(original)
                text.startsWith("ha proteina informada no rotulo") -> extras.add(
                    "H\u00e1 prote\u00edna informada no r\u00f3tulo, relevante para seu objetivo de ganho de massa muscular. Isso n\u00e3o basta para avaliar sua alimenta\u00e7\u00e3o.")
                text.startsWith("seu objetivo e ganho de massa muscular") -> extras.add(
                    "Faltam dados de prote\u00edna para avaliar seu objetivo de ganho de massa muscular.")
                text.startsWith("seu objetivo e perda de peso") -> extras.add(
                    "Seu objetivo \u00e9 perder peso. O produto sozinho n\u00e3o permite avaliar sua alimenta\u00e7\u00e3o.")
                Regex("^o produto declara (?:zero lactose|sem lactose|lactose free)\\b").containsMatchIn(text) -> extras.add(
                    "O produto declara ser sem lactose. Isso n\u00e3o significa que seja livre de prote\u00ednas do leite.")
                (text.startsWith("nao ha declaracao explicita disponivel para confirmar") || text.startsWith("ha leite declarado na fonte")) && text.contains("lactose") -> extras.add(
                    (if (text.startsWith("ha leite declarado na fonte"))
                        "H\u00e1 leite declarado, mas n\u00e3o foi poss\u00edvel confirmar sua prefer\u00eancia sem lactose. "
                     else "N\u00e3o foi poss\u00edvel confirmar sua prefer\u00eancia sem lactose nos dados dispon\u00edveis. ") +
                        "A lactase, sozinha, n\u00e3o confirma isso.")
                text.startsWith("para a preferencia") && text.contains("sodio") -> extras.add(
                    "Ainda n\u00e3o \u00e9 poss\u00edvel avaliar a prefer\u00eancia por baixo s\u00f3dio.")
                text.startsWith("a preferencia") && text.contains("sodio") -> extras.add(
                    "A prefer\u00eancia por baixo s\u00f3dio depende dos valores do r\u00f3tulo.")
                text.startsWith("a referencia dos valores nutricionais e desconhecida") -> extras.add(
                    "Falta informar se os valores s\u00e3o por 100 g, 100 ml ou por por\u00e7\u00e3o.")
                fatoNutricional && tabela != null -> Unit
                fatoNutricional -> extras.add(original.removePrefix("O r\u00f3tulo informa ")
                    .replace(Regex("(?<=\\d)\\.(?=\\d)"), ","))
                text.startsWith("a preferencia declarada e") -> extras.add(original)
                text.startsWith("uma conclusao de seguranca do provedor") -> motivos.add(
                    "N\u00e3o foi poss\u00edvel confirmar uma informa\u00e7\u00e3o de seguran\u00e7a da an\u00e1lise.")
                // Never drop unfamiliar safety reasons or silently truncate them.
                else -> motivos.add(original)
            }
        }
        val resumo = if (analise.analise == null && analise.processamento in setOf("pending", "failed", "unlinked")) {
            when (analise.processamento) {
                "pending" -> "O resultado desta tentativa ainda não foi confirmado."
                "failed" -> "Esta tentativa não foi concluída."
                else -> "Esta captura antiga não tem uma análise vinculada à tentativa."
            }
        } else when (analise.status) {
            StatusAnalise.NAO_RECOMENDADO -> if (confirmado)
                "O produto cont\u00e9m ingredientes incompat\u00edveis com seu perfil."
                else "O resultado indica incompatibilidade com seu perfil. Confira os motivos."
            StatusAnalise.INSUFICIENTE -> if (confirmado)
                "H\u00e1 um conflito identificado e tamb\u00e9m informa\u00e7\u00f5es incompletas."
                else "Faltam informa\u00e7\u00f5es para concluir a an\u00e1lise com seguran\u00e7a."
            StatusAnalise.ATENCAO -> if (alertas.any { it.possivel })
                "O r\u00f3tulo informa poss\u00edvel contamina\u00e7\u00e3o por um item do seu perfil."
                else "Veja os pontos que merecem aten\u00e7\u00e3o no seu perfil."
            StatusAnalise.RECOMENDADO -> "An\u00e1lise dispon\u00edvel para o seu perfil."
            StatusAnalise.NAO_ENCONTRADO -> "O produto n\u00e3o foi encontrado. Tente enviar uma foto do r\u00f3tulo."
        }
        val motivosUnicos = motivos.distinctBy(::normalizar)
        val extrasUnicos = extras.distinctBy(::normalizar)
        val avisosLactose = extrasUnicos.filter { normalizar(it).contains("confirmar sua preferencia sem lactose") }
        val avisosAlimentares = (motivosUnicos.filter { normalizar(it).startsWith("para sua restricao de lactose") } + avisosLactose).distinct()

        fun secundario(texto: String): Boolean {
            val t = normalizar(texto)
            return t.startsWith("nao identificar conflitos") || t.startsWith("nenhum conflito") ||
                t.startsWith("nao foram identificados conflitos") || t.startsWith("nao ha conflitos") ||
                t.startsWith("a cobertura")
        }
        // Unfamiliar reasons stay visible: a display limit must never hide a
        // missing-data warning or a newly introduced safety alert.
        val criticos = motivosUnicos.filterNot(::secundario)
        val usadosNoResumo = mutableSetOf<String>()
        val resumoPersonalizado = if (alertas.isEmpty() && analise.status in setOf(
                StatusAnalise.ATENCAO, StatusAnalise.RECOMENDADO)) {
            val frases = mutableListOf<String>()
            if (avisosAlimentares.isNotEmpty()) {
                frases.add("N\u00e3o foi poss\u00edvel confirmar se o produto atende ao seu perfil em rela\u00e7\u00e3o \u00e0 lactose.")
            }
            if (frases.isEmpty()) extrasUnicos.firstOrNull { normalizar(it).startsWith("avaliacao para") }?.let {
                frases.add(it)
                usadosNoResumo.add(it)
            }
            if (frases.isEmpty()) extrasUnicos.firstOrNull {
                Regex("^[0-9].*g de proteinas por").containsMatchIn(normalizar(it))
            }?.let {
                frases.add(it)
                usadosNoResumo.add(it)
            }
            if (frases.isEmpty()) extrasUnicos.firstOrNull { it.startsWith("H\u00e1 prote\u00edna informada") }?.let {
                frases.add("O r\u00f3tulo informa prote\u00edna, relevante para seu objetivo de ganho de massa muscular.")
                usadosNoResumo.add(it)
            }
            if (frases.isEmpty()) extrasUnicos.firstOrNull { it.startsWith("Faltam dados de prote\u00edna") }?.let {
                frases.add(it)
                usadosNoResumo.add(it)
            }
            if (frases.isEmpty()) extrasUnicos.firstOrNull { it.startsWith("Seu objetivo \u00e9 perder peso") }?.let {
                frases.add("Seu objetivo \u00e9 perder peso, mas o produto sozinho n\u00e3o permite avaliar sua alimenta\u00e7\u00e3o.")
                usadosNoResumo.add(it)
            }
            extrasUnicos.firstOrNull { it.startsWith("O produto declara ser sem lactose") }?.let {
                frases.add("O produto declara ser sem lactose.")
                usadosNoResumo.add(it)
            }
            if (frases.isEmpty()) extrasUnicos.firstOrNull { it.contains("prefer\u00eancia por baixo s\u00f3dio") }?.let {
                frases.add(it)
                usadosNoResumo.add(it)
            }
            frases.take(2).joinToString(" ").ifBlank { resumo }
        } else if (confirmado && analise.status == StatusAnalise.NAO_RECOMENDADO) {
            val alergiaLeite = seguranca.any { normalizar(nome(it)) == "leite" && it.category == "allergy" }
            val restricaoLactose = seguranca.any { normalizar(nome(it)) == "lactose" && it.category == "restriction" }
            when {
                alergiaLeite -> "H\u00e1 conflito com sua alergia ao leite." +
                    if (extrasUnicos.any { it.startsWith("O produto declara ser sem lactose") })
                        " Zero lactose n\u00e3o significa livre de prote\u00ednas do leite." else ""
                restricaoLactose -> if (seguranca.any { normalizar(it.itemPerfil) == "intolerancia a lactose" })
                    "H\u00e1 conflito com a intoler\u00e2ncia \u00e0 lactose informada no seu perfil. Isso \u00e9 diferente de alergia \u00e0 prote\u00edna do leite."
                    else "H\u00e1 conflito com sua restri\u00e7\u00e3o \u00e0 lactose. Isso \u00e9 diferente de alergia \u00e0 prote\u00edna do leite."
                else -> resumo
            }
        } else resumo
        val temProteinaQuantificada = extrasUnicos.any {
            Regex("[0-9].*g de proteinas por").containsMatchIn(normalizar(it)) ||
                normalizar(it).startsWith("avaliacao para ganho de massa") && it.contains("%")
        }
        val candidatos = if (alertas.isNotEmpty() || analise.status == StatusAnalise.INSUFICIENTE)
            emptyList() else extrasUnicos.filterNot { it in usadosNoResumo ||
                temProteinaQuantificada && assunto(it) == "proteina_generica" ||
                assunto(it) == "referencia" || normalizar(it).startsWith("detalhe da avaliacao")
                || normalizar(it).startsWith("resultado reutilizado")
            }.sortedBy { if (Regex("^[0-9].*g de proteinas por").containsMatchIn(normalizar(it))) 0 else 1 }
        val criticosSemRepeticao = criticos.filterNot { normalizar(it) == normalizar(resumoPersonalizado) }
        val avisosVisiveis = (criticosSemRepeticao + avisosLactose).distinct()
        val visiveis = avisosVisiveis + candidatos.filterNot { it in avisosVisiveis }.take((2 - avisosVisiveis.size).coerceAtLeast(0))
        val detalhes = detalhesUteis(
            motivosUnicos.filterNot { it in visiveis } + extrasUnicos.filterNot { it in visiveis } +
                razoes.filter { normalizar(it).startsWith("a cobertura das regras") },
            usadosNoResumo.toList() + visiveis + listOf(resumoPersonalizado)
        )
        return ResultadoPresentation(resumoPersonalizado, alertas, motivosUnicos, extrasUnicos, visiveis, detalhes, tabela)
    }
}
