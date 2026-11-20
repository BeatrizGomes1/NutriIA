package com.uece.nutriia.data.model

import com.google.gson.annotations.SerializedName
import java.io.Serializable

data class EanCaptureRequest(
    val ean: String
)

data class InformacaoNutricionalDto(
    @SerializedName("calories_kcal") val calorias: Double?,
    @SerializedName("sugars_g") val acucares: Double?,
    @SerializedName("carbohydrates_g") val carboidratos: Double?,
    @SerializedName("protein_g") val proteinas: Double?,
    @SerializedName("sodium_mg") val sodio: Double?
) : Serializable

data class ProdutoDto(
    val id: String?,
    @SerializedName("name") val nome: String?,
    @SerializedName("brand") val marca: String?,
    val ean: String?,
    @SerializedName("ingredients") val ingredientes: List<String>?,
    @SerializedName("ingredients_text") val textoIngredientes: String?,
    @SerializedName("nutrition") val nutricao: InformacaoNutricionalDto?
) : Serializable

data class ConflitoDto(
    val term: String,
    val category: String,
    @SerializedName("profile_item") val itemPerfil: String,
    val evidence: String,
    @SerializedName("source_excerpt") val trechoOrigem: String?
) : Serializable

data class AnaliseDto(
    val id: String?,
    @SerializedName("created_at") val criadaEm: String?,
    val status: String,
    @SerializedName("product_name") val nomeProduto: String?,
    val summary: String,
    val reasons: List<String>?,
    val conflicts: List<ConflitoDto>?,
    val evidence: List<String>?,
    val disclaimer: String?
) : Serializable

/** Resposta de POST /profiles/{id}/captures/ean. */
data class CapturaResponse(
    @SerializedName("capture_id") val capturaId: String,
    @SerializedName("source_status") val statusOrigem: String,
    val product: ProdutoDto?,
    val analysis: AnaliseDto?
)

/** Item de GET /profiles/{id}/history/captures. */
data class CapturaHistoricoResponse(
    @SerializedName("capture_id") val capturaId: String,
    @SerializedName("captured_at") val capturadaEm: String,
    val ean: String?,
    @SerializedName("source_status") val statusOrigem: String,
    val product: ProdutoDto?,
    val analysis: AnaliseDto?
)

/** Valores de `source_status` devolvidos pelo backend. */
object StatusOrigem {
    const val ENCONTRADO = "found"
    const val NAO_ENCONTRADO = "not_found"
}

/** Valores de `status` da análise devolvidos pelo backend. */
enum class StatusAnalise(val valorApi: String) {
    RECOMENDADO("recommended"),
    ATENCAO("attention"),
    NAO_RECOMENDADO("not_recommended"),
    INSUFICIENTE("insufficient_information"),
    NAO_ENCONTRADO("not_found");

    companion object {
        fun deApi(valor: String?): StatusAnalise =
            entries.firstOrNull { it.valorApi == valor } ?: INSUFICIENTE
    }
}
