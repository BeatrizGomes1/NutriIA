package com.uece.nutriia.data.repository

import com.uece.nutriia.data.model.CapturaResponse
import com.uece.nutriia.data.remote.ApiResult
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull

/** Reconciles the exact attempt; never substitutes a product's older history. */
object ConciliadorCaptura {
    suspend fun resolver(id: String, consultar: suspend () -> ApiResult<CapturaResponse>): ApiResult<CapturaResponse> {
        return withTimeoutOrNull(6000) {
            repeat(3) { index ->
                if (index > 0) delay(500)
                when (val resposta = consultar()) {
                    is ApiResult.Sucesso -> {
                        val dados = resposta.dados
                        if (dados.tentativaId == id) {
                            if (dados.processamento == "failed") return@withTimeoutOrNull ApiResult.Erro(
                                "Não foi possível concluir esta tentativa de análise.", 502)
                            if (dados.processamento == "completed" &&
                                (dados.analysis != null || dados.statusOrigem == "not_found"))
                                return@withTimeoutOrNull resposta
                        }
                    }
                    is ApiResult.Erro -> if (resposta.sessaoExpirada) return@withTimeoutOrNull resposta
                }
            }
            null
        } ?: ApiResult.Erro("O resultado desta tentativa ainda não foi confirmado. Confira o histórico antes de tentar novamente.",
            resultadoNaoConfirmado = true)
    }
}
