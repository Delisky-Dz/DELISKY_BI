from dataclasses import dataclass

from apps.analytics.services.ask_delisky_context import (
    AskDeliskyContext,
)


@dataclass(frozen=True, slots=True)
class AskDeliskyRequest:
    question: str
    context: AskDeliskyContext

    def __post_init__(self) -> None:
        if not isinstance(
            self.context,
            AskDeliskyContext,
        ):
            raise TypeError(
                "Ask DELISKY context must be "
                "an AskDeliskyContext."
            )

        question = self.question.strip()

        if not question:
            raise ValueError(
                "Ask DELISKY question cannot be empty."
            )

        object.__setattr__(
            self,
            "question",
            question,
        )


@dataclass(frozen=True, slots=True)
class AskDeliskyProviderRequest:
    question: str
    context_json: str
    context_schema_version: str

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError(
                "Provider question cannot be empty."
            )

        if not self.context_json.strip():
            raise ValueError(
                "Provider context cannot be empty."
            )

        if not self.context_schema_version.strip():
            raise ValueError(
                "Context schema version cannot be empty."
            )


@dataclass(frozen=True, slots=True)
class AskDeliskyProviderResult:
    answer: str
    provider_name: str
    model_name: str = ""

    def __post_init__(self) -> None:
        answer = self.answer.strip()
        provider_name = self.provider_name.strip()
        model_name = self.model_name.strip()

        if not answer:
            raise ValueError(
                "Provider answer cannot be empty."
            )

        if not provider_name:
            raise ValueError(
                "Provider name cannot be empty."
            )

        object.__setattr__(
            self,
            "answer",
            answer,
        )
        object.__setattr__(
            self,
            "provider_name",
            provider_name,
        )
        object.__setattr__(
            self,
            "model_name",
            model_name,
        )


@dataclass(frozen=True, slots=True)
class AskDeliskyResponse:
    answer: str
    provider_name: str
    model_name: str
    context_schema_version: str
