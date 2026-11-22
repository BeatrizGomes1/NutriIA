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
from app.services.goal_assessment import assess_goal
from app.services.food_safety import NO_GUARANTEE, deterministic_result
from app.services.nutrition_observations import (
    append_nutrition, has_nutritional_context, observation_catalog, verified_explanations,
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
    nutrition_observation_ids: list[str] = Field(default_factory=list)


class GeminiAnalysisProvider:
    """Adaptador que delega a decisão final à integração com o Gemini."""

    name = "gemini"

    def __call__(self, context: AnalysisContext) -> str:
        from app.gemini.nutrition_ai import generate_product_analysis

        payload = context.to_provider_payload()
        payload["nutrition_observations"] = list(observation_catalog(context).values())
        return generate_product_analysis(payload)


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

    guarded = deterministic_result(context)
    if guarded is not None:
        return append_nutrition(guarded, context)

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

    grounded = _is_grounded(result, context)
    reasons, evidence = verified_explanations(
        context, result.nutrition_observation_ids, [result.summary, *result.reasons])
    meaningful = has_nutritional_context(context)
    unverified_safety = any(c.category in {"allergy", "restriction"} for c in result.conflicts)
    inconsistent_nutrition = assess_goal(context.product.nutrition, str(context.profile.get("goal") or "")).state == "inconsistent"
    if inconsistent_nutrition or unverified_safety or ((not grounded or result.status in {
            AnalysisStatus.INSUFFICIENT_INFORMATION, AnalysisStatus.NOT_RECOMMENDED}) and not meaningful):
        status = AnalysisStatus.INSUFFICIENT_INFORMATION
    elif not grounded:
        status = AnalysisStatus.ATTENTION
    elif result.status in {AnalysisStatus.INSUFFICIENT_INFORMATION, AnalysisStatus.NOT_RECOMMENDED}:
        # Uncertainty or an unsupported AI verdict must not erase verifiable
        # qualitative nutrition. Safety guards already took precedence above.
        status = AnalysisStatus.ATTENTION
    elif (context.profile.get("allergies") or context.profile.get("restrictions")
          or str(context.profile.get("goal") or "") in {"muscle_gain", "weight_loss"}):
        # Composition benchmarks do not establish a consumption recommendation
        # or suitability of the entire diet, even without declared allergies.
        status = AnalysisStatus.ATTENTION
    else:
        status = result.status

    if unverified_safety:
        reasons.insert(0, "Uma conclus\u00e3o de seguran\u00e7a do provedor n\u00e3o p\u00f4de ser confirmada; "
                          "as observa\u00e7\u00f5es nutricionais n\u00e3o garantem seguran\u00e7a alimentar.")

    # Nutrition-related preferences are explanations, not forbidden ingredients.
    # Only deterministic safety evaluation creates public safety conflicts.
    return AnalysisResult(
        status=status,
        product_name=context.product.name or context.product.ean,
        summary=(" ".join(reasons[:2]) if meaningful and reasons
                 else SUMMARY_BY_STATUS[status]),
        reasons=list(dict.fromkeys([*reasons, NO_GUARANTEE])),
        conflicts=[],
        evidence=evidence,
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
        # Safety conflicts require deterministic semantic support, not just a
        # substring copied by the model. Supported conflicts already returned
        # through deterministic_result above.
        if conflict.category in {"allergy", "restriction"}:
            return False
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
