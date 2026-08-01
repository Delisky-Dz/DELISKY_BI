from typing import Protocol

from .contracts import (
    AskDeliskyProviderRequest,
    AskDeliskyProviderResult,
)


class AskDeliskyProvider(Protocol):
    """
    Provider-neutral Ask DELISKY language-model boundary.

    Implementations receive only the already-sanitized JSON
    context. They must not access analytics ORM data directly.
    """

    def generate(
        self,
        request: AskDeliskyProviderRequest,
    ) -> AskDeliskyProviderResult:
        ...
