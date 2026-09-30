package com.uece.nutriia.ui.inicio

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.uece.nutriia.R
import com.uece.nutriia.data.mock.MockData
import com.uece.nutriia.databinding.ActivityInicioBinding
import com.uece.nutriia.ui.common.BottomNavigationBinder
import com.uece.nutriia.ui.common.BottomTab
import com.uece.nutriia.ui.common.ScreenInsets
import com.uece.nutriia.ui.escanear.EscanearActivity
import com.uece.nutriia.ui.historico.HistoricoActivity

class InicioActivity : AppCompatActivity() {

    private lateinit var binding: ActivityInicioBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        binding = ActivityInicioBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ScreenInsets.apply(binding.root, binding.bottomNav.root)
        BottomNavigationBinder.bind(this, binding.bottomNav, BottomTab.INICIO)

        binding.txtGreeting.text = getString(R.string.greeting, MockData.NOME_USUARIA)

        val ultima = MockData.analises.first()
        binding.txtUltimaNome.text = ultima.nome
        binding.txtUltimaMarca.text = getString(
            R.string.marca_data_format,
            ultima.marca,
            ultima.dataRelativa
        )
        binding.txtUltimaStatus.text = getString(R.string.not_recommended)
        binding.txtUltimaStatus.setTextColor(ContextCompat.getColor(this, R.color.danger))

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
            Toast.makeText(this, R.string.coming_soon, Toast.LENGTH_SHORT).show()
        }
    }
}
