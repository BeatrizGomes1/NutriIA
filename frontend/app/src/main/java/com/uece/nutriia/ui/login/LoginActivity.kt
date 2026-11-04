package com.uece.nutriia.ui.login

import android.content.Intent
import android.graphics.Paint
import android.os.Bundle
import android.util.Patterns
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.uece.nutriia.R
import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AuthRepository
import com.uece.nutriia.ui.cadastro.CadastroActivity
import com.uece.nutriia.ui.inicio.InicioActivity
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    private val authRepository = AuthRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Sessão ainda válida: pula o login.
        if (SessionManager.sessaoValida) {
            abrirInicio()
            return
        }

        setContentView(R.layout.activity_login)

        val etEmail = findViewById<EditText>(R.id.etEmail)
        val etSenha = findViewById<EditText>(R.id.etSenha)
        val tvErro = findViewById<TextView>(R.id.tvErro)
        val btnEntrar = findViewById<Button>(R.id.btnEntrar)
        val tvEntrar = findViewById<TextView>(R.id.tvEntrar)

        btnEntrar.setOnClickListener {
            val email = etEmail.text.toString().trim()
            val senha = etSenha.text.toString()

            val erro = when {
                !Patterns.EMAIL_ADDRESS.matcher(email).matches() -> "Digite um e-mail válido."
                senha.length < 6 -> "A senha deve ter no mínimo 6 caracteres."
                else -> null
            }

            if (erro != null) {
                tvErro.text = erro
                tvErro.visibility = View.VISIBLE
                return@setOnClickListener
            }

            tvErro.visibility = View.GONE
            btnEntrar.isEnabled = false
            tvEntrar.setText(R.string.entering)

            lifecycleScope.launch {
                when (val resultado = authRepository.entrar(email, senha)) {
                    is ApiResult.Sucesso -> abrirInicio()
                    is ApiResult.Erro -> {
                        tvErro.text = resultado.mensagem
                        tvErro.visibility = View.VISIBLE
                        btnEntrar.isEnabled = true
                        tvEntrar.setText(R.string.enter)
                    }
                }
            }
        }

        findViewById<Button>(R.id.btnCriarCadastro).setOnClickListener {
            startActivity(Intent(this, CadastroActivity::class.java))
        }

        val tvEsqueciSenha = findViewById<TextView>(R.id.tvEsqueciSenha)
        tvEsqueciSenha.paintFlags = tvEsqueciSenha.paintFlags or Paint.UNDERLINE_TEXT_FLAG
        tvEsqueciSenha.setOnClickListener {
            // O backend ainda não tem rota de recuperação de senha.
            Toast.makeText(this, R.string.password_recovery_unavailable, Toast.LENGTH_LONG).show()
        }
    }

    private fun abrirInicio() {
        startActivity(Intent(this, InicioActivity::class.java))
        finish()
    }
}
