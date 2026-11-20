import json
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.models.nutrition import (
    AnalysisContext,
    AnalysisResult,
    AnalysisStatus,
    Conflict,
)
from app.utils.helpers import normalize_text
from app.utils.ingredient_aliases import find_ingredient_alias


class AnalysisProvider(Protocol):
    """Contrato compartilhado pelos provedores Gemini e simulado."""

    name: str

    def __call__(
        self, context: AnalysisContext
    ) -> "ProviderAnalysisResult | Mapping[str, Any] | str":
        ...


class ProviderConflict(BaseModel):
    """Conflito do provedor com um trecho da fonte usado para validar a análise."""

    term: str
    category: str
    profile_item: str
    evidence: str = Field(
        description="Explicação legível de como o ingrediente se relaciona ao perfil."
    )
    source_excerpt: str = Field(
        default="",
        description="Trecho literal dos ingredientes que sustenta o conflito.",
    )


class ProviderAnalysisResult(BaseModel):
    """Resposta interna do provedor; trechos da fonte são removidos antes do retorno."""

    status: AnalysisStatus
    product_name: str | None = None
    summary: str
    reasons: list[str] = Field(default_factory=list)
    conflicts: list[ProviderConflict] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class GeminiAnalysisProvider:
    """Adaptador que delega a decisão final à integração com o Gemini."""

    name = "gemini"

    def __call__(self, context: AnalysisContext) -> str:
        from app.gemini.nutrition_ai import generate_product_analysis

        return generate_product_analysis(context.to_provider_payload())


SUMMARY_BY_STATUS = {
    AnalysisStatus.RECOMMENDED: "Recomendado para o seu perfil.",
    AnalysisStatus.ATTENTION: "Consuma com atenção.",
    AnalysisStatus.NOT_RECOMMENDED: "Não recomendamos este produto para o seu perfil.",
    AnalysisStatus.INSUFFICIENT_INFORMATION: "Informações insuficientes.",
}


class MockAnalysisProvider:
    """Substituto determinístico e simples do Gemini para desenvolvimento local."""

    name = "mock"

    def __call__(self, context: AnalysisContext) -> ProviderAnalysisResult:
        conflicts = self._find_literal_conflicts(context)
        reasons: list[str] = []

        blocking_conflicts = [
            conflict
            for conflict in conflicts
            if conflict.category in {"allergy", "restriction"}
            and not conflict.evidence.startswith("Relação indireta:")
        ]
        indirect_restriction_conflicts = [
            conflict
            for conflict in conflicts
            if conflict.category == "restriction"
            and conflict.evidence.startswith("Relação indireta:")
        ]

        if blocking_conflicts:
            status = AnalysisStatus.NOT_RECOMMENDED
            reasons.extend(
                f"Foi identificado '{conflict.term}', relacionado à declaração "
                f"'{conflict.profile_item}'."
                for conflict in blocking_conflicts
            )
        elif indirect_restriction_conflicts:
            status = AnalysisStatus.ATTENTION
            reasons.extend(conflict.evidence for conflict in indirect_restriction_conflicts)
        elif conflicts:
            status = AnalysisStatus.ATTENTION
            reasons.extend(
                f"Foi identificado '{conflict.term}', relacionado à preferência "
                f"'{conflict.profile_item}'."
                for conflict in conflicts
            )
        else:
            status = AnalysisStatus.RECOMMENDED
            reasons.append("Nenhum conflito declarado foi encontrado nos dados disponíveis.")

        self._add_goal_reason(context, reasons)

        return ProviderAnalysisResult(
            status=status,
            product_name=context.product.name or context.product.ean,
            summary=SUMMARY_BY_STATUS[status],
            reasons=list(dict.fromkeys(reasons)),
            conflicts=conflicts,
            evidence=list(dict.fromkeys(conflict.source_excerpt for conflict in conflicts)),
        )

    @staticmethod
    def _find_literal_conflicts(context: AnalysisContext) -> list[ProviderConflict]:
        ingredient_text = context.product.ingredient_text()
        conflicts: list[ProviderConflict] = []

        for category, profile_item in _declared_items(context.profile):
            match = find_ingredient_alias(profile_item, ingredient_text)
            if match is None:
                continue

            if match.relation == "related":
                explanation = (
                    f"Relação indireta: '{match.matched_term}' é um carboidrato derivado do amido; "
                    "pode ser relevante para quem evita açúcar, mas não é sinônimo químico de açúcar. "
                    "O rótulo não permite inferir a quantidade de açúcares simples."
                )
            elif match.concept == "milk" and match.relation == "synonym":
                explanation = (
                    f"'{match.matched_term}' é um nome alternativo, derivado ou tradução de ingrediente lácteo "
                    f"relacionado à declaração '{profile_item}'."
                )
            elif match.relation == "synonym":
                explanation = (
                    f"'{match.matched_term}' é um nome alternativo ou tradução relacionada à declaração "
                    f"'{profile_item}'."
                )
            else:
                explanation = f"Foi identificado o ingrediente declarado: '{match.source_excerpt}'."

            conflicts.append(
                ProviderConflict(
                    term=match.source_excerpt,
                    category=category,
                    profile_item=profile_item,
                    evidence=explanation,
                    source_excerpt=match.source_excerpt,
                )
            )
        return conflicts

    @staticmethod
    def _add_goal_reason(context: AnalysisContext, reasons: list[str]) -> None:
        goal = normalize_text(str(context.profile.get("goal") or ""))
        nutrition = context.product.nutrition

        if goal in {"weight_loss", "emagrecimento"} and (
            nutrition.calories_kcal is not None or nutrition.sugars_g is not None
        ):
            reasons.append("Os dados disponíveis de calorias e açúcares foram considerados.")
        elif goal in {
            "muscle_gain",
            "ganho de massa",
            "ganho de massa muscular",
            "hipertrofia",
        } and (nutrition.carbohydrates_g is not None or nutrition.protein_g is not None):
            reasons.append("Os dados disponíveis de carboidratos e proteínas foram considerados.")


def parse_provider_result(
    response: ProviderAnalysisResult | Mapping[str, Any] | str,
    provider_name: str,
    context: AnalysisContext,
) -> AnalysisResult:
    """Valida, fundamenta e converte a resposta do provedor para o resultado público."""

    if isinstance(response, ProviderAnalysisResult):
        result = response
    elif isinstance(response, Mapping):
        result = ProviderAnalysisResult.model_validate(response)
    elif isinstance(response, str):
        try:
            result = ProviderAnalysisResult.model_validate(json.loads(response))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError("AI analysis response must be valid JSON") from error
    else:
        raise TypeError("Analysis provider returned an unsupported response")

    if not _is_grounded(result, context):
        return AnalysisResult(
            status=AnalysisStatus.INSUFFICIENT_INFORMATION,
            product_name=context.product.name or context.product.ean,
            summary=SUMMARY_BY_STATUS[AnalysisStatus.INSUFFICIENT_INFORMATION],
            reasons=["Não foi possível confirmar as evidências da análise nos dados recebidos."],
            provider=provider_name,
        )

    return AnalysisResult(
        status=result.status,
        product_name=result.product_name or context.product.name or context.product.ean,
        summary=result.summary,
        reasons=result.reasons,
        conflicts=[
            Conflict(
                term=conflict.term,
                category=conflict.category,
                profile_item=conflict.profile_item,
                evidence=conflict.evidence,
                source_excerpt=conflict.source_excerpt,
            )
            for conflict in result.conflicts
        ],
        evidence=result.evidence,
        provider=provider_name,
    )


def _declared_items(profile: Mapping[str, Any]) -> list[tuple[str, str]]:
    categories = ("allergy", "restriction", "preference")
    declared: list[tuple[str, str]] = []
    for category, key in zip(categories, ("allergies", "restrictions", "preferences")):
        items = profile.get(key, [])
        if isinstance(items, list):
            declared.extend(
                (category, item)
                for item in items
                if isinstance(item, str) and item.strip()
            )
    return declared


def _contains_normalized_text(source: str, quoted_text: str) -> bool:
    normalized_source = normalize_text(source)
    normalized_quote = normalize_text(quoted_text)
    if not normalized_source or not normalized_quote:
        return False
    return f" {normalized_quote} " in f" {normalized_source} "


def _is_grounded(result: ProviderAnalysisResult, context: AnalysisContext) -> bool:
    profile_items = {
        (category, normalize_text(item))
        for category, item in _declared_items(context.profile)
    }
    ingredients = context.product.ingredient_text()
    source_values = _flatten_values(
        {
            "product": context.product.model_dump(mode="json"),
            "profile": context.profile,
        }
    )

    for conflict in result.conflicts:
        if (conflict.category, normalize_text(conflict.profile_item)) not in profile_items:
            return False
        if not _contains_normalized_text(ingredients, conflict.source_excerpt):
            return False

    return all(
        any(_contains_normalized_text(source, excerpt) for source in source_values)
        for excerpt in result.evidence
    )


def _flatten_values(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return [source for nested in value.values() for source in _flatten_values(nested)]
    if isinstance(value, list):
        return [source for nested in value for source in _flatten_values(nested)]
    if isinstance(value, (str, int, float)):
        return [str(value)]
    return []
