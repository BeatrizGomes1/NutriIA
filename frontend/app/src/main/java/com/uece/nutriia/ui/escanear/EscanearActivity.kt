package com.uece.nutriia.ui.escanear

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.HapticFeedbackConstants
import android.view.View
import android.widget.EditText
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.uece.nutriia.R
import com.uece.nutriia.databinding.ActivityEscanearBinding
import com.uece.nutriia.ui.analise.AnaliseAndamentoActivity
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.common.exigirSessao

class EscanearActivity : AppCompatActivity() {

    private lateinit var binding: ActivityEscanearBinding
    private var leitor: LeitorCodigoBarras? = null

    private val pedirPermissaoCamera =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { concedida ->
            if (concedida) {
                iniciarCamera()
            } else {
                Toast.makeText(this, R.string.camera_permission_denied, Toast.LENGTH_LONG).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!exigirSessao()) return
        enableEdgeToEdge()
        binding = ActivityEscanearBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.ESCANEAR)

        // Recorta a prévia da câmera nos cantos arredondados do scanner.
        binding.frameScanner.clipToOutline = true

        binding.btnFlash.setOnClickListener { alternarFlash() }
        binding.btnUsarCamera.setOnClickListener { usarCamera() }
        binding.btnSimularEan.setOnClickListener {
            analisar(getString(R.string.ean_simulado_valor))
        }
        binding.txtSemCamera.setOnClickListener { pedirEanDigitado() }

        // Se a permissão já foi dada antes, a câmera abre direto.
        if (temPermissaoCamera()) iniciarCamera()
    }

    override fun onResume() {
        super.onResume()
        // Ao voltar do resultado, aceita uma nova leitura.
        leitor?.retomar()
    }

    override fun onDestroy() {
        leitor?.liberar()
        super.onDestroy()
    }

    private fun temPermissaoCamera() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun usarCamera() {
        if (temPermissaoCamera()) iniciarCamera()
        else pedirPermissaoCamera.launch(Manifest.permission.CAMERA)
    }

    private fun iniciarCamera() {
        if (leitor?.ativo == true) return
        val novo = leitor ?: LeitorCodigoBarras(this, binding.previewCamera) { ean ->
            binding.root.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            analisar(ean)
        }.also { leitor = it }

        mostrarPrevia(true)
        novo.iniciar(aoFalhar = {
            mostrarPrevia(false)
            Toast.makeText(this, R.string.camera_unavailable, Toast.LENGTH_LONG).show()
        })
    }

    private fun mostrarPrevia(ativa: Boolean) {
        binding.previewCamera.visibility = if (ativa) View.VISIBLE else View.GONE
        binding.guiaLeitura.visibility = if (ativa) View.VISIBLE else View.GONE
        binding.iconeCamera.visibility = if (ativa) View.GONE else View.VISIBLE
        binding.txtDicaScanner.setText(if (ativa) R.string.scan_hint_active else R.string.scan_hint)
    }

    private fun alternarFlash() {
        val atual = leitor
        if (atual == null || !atual.ativo) {
            Toast.makeText(this, R.string.flash_needs_camera, Toast.LENGTH_SHORT).show()
            return
        }
        val mensagem = when (atual.alternarFlash()) {
            null -> R.string.flash_unavailable
            true -> R.string.flash_on
            false -> R.string.flash_off
        }
        Toast.makeText(this, mensagem, Toast.LENGTH_SHORT).show()
    }

    private fun pedirEanDigitado() {
        val conteudo = layoutInflater.inflate(R.layout.dialog_digitar_ean, null)
        val edtEan = conteudo.findViewById<EditText>(R.id.edtEan)
        val dialog = MaterialAlertDialogBuilder(this)
            .setTitle(R.string.type_ean_title)
            .setView(conteudo)
            .setPositiveButton(R.string.analyze, null)
            .setNegativeButton(R.string.cancel, null)
            .show()
        // Valida antes de fechar o diálogo.
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            val ean = edtEan.text.toString().trim()
            if (!EAN_VALIDO.matches(ean)) {
                edtEan.error = getString(R.string.invalid_ean)
            } else {
                dialog.dismiss()
                analisar(ean)
            }
        }
    }

    private fun analisar(ean: String) = AnaliseAndamentoActivity.abrir(this, ean)

    private companion object {
        // Mesma regra do backend: só dígitos, de 8 a 32.
        val EAN_VALIDO = Regex("^[0-9]{8,32}$")
    }
}
