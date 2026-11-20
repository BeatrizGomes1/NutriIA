package com.uece.nutriia.ui.escanear

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.TimeUnit

/** Roda o ML Kit no aparelho com a mesma configuração usada pela câmera. */
@RunWith(AndroidJUnit4::class)
class LeitorCodigoBarrasTest {

    private val scanner = LeitorCodigoBarras.criarScanner()

    @After
    fun fechar() = scanner.close()

    @Test
    fun leEan13DeUmaImagem() {
        val bitmap = InstrumentationRegistry.getInstrumentation().context.assets
            .open("ean13_3017624010701.png")
            .use(BitmapFactory::decodeStream)

        assertEquals("3017624010701", ler(bitmap))
    }

    @Test
    fun imagemSemCodigoNaoDevolveEan() {
        val vazio = Bitmap.createBitmap(400, 200, Bitmap.Config.ARGB_8888).apply {
            eraseColor(Color.WHITE)
        }

        assertNull(ler(vazio))
    }

    private fun ler(bitmap: Bitmap): String? {
        val codigos = Tasks.await(scanner.process(InputImage.fromBitmap(bitmap, 0)), 30, TimeUnit.SECONDS)
        return LeitorCodigoBarras.primeiroEan(codigos)
    }
}
