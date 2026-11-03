package com.uece.nutriia.ui.login

import android.content.Intent
import android.graphics.Paint
import android.os.Bundle
import android.util.Patterns
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.uece.nutriia.R
import com.uece.nutriia.ui.inicio.InicioActivity

class LoginActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        val etEmail = findViewById<EditText>(R.id.etEmail)
        val etSenha = findViewById<EditText>(R.id.etSenha)
        val tvErro = findViewById<TextView>(R.id.tvErro)

        findViewById<Button>(R.id.btnEntrar).setOnClickListener {
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
            } else {
                tvErro.visibility = View.GONE
                // Provisório: o back ainda não tem rota de login.
                // Quando existir, a chamada da API entra aqui antes de abrir a tela de início.
                startActivity(Intent(this, InicioActivity::class.java))
                finish()
            }
        }

        findViewById<Button>(R.id.btnCriarCadastro).setOnClickListener {
            // TODO: abrir a tela de cadastro
        }

        val tvEsqueciSenha = findViewById<TextView>(R.id.tvEsqueciSenha)
        tvEsqueciSenha.paintFlags = tvEsqueciSenha.paintFlags or Paint.UNDERLINE_TEXT_FLAG
        tvEsqueciSenha.setOnClickListener {
            // TODO: abrir a tela de recuperação de senha
        }
    }
}