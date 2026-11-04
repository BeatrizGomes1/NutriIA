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
    private val CAMPOS_SENSIVEIS = Regex("\"(password|access_token)\"\\s*:\\s*\"[^\"]*\"")

    private val logging = HttpLoggingInterceptor { mensagem ->
        Log.i("NutriIaHttp", mensagem.replace(CAMPOS_SENSIVEIS, "\"$1\":\"***\""))
    }.apply {
        level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY else HttpLoggingInterceptor.Level.NONE
        redactHeader("Authorization")
    }

    // Anexa o token salvo às requisições quando houver sessão.
    private val authInterceptor = Interceptor { chain ->
        val token = SessionManager.token
        val request = if (token != null) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        chain.proceed(request)
    }

    private val httpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(logging)
        .connectTimeout(30, TimeUnit.SECONDS)
        // A análise com IA pode demorar mais que uma requisição comum.
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    val api: NutriIaApi by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(NutriIaApi::class.java)
    }
}
