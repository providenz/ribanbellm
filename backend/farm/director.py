"""The conversation director: one LLM call writes a whole exchange between two characters."""

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from django.db import transaction
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model

from .llm import build_model
from .models import Character, Conversation, Memory, Relationship

Emotion = Literal['neutral', 'happy', 'angry', 'sad', 'surprised', 'smug', 'scared']


class Line(BaseModel):
    speaker: Literal['A', 'B']
    text: str = Field(max_length=200, description='Une réplique courte et percutante, en français.')
    emotion: Emotion


class MemoryNote(BaseModel):
    text: str = Field(max_length=200, description='Une phrase, du point de vue du personnage.')
    about: str | None = Field(
        default=None,
        description='Nom d\'un TROISIÈME personnage si le souvenir le concerne (ragot), sinon null.',
    )


class ConversationResult(BaseModel):
    lines: list[Line] = Field(min_length=2, max_length=8)
    memory_a: MemoryNote = Field(description='Ce que A retiendra de cette conversation.')
    memory_b: MemoryNote = Field(description='Ce que B retiendra de cette conversation.')
    score_delta: int = Field(ge=-3, le=3, description='Évolution de la relation: -3 (brouille) à +3 (complicité).')


INSTRUCTIONS = """\
Tu es le scénariste d'une petite série comique. Deux personnages excentriques se croisent \
et échangent quelques répliques.

Règles:
- Écris 4 à 6 répliques au total, en alternant A et B, en français.
- Chaque réplique fait moins de 120 caractères: courte, drôle, percutante.
- Chaque personnage a une voix très marquée: sa personnalité et son tic de langage doivent se sentir.
- Si les personnages ont des souvenirs l'un de l'autre ou des ragots, utilise-les: rancunes, \
blagues récurrentes, dettes, malentendus.
- La relation actuelle doit colorer le ton (froid entre ennemis, complice entre amis).
- Jamais de ton d'assistant poli ou neutre. Humour tout public.
- Termine par ce que chacun retiendra (une phrase chacun) et l'évolution de leur relation.
"""

director = Agent(
    output_type=ConversationResult,
    instructions=INSTRUCTIONS,
    name='director',
    retries=1,
)


def relationship_label(score: int) -> str:
    if score <= -7:
        return 'ennemis jurés'
    if score <= -3:
        return 'ils ne se supportent pas'
    if score < 3:
        return 'ils se connaissent à peine'
    if score < 7:
        return 'bons copains'
    return 'meilleurs amis'


def _describe(label: str, character: Character) -> str:
    memories = [
        f'  - {m.text}' + (f' (à propos de {m.about.name})' if m.about else '')
        for m in Memory.latest_for(character)
    ]
    return '\n'.join(
        [
            f'{label} = {character.name}',
            f'Personnalité: {character.personality}',
            f'Tic de langage: {character.speech_quirk}',
            'Souvenirs:' if memories else 'Souvenirs: aucun',
            *memories,
        ]
    )


def build_prompt(a: Character, b: Character) -> str:
    score = Relationship.between(a, b).score
    return '\n\n'.join(
        [
            _describe('A', a),
            _describe('B', b),
            f'Relation entre A et B: {score} sur une échelle de -10 à +10 ({relationship_label(score)}).',
        ]
    )


def _resolve_about(note: MemoryNote, partner: Character, a: Character, b: Character) -> Character:
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


def run_conversation(a: Character, b: Character, *, model: Model | None = None) -> Conversation:
    if a.pk == b.pk:
        raise ValueError('A character cannot talk to itself.')

    run = director.run_sync(build_prompt(a, b), model=model or build_model())
    result = run.output
    usage = run.usage
    responses = [m for m in run.new_messages() if isinstance(m, ModelResponse)]
    names = {'A': a.name, 'B': b.name}

    with transaction.atomic():
        relationship = Relationship.between(a, b)
        score_before = relationship.score
        relationship.apply_delta(result.score_delta)
        Memory.remember(owner=a, text=result.memory_a.text, about=_resolve_about(result.memory_a, b, a, b))
        Memory.remember(owner=b, text=result.memory_b.text, about=_resolve_about(result.memory_b, a, a, b))
        return Conversation.objects.create(
            a=a,
            b=b,
            lines=[{**line.model_dump(), 'speaker': names[line.speaker]} for line in result.lines],
            score_before=score_before,
            score_after=relationship.score,
            model_name=responses[-1].model_name or '',
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost_of(responses),
        )
