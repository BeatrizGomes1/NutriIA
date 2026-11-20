package com.uece.nutriia.data.model

import com.google.gson.annotations.SerializedName

/** Valores aceitos pelo backend no campo `objective`. */
object Objetivo {
    const val PERDA_DE_PESO = "weight_loss"
    const val GANHO_DE_MASSA = "muscle_gain"
}

data class LoginRequest(
    val email: String,
    val password: String
)

/** Corpo de POST /auth/register e, sem a senha, de PUT /profiles/{id}. */
data class PerfilRequest(
    @SerializedName("name_or_nickname") val nome: String,
    val email: String,
    @SerializedName("age_range") val faixaEtaria: String? = null,
    val objective: String,
    @SerializedName("declared_allergies") val alergias: List<String> = emptyList(),
    @SerializedName("avoided_ingredients") val ingredientesEvitados: List<String> = emptyList(),
    @SerializedName("food_preferences") val preferencias: List<String> = emptyList(),
    @SerializedName("onboarding_completed") val onboardingConcluido: Boolean = true,
    // Só é enviado no cadastro; o Gson omite campos nulos.
    val password: String? = null
)

data class PerfilResponse(
    val id: String,
    @SerializedName("name_or_nickname") val nome: String,
    val email: String,
    @SerializedName("age_range") val faixaEtaria: String?,
    val objective: String,
    @SerializedName("declared_allergies") val alergias: List<String>,
    @SerializedName("avoided_ingredients") val ingredientesEvitados: List<String>,
    @SerializedName("food_preferences") val preferencias: List<String>,
    @SerializedName("onboarding_completed") val onboardingConcluido: Boolean
) {
    fun paraRequest(): PerfilRequest = PerfilRequest(
        nome = nome,
        email = email,
        faixaEtaria = faixaEtaria,
        objective = objective,
        alergias = alergias,
        ingredientesEvitados = ingredientesEvitados,
        preferencias = preferencias,
        onboardingConcluido = onboardingConcluido
    )
}

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String,
    @SerializedName("expires_in") val expiraEmSegundos: Long,
    val user: PerfilResponse
)

data class RefreshRequest(
    @SerializedName("refresh_token") val refreshToken: String
)

data class RecuperarSenhaRequest(
    val email: String
)

data class RedefinirSenhaRequest(
    val token: String,
    @SerializedName("new_password") val novaSenha: String
)

/** Resposta simples ({"message": "..."}) das rotas de recuperação de senha. */
data class MensagemResponse(
    val message: String
)
