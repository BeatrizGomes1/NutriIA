package com.uece.nutriia.ui.escanear

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import java.io.File
import java.io.FileOutputStream
import kotlin.math.max

/**
 * Deixa a foto do rótulo pronta para o backend: no máximo [LADO_MAXIMO] px no
 * maior lado, na orientação certa e em JPEG (bem abaixo do limite de 8 MB).
 * Faz leitura de disco/decodificação: chame fora da thread principal.
 */
object PreparadorFoto {
    private const val LADO_MAXIMO = 2048
    private const val QUALIDADE_JPEG = 88

    /** Foto tirada pela câmera do app (já em memória, com a rotação do sensor). */
    fun deBitmap(context: Context, bitmap: Bitmap, rotacaoGraus: Int): File =
        salvar(context, reduzir(girar(bitmap, rotacaoGraus)))

    /** Foto escolhida na galeria. */
    fun deUri(context: Context, uri: Uri): File {
        val resolver = context.contentResolver

        // Lê só as dimensões para decodificar já reduzida.
        val limites = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, limites) }
        var amostra = 1
        while (max(limites.outWidth, limites.outHeight) / (amostra * 2) >= LADO_MAXIMO) amostra *= 2

        val bitmap = resolver.openInputStream(uri).use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = amostra })
        } ?: throw IllegalArgumentException("Imagem inválida")

        val rotacao = resolver.openInputStream(uri)?.use { rotacaoExif(ExifInterface(it)) } ?: 0
        return deBitmap(context, bitmap, rotacao)
    }

    private fun rotacaoExif(exif: ExifInterface): Int =
        when (exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90
            ExifInterface.ORIENTATION_ROTATE_180 -> 180
            ExifInterface.ORIENTATION_ROTATE_270 -> 270
            else -> 0
        }

    private fun girar(bitmap: Bitmap, graus: Int): Bitmap {
        if (graus % 360 == 0) return bitmap
        val matriz = Matrix().apply { postRotate(graus.toFloat()) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matriz, true)
    }

    private fun reduzir(bitmap: Bitmap): Bitmap {
        val maior = max(bitmap.width, bitmap.height)
        if (maior <= LADO_MAXIMO) return bitmap
        val escala = LADO_MAXIMO.toFloat() / maior
        return Bitmap.createScaledBitmap(
            bitmap,
            (bitmap.width * escala).toInt(),
            (bitmap.height * escala).toInt(),
            true
        )
    }

    private fun salvar(context: Context, bitmap: Bitmap): File {
        val arquivo = File.createTempFile("rotulo_", ".jpg", context.cacheDir)
        FileOutputStream(arquivo).use { bitmap.compress(Bitmap.CompressFormat.JPEG, QUALIDADE_JPEG, it) }
        return arquivo
    }
}
