package com.uece.nutriia.ui.common

import android.view.LayoutInflater
import android.widget.EditText
import android.widget.FrameLayout
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.children
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.uece.nutriia.R

/** Cria um chip no estilo do app (branco, verde quando marcado). */
fun ChipGroup.adicionarChip(
    texto: String,
    marcavel: Boolean = true,
    marcado: Boolean = false,
    configurar: Chip.() -> Unit = {}
): Chip {
    val chip = (LayoutInflater.from(context).inflate(R.layout.view_chip, this, false) as Chip).apply {
        text = texto
        isCheckable = marcavel
        isChecked = marcado
        isCheckedIconVisible = marcavel
        // "+" quando desmarcado, check quando marcado (como no Figma).
        if (marcavel) {
            setChipIconResource(R.drawable.ic_add)
            isChipIconVisible = !marcado
            setOnCheckedChangeListener { _, checked -> isChipIconVisible = !checked }
        }
        setEnsureMinTouchTargetSize(false)
        configurar()
    }
    // Mantém um eventual chip "Outros" sempre no final.
    val outros = children.indexOfFirst { it.tag == TAG_OUTROS }
    if (outros >= 0) addView(chip, outros) else addView(chip)
    return chip
}

/** Textos dos chips marcados, ignorando o "Outros". */
fun ChipGroup.textosMarcados(): List<String> =
    children.filterIsInstance<Chip>()
        .filter { it.isChecked && it.tag != TAG_OUTROS }
        .map { it.text.toString() }
        .toList()

/** Chip "+ Outros" que abre um campo para o usuário digitar um item livre. */
fun ChipGroup.adicionarChipOutros(activity: AppCompatActivity) {
    adicionarChip(activity.getString(R.string.other), marcavel = false) {
        tag = TAG_OUTROS
        setChipIconResource(R.drawable.ic_add)
        isChipIconVisible = true
        setOnClickListener {
            activity.pedirTexto(R.string.other_title) { termo ->
                val existente = children.filterIsInstance<Chip>()
                    .firstOrNull { it.text.toString().equals(termo, ignoreCase = true) }
                if (existente != null) existente.isChecked = true
                else adicionarChip(termo, marcado = true)
            }
        }
    }
}

/** Diálogo simples com um campo de texto. */
fun AppCompatActivity.pedirTexto(titulo: Int, aoConfirmar: (String) -> Unit) {
    val campo = EditText(this).apply {
        setHint(R.string.other_hint)
        setBackgroundResource(R.drawable.bg_input)
        val p = (16 * resources.displayMetrics.density).toInt()
        setPadding(p, p, p, p)
        maxLines = 1
    }
    val container = FrameLayout(this).apply {
        val p = (24 * resources.displayMetrics.density).toInt()
        setPadding(p, p / 3, p, 0)
        addView(campo)
    }
    val dialog = MaterialAlertDialogBuilder(this)
        .setTitle(titulo)
        .setView(container)
        .setPositiveButton(R.string.add, null)
        .setNegativeButton(R.string.cancel, null)
        .show()
    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
        val termo = campo.text.toString().trim()
        if (termo.isNotEmpty()) {
            dialog.dismiss()
            aoConfirmar(termo)
        }
    }
}

private const val TAG_OUTROS = "outros"
