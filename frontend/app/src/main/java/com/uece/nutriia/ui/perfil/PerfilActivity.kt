package com.uece.nutriia.ui.perfil

import android.content.Intent
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.uece.nutriia.R
import com.uece.nutriia.data.model.Objetivo
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AuthRepository
import com.uece.nutriia.data.repository.PerfilRepository
import com.uece.nutriia.databinding.ActivityPerfilBinding
import com.uece.nutriia.databinding.ItemPerfilOpcaoBinding
import com.uece.nutriia.ui.cadastro.OnboardingActivity
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.exigirSessao
import com.uece.nutriia.ui.common.irParaLogin
import com.uece.nutriia.ui.common.mostrarErro
import com.uece.nutriia.ui.restricoes.RestricoesActivity
import kotlinx.coroutines.launch

class PerfilActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPerfilBinding
    private val repository = PerfilRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        enableEdgeToEdge()
        binding = ActivityPerfilBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.PERFIL)

        configurarOpcao(binding.opcaoDadosPessoais, R.drawable.ic_info, R.string.personal_data, getString(R.string.personal_data_desc)) {
            OnboardingActivity.abrirEdicao(this)
        }
        configurarOpcao(binding.opcaoIngredientes, R.drawable.ic_block, R.string.avoided_ingredients, "") {
            startActivity(Intent(this, RestricoesActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            })
        }
        configurarOpcao(binding.opcaoComoFunciona, R.drawable.ic_block, R.string.how_analysis_works, getString(R.string.how_analysis_works_desc)) {
            MaterialAlertDialogBuilder(this)
                .setTitle(R.string.how_analysis_works)
                .setMessage(R.string.how_analysis_works_text)
                .setPositiveButton(R.string.ok, null)
                .show()
        }

        binding.btnEditar.setOnClickListener { OnboardingActivity.abrirEdicao(this) }
        binding.btnSair.setOnClickListener {
            AuthRepository().sair()
            irParaLogin()
        }
    }

    override fun onResume() {
        super.onResume()
        if (!::binding.isInitialized) return
        lifecycleScope.launch {
            when (val resultado = repository.buscar()) {
                is ApiResult.Sucesso -> mostrar(resultado.dados)
                is ApiResult.Erro -> mostrarErro(resultado)
            }
        }
    }

    private fun mostrar(perfil: PerfilResponse) {
        binding.txtInicial.text = perfil.nome.firstOrNull()?.uppercase().orEmpty()
        binding.txtNome.text = perfil.nome
        val objetivo = getString(
            if (perfil.objective == Objetivo.GANHO_DE_MASSA) R.string.goal_muscle_gain else R.string.goal_weight_loss
        )
        // Alergias + ingredientes evitados, que geram conflitos na análise.
        val restricoes = perfil.alergias.size + perfil.ingredientesEvitados.size
        binding.txtResumo.text = resources.getQuantityString(R.plurals.profile_summary, restricoes, objetivo, restricoes)
        val evitados = perfil.ingredientesEvitados.size
        binding.opcaoIngredientes.descricao.text =
            resources.getQuantityString(R.plurals.avoided_count, evitados, evitados)
    }

    private fun configurarOpcao(
        opcao: ItemPerfilOpcaoBinding,
        icone: Int,
        titulo: Int,
        descricao: String,
        aoClicar: () -> Unit
    ) {
        opcao.icone.setImageResource(icone)
        opcao.titulo.setText(titulo)
        opcao.descricao.text = descricao
        opcao.root.setOnClickListener { aoClicar() }
    }
}
