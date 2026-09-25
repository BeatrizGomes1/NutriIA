from app.models.nutrition import (
    AnalysisContext,
    AnalysisResult,
    AnalysisStatus,
    Conflict,
    Product,
)
from app.models.user import UserProfile
from app.utils.helpers import contains_term, normalize_text

from app.config.settings import get_settings

from .analysis_provider import (
    AnalysisProvider,
    GeminiAnalysisProvider,
    MockAnalysisProvider,
    parse_provider_result,
)


# This is intentionally a small, explicit vocabulary for the first mock slice.
# A complete allergen/synonym taxonomy is a separate product decision.
TERM_ALIASES = {
    "leite": ("leite", "lactose", "soro de leite", "caseinato", "caseina"),
    "lactose": ("leite", "lactose", "soro de leite", "caseinato", "caseina"),
    "sem lactose": ("leite", "lactose", "soro de leite", "caseinato", "caseina"),
    "gluten": ("gluten", "trigo", "cevada", "centeio"),
    "trigo": ("trigo", "gluten"),
    "sem gluten": ("gluten", "trigo", "cevada", "centeio"),
    "amendoim": ("amendoim",),
    "soja": ("soja", "lecitina de soja"),
    "ovo": ("ovo", "albumina"),
    "acucar": ("acucar", "sacarose", "xarope de milho", "dextrose", "maltodextrina"),
    "sem acucar": ("acucar", "sacarose", "xarope de milho", "dextrose", "maltodextrina"),
    "sodio": ("sodio",),
    "baixo sodio": ("sodio",),
}


def build_analysis_provider(provider_name: str | None = None) -> AnalysisProvider:
    selected_provider = provider_name or get_settings().nutrition_provider
    if selected_provider == "mock":
        return MockAnalysisProvider()
    if selected_provider == "gemini":
        return GeminiAnalysisProvider()
    raise ValueError(f"Unsupported nutrition provider: {selected_provider}")


class NutritionService:
    """Prepare input and delegate the final analysis to an AI provider."""

    def __init__(self, provider: AnalysisProvider | None = None):
        self.provider = provider or build_analysis_provider()

    def prepare(self, product: Product, profile: UserProfile) -> AnalysisContext:
        ingredient_text = product.ingredient_text()
        normalized_ingredients = normalize_text(ingredient_text)
        evidence: list[str] = []
        blocking_reasons: list[str] = []

        if product.has_identity():
            evidence.append("Produto identificado por nome ou EAN.")
        else:
            blocking_reasons.append("Não foi possível identificar o produto por nome ou EAN.")

        if normalized_ingredients:
            evidence.append("Lista de ingredientes disponível para comparação.")
        else:
            blocking_reasons.append("A lista de ingredientes é necessária para uma análise confiável.")

        if product.nutrition.has_any_value():
            evidence.append("Há dados nutricionais informados para o produto.")

        conflicts = self._find_conflicts(ingredient_text, profile)
        evidence.extend(
            f"O termo '{conflict.term}' aparece nos ingredientes informados."
            for conflict in conflicts
        )

        return AnalysisContext(
            product=product,
            profile=profile.model_dump(mode="json"),
            normalized_ingredients=normalized_ingredients,
            conflicts=conflicts,
            evidence=list(dict.fromkeys(evidence)),
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
                conflicts=context.conflicts,
                evidence=context.evidence,
                provider="service_guardrail",
            )

        provider_name = getattr(self.provider, "name", self.provider.__class__.__name__)
        response = self.provider(context)
        return parse_provider_result(response, provider_name)

    @staticmethod
    def _find_conflicts(ingredient_text: str, profile: UserProfile) -> list[Conflict]:
        conflicts: list[Conflict] = []
        for category, profile_item in profile.declared_items():
            matched_term = NutritionService._find_match(ingredient_text, profile_item)
            if not matched_term:
                continue

            conflicts.append(
                Conflict(
                    term=matched_term,
                    category=category,
                    profile_item=profile_item,
                    evidence=f"O termo '{matched_term}' aparece nos ingredientes informados.",
                )
            )
        return conflicts

    @staticmethod
    def _find_match(ingredient_text: str, profile_item: str) -> str | None:
        normalized_item = normalize_text(profile_item)
        candidate_terms = TERM_ALIASES.get(normalized_item, (normalized_item,))
        for term in candidate_terms:
            if contains_term(ingredient_text, term):
                return term
        return None


def analyze_product(
    product: Product,
    profile: UserProfile,
    provider: AnalysisProvider | None = None,
) -> AnalysisResult:
    """Convenience entry point for an API adapter or application service."""

    return NutritionService(provider=provider).analyze(product, profile)
