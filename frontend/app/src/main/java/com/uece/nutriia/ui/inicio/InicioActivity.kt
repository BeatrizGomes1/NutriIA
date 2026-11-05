package com.uece.nutriia.ui.inicio

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.uece.nutriia.R
import com.uece.nutriia.data.local.SessionManager
import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AnaliseRepository
import com.uece.nutriia.databinding.ActivityInicioBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.aplicarStatus
import com.uece.nutriia.ui.common.exigirSessao
import com.uece.nutriia.ui.common.mostrarErro
import com.uece.nutriia.ui.escanear.EscanearActivity
import com.uece.nutriia.ui.historico.HistoricoActivity
import com.uece.nutriia.ui.perfil.PerfilActivity
import com.uece.nutriia.ui.resultado.ResultadoActivity
import kotlinx.coroutines.launch

class InicioActivity : AppCompatActivity() {

    private lateinit var binding: ActivityInicioBinding
    private val repository = AnaliseRepository()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        enableEdgeToEdge()
        binding = ActivityInicioBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.INICIO)

        binding.btnEscanearProduto.setOnClickListener {
            startActivity(Intent(this, EscanearActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_NO_ANIMATION)
            })
            @Suppress("DEPRECATION")
            overridePendingTransition(0, 0)
        }
        binding.btnVerHistorico.setOnClickListener {
            startActivity(Intent(this, HistoricoActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_NO_ANIMATION)
            })
            @Suppress("DEPRECATION")
            overridePendingTransition(0, 0)
        }
        binding.btnRevisar.setOnClickListener {
            startActivity(Intent(this, PerfilActivity::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        if (!::binding.isInitialized) return
        binding.txtGreeting.text = getString(R.string.greeting, SessionManager.nome.orEmpty())
        carregarUltimaAnalise()
    }

    private fun carregarUltimaAnalise() {
        lifecycleScope.launch {
            when (val resultado = repository.historico(limite = 1)) {
                is ApiResult.Sucesso -> mostrarUltima(resultado.dados.firstOrNull())
                is ApiResult.Erro -> {
                    if (resultado.sessaoExpirada) mostrarErro(resultado)
                    mostrarUltima(null)
                }
            }
        }
    }

    private fun mostrarUltima(ultima: Analise?) {
        if (ultima == null) {
            binding.txtUltimaNome.setText(R.string.no_analyses_yet)
            binding.txtUltimaMarca.visibility = View.GONE
            binding.txtUltimaStatus.visibility = View.GONE
            binding.cardUltimaAnalise.setOnClickListener(null)
            return
        }
        binding.txtUltimaNome.text = ultima.nome
        binding.txtUltimaMarca.visibility = View.VISIBLE
        binding.txtUltimaMarca.text = getString(
            R.string.marca_data_format,
            ultima.marca,
            ultima.dataRelativa
        )
        binding.txtUltimaStatus.visibility = View.VISIBLE
        binding.txtUltimaStatus.aplicarStatus(ultima.status)
        binding.cardUltimaAnalise.setOnClickListener { ResultadoActivity.abrir(this, ultima) }
    }
}
