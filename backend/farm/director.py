"""The conversation director: one LLM call writes a whole exchange between two characters."""

from typing import Literal

from django.db import transaction
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model

from .common import TONE_RULES, LenientEmotion, MemoryNote, ShortText, cost_of, feeling_label, resolve_about
from .llm import build_model
from .models import Character, Conversation, Feeling, Memory


class Line(BaseModel):
    speaker: Literal['A', 'B']
    text: ShortText = Field(description='Une réplique courte et percutante, en français.')
    emotion: LenientEmotion


class ConversationResult(BaseModel):
    lines: list[Line] = Field(min_length=2, max_length=8)
    memory_a: MemoryNote = Field(description='Ce que A retiendra de cette conversation.')
    memory_b: MemoryNote = Field(description='Ce que B retiendra de cette conversation.')
    score_delta: int = Field(ge=-2, le=2, description='Évolution de leur entente: -2 (un peu refroidis) à +2 (plus complices).')


INSTRUCTIONS = """\
Tu es le scénariste d'une petite série comique. Deux personnages excentriques se croisent \
et échangent quelques répliques.

Règles:
- Écris 4 à 6 répliques au total, en alternant A et B, en français.
- Chaque réplique fait moins de 120 caractères: courte, drôle, percutante.
- Chaque personnage a une voix très marquée: sa personnalité et son tic de langage doivent se sentir.
- Si les personnages ont des souvenirs l'un de l'autre ou des ragots, utilise-les: blagues \
récurrentes, petites dettes, malentendus.
- Ce que chacun ressent pour l'autre doit colorer le ton (réservé ou complice).
- Jamais de ton d'assistant poli ou neutre.
- Termine par ce que chacun retiendra (une phrase chacun) et l'évolution de leur entente.

""" + TONE_RULES

director = Agent(
    output_type=ConversationResult,
    instructions=INSTRUCTIONS,
    name='director',
    retries=1,
)


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
    a_to_b = Feeling.of(a, b).score
    b_to_a = Feeling.of(b, a).score
    return '\n\n'.join(
        [
            _describe('A', a),
            _describe('B', b),
            f'Ce que A ressent pour B: {feeling_label(a_to_b)} ({a_to_b} sur une échelle de -10 à +10).\n'
            f'Ce que B ressent pour A: {feeling_label(b_to_a)} ({b_to_a} sur une échelle de -10 à +10).',
        ]
    )


def run_conversation(a: Character, b: Character, *, model: Model | None = None) -> Conversation:
    if a.pk == b.pk:
        raise ValueError('A character cannot talk to itself.')

    run = director.run_sync(build_prompt(a, b), model=model or build_model())
    result = run.output
    usage = run.usage
    responses = [m for m in run.new_messages() if isinstance(m, ModelResponse)]
    names = {'A': a.name, 'B': b.name}

    with transaction.atomic():
        a_to_b, b_to_a = Feeling.of(a, b), Feeling.of(b, a)
        a_before, b_before = a_to_b.score, b_to_a.score
        a_to_b.apply_delta(result.score_delta)
        b_to_a.apply_delta(result.score_delta)
        Memory.remember(owner=a, text=result.memory_a.text, about=resolve_about(result.memory_a, b, a, b))
        Memory.remember(owner=b, text=result.memory_b.text, about=resolve_about(result.memory_b, a, a, b))
        return Conversation.objects.create(
            a=a,
            b=b,
            lines=[{**line.model_dump(), 'speaker': names[line.speaker]} for line in result.lines],
            feeling_a_before=a_before,
            feeling_a_after=a_to_b.score,
            feeling_b_before=b_before,
            feeling_b_after=b_to_a.score,
            engine='director',
            model_name=responses[-1].model_name or '',
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost_of(responses),
        )
