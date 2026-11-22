package com.uece.nutriia.ui.resultado

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.View
import android.widget.TextView
import android.widget.LinearLayout
import android.graphics.Typeface
import android.widget.Toast
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
    private lateinit var apresentacao: ResultadoPresentation

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

        apresentacao = ApresentadorResultado.apresentar(analise)
        mostrarCabecalho(analise)
        mostrarStatus(analise)
        mostrarMotivos()
        mostrarTabelaNutricional()
        mostrarIngredientes(analise)

        binding.btnAvaliarAnalise.setOnClickListener {
            val marca = analise.produto?.marca?.takeIf { it.isNotBlank() }
            AvaliacaoBottomSheet
                .newInstance(analise.nome, marca)
                .show(supportFragmentManager, "avaliacao")
        }
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
        if (analise.analise == null) when (analise.processamento) {
            "pending" -> binding.txtStatus.setText(R.string.analysis_pending)
            "failed" -> binding.txtStatus.setText(R.string.analysis_failed)
            "unlinked" -> binding.txtStatus.setText(R.string.analysis_unlinked)
        }
        binding.txtResumo.text = apresentacao.resumo

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

        binding.txtDica.visibility = View.GONE
    }

    private fun mostrarMotivos() {
        binding.listaMotivos.removeAllViews()
        binding.listaInformacoesNutricionais.removeAllViews()
        apresentacao.alertas.forEach { alerta ->
            adicionarMotivo(alerta.titulo, alerta.descricao, true, alerta.originais)
        }
        apresentacao.motivosVisiveis.forEach { adicionarMotivo(it, null, false) }
        if (apresentacao.detalhes.isNotEmpty()) adicionarMotivo(apresentacao.detalhes.joinToString("\n\n"), null, false, nutricional = true)
        binding.tituloMotivos.visibility = if (binding.listaMotivos.isEmpty()) View.GONE else View.VISIBLE
        binding.tituloInformacoesNutricionais.visibility =
            if (binding.listaInformacoesNutricionais.isEmpty()) View.GONE else View.VISIBLE
        binding.listaInformacoesNutricionais.visibility = View.GONE
        var detalhesExpandidos = false
        binding.tituloInformacoesNutricionais.setText(R.string.show_analysis_details)
        binding.tituloInformacoesNutricionais.setOnClickListener {
            detalhesExpandidos = !detalhesExpandidos
            binding.listaInformacoesNutricionais.visibility = if (detalhesExpandidos) View.VISIBLE else View.GONE
            binding.tituloInformacoesNutricionais.setText(
                if (detalhesExpandidos) R.string.hide_analysis_details else R.string.show_analysis_details)
            binding.tituloInformacoesNutricionais.isSelected = detalhesExpandidos
        }
    }

    private fun adicionarMotivo(
        titulo: String, descricao: String?, alerta: Boolean,
        originais: List<String> = emptyList(), nutricional: Boolean = false
    ) {
        val container = if (nutricional) binding.listaInformacoesNutricionais else binding.listaMotivos
        val item = ItemMotivoBinding.inflate(layoutInflater, container, true)
        item.titulo.text = titulo
        item.descricao.text = descricao
        item.descricao.visibility = if (descricao.isNullOrBlank()) View.GONE else View.VISIBLE
        if (!alerta) {
            item.icone.setImageResource(R.drawable.ic_info)
            item.titulo.textSize = 14f
        }
        if (originais.isNotEmpty()) {
            item.btnVerOriginais.visibility = View.VISIBLE
            var expandido = false
            item.btnVerOriginais.setOnClickListener {
                expandido = !expandido
                item.descricao.text = if (expandido) listOfNotNull(descricao,
                    originais.joinToString("\n") { "\u2022 $it" }).joinToString("\n\n") else descricao
                item.descricao.visibility = View.VISIBLE
                item.btnVerOriginais.setText(if (expandido) R.string.hide_label_details else R.string.show_label_details)
                item.btnVerOriginais.isSelected = expandido
            }
        }
    }

    private fun mostrarTabelaNutricional() {
        binding.tabelaNutricional.removeAllViews()
        val tabela = apresentacao.tabela ?: run {
            binding.tabelaNutricional.visibility = View.GONE
            return
        }
        binding.tabelaNutricional.visibility = View.VISIBLE
        binding.tabelaNutricional.addView(TextView(this).apply {
            text = getString(R.string.nutrition_table_reference, tabela.referencia)
            setTextColor(ContextCompat.getColor(context, R.color.text_primary))
            textSize = 15f
            setTypeface(null, Typeface.BOLD)
            setPadding(0, 0, 0, 12)
        })
        tabela.linhas.forEach { (nome, valor) ->
            binding.tabelaNutricional.addView(LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                setPadding(0, 4, 0, 4)
                addView(TextView(context).apply {
                    text = nome
                    setTextColor(ContextCompat.getColor(context, R.color.text_primary))
                }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
                addView(TextView(context).apply {
                    text = valor
                    setTextColor(ContextCompat.getColor(context, R.color.text_primary))
                })
            })
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
        /** [ean] é null quando a análise veio da foto do rótulo. */
        fun paraAnalise(context: Context, resposta: CapturaResponse, ean: String?): Analise {
            val status = if (resposta.statusOrigem == StatusOrigem.NAO_ENCONTRADO) {
                StatusAnalise.NAO_ENCONTRADO
            } else {
                StatusAnalise.deApi(resposta.analysis?.status)
            }
            return Analise(
                nome = resposta.product?.nome
                    ?: resposta.analysis?.nomeProduto
                    ?: ean?.let { context.getString(R.string.product_fallback_name, it) }
                    ?: context.getString(R.string.product_from_label),
                marca = resposta.product?.marca.orEmpty(),
                dataRelativa = "hoje",
                status = status,
                ean = resposta.product?.ean ?: ean,
                produto = resposta.product,
                analise = resposta.analysis,
                origemAnalise = resposta.origemAnalise,
                processamento = resposta.processamento
            )
        }
    }
}
