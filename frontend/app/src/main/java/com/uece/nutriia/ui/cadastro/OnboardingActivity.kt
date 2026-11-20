package com.uece.nutriia.ui.cadastro

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.chip.ChipGroup
import com.uece.nutriia.R
import com.uece.nutriia.data.model.Objetivo
import com.uece.nutriia.data.model.PerfilRequest
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AuthRepository
import com.uece.nutriia.data.repository.PerfilRepository
import com.uece.nutriia.databinding.ActivityOnboardingBinding
import com.uece.nutriia.ui.common.adicionarChip
import com.uece.nutriia.ui.common.adicionarChipOutros
import com.uece.nutriia.ui.common.exigirSessao
import com.uece.nutriia.ui.common.mostrarErro
import com.uece.nutriia.ui.common.textosMarcados
import com.uece.nutriia.ui.inicio.InicioActivity
import kotlinx.coroutines.launch

/**
 * Etapas "Informações de perfil" e "Alergias e preferências".
 * No cadastro, termina em POST /auth/register; na edição, em PUT /profiles/{id}.
 */
class OnboardingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityOnboardingBinding
    private val authRepository = AuthRepository()
    private val perfilRepository = PerfilRepository()

    private val modoEdicao by lazy { intent.getBooleanExtra(EXTRA_EDICAO, false) }
    private var perfilOriginal: PerfilResponse? = null
    private var objetivo = Objetivo.PERDA_DE_PESO
    private var etapa = 1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (modoEdicao && !exigirSessao()) return
        binding = ActivityOnboardingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.spFaixaEtaria.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            FAIXAS_ETARIAS
        )
        binding.opcaoEmagrecimento.setOnClickListener { selecionarObjetivo(Objetivo.PERDA_DE_PESO) }
        binding.opcaoGanhoMassa.setOnClickListener { selecionarObjetivo(Objetivo.GANHO_DE_MASSA) }
        binding.btnContinuar.setOnClickListener {
            if (modoEdicao && binding.etNome.text.isNullOrBlank()) {
                binding.etNome.error = getString(R.string.error_name)
            } else {
                mostrarEtapa(2)
            }
        }
        binding.btnVoltar.setOnClickListener { mostrarEtapa(1) }
        binding.btnSalvar.setOnClickListener { salvar() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (etapa == 2) mostrarEtapa(1) else finish()
            }
        })

        if (modoEdicao) {
            binding.grupoNome.visibility = View.VISIBLE
            binding.txtTituloEtapa1.setText(R.string.edit_personal_data)
            carregarPerfil()
        } else {
            montarChips(emptyList(), emptyList())
            selecionarObjetivo(Objetivo.PERDA_DE_PESO)
            mostrarEtapa(1)
        }
    }

    private fun carregarPerfil() {
        binding.etapa1.visibility = View.GONE
        binding.progressCarregando.visibility = View.VISIBLE
        lifecycleScope.launch {
            when (val resultado = perfilRepository.buscar()) {
                is ApiResult.Sucesso -> {
                    val perfil = resultado.dados
                    perfilOriginal = perfil
                    binding.etNome.setText(perfil.nome)
                    val faixa = FAIXAS_ETARIAS.indexOf(perfil.faixaEtaria)
                    binding.spFaixaEtaria.setSelection(if (faixa >= 0) faixa else 0)
                    selecionarObjetivo(perfil.objective)
                    montarChips(perfil.alergias, perfil.preferencias)
                    binding.progressCarregando.visibility = View.GONE
                    mostrarEtapa(1)
                }
                is ApiResult.Erro -> {
                    mostrarErro(resultado)
                    finish()
                }
            }
        }
    }

    private fun montarChips(alergias: List<String>, preferencias: List<String>) {
        preencherGrupo(binding.grupoAlergias, OPCOES_ALERGIAS, alergias)
        preencherGrupo(binding.grupoPreferencias, OPCOES_PREFERENCIAS, preferencias)
    }

    // Opções padrão do Figma + itens personalizados já salvos no perfil.
    private fun preencherGrupo(grupo: ChipGroup, opcoes: List<String>, marcados: List<String>) {
        grupo.removeAllViews()
        grupo.adicionarChipOutros(this)
        val extras = marcados.filter { item -> opcoes.none { it.equals(item, ignoreCase = true) } }
        (opcoes + extras).forEach { opcao ->
            grupo.adicionarChip(opcao, marcado = marcados.any { it.equals(opcao, ignoreCase = true) })
        }
    }

    private fun selecionarObjetivo(novo: String) {
        objetivo = novo
        val emagrecer = novo == Objetivo.PERDA_DE_PESO
        binding.opcaoEmagrecimento.setBackgroundResource(if (emagrecer) R.drawable.bg_option_selected else R.drawable.bg_card)
        binding.opcaoGanhoMassa.setBackgroundResource(if (emagrecer) R.drawable.bg_card else R.drawable.bg_option_selected)
        binding.icoEmagrecimento.setImageResource(if (emagrecer) R.drawable.ic_check_circle else R.drawable.ic_circle_outline)
        binding.icoGanhoMassa.setImageResource(if (emagrecer) R.drawable.ic_circle_outline else R.drawable.ic_check_circle)
    }

    private fun mostrarEtapa(nova: Int) {
        etapa = nova
        binding.etapa1.visibility = if (nova == 1) View.VISIBLE else View.GONE
        binding.etapa2.visibility = if (nova == 2) View.VISIBLE else View.GONE
        binding.progressoEtapa2.setBackgroundResource(
            if (nova == 2) R.drawable.bg_progress_on else R.drawable.bg_progress_off
        )
        binding.onboardingScroll.scrollTo(0, 0)
    }

    private fun faixaSelecionada(): String? =
        binding.spFaixaEtaria.selectedItemPosition.takeIf { it > 0 }?.let { FAIXAS_ETARIAS[it] }

    private fun salvar() {
        binding.tvErro.visibility = View.GONE
        binding.btnSalvar.isEnabled = false
        binding.btnSalvar.setText(R.string.saving)

        lifecycleScope.launch {
            val alergias = binding.grupoAlergias.textosMarcados()
            val preferencias = binding.grupoPreferencias.textosMarcados()

            val resultado = if (modoEdicao) {
                // Mantém e-mail e ingredientes evitados, editados em outras telas.
                val base = perfilOriginal?.paraRequest() ?: return@launch
                perfilRepository.atualizar(
                    base.copy(
                        nome = binding.etNome.text.toString().trim(),
                        faixaEtaria = faixaSelecionada(),
                        objective = objetivo,
                        alergias = alergias,
                        preferencias = preferencias,
                        onboardingConcluido = true
                    )
                )
            } else {
                authRepository.cadastrar(
                    PerfilRequest(
                        nome = intent.getStringExtra(EXTRA_NOME).orEmpty(),
                        email = intent.getStringExtra(EXTRA_EMAIL).orEmpty(),
                        faixaEtaria = faixaSelecionada(),
                        objective = objetivo,
                        alergias = alergias,
                        preferencias = preferencias,
                        onboardingConcluido = true,
                        password = intent.getStringExtra(EXTRA_SENHA).orEmpty()
                    )
                )
            }

            when (resultado) {
                is ApiResult.Sucesso -> concluir()
                is ApiResult.Erro -> {
                    binding.btnSalvar.isEnabled = true
                    binding.btnSalvar.setText(R.string.save_profile)
                    binding.tvErro.text = resultado.mensagem
                    binding.tvErro.visibility = View.VISIBLE
                    if (resultado.sessaoExpirada) mostrarErro(resultado)
                }
            }
        }
    }

    private fun concluir() {
        if (modoEdicao) {
            Toast.makeText(this, R.string.profile_saved, Toast.LENGTH_SHORT).show()
            finish()
        } else {
            startActivity(Intent(this, InicioActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            })
            finish()
        }
    }

    companion object {
        private const val EXTRA_EDICAO = "edicao"
        private const val EXTRA_NOME = "nome"
        private const val EXTRA_EMAIL = "email"
        private const val EXTRA_SENHA = "senha"

        // O primeiro item significa "não informado" (age_range = null).
        private val FAIXAS_ETARIAS = listOf(
            "Prefiro não informar", "Até 17 anos", "18 a 24 anos", "25 a 34 anos",
            "35 a 44 anos", "45 a 59 anos", "60 anos ou mais"
        )
        private val OPCOES_ALERGIAS = listOf("Leite", "Glúten", "Amendoim", "Soja", "Crustáceos", "Ovos")
        private val OPCOES_PREFERENCIAS = listOf("Sem açúcar", "Sem lactose", "Baixo sódio", "Vegetariano / Vegano")

        fun abrirCadastro(context: Context, nome: String, email: String, senha: String) {
            context.startActivity(Intent(context, OnboardingActivity::class.java).apply {
                putExtra(EXTRA_NOME, nome)
                putExtra(EXTRA_EMAIL, email)
                putExtra(EXTRA_SENHA, senha)
            })
        }

        fun abrirEdicao(context: Context) {
            context.startActivity(Intent(context, OnboardingActivity::class.java).apply {
                putExtra(EXTRA_EDICAO, true)
            })
        }
    }
}
