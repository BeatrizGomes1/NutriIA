from app.models.nutrition import (
    AnalysisContext,
    AnalysisResult,
    Product,
    AnalysisStatus,
)
from app.models.user import UserProfile

from app.config.settings import get_settings

from .analysis_provider import (
    AnalysisProvider,
    GeminiAnalysisProvider,
    MockAnalysisProvider,
)
from .food_safety import deterministic_result, NO_GUARANTEE
from .nutrition_observations import append_nutrition
from .nutrition_observations import verified_explanations
from .goal_assessment import assess_goal
from .optional_enrichment import enrich


def build_analysis_provider(provider_name: str | None = None) -> AnalysisProvider:
    selected_provider = provider_name or get_settings().nutrition_provider
    if selected_provider == "mock":
        return MockAnalysisProvider()
    if selected_provider == "gemini":
        return GeminiAnalysisProvider()
    raise ValueError(f"Unsupported nutrition provider: {selected_provider}")


class NutritionService:
    """Aplica regras de segurança antes de delegar a análise ao provedor."""

    def __init__(self, provider: AnalysisProvider | None = None):
        self.provider = provider or build_analysis_provider()

    def prepare(self, product: Product, profile: UserProfile) -> AnalysisContext:
        ingredient_text = product.ingredient_text()
        blocking_reasons: list[str] = []

        if not product.has_identity():
            blocking_reasons.append("Não foi possível identificar o produto por nome ou EAN.")

        if not ingredient_text.strip():
            blocking_reasons.append("A lista de ingredientes é necessária para uma análise confiável.")

        return AnalysisContext(
            product=product,
            profile={
                "goal": profile.goal,
                "allergies": profile.allergies,
                "restrictions": profile.restrictions,
                "preferences": profile.preferences,
            },
            blocking_reasons=blocking_reasons,
        )

    def analyze(self, product: Product, profile: UserProfile) -> AnalysisResult:
        context = self.prepare(product, profile)

        guarded = deterministic_result(context)
        if guarded is not None:
            return append_nutrition(guarded, context)

        reasons, evidence = verified_explanations(context)
        assessment = assess_goal(product.nutrition, str(profile.goal or ""))
        insufficient = assessment.state in {"inconsistent", "insufficient"} and str(profile.goal or "") in {
            "muscle_gain", "weight_loss"}
        if product.nutrition.basis == "unknown" and product.nutrition.has_any_value():
            insufficient = True
        if not product.nutrition.has_any_value():
            insufficient = True
        result = AnalysisResult(
            status=AnalysisStatus.INSUFFICIENT_INFORMATION if insufficient else AnalysisStatus.ATTENTION,
            product_name=product.name or product.ean,
            summary=" ".join(reasons[:2]) if reasons else "Faltam dados para concluir a avaliação nutricional.",
            reasons=[*reasons, NO_GUARANTEE],
            evidence=evidence, provider="deterministic_nutrition",
        )
        settings = get_settings()
        if not settings.gemini_enrichment_enabled or not reasons:
            return result
        # Only reorder verified explanations. Safety status and conflicts are immutable.
        return enrich(result, context, self.provider, settings.gemini_enrichment_timeout_seconds)


def analyze_product(
    product: Product,
    profile: UserProfile,
    provider: AnalysisProvider | None = None,
) -> AnalysisResult:
    """Ponto de entrada prático para um adaptador de API ou serviço da aplicação."""

    return NutritionService(provider=provider).analyze(product, profile)
