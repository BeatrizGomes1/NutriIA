package com.uece.nutriia

import android.app.Application
import com.uece.nutriia.data.local.SessionManager

class NutriIaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        SessionManager.init(this)
    }
}
