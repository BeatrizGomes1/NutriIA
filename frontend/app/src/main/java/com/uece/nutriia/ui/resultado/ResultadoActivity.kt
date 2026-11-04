package com.uece.nutriia.ui.resultado

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.IntentCompat
import androidx.core.view.isEmpty
import androidx.core.widget.ImageViewCompat
import com.uece.nutriia.R
import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.model.CapturaResponse
import com.uece.nutriia.data.model.StatusAnalise
import com.uece.nutriia.data.model.StatusOrigem
import com.uece.nutriia.databinding.ActivityResultadoBinding
import com.uece.nutriia.databinding.ItemMotivoBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.adicionarChip
import com.uece.nutriia.ui.common.aplicarStatus
import com.uece.nutriia.ui.common.exigirSessao
import java.text.Normalizer

/** Mostra uma análise recém-feita ou aberta pelo histórico (sem nova chamada ao backend). */
class ResultadoActivity : AppCompatActivity() {

    private lateinit var binding: ActivityResultadoBinding
    private var ingredientesExpandidos = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        val analise = IntentCompat.getSerializableExtra(intent, EXTRA_ANALISE, Analise::class.java)
        if (analise == null) {
            finish()
            return
        }
        enableEdgeToEdge()
        binding = ActivityResultadoBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.NENHUMA)

        mostrarCabecalho(analise)
        mostrarStatus(analise)
        mostrarMotivos(analise)
        mostrarIngredientes(analise)
    }

    private fun mostrarCabecalho(analise: Analise) {
        binding.txtProduto.text = analise.nome
        binding.txtMarca.text = listOfNotNull(
            analise.produto?.marca?.takeIf { it.isNotBlank() },
            analise.ean?.takeIf { it.isNotBlank() }
        ).joinToString(" · ")
        binding.txtMarca.visibility = if (binding.txtMarca.text.isEmpty()) View.GONE else View.VISIBLE
        analise.analise?.disclaimer?.let { binding.txtAviso.text = it }
    }

    private fun mostrarStatus(analise: Analise) {
        binding.txtStatus.aplicarStatus(analise.status)
        binding.txtResumo.text = when (analise.status) {
            StatusAnalise.NAO_ENCONTRADO -> getString(R.string.not_found_summary)
            else -> analise.analise?.summary.orEmpty()
        }

        val (fundo, cor, icone) = when (analise.status) {
            StatusAnalise.RECOMENDADO -> Triple(R.color.green_soft, R.color.green_primary, R.drawable.ic_check_circle)
            StatusAnalise.ATENCAO -> Triple(R.color.warning_soft, R.color.warning, R.drawable.ic_warning)
            StatusAnalise.NAO_RECOMENDADO -> Triple(R.color.danger_soft, R.color.danger, R.drawable.ic_warning)
            StatusAnalise.INSUFICIENTE,
            StatusAnalise.NAO_ENCONTRADO -> Triple(R.color.white, R.color.stroke, R.drawable.ic_info)
        }
        val corInt = ContextCompat.getColor(this, cor)
        (binding.cardStatus.background.mutate() as GradientDrawable).apply {
            setColor(ContextCompat.getColor(this@ResultadoActivity, fundo))
            setStroke((1 * resources.displayMetrics.density).toInt(), corInt)
        }
        binding.icoStatus.setImageResource(icone)
        // O check já é verde; os demais ícones seguem a cor do status.
        if (analise.status != StatusAnalise.RECOMENDADO) {
            val tint = if (cor == R.color.stroke) ContextCompat.getColor(this, R.color.text_secondary) else corInt
            ImageViewCompat.setImageTintList(binding.icoStatus, ColorStateList.valueOf(tint))
        }

        val mostrarDica = analise.status == StatusAnalise.NAO_RECOMENDADO || analise.status == StatusAnalise.ATENCAO
        binding.txtDica.visibility = if (mostrarDica) View.VISIBLE else View.GONE
        binding.txtDica.setTextColor(corInt)
    }

    private fun mostrarMotivos(analise: Analise) {
        binding.listaMotivos.removeAllViews()
        val conflitos = analise.analise?.conflicts.orEmpty()
        val razoes = analise.analise?.reasons.orEmpty()

        // Conflitos têm termo e explicação; sem eles, mostra as razões gerais.
        if (conflitos.isNotEmpty()) {
            conflitos.forEach { conflito ->
                adicionarMotivo(
                    getString(R.string.contains_term, conflito.trechoOrigem?.takeIf { it.isNotBlank() } ?: conflito.term),
                    conflito.evidence,
                    alerta = true
                )
            }
        } else {
            razoes.forEach { razao -> adicionarMotivo(razao, null, alerta = false) }
        }

        binding.tituloMotivos.visibility = if (binding.listaMotivos.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun adicionarMotivo(titulo: String, descricao: String?, alerta: Boolean) {
        val item = ItemMotivoBinding.inflate(layoutInflater, binding.listaMotivos, true)
        item.titulo.text = titulo
        item.descricao.text = descricao
        item.descricao.visibility = if (descricao.isNullOrBlank()) View.GONE else View.VISIBLE
        if (!alerta) {
            item.icone.setImageResource(R.drawable.ic_info)
            item.titulo.textSize = 14f
        }
    }

    private fun mostrarIngredientes(analise: Analise) {
        if (analise.status == StatusAnalise.NAO_ENCONTRADO) {
            binding.tituloIngredientes.visibility = View.GONE
            binding.cardIngredientes.visibility = View.GONE
            return
        }

        val ingredientes = listarIngredientes(analise)
        if (ingredientes.isEmpty()) {
            binding.btnVerIngredientes.visibility = View.GONE
            binding.grupoIngredientes.visibility = View.GONE
            binding.txtSemIngredientes.visibility = View.VISIBLE
            return
        }

        // Termos que geraram conflito ficam destacados em vermelho.
        val termosConflito = analise.analise?.conflicts.orEmpty()
            .flatMap { listOfNotNull(it.trechoOrigem, it.term) }
            .map(::normalizar)
            .filter { it.isNotEmpty() }

        fun renderizar() {
            binding.grupoIngredientes.removeAllViews()
            val visiveis = if (ingredientesExpandidos) ingredientes else ingredientes.take(LIMITE_RECOLHIDO)
            visiveis.forEach { ingrediente ->
                val normalizado = normalizar(ingrediente)
                val conflito = termosConflito.any {
                    normalizado.contains(it) || (normalizado.length >= 3 && it.contains(normalizado))
                }
                binding.grupoIngredientes.adicionarChip(ingrediente, marcavel = false) {
                    textSize = 12f
                    if (conflito) {
                        setChipBackgroundColorResource(R.color.danger_soft)
                        setChipStrokeColorResource(R.color.danger_soft)
                        setTextColor(ContextCompat.getColor(context, R.color.danger))
                    } else {
                        setChipBackgroundColorResource(R.color.background)
                        setChipStrokeColorResource(R.color.background)
                    }
                }
            }
            binding.btnVerIngredientes.setText(
                if (ingredientesExpandidos) R.string.see_less_ingredients else R.string.see_all_ingredients
            )
        }

        binding.btnVerIngredientes.visibility =
            if (ingredientes.size > LIMITE_RECOLHIDO) View.VISIBLE else View.GONE
        binding.btnVerIngredientes.setOnClickListener {
            ingredientesExpandidos = !ingredientesExpandidos
            renderizar()
        }
        renderizar()
    }

    // Prefere o texto original do rótulo; a lista normalizada perde acentos.
    private fun listarIngredientes(analise: Analise): List<String> {
        val texto = analise.produto?.textoIngredientes
        val itens = if (!texto.isNullOrBlank()) {
            dividirIngredientes(texto)
        } else {
            analise.produto?.ingredientes.orEmpty()
        }
        return itens.map { it.trim().trimEnd('.') }.filter { it.isNotEmpty() }.distinct()
    }

    // Divide por vírgula/ponto e vírgula, sem quebrar o que está entre parênteses.
    private fun dividirIngredientes(texto: String): List<String> {
        val partes = mutableListOf<String>()
        val atual = StringBuilder()
        var profundidade = 0
        texto.forEach { c ->
            when {
                c == '(' || c == '[' -> { profundidade++; atual.append(c) }
                c == ')' || c == ']' -> { profundidade = maxOf(0, profundidade - 1); atual.append(c) }
                (c == ',' || c == ';') && profundidade == 0 -> { partes += atual.toString(); atual.clear() }
                else -> atual.append(c)
            }
        }
        partes += atual.toString()
        return partes
    }

    private fun normalizar(texto: String): String =
        Normalizer.normalize(texto.lowercase(), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9 ]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()

    companion object {
        private const val EXTRA_ANALISE = "analise"
        private const val LIMITE_RECOLHIDO = 8

        fun abrir(context: Context, analise: Analise) {
            context.startActivity(Intent(context, ResultadoActivity::class.java).apply {
                putExtra(EXTRA_ANALISE, analise)
            })
        }

        /** Converte a resposta da captura no mesmo modelo usado pelo histórico. */
        fun paraAnalise(context: Context, resposta: CapturaResponse, ean: String): Analise {
            val status = if (resposta.statusOrigem == StatusOrigem.NAO_ENCONTRADO) {
                StatusAnalise.NAO_ENCONTRADO
            } else {
                StatusAnalise.deApi(resposta.analysis?.status)
            }
            return Analise(
                nome = resposta.product?.nome
                    ?: resposta.analysis?.nomeProduto
                    ?: context.getString(R.string.product_fallback_name, ean),
                marca = resposta.product?.marca.orEmpty(),
                dataRelativa = "hoje",
                status = status,
                ean = resposta.product?.ean ?: ean,
                produto = resposta.product,
                analise = resposta.analysis
            )
        }
    }
}
