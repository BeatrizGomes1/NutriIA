package com.uece.nutriia.data.remote

import com.google.gson.JsonParser
import retrofit2.Response
import java.io.IOException
import kotlin.coroutines.cancellation.CancellationException

/** Resultado de uma chamada ao backend, já com mensagem pronta para a tela. */
sealed class ApiResult<out T> {
    data class Sucesso<T>(val dados: T) : ApiResult<T>()
    data class Erro(val mensagem: String, val codigo: Int? = null) : ApiResult<Nothing>() {
        /** Token ausente, inválido ou expirado: o usuário precisa entrar de novo. */
        val sessaoExpirada: Boolean get() = codigo == 401
    }
}

private const val ERRO_CONEXAO = "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente."
private const val ERRO_GENERICO = "Algo deu errado. Tente novamente em instantes."

/** Executa a chamada e traduz falhas de rede e respostas de erro do FastAPI. */
suspend fun <T> chamarApi(
    mensagensPorCodigo: Map<Int, String> = emptyMap(),
    chamada: suspend () -> Response<T>
): ApiResult<T> {
    val resposta = try {
        chamada()
    } catch (e: CancellationException) {
        throw e
    } catch (e: IOException) {
        return ApiResult.Erro(ERRO_CONEXAO)
    } catch (e: RuntimeException) {
        // Ex.: JSON inesperado na resposta.
        return ApiResult.Erro(ERRO_GENERICO)
    }

    if (resposta.isSuccessful) {
        val corpo = resposta.body() ?: return ApiResult.Erro(ERRO_GENERICO, resposta.code())
        return ApiResult.Sucesso(corpo)
    }

    val codigo = resposta.code()
    val mensagem = mensagensPorCodigo[codigo] ?: mensagemPadrao(codigo, lerDetalhe(resposta))
    return ApiResult.Erro(mensagem, codigo)
}

private fun mensagemPadrao(codigo: Int, detalhe: String?): String = when (codigo) {
    401 -> "Sua sessão expirou. Entre novamente."
    404 -> "Não encontramos o que você procurou."
    409 -> "Esses dados já estão em uso."
    422 -> detalhe?.let { "Dados inválidos: $it" } ?: "Confira os dados informados."
    502 -> "Um serviço externo não respondeu. Tente novamente em instantes."
    503 -> "O servidor está indisponível no momento."
    else -> ERRO_GENERICO
}

// O FastAPI devolve {"detail": "texto"} ou {"detail": [{"msg": "...", ...}]}.
private fun lerDetalhe(resposta: Response<*>): String? = try {
    val texto = resposta.errorBody()?.string().orEmpty()
    val detalhe = JsonParser.parseString(texto).asJsonObject.get("detail")
    when {
        detalhe == null || detalhe.isJsonNull -> null
        detalhe.isJsonPrimitive -> detalhe.asString
        detalhe.isJsonArray -> detalhe.asJsonArray.joinToString("; ") {
            it.asJsonObject.get("msg")?.asString.orEmpty()
        }
        else -> null
    }
} catch (e: Exception) {
    null
}
