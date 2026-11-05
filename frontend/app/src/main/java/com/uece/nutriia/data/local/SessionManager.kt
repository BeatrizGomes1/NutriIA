package com.uece.nutriia.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import com.uece.nutriia.data.model.TokenResponse

/**
 * Guarda o access token (curto), o refresh token (longo) e os dados básicos do usuário.
 * Quando o access token expira, o RetrofitClient renova a sessão com o refresh token.
 */
object SessionManager {
    private const val PREFS = "nutriia_sessao"
    private const val KEY_TOKEN = "token"
    private const val KEY_REFRESH = "refresh_token"
    private const val KEY_EXPIRA_EM = "expira_em"
    private const val KEY_USER_ID = "user_id"
    private const val KEY_NOME = "nome"

    // Renova um pouco antes de expirar, para não perder uma requisição em andamento.
    private const val MARGEM_MS = 30_000L

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    }

    val token: String?
        get() = prefs.getString(KEY_TOKEN, null)

    val refreshToken: String?
        get() = prefs.getString(KEY_REFRESH, null)

    val userId: String?
        get() = prefs.getString(KEY_USER_ID, null)

    val nome: String?
        get() = prefs.getString(KEY_NOME, null)

    val acessoExpirado: Boolean
        get() = System.currentTimeMillis() + MARGEM_MS >= prefs.getLong(KEY_EXPIRA_EM, 0L)

    /** Há sessão enquanto existir um refresh token (ou um access token ainda válido). */
    val sessaoValida: Boolean
        get() = refreshToken != null || (token != null && !acessoExpirado)

    fun salvar(resposta: TokenResponse) {
        prefs.edit {
            putString(KEY_TOKEN, resposta.accessToken)
            putString(KEY_REFRESH, resposta.refreshToken)
            putLong(KEY_EXPIRA_EM, System.currentTimeMillis() + resposta.expiraEmSegundos * 1000)
            putString(KEY_USER_ID, resposta.user.id)
            putString(KEY_NOME, resposta.user.nome)
        }
    }

    fun atualizarNome(nome: String) {
        prefs.edit { putString(KEY_NOME, nome) }
    }

    fun encerrar() {
        prefs.edit { clear() }
    }
}
