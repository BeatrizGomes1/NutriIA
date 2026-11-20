package com.uece.nutriia.data.remote

import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.model.RefreshRequest
import com.uece.nutriia.data.model.TokenResponse
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.POST
import java.io.IOException

/** Rota de refresh isolada, num cliente sem interceptor de auth (evita recursão). */
interface RefreshApi {
    @POST("auth/refresh")
    fun renovar(@Body corpo: RefreshRequest): Call<TokenResponse>
}

/**
 * Renova o access token com o refresh token (POST /auth/refresh).
 *
 * O backend rotaciona o refresh token a cada uso e invalida a sessão inteira se
 * um token já usado for reenviado. Por isso a renovação é sincronizada: se duas
 * requisições falharem juntas, só a primeira renova e a outra reaproveita o novo token.
 */
class RenovadorSessao(private val refreshApi: () -> RefreshApi) : Authenticator {

    /** Devolve um access token válido, renovando se preciso; null se a sessão acabou. */
    @Synchronized
    fun tokenValido(tokenQueFalhou: String? = null): String? {
        val atual = SessionManager.token
        // Outra thread já renovou depois da falha: usa o token novo.
        if (atual != null && atual != tokenQueFalhou && !SessionManager.acessoExpirado) return atual

        val refresh = SessionManager.refreshToken ?: return null
        val resposta = try {
            refreshApi().renovar(RefreshRequest(refresh)).execute()
        } catch (e: IOException) {
            // Sem conexão: mantém a sessão para tentar de novo depois.
            return null
        }
        return when {
            resposta.isSuccessful -> resposta.body()?.let {
                SessionManager.salvar(it)
                it.accessToken
            }
            resposta.code() == 401 -> {
                // Refresh expirado ou revogado: precisa entrar de novo.
                SessionManager.encerrar()
                null
            }
            else -> null
        }
    }

    // Chamado pelo OkHttp quando uma rota protegida responde 401.
    override fun authenticate(route: Route?, response: Response): Request? {
        val enviado = response.request.header("Authorization")?.removePrefix("Bearer ") ?: return null
        // Já tentou renovar nesta requisição: desiste para não entrar em loop.
        if (response.priorResponse != null) return null
        val novo = tokenValido(tokenQueFalhou = enviado) ?: return null
        return response.request.newBuilder()
            .header("Authorization", "Bearer $novo")
            .build()
    }
}
