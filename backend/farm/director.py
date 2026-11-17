"""The conversation director: one LLM call writes a whole exchange between two characters."""

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from .common import TONE_RULES, LenientEmotion, MemoryNote, ShortText, Usage, feeling_label
from .conversations import Outcome, end_event, error_event, line_event, record, thinking_event
from .models import Character, Feeling, Memory


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


def run(a: Character, b: Character, *, model: Model) -> Iterator[dict]:
    """Director engine: one call writes the whole scene, then its lines are replayed as events."""
    yield thinking_event(a)
    usage = Usage()
    try:
        run = director.run_sync(build_prompt(a, b), model=model)
    except Exception as exc:  # any model failure ends the stream cleanly
        record(a, b, lines=[], usage=usage, engine='director', outcome=None)
        yield error_event(str(exc))
        return
    usage.add(run)
    result = run.output
    speakers = {'A': a, 'B': b}
    lines = [{**line.model_dump(), 'speaker': speakers[line.speaker].name} for line in result.lines]
    for line, raw in zip(lines, result.lines):
        yield thinking_event(speakers[raw.speaker])
        yield line_event(line)
    outcome = Outcome(result.memory_a, result.memory_b, result.score_delta, result.score_delta)
    yield end_event(record(a, b, lines=lines, usage=usage, engine='director', outcome=outcome))
