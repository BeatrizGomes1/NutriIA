package com.uece.nutriia.data.repository

import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.model.LoginRequest
import com.uece.nutriia.data.model.MensagemResponse
import com.uece.nutriia.data.model.PerfilRequest
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.model.RecuperarSenhaRequest
import com.uece.nutriia.data.model.RedefinirSenhaRequest
import com.uece.nutriia.data.model.TokenResponse
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.remote.NutriIaApi
import com.uece.nutriia.data.remote.RetrofitClient
import com.uece.nutriia.data.remote.chamarApi

class AuthRepository(private val api: NutriIaApi = RetrofitClient.api) {

    suspend fun entrar(email: String, senha: String): ApiResult<PerfilResponse> {
        val resultado = chamarApi(mapOf(401 to "E-mail ou senha inválidos.")) {
            api.entrar(LoginRequest(email, senha))
        }
        return salvarSessao(resultado)
    }

    suspend fun cadastrar(perfil: PerfilRequest): ApiResult<PerfilResponse> {
        val resultado = chamarApi(mapOf(409 to "Já existe uma conta com este e-mail.")) {
            api.cadastrar(perfil)
        }
        return salvarSessao(resultado)
    }

    /** Pede o e-mail de recuperação. O backend responde igual exista ou não a conta. */
    suspend fun pedirRecuperacaoSenha(email: String): ApiResult<MensagemResponse> =
        chamarApi(
            mapOf(503 to "A recuperação de senha ainda não está configurada no servidor (SMTP).")
        ) { api.pedirRecuperacaoSenha(RecuperarSenhaRequest(email)) }

    suspend fun redefinirSenha(token: String, novaSenha: String): ApiResult<MensagemResponse> =
        chamarApi(
            mapOf(
                400 to "Este link de recuperação é inválido ou já expirou. Peça um novo.",
                422 to "Link inválido ou senha fora do tamanho permitido (8 a 128 caracteres)."
            )
        ) { api.redefinirSenha(RedefinirSenhaRequest(token, novaSenha)) }

    // O backend não tem rota de logout: encerrar a sessão local basta,
    // e o refresh token expira sozinho.
    fun sair() = SessionManager.encerrar()

    private fun salvarSessao(resultado: ApiResult<TokenResponse>): ApiResult<PerfilResponse> = when (resultado) {
        is ApiResult.Sucesso -> {
            SessionManager.salvar(resultado.dados)
            ApiResult.Sucesso(resultado.dados.user)
        }
        is ApiResult.Erro -> resultado
    }
}
