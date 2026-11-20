package com.uece.nutriia.data.repository

import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.model.CapturaHistoricoResponse
import com.uece.nutriia.data.model.CapturaResponse
import com.uece.nutriia.data.model.EanCaptureRequest
import com.uece.nutriia.data.model.StatusAnalise
import com.uece.nutriia.data.model.StatusOrigem
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.remote.NutriIaApi
import com.uece.nutriia.data.remote.RetrofitClient
import com.uece.nutriia.data.remote.chamarApi
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.text.ParseException
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

/** Captura de produtos por EAN ou foto do rótulo (consulta + análise por IA) e histórico. */
class AnaliseRepository(private val api: NutriIaApi = RetrofitClient.api) {

    suspend fun analisarEan(ean: String): ApiResult<CapturaResponse> {
        val userId = SessionManager.userId ?: return ApiResult.Erro("Sessão não encontrada.", 401)
        return chamarApi(
            mapOf(
                422 to "Código de barras inválido. Use apenas números (8 a 32 dígitos).",
                502 to "Não foi possível consultar o produto ou gerar a análise agora. Tente novamente."
            )
        ) { api.capturarEan(userId, EanCaptureRequest(ean)) }
    }

    /** Envia a foto do rótulo (JPEG) para o backend extrair os dados e analisar. */
    suspend fun analisarFotoRotulo(foto: File): ApiResult<CapturaResponse> {
        val userId = SessionManager.userId ?: return ApiResult.Erro("Sessão não encontrada.", 401)
        val parte = MultipartBody.Part.createFormData(
            "file",
            foto.name,
            foto.asRequestBody("image/jpeg".toMediaType())
        )
        return chamarApi(
            mapOf(
                400 to "Não foi possível ler essa imagem. Tente outra foto.",
                413 to "A foto é grande demais. Tente novamente.",
                415 to "Formato de imagem não suportado. Use JPEG, PNG ou WEBP.",
                502 to "Não foi possível ler o rótulo agora (a análise por foto usa o Gemini). Tente novamente.",
                503 to "A análise por foto não está disponível no servidor no momento."
            )
        ) { api.capturarFotoRotulo(userId, parte) }
    }

    suspend fun historico(limite: Int = 50): ApiResult<List<Analise>> {
        val userId = SessionManager.userId ?: return ApiResult.Erro("Sessão não encontrada.", 401)
        return when (val resultado = chamarApi { api.historicoCapturas(userId, limite) }) {
            is ApiResult.Sucesso -> ApiResult.Sucesso(resultado.dados.mapIndexed(::paraAnalise))
            is ApiResult.Erro -> resultado
        }
    }

    private fun paraAnalise(indice: Int, item: CapturaHistoricoResponse): Analise {
        val status = if (item.statusOrigem == StatusOrigem.NAO_ENCONTRADO) {
            StatusAnalise.NAO_ENCONTRADO
        } else {
            StatusAnalise.deApi(item.analysis?.status)
        }
        return Analise(
            nome = item.product?.nome
                ?: item.analysis?.nomeProduto
                ?: item.ean?.let { "Produto $it" }
                ?: "Produto lido pelo rótulo",
            marca = item.product?.marca ?: item.ean.orEmpty(),
            dataRelativa = dataRelativa(item.capturadaEm),
            status = status,
            thumbPeach = indice % 3 == 2,
            ean = item.ean,
            produto = item.product,
            analise = item.analysis
        )
    }

    companion object {
        // Ex.: 2026-11-04T12:34:56.123456Z ou 2026-11-04T12:34:56+00:00
        private val ISO = Regex("""^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$""")

        /** "hoje", "ontem" ou "12 mai", como no layout. */
        fun dataRelativa(iso: String): String {
            val instante = paraMillis(iso) ?: return ""
            val data = Calendar.getInstance().apply { timeInMillis = instante }
            val hoje = Calendar.getInstance()
            val ontem = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, -1) }
            return when {
                mesmoDia(data, hoje) -> "hoje"
                mesmoDia(data, ontem) -> "ontem"
                else -> SimpleDateFormat("d MMM", Locale("pt", "BR")).format(data.time).replace(".", "")
            }
        }

        private fun paraMillis(iso: String): Long? {
            val partes = ISO.matchEntire(iso.trim()) ?: return null
            val (dataHora, fuso) = partes.destructured
            val formato = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
                timeZone = when {
                    fuso.isEmpty() || fuso == "Z" -> TimeZone.getTimeZone("UTC")
                    else -> TimeZone.getTimeZone("GMT" + fuso.replace(Regex("""(\d{2})(\d{2})$"""), "$1:$2"))
                }
            }
            return try {
                formato.parse(dataHora)?.time
            } catch (e: ParseException) {
                null
            }
        }

        private fun mesmoDia(a: Calendar, b: Calendar) =
            a.get(Calendar.YEAR) == b.get(Calendar.YEAR) &&
                a.get(Calendar.DAY_OF_YEAR) == b.get(Calendar.DAY_OF_YEAR)
    }
}
