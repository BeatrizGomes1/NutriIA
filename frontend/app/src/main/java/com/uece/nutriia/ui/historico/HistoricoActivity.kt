package com.uece.nutriia.ui.historico

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import com.uece.nutriia.R
import com.uece.nutriia.data.mock.MockData
import com.uece.nutriia.databinding.ActivityHistoricoBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets

class HistoricoActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHistoricoBinding
    private val adapter = HistoricoAdapter()
    private var filtro = Filtro.RECOMENDADOS

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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

        selecionarFiltro(Filtro.RECOMENDADOS)
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
        val filtrados = MockData.analises.filter { analise ->
            val bateFiltro = when (filtro) {
                Filtro.TODOS -> true
                Filtro.RECOMENDADOS -> analise.recomendado
                Filtro.NAO_RECOMENDADOS -> !analise.recomendado
            }
            val bateBusca = busca.isEmpty() ||
                analise.nome.contains(busca, ignoreCase = true) ||
                analise.marca.contains(busca, ignoreCase = true)
            bateFiltro && bateBusca
        }
        adapter.atualizar(filtrados)
    }

    private enum class Filtro {
        TODOS, RECOMENDADOS, NAO_RECOMENDADOS
    }
}
