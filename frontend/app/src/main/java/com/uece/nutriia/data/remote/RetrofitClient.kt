package com.uece.nutriia.data.remote

import android.util.Log
import com.uece.nutriia.BuildConfig
import com.uece.nutriia.data.local.SessionManager
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    private const val BASE_URL = BuildConfig.API_BASE_URL

    // Nunca grava senha nem token no logcat.
    private val CAMPOS_SENSIVEIS =
        Regex("\"(password|new_password|access_token|refresh_token|token)\"\\s*:\\s*\"[^\"]*\"")

    private val logging = HttpLoggingInterceptor { mensagem ->
        Log.i("NutriIaHttp", mensagem.replace(CAMPOS_SENSIVEIS, "\"$1\":\"***\""))
    }.apply {
        level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY else HttpLoggingInterceptor.Level.NONE
        redactHeader("Authorization")
    }

    private val renovador = RenovadorSessao { refreshApi }

    // Anexa o token salvo; se ele já expirou, renova antes de enviar.
    private val authInterceptor = Interceptor { chain ->
        val token = when {
            SessionManager.token == null -> null
            SessionManager.acessoExpirado -> renovador.tokenValido() ?: SessionManager.token
            else -> SessionManager.token
        }
        val request = if (token != null) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        chain.proceed(request)
    }

    private fun builder() = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        // A análise com IA (principalmente por foto) pode demorar.
        .readTimeout(90, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)

    private val httpClient = builder()
        .addInterceptor(authInterceptor)
        .authenticator(renovador)
        .addInterceptor(logging)
        .build()

    // Cliente só para o refresh: sem auth nem authenticator.
    private val refreshClient = builder()
        .addInterceptor(logging)
        .build()

    private fun retrofit(client: OkHttpClient) = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(client)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val api: NutriIaApi by lazy { retrofit(httpClient).create(NutriIaApi::class.java) }

    private val refreshApi: RefreshApi by lazy { retrofit(refreshClient).create(RefreshApi::class.java) }
}
