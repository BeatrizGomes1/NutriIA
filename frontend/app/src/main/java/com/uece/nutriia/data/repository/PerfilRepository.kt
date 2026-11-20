package com.uece.nutriia.data.repository

import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.model.PerfilRequest
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.remote.NutriIaApi
import com.uece.nutriia.data.remote.RetrofitClient
import com.uece.nutriia.data.remote.chamarApi

class PerfilRepository(private val api: NutriIaApi = RetrofitClient.api) {

    suspend fun buscar(): ApiResult<PerfilResponse> = chamarApi { api.perfilAutenticado() }

    suspend fun atualizar(perfil: PerfilRequest): ApiResult<PerfilResponse> {
        val userId = SessionManager.userId ?: return ApiResult.Erro("Sessão não encontrada.", 401)
        val resultado = chamarApi(mapOf(409 to "Este e-mail já está em uso por outra conta.")) {
            api.atualizarPerfil(userId, perfil)
        }
        if (resultado is ApiResult.Sucesso) SessionManager.atualizarNome(resultado.dados.nome)
        return resultado
    }
}
