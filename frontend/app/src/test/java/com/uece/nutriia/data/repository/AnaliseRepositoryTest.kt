package com.uece.nutriia.data.repository

import com.uece.nutriia.data.model.*
import com.uece.nutriia.data.remote.*
import kotlinx.coroutines.runBlocking
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Response
import java.lang.reflect.Proxy
import java.net.SocketTimeoutException
import kotlin.coroutines.Continuation
import kotlin.coroutines.intrinsics.COROUTINE_SUSPENDED

class AnaliseRepositoryTest {
    private fun api(handler: (String, Array<out Any?>) -> Any?): NutriIaApi =
        Proxy.newProxyInstance(NutriIaApi::class.java.classLoader, arrayOf(NutriIaApi::class.java)) {
            _, method, args -> handler(method.name, args ?: emptyArray())
        } as NutriIaApi

    private fun complete() = CapturaResponse("capture", "found", null,
        AnaliseDto("analysis", null, "attention", "Ninho", "Resumo", emptyList(), emptyList(), emptyList(), null),
        "attempt", "generated", "completed")

    @Test fun timeoutRecoversExactAttemptWithoutRepeatingPost() = runBlocking {
        var posts = 0; var gets = 0
        val service = api { name, args ->
            when (name) {
                "capturarEan" -> {
                    posts++
                    assertEquals("attempt", (args[1] as EanCaptureRequest).tentativaId)
                    @Suppress("UNCHECKED_CAST")
                    val continuation = args.last() as Continuation<Any?>
                    continuation.resumeWith(Result.failure(SocketTimeoutException("simulated")))
                    COROUTINE_SUSPENDED
                }
                "resultadoTentativa" -> {
                    gets++; assertEquals("attempt", args[1]); Response.success(complete())
                }
                else -> error("Unexpected API method")
            }
        }
        val result = AnaliseRepository(service) { "user" }.analisarEan("7891000325858", "attempt")
        assertTrue(result is ApiResult.Sucesso)
        assertEquals(1, posts); assertEquals(1, gets)
    }

    @Test fun definitiveValidationFailureDoesNotPollOrRetry() = runBlocking {
        var calls = 0
        val service = api { name, _ ->
            calls++; assertEquals("capturarEan", name)
            Response.error<CapturaResponse>(422, "{}".toResponseBody())
        }
        val result = AnaliseRepository(service) { "user" }.analisarEan("bad", "attempt")
        assertTrue(result is ApiResult.Erro && !result.resultadoNaoConfirmado && result.codigo == 422)
        assertEquals(1, calls)
    }

    @Test fun pendingResponseIsReconciledInsteadOfOpeningAnEmptyResult() = runBlocking {
        val service = api { name, _ -> Response.success(
            if (name == "capturarEan") complete().copy(analysis = null, processamento = "pending") else complete()) }
        val result = AnaliseRepository(service) { "user" }.analisarEan("7891000325858", "attempt")
        assertTrue(result is ApiResult.Sucesso && result.dados.analysis != null)
    }
}
