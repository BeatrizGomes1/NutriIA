package com.uece.nutriia.ui.restricoes

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.view.inputmethod.EditorInfo
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.uece.nutriia.R
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.PerfilRepository
import com.uece.nutriia.databinding.ActivityRestricoesBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.adicionarChip
import com.uece.nutriia.ui.common.exigirSessao
import com.uece.nutriia.ui.common.mostrarErro
import kotlinx.coroutines.launch

/** "Ingredientes que evito": edita avoided_ingredients do perfil via PUT /profiles/{id}. */
class RestricoesActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRestricoesBinding
    private val repository = PerfilRepository()
    private var perfil: PerfilResponse? = null
    private var selecionados: List<String> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        enableEdgeToEdge()
        binding = ActivityRestricoesBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.RESTRICOES)

        binding.edtBuscar.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) = mostrarSugestoes()
        })
        // Enter no teclado adiciona o termo digitado, mesmo fora das sugestões.
        binding.edtBuscar.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) {
                val termo = binding.edtBuscar.text.toString().trim()
                if (termo.isNotEmpty()) adicionar(termo)
                true
            } else {
                false
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) carregar()
    }

    private fun carregar() {
        if (perfil == null) {
            binding.conteudoRestricoes.visibility = View.GONE
            binding.progressRestricoes.visibility = View.VISIBLE
        }
        lifecycleScope.launch {
            val resultado = repository.buscar()
            binding.progressRestricoes.visibility = View.GONE
            when (resultado) {
                is ApiResult.Sucesso -> {
                    perfil = resultado.dados
                    selecionados = resultado.dados.ingredientesEvitados
                    binding.conteudoRestricoes.visibility = View.VISIBLE
                    renderizar()
                }
                is ApiResult.Erro -> mostrarErro(resultado)
            }
        }
    }

    private fun renderizar() {
        binding.txtContagem.text = resources.getQuantityString(R.plurals.items_count, selecionados.size, selecionados.size)
        binding.txtSemSelecionados.visibility = if (selecionados.isEmpty()) View.VISIBLE else View.GONE
        binding.grupoSelecionados.removeAllViews()
        selecionados.forEach { termo ->
            binding.grupoSelecionados.adicionarChip(termo, marcavel = false) {
                setChipBackgroundColorResource(R.color.green_soft)
                setTextColor(getColor(R.color.green_dark))
                isCloseIconVisible = true
                setOnCloseIconClickListener { remover(termo) }
            }
        }
        mostrarSugestoes()
    }

    private fun mostrarSugestoes() {
        val busca = binding.edtBuscar.text.toString().trim()
        val disponiveis = SUGESTOES
            .filter { s -> selecionados.none { it.equals(s, ignoreCase = true) } }
            .filter { busca.isEmpty() || it.contains(busca, ignoreCase = true) }

        binding.grupoSugestoes.removeAllViews()
        disponiveis.forEach { sugestao ->
            binding.grupoSugestoes.adicionarChip(sugestao, marcavel = false) {
                setCloseIconResource(R.drawable.ic_add)
                isCloseIconVisible = true
                setOnClickListener { adicionar(sugestao) }
                setOnCloseIconClickListener { adicionar(sugestao) }
            }
        }
        // Termo livre que não está nas sugestões.
        val jaExiste = (SUGESTOES + selecionados).any { it.equals(busca, ignoreCase = true) }
        if (busca.isNotEmpty() && !jaExiste) {
            binding.grupoSugestoes.adicionarChip(getString(R.string.add_term, busca), marcavel = false) {
                setOnClickListener { adicionar(busca) }
            }
        }
    }

    private fun adicionar(termo: String) {
        if (selecionados.any { it.equals(termo, ignoreCase = true) }) return
        binding.edtBuscar.setText("")
        salvar(selecionados + termo)
    }

    private fun remover(termo: String) = salvar(selecionados - termo)

    // Atualiza a tela na hora e desfaz se o backend recusar.
    private fun salvar(novaLista: List<String>) {
        val atual = perfil ?: return
        val anterior = selecionados
        selecionados = novaLista
        renderizar()

        lifecycleScope.launch {
            val resultado = repository.atualizar(atual.paraRequest().copy(ingredientesEvitados = novaLista))
            when (resultado) {
                is ApiResult.Sucesso -> perfil = resultado.dados
                is ApiResult.Erro -> {
                    selecionados = anterior
                    renderizar()
                    mostrarErro(resultado)
                }
            }
        }
    }

    private companion object {
        val SUGESTOES = listOf(
            "Amendoim", "Lactose", "Cafeína", "Açúcar", "Soja", "Glúten",
            "Ovos", "Peixe", "Castanha", "Sulfitos", "Tartrazina", "Leite"
        )
    }
}
