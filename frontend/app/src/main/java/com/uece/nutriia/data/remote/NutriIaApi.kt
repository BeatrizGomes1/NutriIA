package com.uece.nutriia.data.remote

import com.uece.nutriia.data.model.ProdutoDto
import retrofit2.Call
import retrofit2.http.GET
import retrofit2.http.Path

interface NutriIaApi {
    @GET("produtos/{ean}")
    fun buscarProduto(@Path("ean") ean: String): Call<ProdutoDto>
}
