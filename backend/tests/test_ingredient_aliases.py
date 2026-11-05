from app.gemini.prompts import PRODUCT_ANALYSIS_PROMPT
from app.models.nutrition import AnalysisContext, AnalysisStatus, Product
from app.services.analysis_provider import MockAnalysisProvider


def test_mock_matches_english_milk_and_sugar_terms_on_portuguese_profile():
    product = Product(
        name="Creme de avelã",
        ingredients_text="Sugar, skimmed milk powder, hazelnuts",
    )
    context = AnalysisContext(
        product=product,
        profile={"allergies": ["leite"], "restrictions": ["açúcar"]},
    )

    result = MockAnalysisProvider()(context)

    assert result.status == AnalysisStatus.NOT_RECOMMENDED
    assert {conflict.source_excerpt for conflict in result.conflicts} == {
        "Sugar",
        "skimmed milk powder",
    }


def test_maltodextrin_is_flagged_as_related_not_equivalent_to_sugar():
    context = AnalysisContext(
        product=Product(name="Produto", ingredients_text="Maltodextrin, salt"),
        profile={"restrictions": ["açúcar"]},
    )

    result = MockAnalysisProvider()(context)

    assert result.status == AnalysisStatus.ATTENTION
    assert len(result.conflicts) == 1
    assert result.conflicts[0].source_excerpt == "Maltodextrin"
    assert "não é sinônimo químico de açúcar" in result.conflicts[0].evidence


def test_product_prompt_requests_aliases_and_literal_evidence():
    assert "traduções, sinônimos" in PRODUCT_ANALYSIS_PROMPT
    assert "maltodextrina" in PRODUCT_ANALYSIS_PROMPT
    assert "copiar literalmente" in PRODUCT_ANALYSIS_PROMPT
