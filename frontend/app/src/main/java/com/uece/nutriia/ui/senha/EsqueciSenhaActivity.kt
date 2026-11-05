package com.uece.nutriia.ui.senha

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Patterns
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.uece.nutriia.R
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AuthRepository
import com.uece.nutriia.databinding.ActivityEsqueciSenhaBinding
import kotlinx.coroutines.launch

/** Pede o e-mail e chama POST /auth/password-reset/request. */
class EsqueciSenhaActivity : AppCompatActivity() {

    private lateinit var binding: ActivityEsqueciSenhaBinding
    private val repository = AuthRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityEsqueciSenhaBinding.inflate(layoutInflater)
        setContentView(binding.root)

        intent.getStringExtra(EXTRA_EMAIL)?.let { binding.etEmail.setText(it) }

        binding.btnEnviar.setOnClickListener { enviar() }
        binding.btnJaTenhoLink.setOnClickListener {
            startActivity(Intent(this, RedefinirSenhaActivity::class.java))
        }
        binding.btnVoltar.setOnClickListener { finish() }
    }

    private fun enviar() {
        val email = binding.etEmail.text.toString().trim()
        if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            mostrarErro(getString(R.string.error_email))
            return
        }
        binding.tvErro.visibility = View.GONE
        binding.btnEnviar.isEnabled = false
        binding.btnEnviar.setText(R.string.sending)

        lifecycleScope.launch {
            val resultado = repository.pedirRecuperacaoSenha(email)
            binding.btnEnviar.isEnabled = true
            when (resultado) {
                is ApiResult.Sucesso -> {
                    // A resposta é a mesma exista ou não a conta (o backend não revela).
                    binding.cardEnviado.visibility = View.VISIBLE
                    binding.btnEnviar.setText(R.string.forgot_resend)
                }
                is ApiResult.Erro -> {
                    binding.btnEnviar.setText(R.string.forgot_send)
                    mostrarErro(resultado.mensagem)
                }
            }
        }
    }

    private fun mostrarErro(mensagem: String) {
        binding.tvErro.text = mensagem
        binding.tvErro.visibility = View.VISIBLE
    }

    companion object {
        private const val EXTRA_EMAIL = "email"

        fun abrir(context: Context, email: String) {
            context.startActivity(Intent(context, EsqueciSenhaActivity::class.java).apply {
                putExtra(EXTRA_EMAIL, email)
            })
        }
    }
}
