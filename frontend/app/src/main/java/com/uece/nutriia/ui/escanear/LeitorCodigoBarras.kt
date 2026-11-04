package com.uece.nutriia.ui.escanear

import androidx.annotation.OptIn
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Câmera (CameraX) + leitura de código de barras (ML Kit, modelo embutido no app).
 * A câmera segue o ciclo de vida da Activity: fecha no onStop e reabre no onStart.
 */
class LeitorCodigoBarras(
    private val activity: AppCompatActivity,
    private val previewView: PreviewView,
    private val aoLer: (String) -> Unit
) {
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val scanner = criarScanner()

    // Evita disparar várias análises para o mesmo produto.
    private val lido = AtomicBoolean(false)
    private var camera: Camera? = null
    private var flashLigado = false

    val ativo: Boolean get() = camera != null

    fun iniciar(aoFalhar: () -> Unit) {
        val futuro = ProcessCameraProvider.getInstance(activity)
        futuro.addListener({
            try {
                val provider = futuro.get()
                val preview = Preview.Builder().build().also {
                    it.surfaceProvider = previewView.surfaceProvider
                }
                val analise = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { it.setAnalyzer(executor, ::analisarQuadro) }

                provider.unbindAll()
                camera = provider.bindToLifecycle(
                    activity,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    analise
                )
                flashLigado = false
            } catch (e: Exception) {
                // Sem câmera traseira, câmera em uso por outro app etc.
                camera = null
                aoFalhar()
            }
        }, ContextCompat.getMainExecutor(activity))
    }

    /** Volta a aceitar leituras (ex.: ao retornar do resultado). */
    fun retomar() = lido.set(false)

    /** Liga/desliga o flash. Devolve o novo estado, ou null se não houver flash. */
    fun alternarFlash(): Boolean? {
        val atual = camera ?: return null
        if (!atual.cameraInfo.hasFlashUnit()) return null
        flashLigado = !flashLigado
        atual.cameraControl.enableTorch(flashLigado)
        return flashLigado
    }

    fun liberar() {
        scanner.close()
        executor.shutdown()
    }

    @OptIn(ExperimentalGetImage::class)
    private fun analisarQuadro(quadro: ImageProxy) {
        val imagem = quadro.image
        if (imagem == null || lido.get()) {
            quadro.close()
            return
        }
        val entrada = InputImage.fromMediaImage(imagem, quadro.imageInfo.rotationDegrees)
        scanner.process(entrada)
            .addOnSuccessListener { codigos ->
                val ean = primeiroEan(codigos)
                if (ean != null && lido.compareAndSet(false, true)) {
                    activity.runOnUiThread { aoLer(ean) }
                }
            }
            .addOnCompleteListener { quadro.close() }
    }

    companion object {
        // Mesma regra do backend: só dígitos, de 8 a 32.
        private val EAN_VALIDO = Regex("^[0-9]{8,32}$")

        /** Scanner restrito aos formatos usados em alimentos industrializados. */
        fun criarScanner(): BarcodeScanner = BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(
                    Barcode.FORMAT_EAN_13,
                    Barcode.FORMAT_EAN_8,
                    Barcode.FORMAT_UPC_A,
                    Barcode.FORMAT_UPC_E
                )
                .build()
        )

        /** Primeiro código lido que o backend aceita como EAN. */
        fun primeiroEan(codigos: List<Barcode>): String? =
            codigos.firstNotNullOfOrNull { it.rawValue?.takeIf(EAN_VALIDO::matches) }
    }
}
