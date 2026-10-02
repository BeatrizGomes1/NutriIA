package com.uece.nutriia.data.mock

import com.uece.nutriia.data.model.Analise

object MockData {
    const val NOME_USUARIA = "Larissa"

    val analises = listOf(
        Analise(
            nome = "Iogurte sabor Morango",
            marca = "Verde Campo",
            dataRelativa = "hoje",
            recomendado = false
        ),
        Analise(
            nome = "Granola sem açúcar",
            marca = "Mãe Terra",
            dataRelativa = "ontem",
            recomendado = true
        ),
        Analise(
            nome = "Bebida de aveia",
            marca = "A Tal da Castanha",
            dataRelativa = "12 mai",
            recomendado = true,
            thumbPeach = true
        )
    )
}
