package com.uece.nutriia.ui.analise

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.uece.nutriia.R
import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.remote.ApiResult
import com.uece.nutriia.data.repository.AnaliseRepository
import com.uece.nutriia.databinding.ActivityAnaliseAndamentoBinding
import com.uece.nutriia.databinding.ItemEtapaAnaliseBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.exigirSessao
import com.uece.nutriia.ui.common.mostrarErro
import com.uece.nutriia.ui.resultado.ResultadoActivity
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File

/**
 * Envia o EAN (POST /profiles/{id}/captures/ean) ou a foto do rótulo
 * (POST /profiles/{id}/captures/label-photo) e mostra o progresso.
 * O backend responde tudo de uma vez (não há status intermediário), então as
 * etapas avançam por tempo e a última só conclui quando a resposta chega.
 */
class AnaliseAndamentoActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAnaliseAndamentoBinding
    private val repository = AnaliseRepository()
    private var resultado: Analise? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        enableEdgeToEdge()
        binding = ActivityAnaliseAndamentoBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.ESCANEAR)

        val etapas = listOf(binding.etapa1, binding.etapa2, binding.etapa3, binding.etapa4)
        val textos = listOf(
            R.string.analysis_step_extract, R.string.analysis_step_hidden,
            R.string.analysis_step_compare, R.string.analysis_step_goal
        )
        etapas.zip(textos).forEach { (etapa, texto) -> marcarEtapa(etapa, texto, concluida = false) }

        binding.btnVerResultado.setOnClickListener { abrirResultado() }

        val ean = intent.getStringExtra(EXTRA_EAN)
        val foto = intent.getStringExtra(EXTRA_FOTO)?.let(::File)
        lifecycleScope.launch {
            val chamada = async {
                if (foto != null) {
                    // A foto temporária não é mais necessária depois do envio.
                    repository.analisarFotoRotulo(foto).also { foto.delete() }
                } else {
                    repository.analisarEan(ean.orEmpty())
                }
            }

            // Avança as três primeiras etapas enquanto aguarda o backend.
            for (i in 0 until etapas.lastIndex) {
                delay(TEMPO_ETAPA_MS)
                if (chamada.isCompleted && chamada.await() is ApiResult.Erro) break
                marcarEtapa(etapas[i], textos[i], concluida = true)
            }

            when (val resposta = chamada.await()) {
                is ApiResult.Sucesso -> {
                    etapas.zip(textos).forEach { (etapa, texto) -> marcarEtapa(etapa, texto, concluida = true) }
                    resultado = ResultadoActivity.paraAnalise(this@AnaliseAndamentoActivity, resposta.dados, ean)
                    binding.btnVerResultado.visibility = View.VISIBLE
                    delay(TEMPO_ETAPA_MS)
                    abrirResultado()
                }
                is ApiResult.Erro -> {
                    mostrarErro(resposta)
                    finish()
                }
            }
        }
    }

    private fun abrirResultado() {
        val analise = resultado ?: return
        if (isFinishing) return
        ResultadoActivity.abrir(this, analise)
        finish()
    }

    private fun marcarEtapa(etapa: ItemEtapaAnaliseBinding, texto: Int, concluida: Boolean) {
        etapa.texto.setText(texto)
        etapa.icone.setImageResource(if (concluida) R.drawable.ic_check_circle else R.drawable.ic_circle_outline)
        etapa.texto.setTextColor(
            ContextCompat.getColor(this, if (concluida) R.color.text_primary else R.color.text_secondary)
        )
        etapa.texto.paint.isFakeBoldText = concluida
        etapa.texto.invalidate()
    }

    companion object {
        private const val EXTRA_EAN = "ean"
        private const val EXTRA_FOTO = "foto"
        private const val TEMPO_ETAPA_MS = 700L

        fun abrir(context: Context, ean: String) {
            context.startActivity(Intent(context, AnaliseAndamentoActivity::class.java).apply {
                putExtra(EXTRA_EAN, ean)
            })
        }

        /** [foto] é um JPEG já preparado por [com.uece.nutriia.ui.escanear.PreparadorFoto]. */
        fun abrirComFoto(context: Context, foto: File) {
            context.startActivity(Intent(context, AnaliseAndamentoActivity::class.java).apply {
                putExtra(EXTRA_FOTO, foto.absolutePath)
            })
        }
    }
}
