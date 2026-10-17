package com.uece.nutriia.ui.escanear

import android.os.Bundle
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import com.uece.nutriia.R
import com.uece.nutriia.databinding.ActivityEscanearBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets

class EscanearActivity : AppCompatActivity() {

    private lateinit var binding: ActivityEscanearBinding
    private var flashLigado = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        binding = ActivityEscanearBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.ESCANEAR)

        binding.btnFlash.setOnClickListener {
            flashLigado = !flashLigado
            val mensagem = if (flashLigado) R.string.flash_on else R.string.flash_off
            Toast.makeText(this, mensagem, Toast.LENGTH_SHORT).show()
        }
        binding.btnUsarCamera.setOnClickListener {
            Toast.makeText(this, R.string.camera_placeholder, Toast.LENGTH_SHORT).show()
        }
        binding.btnSimularEan.setOnClickListener {
            Toast.makeText(this, R.string.ean_simulado, Toast.LENGTH_SHORT).show()
        }
        binding.txtSemCamera.setOnClickListener {
            Toast.makeText(this, R.string.ean_simulado, Toast.LENGTH_SHORT).show()
        }
    }
}
