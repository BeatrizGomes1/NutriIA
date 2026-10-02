package com.uece.nutriia.data.model

data class Analise(
    val nome: String,
    val marca: String,
    val dataRelativa: String,
    val recomendado: Boolean,
    val thumbPeach: Boolean = false
)
