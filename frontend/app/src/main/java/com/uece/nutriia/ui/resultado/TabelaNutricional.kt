package com.uece.nutriia.ui.resultado

import com.uece.nutriia.data.model.InformacaoNutricionalDto
import java.text.NumberFormat
import java.util.Locale

data class TabelaNutricional(val referencia: String, val linhas: List<Pair<String, String>>) {
    companion object {
        fun de(dados: InformacaoNutricionalDto?): TabelaNutricional? {
            dados ?: return null
            val formato = NumberFormat.getNumberInstance(Locale.forLanguageTag("pt-BR")).apply {
                maximumFractionDigits = 3
            }
            val referencia = when (dados.basis) {
                "per_100g" -> "Por 100 g"
                "per_100ml" -> "Por 100 ml"
                "per_serving" -> {
                    val quantidade = dados.porcao ?: return null
                    if (!quantidade.isFinite() || quantidade <= 0 || dados.unidadePorcao !in setOf("g", "ml")) return null
                    "Porção de ${formato.format(quantidade)} ${dados.unidadePorcao}"
                }
                else -> return null
            }
            val linhas = listOf(
                Triple("Proteínas", dados.proteinas, "g"), Triple("Energia", dados.calorias, "kcal"),
                Triple("Carboidratos", dados.carboidratos, "g"), Triple("Fibras", dados.fibras, "g"),
                Triple("Sódio", dados.sodio, "mg"), Triple("Açúcares", dados.acucares, "g")
            ).mapNotNull { (nome, valor, unidade) ->
                valor?.takeIf { it.isFinite() && it >= 0 }?.let { nome to "${formato.format(it)} $unidade" }
            }
            return if (linhas.isEmpty()) null else TabelaNutricional(referencia, linhas)
        }
    }
}
