"""Pieces shared by the character agents, the conversation layer and character generation."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field
from pydantic_ai.messages import ModelResponse

from .models import Character

Emotion = Literal['neutral', 'happy', 'annoyed', 'sad', 'surprised', 'smug', 'scared']

# Lenient schemas: a slightly off answer is fixed up instead of costing a retry call
LenientEmotion = Annotated[Emotion, BeforeValidator(lambda v: v if v in get_args(Emotion) else 'neutral')]
ShortText = Annotated[str, AfterValidator(lambda s: s[:200])]


class MemoryNote(BaseModel):
    text: ShortText = Field(description='Une phrase, du point de vue du personnage.')
    about: str | None = Field(
        default=None,
        description='Nom d\'un TROISIÈME personnage si le souvenir le concerne (ragot), sinon null.',
    )


TONE_RULES = """\
Ton: humour tout public, bienveillant. Les personnages sont excentriques, taquins, parfois un peu \
vexés ou agacés, mais toujours pour rire. Jamais de haine, d'insulte, de mépris ni de méchanceté. \
Les désaccords restent légers et drôles."""


def feeling_label(score: int) -> str:
    if score <= -6:
        return "pas vraiment sur la même longueur d'onde"
    if score <= -2:
        return 'un peu froid'
    if score < 3:
        return 'connaissance'
    if score < 7:
        return 'bon copain'
    return 'meilleur ami'


def resolve_about(note: MemoryNote, partner: Character, a: Character, b: Character) -> Character:
    """A memory is about the partner unless it names an existing third character."""
    if note.about:
        third = Character.objects.exclude(pk__in=[a.pk, b.pk]).filter(name__iexact=note.about.strip()).first()
        if third:
            return third
    return partner


def cost_of(responses: Iterable[ModelResponse]) -> Decimal | None:
    """Total USD cost of the responses, or None if any of them has no known price (e.g. Albert)."""
    total = Decimal(0)
    for response in responses:
        try:
            total += response.cost().total_price
        except (LookupError, ValueError):
            return None
    return total


@dataclass
class Usage:
    """Tokens and cost summed over every LLM call of one conversation."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal | None = Decimal(0)
    model_name: str = ''

    def add(self, run) -> None:
        self.input_tokens += run.usage.input_tokens
        self.output_tokens += run.usage.output_tokens
        responses = [m for m in run.new_messages() if isinstance(m, ModelResponse)]
        cost = cost_of(responses)
        self.cost_usd = None if cost is None or self.cost_usd is None else self.cost_usd + cost
        if responses:
            self.model_name = responses[-1].model_name or self.model_name
