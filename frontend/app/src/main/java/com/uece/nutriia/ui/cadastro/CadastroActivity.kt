package com.uece.nutriia.ui.cadastro

import android.os.Bundle
import android.util.Patterns
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.uece.nutriia.R

/**
 * Primeira etapa do cadastro: nome, e-mail e senha.
 * A conta só é criada no fim do onboarding, porque POST /auth/register
 * exige também o objetivo alimentar.
 */
class CadastroActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_cadastro)

        val etNome = findViewById<EditText>(R.id.etNome)
        val etEmail = findViewById<EditText>(R.id.etEmail)
        val etSenha = findViewById<EditText>(R.id.etSenha)
        val tvErro = findViewById<TextView>(R.id.tvErro)

        findViewById<Button>(R.id.btnCriarCadastro).setOnClickListener {
            val nome = etNome.text.toString().trim()
            val email = etEmail.text.toString().trim()
            val senha = etSenha.text.toString()

            // Mesmas regras do backend (RegisterPayload).
            val erro = when {
                nome.isEmpty() -> getString(R.string.error_name)
                !Patterns.EMAIL_ADDRESS.matcher(email).matches() -> getString(R.string.error_email)
                senha.length !in 8..128 -> getString(R.string.error_password)
                else -> null
            }

            if (erro != null) {
                tvErro.text = erro
                tvErro.visibility = View.VISIBLE
            } else {
                tvErro.visibility = View.GONE
                OnboardingActivity.abrirCadastro(this, nome, email, senha)
            }
        }

        findViewById<Button>(R.id.btnJaTenhoCadastro).setOnClickListener { finish() }
    }
}
