package com.uece.nutriia.ui.historico

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.uece.nutriia.R
import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AnaliseRepository
import com.uece.nutriia.databinding.ActivityHistoricoBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.exigirSessao
import com.uece.nutriia.ui.common.mostrarErro
import com.uece.nutriia.ui.resultado.ResultadoActivity
import kotlinx.coroutines.launch

class HistoricoActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHistoricoBinding
    private val adapter = HistoricoAdapter { analise -> ResultadoActivity.abrir(this, analise) }
    private val repository = AnaliseRepository()
    private var analises: List<Analise> = emptyList()
    private var filtro = Filtro.TODOS

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        enableEdgeToEdge()
        binding = ActivityHistoricoBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.HISTORICO)

        binding.rvHistorico.layoutManager = LinearLayoutManager(this)
        binding.rvHistorico.adapter = adapter

        binding.chipTodos.setOnClickListener { selecionarFiltro(Filtro.TODOS) }
        binding.chipRecomendados.setOnClickListener { selecionarFiltro(Filtro.RECOMENDADOS) }
        binding.chipNaoRecomendados.setOnClickListener { selecionarFiltro(Filtro.NAO_RECOMENDADOS) }

        binding.edtBuscar.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) {
                atualizarLista()
            }
        })

        selecionarFiltro(filtro)
    }

    override fun onResume() {
        super.onResume()
        // Recarrega ao voltar de uma nova análise (a Activity é reaproveitada).
        if (::binding.isInitialized) carregarHistorico()
    }

    private fun carregarHistorico() {
        binding.txtVazio.visibility = View.GONE
        if (analises.isEmpty()) binding.progressHistorico.visibility = View.VISIBLE

        lifecycleScope.launch {
            val resultado = repository.historico()
            binding.progressHistorico.visibility = View.GONE
            when (resultado) {
                is ApiResult.Sucesso -> {
                    analises = resultado.dados
                    atualizarLista()
                }
                is ApiResult.Erro -> {
                    mostrarErro(resultado)
                    if (analises.isEmpty()) {
                        binding.txtVazio.setText(R.string.history_load_error)
                        binding.txtVazio.visibility = View.VISIBLE
                        binding.txtVazio.setOnClickListener { carregarHistorico() }
                    }
                }
            }
        }
    }

    private fun selecionarFiltro(novoFiltro: Filtro) {
        filtro = novoFiltro
        estiloChip(binding.chipTodos, filtro == Filtro.TODOS)
        estiloChip(binding.chipRecomendados, filtro == Filtro.RECOMENDADOS)
        estiloChip(binding.chipNaoRecomendados, filtro == Filtro.NAO_RECOMENDADOS)
        atualizarLista()
    }

    private fun estiloChip(chip: TextView, selecionado: Boolean) {
        if (selecionado) {
            chip.setBackgroundResource(R.drawable.bg_chip_selected)
            chip.setTextColor(ContextCompat.getColor(this, R.color.green_primary))
        } else {
            chip.setBackgroundResource(R.drawable.bg_chip)
            chip.setTextColor(ContextCompat.getColor(this, R.color.text_primary))
        }
    }

    private fun atualizarLista() {
        val busca = binding.edtBuscar.text.toString().trim()
        val filtrados = analises.filter { analise ->
            val bateFiltro = when (filtro) {
                Filtro.TODOS -> true
                Filtro.RECOMENDADOS -> analise.recomendado
                Filtro.NAO_RECOMENDADOS -> analise.naoRecomendado
            }
            val bateBusca = busca.isEmpty() ||
                analise.nome.contains(busca, ignoreCase = true) ||
                analise.marca.contains(busca, ignoreCase = true)
            bateFiltro && bateBusca
        }
        adapter.atualizar(filtrados)

        if (binding.progressHistorico.visibility != View.VISIBLE) {
            binding.txtVazio.setOnClickListener(null)
            binding.txtVazio.visibility = if (filtrados.isEmpty()) View.VISIBLE else View.GONE
            binding.txtVazio.setText(
                if (analises.isEmpty()) R.string.no_analyses_yet else R.string.no_results_filter
            )
        }
    }

    private enum class Filtro {
        TODOS, RECOMENDADOS, NAO_RECOMENDADOS
    }
}
