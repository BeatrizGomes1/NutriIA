package com.uece.nutriia.ui.senha

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.uece.nutriia.R
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AuthRepository
import com.uece.nutriia.databinding.ActivityRedefinirSenhaBinding
import com.uece.nutriia.ui.login.LoginActivity
import kotlinx.coroutines.launch

/**
 * Define a nova senha com o token do e-mail (POST /auth/password-reset/confirm).
 * Abre pelo link nutriia://redefinir-senha?token=... (PASSWORD_RESET_URL do backend)
 * ou com o link/código colado à mão.
 */
class RedefinirSenhaActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRedefinirSenhaBinding
    private val repository = AuthRepository()
    private var tokenDoLink: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRedefinirSenhaBinding.inflate(layoutInflater)
        setContentView(binding.root)

        lerLink(intent)
        binding.btnSalvar.setOnClickListener { salvar() }
        binding.btnVoltar.setOnClickListener { voltarAoLogin() }
    }

    // A tela já aberta pode receber um link novo (launchMode singleTask).
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        lerLink(intent)
    }

    private fun lerLink(intent: Intent) {
        tokenDoLink = intent.data?.getQueryParameter("token")?.takeIf { it.isNotBlank() }
        if (tokenDoLink != null) {
            binding.grupoLink.visibility = View.GONE
            binding.txtSubtitulo.setText(R.string.reset_subtitle_link)
        }
    }

    private fun salvar() {
        val token = tokenDoLink ?: extrairToken(binding.etLink.text.toString())
        val senha = binding.etSenha.text.toString()
        val confirmacao = binding.etConfirmar.text.toString()

        val erro = when {
            token.isNullOrEmpty() -> getString(R.string.reset_error_link)
            senha.length !in 8..128 -> getString(R.string.error_password)
            senha != confirmacao -> getString(R.string.reset_error_match)
            else -> null
        }
        if (erro != null) {
            mostrarErro(erro)
            return
        }

        binding.tvErro.visibility = View.GONE
        binding.btnSalvar.isEnabled = false
        binding.btnSalvar.setText(R.string.saving)

        lifecycleScope.launch {
            when (val resultado = repository.redefinirSenha(token!!, senha)) {
                is ApiResult.Sucesso -> {
                    // O backend revoga as sessões antigas; limpa a local também.
                    repository.sair()
                    Toast.makeText(this@RedefinirSenhaActivity, R.string.reset_done, Toast.LENGTH_LONG).show()
                    voltarAoLogin()
                }
                is ApiResult.Erro -> {
                    binding.btnSalvar.isEnabled = true
                    binding.btnSalvar.setText(R.string.reset_save)
                    mostrarErro(resultado.mensagem)
                }
            }
        }
    }

    // Aceita o link completo do e-mail ou só o código.
    private fun extrairToken(texto: String): String? {
        val limpo = texto.trim()
        if (limpo.isEmpty()) return null
        if (limpo.contains("token=")) {
            return Uri.parse(limpo).getQueryParameter("token")
                ?: limpo.substringAfter("token=").substringBefore('&')
        }
        return limpo
    }

    private fun mostrarErro(mensagem: String) {
        binding.tvErro.text = mensagem
        binding.tvErro.visibility = View.VISIBLE
    }

    // A troca de senha encerra as sessões no backend, então volta para o login.
    private fun voltarAoLogin() {
        startActivity(Intent(this, LoginActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        })
        finish()
    }
}
