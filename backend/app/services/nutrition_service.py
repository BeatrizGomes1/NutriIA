from app.models.nutrition import (
    AnalysisContext,
    AnalysisResult,
    AnalysisStatus,
    Product,
)
from app.models.user import UserProfile

from app.config.settings import get_settings

from .analysis_provider import (
    AnalysisProvider,
    GeminiAnalysisProvider,
    MockAnalysisProvider,
    parse_provider_result,
)


def build_analysis_provider(provider_name: str | None = None) -> AnalysisProvider:
    selected_provider = provider_name or get_settings().nutrition_provider
    if selected_provider == "mock":
        return MockAnalysisProvider()
    if selected_provider == "gemini":
        return GeminiAnalysisProvider()
    raise ValueError(f"Unsupported nutrition provider: {selected_provider}")


class NutritionService:
    """Prepara os dados e delega a análise final a um provedor de IA."""

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

        if context.blocking_reasons:
            return AnalysisResult(
                status=AnalysisStatus.INSUFFICIENT_INFORMATION,
                product_name=product.name or product.ean,
                summary="Informações insuficientes.",
                reasons=context.blocking_reasons,
                provider="service_guardrail",
            )

        provider_name = getattr(self.provider, "name", self.provider.__class__.__name__)
        response = self.provider(context)
        return parse_provider_result(response, provider_name, context)


def analyze_product(
    product: Product,
    profile: UserProfile,
    provider: AnalysisProvider | None = None,
) -> AnalysisResult:
    """Ponto de entrada prático para um adaptador de API ou serviço da aplicação."""

    return NutritionService(provider=provider).analyze(product, profile)
