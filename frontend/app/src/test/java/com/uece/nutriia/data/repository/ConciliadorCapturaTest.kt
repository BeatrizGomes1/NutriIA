package com.uece.nutriia.data.repository

import com.uece.nutriia.data.model.AnaliseDto
import com.uece.nutriia.data.model.CapturaResponse
import com.uece.nutriia.data.remote.ApiResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class ConciliadorCapturaTest {
    private fun resposta(id: String = "attempt", state: String = "completed", analysis: Boolean = true) =
        CapturaResponse("capture", "found", null,
            if (analysis) AnaliseDto("analysis", null, "attention", "Ninho", "Resumo", emptyList(), emptyList(), emptyList(), null) else null,
            id, "generated", state)

    @Test fun completedAttemptIsRecoveredAfterTimeout() = runBlocking {
        val result = ConciliadorCaptura.resolver("attempt") { ApiResult.Sucesso(resposta()) }
        assertTrue(result is ApiResult.Sucesso)
    }

    @Test fun pendingAttemptIsPolledUntilItsOwnResultCompletes() = runBlocking {
        var calls = 0
        val result = ConciliadorCaptura.resolver("attempt") {
            calls++
            ApiResult.Sucesso(if (calls == 1) resposta(state = "pending", analysis = false) else resposta())
        }
        assertEquals(2, calls)
        assertTrue(result is ApiResult.Sucesso)
    }

    @Test fun unrelatedOldResultNeverReplacesTheAttempt() = runBlocking {
        val result = ConciliadorCaptura.resolver("attempt") { ApiResult.Sucesso(resposta(id = "old-attempt")) }
        assertTrue(result is ApiResult.Erro && result.resultadoNaoConfirmado)
    }

    @Test fun missingOrPendingResultIsNotReportedAsDefinitiveFailure() = runBlocking {
        for (response in listOf(ApiResult.Sucesso(resposta(state = "pending", analysis = false)), ApiResult.Erro("missing", 404))) {
            val result = ConciliadorCaptura.resolver("attempt") { response }
            assertTrue(result is ApiResult.Erro && result.resultadoNaoConfirmado)
        }
    }

    @Test fun confirmedFailureIsDistinguishedFromUnknownOutcome() = runBlocking {
        val result = ConciliadorCaptura.resolver("attempt") { ApiResult.Sucesso(resposta(state = "failed", analysis = false)) }
        assertTrue(result is ApiResult.Erro && !result.resultadoNaoConfirmado)
    }

    @Test fun expiredSessionIsPreserved() = runBlocking {
        val result = ConciliadorCaptura.resolver("attempt") { ApiResult.Erro("expired", 401) }
        assertTrue(result is ApiResult.Erro && result.sessaoExpirada)
    }
}
