package com.uece.nutriia.ui.resultado

import com.google.gson.Gson
import com.uece.nutriia.data.model.InformacaoNutricionalDto
import org.junit.Assert.*
import org.junit.Test

class TabelaNutricionalTest {
    private fun dados(basis: String? = "per_serving", quantidade: Double? = 25.0,
                      unidade: String? = "g") =
        InformacaoNutricionalDto(124.0, 9.4, 9.4, 6.3, 98.0, 0.0, basis, quantidade, unidade)

    @Test fun ninhoShowsAllAvailableValuesWithCorrectPortion() {
        val tabela = TabelaNutricional.de(dados())!!
        assertEquals("Porção de 25 g", tabela.referencia)
        assertEquals("6,3 g", tabela.linhas.toMap()["Proteínas"])
        assertEquals("124 kcal", tabela.linhas.toMap()["Energia"])
        assertEquals("0 g", tabela.linhas.toMap()["Fibras"])
        assertEquals("98 mg", tabela.linhas.toMap()["Sódio"])
        assertEquals(6, tabela.linhas.size)
    }

    @Test fun unknownOrAbsentBasisNeverDisplaysQuantities() {
        for (basis in listOf("unknown", null, "invalid")) assertNull(TabelaNutricional.de(dados(basis)))
    }

    @Test fun servingRequiresQuantityAndUnit() {
        assertNull(TabelaNutricional.de(dados(quantidade = null)))
        assertNull(TabelaNutricional.de(dados(unidade = null)))
        assertNull(TabelaNutricional.de(dados(quantidade = 0.0)))
        assertNull(TabelaNutricional.de(dados(quantidade = Double.NaN)))
    }

    @Test fun hundredGramAndMillilitreValuesAreNeverConvertedToServing() {
        assertEquals("Por 100 g", TabelaNutricional.de(dados("per_100g"))!!.referencia)
        assertEquals("Por 100 ml", TabelaNutricional.de(dados("per_100ml"))!!.referencia)
        assertEquals("6,3 g", TabelaNutricional.de(dados("per_100ml"))!!.linhas.toMap()["Proteínas"])
    }

    @Test fun invalidAndMissingValuesAreOmittedWhileZeroIsPreserved() {
        val tabela = TabelaNutricional.de(InformacaoNutricionalDto(Double.NaN, -1.0, null,
            0.0, Double.POSITIVE_INFINITY, basis = "per_100g"))!!
        assertEquals(listOf("Proteínas" to "0 g"), tabela.linhas)
        assertNull(TabelaNutricional.de(InformacaoNutricionalDto(null, null, null, null, null, basis = "per_100g")))
    }

    @Test fun apiFieldsAreMappedAndLegacyResponseRemainsReadable() {
        val gson = Gson()
        val json = """{"protein_g":6.3,"calories_kcal":124,"fiber_g":0,"basis":"per_serving","serving_quantity":25,"serving_unit":"g"}"""
        assertEquals(3, TabelaNutricional.de(gson.fromJson(json, InformacaoNutricionalDto::class.java))!!.linhas.size)
        assertNull(TabelaNutricional.de(gson.fromJson("""{"protein_g":6.3}""", InformacaoNutricionalDto::class.java)))
    }
}
