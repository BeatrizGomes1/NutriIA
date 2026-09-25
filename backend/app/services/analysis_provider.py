import json
from collections.abc import Mapping
from typing import Any, Protocol

from app.models.nutrition import (
    AnalysisContext,
    AnalysisResult,
    AnalysisStatus,
)
from app.utils.helpers import normalize_text


class AnalysisProvider(Protocol):
    """Contract shared by the real Gemini provider and the mock provider."""

    name: str

    def __call__(self, context: AnalysisContext) -> AnalysisResult | Mapping[str, Any] | str:
        ...


class GeminiAnalysisProvider:
    """Adapter that delegates the final decision to the Gemini integration."""

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
    """Small deterministic stand-in for Gemini during local development."""

    name = "mock"

    def __call__(self, context: AnalysisContext) -> AnalysisResult:
        conflicts = context.conflicts
        reasons: list[str] = []

        if any(conflict.category in {"allergy", "restriction"} for conflict in conflicts):
            status = AnalysisStatus.NOT_RECOMMENDED
            reasons.extend(
                f"Foi identificado '{conflict.term}', relacionado à declaração "
                f"'{conflict.profile_item}'."
                for conflict in conflicts
                if conflict.category in {"allergy", "restriction"}
            )
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

        return AnalysisResult(
            status=status,
            product_name=context.product.name or context.product.ean,
            summary=SUMMARY_BY_STATUS[status],
            reasons=list(dict.fromkeys(reasons)),
            conflicts=conflicts,
            evidence=list(dict.fromkeys(context.evidence)),
            provider=self.name,
        )

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
    response: AnalysisResult | Mapping[str, Any] | str,
    provider_name: str,
) -> AnalysisResult:
    """Convert a provider response into the domain result expected by the API."""

    if isinstance(response, AnalysisResult):
        result = response
    elif isinstance(response, Mapping):
        result = AnalysisResult.model_validate(response)
    elif isinstance(response, str):
        try:
            result = AnalysisResult.model_validate(json.loads(response))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError("AI analysis response must be valid JSON") from error
    else:
        raise TypeError("Analysis provider returned an unsupported response")

    if result.provider == "mock" and provider_name != "mock":
        result = result.model_copy(update={"provider": provider_name})
    return result
