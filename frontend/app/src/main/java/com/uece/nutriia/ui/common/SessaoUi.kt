package com.uece.nutriia.ui.common

import android.content.Intent
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.uece.nutriia.R
import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.model.StatusAnalise
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.ui.login.LoginActivity

/** Encerra a sessão e volta para o login, limpando a pilha de telas. */
fun AppCompatActivity.irParaLogin() {
    SessionManager.encerrar()
    startActivity(Intent(this, LoginActivity::class.java).apply {
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
    })
    finish()
}

/** Telas privadas chamam no onCreate; devolve false se já redirecionou ao login. */
fun AppCompatActivity.exigirSessao(): Boolean {
    if (SessionManager.sessaoValida) return true
    irParaLogin()
    return false
}

/** Mostra o erro da API; se a sessão expirou, manda para o login. */
fun AppCompatActivity.mostrarErro(erro: ApiResult.Erro) {
    Toast.makeText(this, erro.mensagem, Toast.LENGTH_LONG).show()
    if (erro.sessaoExpirada) irParaLogin()
}

/** Texto e cor do status da análise, usados na lista, na tela inicial e no resultado. */
fun TextView.aplicarStatus(status: StatusAnalise) {
    val (texto, cor) = when (status) {
        StatusAnalise.RECOMENDADO -> R.string.recommended to R.color.green_primary
        StatusAnalise.ATENCAO -> R.string.status_attention to R.color.warning
        StatusAnalise.NAO_RECOMENDADO -> R.string.not_recommended to R.color.danger
        StatusAnalise.INSUFICIENTE -> R.string.status_insufficient to R.color.text_secondary
        StatusAnalise.NAO_ENCONTRADO -> R.string.status_not_found to R.color.text_secondary
    }
    setText(texto)
    setTextColor(ContextCompat.getColor(context, cor))
}
