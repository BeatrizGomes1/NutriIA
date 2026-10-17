package com.uece.nutriia.ui.common

import android.content.Intent
import android.content.res.ColorStateList
import android.view.View
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.widget.ImageViewCompat
import com.uece.nutriia.R
import com.uece.nutriia.databinding.IncludeBottomNavBinding
import com.uece.nutriia.ui.escanear.EscanearActivity
import com.uece.nutriia.ui.historico.HistoricoActivity
import com.uece.nutriia.ui.inicio.InicioActivity

enum class BottomTab {
    INICIO, HISTORICO, ESCANEAR
}

object ScreenInsets {
    fun apply(root: View, bottomNav: View) {
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(view.paddingLeft, bars.top, view.paddingRight, view.paddingBottom)
            bottomNav.setPadding(
                bottomNav.paddingLeft,
                bottomNav.paddingTop,
                bottomNav.paddingRight,
                bars.bottom + 6
            )
            insets
        }
    }
}

object BottomNavigationBinder {
    fun bind(activity: AppCompatActivity, nav: IncludeBottomNavBinding, selected: BottomTab) {
        val selectedColor = ContextCompat.getColor(activity, R.color.green_primary)
        val unselectedColor = ContextCompat.getColor(activity, R.color.nav_unselected)

        styleItem(nav.navInicioIcon, nav.navInicioLabel, selected == BottomTab.INICIO, selectedColor, unselectedColor)
        styleItem(nav.navHistoricoIcon, nav.navHistoricoLabel, selected == BottomTab.HISTORICO, selectedColor, unselectedColor)
        nav.navEscanearLabel.setTextColor(
            if (selected == BottomTab.ESCANEAR) selectedColor else unselectedColor
        )
        ImageViewCompat.setImageTintList(
            nav.navEscanearIcon,
            ColorStateList.valueOf(ContextCompat.getColor(activity, R.color.white))
        )

        nav.navInicio.setOnClickListener {
            openTab(activity, InicioActivity::class.java, selected == BottomTab.INICIO)
        }
        nav.navHistorico.setOnClickListener {
            openTab(activity, HistoricoActivity::class.java, selected == BottomTab.HISTORICO)
        }
        nav.navEscanear.setOnClickListener {
            openTab(activity, EscanearActivity::class.java, selected == BottomTab.ESCANEAR)
        }
        nav.navRestricoes.setOnClickListener {
            Toast.makeText(activity, R.string.coming_soon, Toast.LENGTH_SHORT).show()
        }
        nav.navPerfil.setOnClickListener {
            Toast.makeText(activity, R.string.coming_soon, Toast.LENGTH_SHORT).show()
        }
    }

    private fun styleItem(
        icon: ImageView,
        label: TextView,
        selected: Boolean,
        selectedColor: Int,
        unselectedColor: Int
    ) {
        val color = if (selected) selectedColor else unselectedColor
        ImageViewCompat.setImageTintList(icon, ColorStateList.valueOf(color))
        label.setTextColor(color)
    }

    private fun openTab(activity: AppCompatActivity, destination: Class<*>, alreadySelected: Boolean) {
        if (alreadySelected) return
        val intent = Intent(activity, destination).apply {
            addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_NO_ANIMATION)
        }
        activity.startActivity(intent)
        @Suppress("DEPRECATION")
        activity.overridePendingTransition(0, 0)
    }
}
