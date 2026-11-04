package com.uece.nutriia.data.remote

import com.uece.nutriia.data.model.CapturaHistoricoResponse
import com.uece.nutriia.data.model.CapturaResponse
import com.uece.nutriia.data.model.EanCaptureRequest
import com.uece.nutriia.data.model.LoginRequest
import com.uece.nutriia.data.model.PerfilRequest
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.model.TokenResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** Rotas do backend (prefixo /api/v1 já está na BASE_URL). */
interface NutriIaApi {

    @POST("auth/register")
    suspend fun cadastrar(@Body corpo: PerfilRequest): Response<TokenResponse>

    @POST("auth/login")
    suspend fun entrar(@Body corpo: LoginRequest): Response<TokenResponse>

    @GET("auth/me")
    suspend fun perfilAutenticado(): Response<PerfilResponse>

    @PUT("profiles/{userId}")
    suspend fun atualizarPerfil(
        @Path("userId") userId: String,
        @Body corpo: PerfilRequest
    ): Response<PerfilResponse>

    @POST("profiles/{userId}/captures/ean")
    suspend fun capturarEan(
        @Path("userId") userId: String,
        @Body corpo: EanCaptureRequest
    ): Response<CapturaResponse>

    @GET("profiles/{userId}/history/captures")
    suspend fun historicoCapturas(
        @Path("userId") userId: String,
        @Query("limit") limite: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<List<CapturaHistoricoResponse>>
}
