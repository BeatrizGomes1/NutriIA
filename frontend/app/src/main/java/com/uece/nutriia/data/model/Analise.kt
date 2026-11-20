package com.uece.nutriia.data.model

import java.io.Serializable

/** Item exibido no histórico, na tela inicial e no resultado. */
data class Analise(
    val nome: String,
    val marca: String,
    val dataRelativa: String,
    val status: StatusAnalise,
    val thumbPeach: Boolean = false,
    // Dados completos para abrir o resultado sem escanear de novo.
    val ean: String? = null,
    val produto: ProdutoDto? = null,
    val analise: AnaliseDto? = null
) : Serializable {
    val recomendado: Boolean get() = status == StatusAnalise.RECOMENDADO
    val naoRecomendado: Boolean get() = status == StatusAnalise.NAO_RECOMENDADO
}
