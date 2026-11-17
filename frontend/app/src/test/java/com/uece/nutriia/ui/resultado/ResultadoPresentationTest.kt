package com.uece.nutriia.ui.resultado

import com.uece.nutriia.data.model.Analise
import com.uece.nutriia.data.model.InformacaoNutricionalDto
import com.uece.nutriia.data.model.AnaliseDto
import com.uece.nutriia.data.model.ConflitoDto
import com.uece.nutriia.data.model.ProdutoDto
import com.uece.nutriia.data.model.StatusAnalise
import org.junit.Assert.*
import org.junit.Test

class ResultadoPresentationTest {
    private val ninho = InformacaoNutricionalDto(124.0, null, null, 6.3, null, 0.0, "per_serving", 25.0, "g")
    private val ausencia = "A aus\u00eancia de conflito identificado n\u00e3o garante seguran\u00e7a alimentar."
    private fun conflito(alvo: String, fonte: String, possivel: Boolean = false, categoria: String = "allergy") =
        ConflitoDto(fonte, categoria, alvo,
            if (possivel) "Poss\u00edvel contamina\u00e7\u00e3o cruzada: $fonte" else "Presen\u00e7a declarada na fonte: $fonte", fonte)

    private fun analise(
        status: StatusAnalise = StatusAnalise.NAO_RECOMENDADO,
        conflitos: List<ConflitoDto> = emptyList(), razoes: List<String> = emptyList(), ingredientes: String? = "Leite integral, enzima lactase",
        nutricao: InformacaoNutricionalDto? = null
    ): Analise {
        val produto = if (ingredientes != null) ProdutoDto(null, "Leite Integral Zero Lactose", "La Serenissima",
            "7896048706126", null, ingredientes, nutricao) else null
        return Analise("Leite Integral Zero Lactose", "La Serenissima", "hoje", status,
            produto = produto, analise = AnaliseDto(null, null, status.valorApi, "Product",
                "Mensagem longa. Outra mensagem. Terceira mensagem. Termos tecnicos.", razoes, conflitos, null, null))
    }

    @Test fun milkAndLeiteBecomeOneAlertWithoutChangingBackendEvidence() {
        val conflitos = listOf(conflito("leite", "Leite integral"), conflito("milk", "milk"))
        val input = analise(conflitos = conflitos, razoes = conflitos.map { it.evidence } + ausencia)
        val result = ApresentadorResultado.apresentar(input)
        assertEquals(1, result.alertas.size)
        assertEquals("Cont\u00e9m leite", result.alertas.single().titulo)
        assertTrue(result.alertas.single().originais.containsAll(listOf("Leite integral", "milk")))
        assertEquals(conflitos, input.analise!!.conflicts)
        assertEquals(StatusAnalise.NAO_RECOMENDADO, input.status)
        assertFalse(result.motivos.any { it.contains("aus\u00eancia") })
        assertFalse(result.motivos.any { it in conflitos.map { c -> c.evidence } })
    }

    @Test fun unrelatedAllergensAreNotMergedOrDropped() {
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(
            conflito("milk", "milk"), conflito("soy", "soy lecithin"), conflito("wheat", "wheat flour"))))
        assertEquals(setOf("Cont\u00e9m leite", "Cont\u00e9m soja", "Cont\u00e9m trigo"), result.alertas.map { it.titulo }.toSet())
    }

    @Test fun lactoseAndMilkProteinRemainDifferentTargets() {
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(
            conflito("prote\u00ednas do leite", "whey"), conflito("lactose", "lactose", categoria = "restriction"))))
        assertEquals(2, result.alertas.size)
        assertTrue(result.alertas.any { it.titulo == "Cont\u00e9m leite" })
        assertTrue(result.alertas.any { it.titulo == "Cont\u00e9m lactose" })
    }

    @Test fun crossContactAloneIsNotPresentedAsConfirmedPresence() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO,
            listOf(conflito("leite", "Pode conter leite", possivel = true))))
        assertEquals("Pode conter leite", result.alertas.single().titulo)
        assertFalse(result.alertas.single().confirmado)
        assertTrue(result.alertas.single().descricao.contains("sem confirmar"))
    }

    @Test fun confirmedAndPossibleEvidenceStayAccessibleWithinOneAlert() {
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(
            conflito("leite", "Leite integral"), conflito("milk", "May contain milk", possivel = true))))
        val alerta = result.alertas.single()
        assertTrue(alerta.confirmado && alerta.possivel)
        assertTrue(alerta.descricao.contains("tamb\u00e9m"))
        assertTrue(alerta.originais.containsAll(listOf("Leite integral", "May contain milk")))
    }

    @Test fun noConfirmedConflictRetainsSafetyCaution() {
        val input = analise(StatusAnalise.ATENCAO, razoes = listOf(ausencia, ausencia))
        val result = ApresentadorResultado.apresentar(input)
        assertTrue(result.alertas.isEmpty())
        assertEquals(1, result.motivos.size)
        assertTrue(result.motivos.single().contains("n\u00e3o garante"))
        assertEquals(StatusAnalise.ATENCAO, input.status)
    }

    @Test fun insufficientIngredientsRemainProminent() {
        val motivo = "A lista de ingredientes est\u00e1 ausente, ileg\u00edvel ou incompleta."
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.INSUFICIENTE,
            razoes = listOf(motivo, ausencia), ingredientes = null))
        assertTrue(result.resumo.contains("Faltam informa\u00e7\u00f5es"))
        assertTrue(result.motivos.contains(motivo))
    }

    @Test fun ingredientListIsNotRepeatedWhenTheIngredientSectionHasData() {
        val reason = "Ingredientes informados: Leite integral, enzima lactase"
        val input = analise(razoes = listOf(reason))
        val result = ApresentadorResultado.apresentar(input)
        assertFalse((result.motivos + result.informacoesNutricionais).contains(reason))
        assertEquals("Leite integral, enzima lactase", input.produto!!.textoIngredientes)
        assertTrue(ApresentadorResultado.apresentar(analise(razoes = listOf(reason), ingredientes = null)).motivos.contains(reason))
    }

    @Test fun personalizedNutritionIsSeparateAndDeduplicated() {
        val goal = "H\u00e1 prote\u00edna informada no r\u00f3tulo, relevante para contextualizar seu objetivo de ganho de massa muscular; isso n\u00e3o comprova adequa\u00e7\u00e3o da dieta."
        val lactose = "O produto declara 'Zero Lactose', relacionado \u00e0 prefer\u00eancia 'Sem lactose'; essa declara\u00e7\u00e3o n\u00e3o garante seguran\u00e7a para alergias."
        val basis = "A refer\u00eancia dos valores nutricionais \u00e9 desconhecida; n\u00e3o \u00e9 poss\u00edvel quantificar por por\u00e7\u00e3o ou comparar teores com confian\u00e7a."
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(conflito("leite", "Leite integral")),
            razoes = listOf(goal, lactose, basis, goal)))
        assertEquals(3, result.informacoesNutricionais.size)
        assertTrue(result.informacoesNutricionais.any { it.contains("ganho de massa muscular") })
        assertTrue(result.informacoesNutricionais.any { it.contains("prote\u00ednas do leite") })
        assertTrue(result.informacoesNutricionais.any { it.contains("por 100 g, 100 ml ou por por\u00e7\u00e3o") })
        assertEquals(1, result.alertas.size)
    }

    @Test fun unfamiliarCriticalReasonsAreNeverSilentlyRemoved() {
        val critical = "Aviso importante: consulte a embalagem antes do consumo por uma diverg\u00eancia na fonte."
        val result = ApresentadorResultado.apresentar(analise(razoes = listOf(critical)))
        assertTrue(result.motivos.contains(critical))
    }

    @Test fun legacyConflictsWithoutSourceDoNotInventConfirmedPresence() {
        val warning = ConflitoDto("milk", "allergy", "leite", "Verifique este alerta", null)
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(warning)))
        assertEquals("Alerta sobre leite", result.alertas.single().titulo)
        assertFalse(result.alertas.single().confirmado)
        assertTrue(result.alertas.single().originais.contains("Verifique este alerta"))
    }

    @Test fun summaryStaysWithinTwoSentencesForAllStatuses() {
        StatusAnalise.entries.forEach { status ->
            val result = ApresentadorResultado.apresentar(analise(status))
            assertTrue(result.resumo.count { it == '.' } <= 2)
            assertFalse(result.resumo.contains("Termos tecnicos"))
        }
    }

    @Test fun quantitativeValuesAreFormattedWithoutChangingTheirAmountOrBase() {
        val result = ApresentadorResultado.apresentar(analise(razoes = listOf("O r\u00f3tulo informa 369.23 mg de s\u00f3dio por 100 g."), nutricao = ninho.copy(basis = "per_100g", sodio = 369.23)))
        assertEquals("369,23 mg", result.tabela!!.linhas.toMap()["S\u00f3dio"])
        assertEquals("Por 100 g", result.tabela!!.referencia)
        assertTrue(result.informacoesNutricionais.isEmpty())
    }

    @Test fun aSafetyMessageStartingWithLabelInformationRemainsAPrimaryReason() {
        val critical = "O r\u00f3tulo informa poss\u00edvel contamina\u00e7\u00e3o adicional."
        val result = ApresentadorResultado.apresentar(analise(razoes = listOf(critical)))
        assertTrue(result.motivos.contains(critical))
    }

    @Test fun absenceStatementsAreRemovedOnlyWhenAConflictIsConfirmed() {
        val reasons = listOf("Nenhum conflito conhecido confirmado nos dados dispon\u00edveis.",
            "N\u00e3o foram identificados conflitos neste produto.")
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(conflito("leite", "Leite integral")), razoes = reasons))
        assertTrue(result.motivos.isEmpty())
        val withoutConflict = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO, razoes = reasons))
        assertTrue(withoutConflict.motivos.containsAll(reasons))
    }

    @Test fun aDifferentIngredientWarningIsNotHiddenAsADuplicateList() {
        val different = "Ingredientes informados: informa\u00e7\u00e3o de seguran\u00e7a divergente da lista atual"
        val result = ApresentadorResultado.apresentar(analise(razoes = listOf(different)))
        assertTrue(result.motivos.contains(different))
    }

    @Test fun unknownRestrictionDoesNotBecomeAFabricatedIngredient() {
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(
            conflito("Baixo s\u00f3dio", "Leite integral", categoria = "restriction"))))
        assertEquals("Conflito com: Baixo s\u00f3dio", result.alertas.single().titulo)
        assertTrue(result.alertas.single().originais.contains("Leite integral"))
    }

    private val objetivo = "H\u00e1 prote\u00edna informada no r\u00f3tulo, relevante para contextualizar seu objetivo de ganho de massa muscular; isso n\u00e3o comprova adequa\u00e7\u00e3o da dieta."
    private val semLactose = "O produto declara 'Zero Lactose', relacionado \u00e0 prefer\u00eancia 'Sem lactose'; essa declara\u00e7\u00e3o n\u00e3o garante seguran\u00e7a para alergias."
    private val baseDesconhecida = "A refer\u00eancia dos valores nutricionais \u00e9 desconhecida; n\u00e3o \u00e9 poss\u00edvel quantificar por por\u00e7\u00e3o ou comparar teores com confian\u00e7a."

    @Test fun compactViewKeepsTechnicalInformationOnDemand() {
        val input = analise(StatusAnalise.ATENCAO, razoes = listOf(objetivo, semLactose, baseDesconhecida, ausencia,
            "Para a prefer\u00eancia 'Baixo s\u00f3dio', faltam dados de s\u00f3dio com refer\u00eancia confirmada; n\u00e3o \u00e9 poss\u00edvel classificar o teor como baixo ou alto."))
        val result = ApresentadorResultado.apresentar(input)
        assertTrue(result.resumo.contains("ganho de massa muscular"))
        assertTrue(result.resumo.contains("sem lactose"))
        assertTrue(result.resumo.count { it == '.' } <= 2)
        assertTrue(result.motivosVisiveis.size <= 2)
        assertFalse(result.motivosVisiveis.any { it.contains("100 g") || it.contains("n\u00e3o garante") })
        assertTrue(result.detalhes.any { it.contains("100 g") })
        assertTrue(result.detalhes.any { it.contains("n\u00e3o garante") })
        assertFalse(result.motivosVisiveis.any { result.resumo.contains(it) })
    }

    @Test fun milkAllergyKeepsOnlyCriticalAlertInCompactView() {
        val input = analise(conflitos = listOf(conflito("leite", "Leite integral")),
            razoes = listOf(objetivo, semLactose, baseDesconhecida))
        val result = ApresentadorResultado.apresentar(input)
        assertEquals(StatusAnalise.NAO_RECOMENDADO, input.status)
        assertEquals(1, result.alertas.size)
        assertTrue(result.motivosVisiveis.isEmpty())
        assertTrue(result.resumo.contains("alergia ao leite"))
        assertTrue(result.resumo.contains("prote\u00ednas do leite"))
        assertTrue(result.detalhes.any { it.contains("ganho de massa muscular") })
        assertTrue(result.alertas.single().originais.contains("Leite integral"))
    }

    @Test fun lactoseRestrictionIsNotPresentedAsMilkProteinAllergy() {
        val input = analise(conflitos = listOf(conflito("lactose", "lactose", categoria = "restriction")))
        val result = ApresentadorResultado.apresentar(input)
        assertTrue(result.resumo.contains("restri\u00e7\u00e3o \u00e0 lactose"))
        assertTrue(result.resumo.contains("diferente de alergia"))
        assertEquals("Cont\u00e9m lactose", result.alertas.single().titulo)
    }

    @Test fun preferenceWithoutConflictIsNotPromotedToAnAllergy() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO, razoes = listOf(semLactose)))
        assertTrue(result.alertas.isEmpty())
        assertEquals("O produto declara ser sem lactose.", result.resumo)
        assertTrue(result.detalhes.any { it.contains("prote\u00ednas do leite") })
    }

    @Test fun compactLimitNeverHidesAdditionalSafetyAlerts() {
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(
            conflito("leite", "milk"), conflito("soja", "soy"), conflito("trigo", "wheat"))))
        assertEquals(3, result.alertas.size)
        assertTrue(result.alertas.all { it.confirmado })
    }

    @Test fun incompleteInformationStaysVisibleInsteadOfBecomingAnOptionalDetail() {
        val critical = "A lista de ingredientes est\u00e1 ausente, ileg\u00edvel ou incompleta."
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.INSUFICIENTE,
            razoes = listOf(critical, objetivo, baseDesconhecida, ausencia)))
        assertTrue(result.motivosVisiveis.contains(critical))
        assertFalse(result.motivosVisiveis.any { it.contains("ganho de massa") })
        assertTrue(result.detalhes.any { it.contains("ganho de massa") })
    }

    @Test fun compactLimitDoesNotDiscardUnfamiliarCriticalReasons() {
        val warnings = listOf("Aviso de seguran\u00e7a A", "Aviso de seguran\u00e7a B", "Aviso de seguran\u00e7a C")
        val result = ApresentadorResultado.apresentar(analise(razoes = warnings))
        assertTrue(result.motivosVisiveis.containsAll(warnings))
    }

    @Test fun declaredLactoseIntoleranceIsNamedWithoutInferringMilkProteinAllergy() {
        val result = ApresentadorResultado.apresentar(analise(conflitos = listOf(
            conflito("Intoler\u00e2ncia \u00e0 lactose", "lactose", categoria = "restriction"))))
        assertTrue(result.resumo.contains("intoler\u00e2ncia \u00e0 lactose informada"))
        assertEquals("Cont\u00e9m lactose", result.alertas.single().titulo)
    }

    @Test fun quantitativeGoalEvaluationIsVisibleWithoutExpandingTechnicalDetails() {
        val evaluation = "Avalia\u00e7\u00e3o para ganho de massa: cerca de 20% da energia vem de prote\u00ednas; atinge a refer\u00eancia de alta propor\u00e7\u00e3o proteica."
        val detail = "Detalhe da avalia\u00e7\u00e3o: prote\u00edna (g) vezes 4 dividida pela energia; limites de 12% e 20%."
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO, razoes = listOf(evaluation, detail), nutricao = ninho))
        assertEquals(evaluation, result.resumo)
        assertTrue(result.motivosVisiveis.size <= 2)
        assertFalse(result.motivosVisiveis.contains(detail))
        assertTrue(result.detalhes.contains(detail))
    }

    @Test fun confirmedAllergyStillDominatesQuantitativeGoalInformation() {
        val evaluation = "Avalia\u00e7\u00e3o para ganho de massa: cerca de 80% da energia vem de prote\u00ednas."
        val input = analise(conflitos = listOf(conflito("leite", "milk")), razoes = listOf(evaluation), nutricao = ninho.copy(calorias = 100.0, proteinas = 20.0))
        val result = ApresentadorResultado.apresentar(input)
        assertEquals(StatusAnalise.NAO_RECOMENDADO, input.status)
        assertEquals("Cont\u00e9m leite", result.alertas.single().titulo)
        assertTrue(result.detalhes.contains(evaluation))
    }

    @Test fun equivalentMissingReferenceMessagesBecomeOneDetail() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO, razoes = listOf(
            objetivo, baseDesconhecida,
            "Detalhe da avalia\u00e7\u00e3o: falta confirmar a refer\u00eancia dos nutrientes para avaliar as quantidades para ganho de massa.",
            "Falta confirmar a refer\u00eancia nutricional.")))
        assertEquals(1, result.detalhes.size)
        assertTrue(result.detalhes.single().contains("por 100 g, por 100 ml ou por por\u00e7\u00e3o"))
        assertFalse(result.detalhes.any { it.contains("ganho de massa muscular") })
    }

    @Test fun summaryAndMainReasonsAreNotRepeatedInDetails() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO, razoes = listOf(
            "Avalia\u00e7\u00e3o para ganho de massa: cerca de 20,32% da energia vem de prote\u00ednas.",
            "O r\u00f3tulo informa 6.3 g de prote\u00ednas por por\u00e7\u00e3o.", objetivo), nutricao = ninho))
        assertTrue(result.resumo.contains("20,32%"))
        assertEquals("6,3 g", result.tabela!!.linhas.toMap()["Prote\u00ednas"])
        assertTrue(result.detalhes.isEmpty())
    }

    @Test fun boilerplateAndGenericGoalAloneDoNotCreateADetailsSection() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO,
            razoes = listOf(objetivo, ausencia, "A cobertura das regras e dos dados do r\u00f3tulo \u00e9 limitada.")))
        assertTrue(result.resumo.contains("ganho de massa muscular"))
        assertTrue(result.detalhes.isEmpty())
    }

    @Test fun quantityIsPreferredOverGenericProteinPresence() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO,
            razoes = listOf(objetivo, "O r\u00f3tulo informa 6.3 g de prote\u00ednas por por\u00e7\u00e3o."), nutricao = ninho))
        assertEquals("6,3 g", result.tabela!!.linhas.toMap()["Prote\u00ednas"])
        assertFalse(result.detalhes.any { it.contains("H\u00e1 prote\u00edna") })
    }

    @Test fun lactosePreferenceUncertaintyPrecedesProteinWithoutCreatingAnAllergy() {
        val warning = "Há leite declarado na fonte. Não há declaração explícita disponível para confirmar a preferência 'Sem lactose'; a presença de lactase, sozinha, não confirma seu atendimento."
        val input = analise(StatusAnalise.ATENCAO, razoes = listOf(
            "Avaliação para ganho de massa: cerca de 20,32% da energia vem de proteínas.", warning), nutricao = ninho)
        val result = ApresentadorResultado.apresentar(input)
        assertTrue(result.resumo.contains("lactose"))
        assertFalse(result.resumo.contains("20,32%"))
        assertTrue(result.motivosVisiveis.first().contains("preferência sem lactose"))
        assertTrue(result.alertas.isEmpty())
        assertEquals(StatusAnalise.ATENCAO, input.status)
        assertNotNull(result.tabela)
    }

    @Test fun lactoseRestrictionIsVisibleEvenWithoutConfirmedLactoseIngredient() {
        val warning = "Para sua restrição de lactose, não foi possível confirmar uma declaração de zero lactose. A lactase, sozinha, não confirma isso."
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO,
            razoes = listOf(warning, objetivo), nutricao = ninho))
        assertTrue(result.resumo.contains("lactose"))
        assertTrue(result.motivosVisiveis.contains(warning))
        assertTrue(result.alertas.isEmpty())
        assertFalse(result.resumo.contains("intolerância"))
    }

    @Test fun numericReasonWithoutReliableStructuredBasisIsNotDisplayed() {
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO,
            razoes = listOf("O rótulo informa 6.3 g de proteínas por porção.",
                "Avaliação para ganho de massa: cerca de 20,32% da energia vem de proteínas."),
            nutricao = ninho.copy(basis = "unknown")))
        assertNull(result.tabela)
        assertFalse((listOf(result.resumo) + result.motivosVisiveis + result.detalhes).any {
            it.contains("6.3") || it.contains("20,32%")
        })
        assertEquals(1, result.detalhes.size)
    }

    @Test fun tableFactsAreNotRepeatedInSummaryReasonsOrDetails() {
        val reasons = listOf("O rótulo informa 6.3 g de proteínas por porção.",
            "O rótulo informa 124 kcal de energia por porção.", "O rótulo informa 0 g de fibras por porção.",
            "Detalhe da avaliação: na porção declarada de 25 g, 124 kcal; 6.3 g de proteínas; 0 g de fibras. Não é recomendação de consumo.")
        val result = ApresentadorResultado.apresentar(analise(StatusAnalise.ATENCAO, razoes = reasons, nutricao = ninho))
        assertNotNull(result.tabela)
        assertTrue(result.detalhes.isEmpty())
        assertTrue(result.motivosVisiveis.isEmpty())
    }

    @Test fun numericSafetyReasonIsNeverMistakenForANutrientFact() {
        val warning = "O rótulo informa 2 alertas: contém leite e pode conter soja."
        for (nutrition in listOf(null, ninho, ninho.copy(basis = "unknown"))) {
            val result = ApresentadorResultado.apresentar(analise(razoes = listOf(warning), nutricao = nutrition))
            assertTrue(result.motivosVisiveis.contains(warning))
        }
    }

    @Test fun pendingAndLegacyCaptureDoNotPretendToHaveANewAnalysis() {
        for ((state, message) in listOf("pending" to "ainda não foi confirmado", "unlinked" to "não tem uma análise vinculada")) {
            val input = analise(StatusAnalise.INSUFICIENTE).copy(analise = null, processamento = state)
            assertTrue(ApresentadorResultado.apresentar(input).resumo.contains(message))
        }
    }

    @Test fun cacheOriginIsAvailableAsOptionalDetail() {
        val input = analise(StatusAnalise.ATENCAO).copy(origemAnalise = "cache")
        val result = ApresentadorResultado.apresentar(input)
        assertTrue(result.detalhes.any { it.startsWith("Resultado reutilizado") })
        assertFalse(result.motivosVisiveis.any { it.startsWith("Resultado reutilizado") })
    }

    @Test fun semanticDetailDeduplicationNeverTouchesCriticalAllergyAlerts() {
        val warnings = listOf(conflito("leite", "Leite integral"), conflito("soja", "Pode conter soja", possivel = true))
        val input = analise(conflitos = warnings, razoes = listOf(objetivo, baseDesconhecida, baseDesconhecida,
            "Aviso importante: informa\u00e7\u00e3o de seguran\u00e7a divergente."))
        val result = ApresentadorResultado.apresentar(input)
        assertEquals(2, result.alertas.size)
        assertTrue(result.alertas.any { it.confirmado })
        assertTrue(result.alertas.any { it.possivel })
        assertTrue(result.motivosVisiveis.any { it.contains("Aviso importante") })
        assertEquals(warnings, input.analise!!.conflicts)
    }
}
