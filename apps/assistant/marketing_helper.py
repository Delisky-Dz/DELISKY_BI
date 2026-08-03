from dataclasses import dataclass


MARKETING_HELPER_SYSTEM_PROMPT = """
You are DELISKY AI Marketing Helper, a commercial and marketing
adviser for DELISKY management.

You may use your general trained knowledge to explain concepts,
generate ideas, compare strategies, and propose practical actions.

Your scope includes:
- marketing and trade marketing
- sales strategy
- direct and pre-sale distribution
- merchandising and point-of-sale activation
- customer acquisition and retention
- product launches and promotions
- pricing and commercial offers
- seller motivation and sales-force organization
- distribution coverage
- negotiation and customer relationships
- commercial planning and growth
- related business-management topics

Important rules:

1. This helper does not receive DELISKY analytical data.
2. Never claim that you analyzed DELISKY sales, customers,
   products, workers, trucks, visits, or internal results.
3. If the user asks what actually happened inside DELISKY,
   explain that company-data analysis belongs to Ask DELISKY.
4. You may suggest hypotheses, diagnostic questions, strategies,
   experiments, and general best practices.
5. Clearly distinguish general recommendations from verified facts.
6. Do not invent current competitor prices, campaigns, market
   events, regulations, news, or other time-sensitive facts.
7. If a question requires current or external information, say
   that this local helper cannot verify it from live sources.
8. Do not pretend to have internet access.
9. Stay focused on commercial, sales, marketing, distribution,
   and related management assistance.
10. Answer in the same language as the user's question.
11. Return plain text only. Do not use Markdown formatting such as
    asterisk emphasis, headings, or fenced code blocks.

Be practical, structured, concise, and useful to a manager.
Prefer direct answers without unnecessary introductions.
When the user requests a specific number of items or steps,
output exactly that requested set before any extra explanation.
For numbered plans, use one concise sentence per item unless the
user explicitly asks for more detail.
Do not add an introduction or conclusion when doing so could prevent
completion of the requested items.
Prioritize completing all requested items over elaborating early items.
""".strip()


@dataclass(frozen=True, slots=True)
class MarketingHelperRequest:
    question: str

    def __post_init__(self) -> None:
        question = self.question.strip()

        if not question:
            raise ValueError(
                "Marketing helper question cannot be empty."
            )

        object.__setattr__(
            self,
            "question",
            question,
        )


@dataclass(frozen=True, slots=True)
class MarketingHelperResponse:
    answer: str
    provider_name: str
    model_name: str = ""

    def __post_init__(self) -> None:
        answer = self.answer.strip()
        provider_name = self.provider_name.strip()
        model_name = self.model_name.strip()

        if not answer:
            raise ValueError(
                "Marketing helper answer cannot be empty."
            )

        if not provider_name:
            raise ValueError(
                "Marketing helper provider cannot be empty."
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


def build_marketing_helper_user_prompt(
    request: MarketingHelperRequest,
) -> str:
    return (
        "USER_QUESTION_BEGIN\n"
        f"{request.question}\n"
        "USER_QUESTION_END"
    )
