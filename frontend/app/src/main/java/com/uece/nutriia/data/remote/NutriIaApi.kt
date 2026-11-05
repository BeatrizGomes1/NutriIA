package com.uece.nutriia.data.remote

import com.uece.nutriia.data.model.CapturaHistoricoResponse
import com.uece.nutriia.data.model.CapturaResponse
import com.uece.nutriia.data.model.EanCaptureRequest
import com.uece.nutriia.data.model.LoginRequest
import com.uece.nutriia.data.model.MensagemResponse
import com.uece.nutriia.data.model.PerfilRequest
import com.uece.nutriia.data.model.PerfilResponse
import com.uece.nutriia.data.model.RecuperarSenhaRequest
import com.uece.nutriia.data.model.RedefinirSenhaRequest
import com.uece.nutriia.data.model.TokenResponse
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

/** Rotas do backend (prefixo /api/v1 já está na BASE_URL). */
interface NutriIaApi {

    @POST("auth/register")
    suspend fun cadastrar(@Body corpo: PerfilRequest): Response<TokenResponse>

    @POST("auth/login")
    suspend fun entrar(@Body corpo: LoginRequest): Response<TokenResponse>

    @POST("auth/password-reset/request")
    suspend fun pedirRecuperacaoSenha(@Body corpo: RecuperarSenhaRequest): Response<MensagemResponse>

    @POST("auth/password-reset/confirm")
    suspend fun redefinirSenha(@Body corpo: RedefinirSenhaRequest): Response<MensagemResponse>

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

    /** Foto do rótulo (JPEG, PNG ou WEBP até 8 MB); o backend extrai os dados com o Gemini. */
    @Multipart
    @POST("profiles/{userId}/captures/label-photo")
    suspend fun capturarFotoRotulo(
        @Path("userId") userId: String,
        @Part file: MultipartBody.Part
    ): Response<CapturaResponse>

    @GET("profiles/{userId}/history/captures")
    suspend fun historicoCapturas(
        @Path("userId") userId: String,
        @Query("limit") limite: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<List<CapturaHistoricoResponse>>
}
