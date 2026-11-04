package com.uece.nutriia.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import com.uece.nutriia.data.model.TokenResponse

/**
 * Guarda o token JWT e os dados básicos do usuário logado.
 * O backend não tem refresh token: quando o token expira, o usuário entra de novo.
 */
object SessionManager {
    private const val PREFS = "nutriia_sessao"
    private const val KEY_TOKEN = "token"
    private const val KEY_EXPIRA_EM = "expira_em"
    private const val KEY_USER_ID = "user_id"
    private const val KEY_NOME = "nome"

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    }

    val token: String?
        get() = prefs.getString(KEY_TOKEN, null)?.takeIf { sessaoValida }

    val userId: String?
        get() = prefs.getString(KEY_USER_ID, null)

    val nome: String?
        get() = prefs.getString(KEY_NOME, null)

    val sessaoValida: Boolean
        get() = prefs.contains(KEY_TOKEN) &&
            System.currentTimeMillis() < prefs.getLong(KEY_EXPIRA_EM, 0L)

    fun salvar(resposta: TokenResponse) {
        prefs.edit {
            putString(KEY_TOKEN, resposta.accessToken)
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
