"""Character agents engine: each character is its own agent and speaks in turns.

A character only knows its own personality, its own memories and its own feeling toward the
partner (plus what anyone can see of the partner). It decides what to say, with which emotion,
and when to leave. Afterwards each one reflects: what it remembers and how its feeling changed.
"""

import random
from collections.abc import Iterator
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from .common import TONE_RULES, LenientEmotion, MemoryNote, ShortText, Usage, feeling_label
from .conversations import Outcome, end_event, interrupted, line_event, record, thinking_event
from .models import Character, Feeling, Memory

MIN_LINES = 4
MAX_LINES = 8


class Turn(BaseModel):
    text: ShortText = Field(description='Ta réplique: courte (moins de 120 caractères), drôle, en français.')
    emotion: LenientEmotion
    leave: bool = Field(default=False, description='true si tu t\'en vas après cette réplique.')


class Reflection(BaseModel):
    memory: MemoryNote = Field(description='Ce que tu retiens de cette conversation.')
    feeling_delta: int = Field(
        ge=-2, le=2, description='Comment ton sentiment envers l\'autre a changé: -2 (un peu refroidi) à +2 (plus complice).'
    )


@dataclass
class CharacterContext:
    me: Character
    partner: Character
    feeling: int
    memories: list[Memory]


def _who_i_am(ctx: CharacterContext) -> str:
    memories = [
        f'- {m.text}' + (f' (à propos de {m.about.name})' if m.about else '') for m in ctx.memories
    ] or ['- aucun']
    return '\n'.join(
        [
            f'Tu es {ctx.me.name}. Personnalité: {ctx.me.personality}',
            f'Ton tic de langage: {ctx.me.speech_quirk}',
            f'Tu croises {ctx.partner.name}. Ce que tout le monde voit de lui: {ctx.partner.personality}',
            f'Ce que tu ressens pour {ctx.partner.name}: {feeling_label(ctx.feeling)}.',
            'Tes souvenirs (toi seul les connais):',
            *memories,
            '',
            TONE_RULES,
        ]
    )


speaker = Agent(output_type=Turn, deps_type=CharacterContext, name='character', retries=1)
reflector = Agent(output_type=Reflection, deps_type=CharacterContext, name='reflection', retries=1)


@speaker.instructions
def _speaker_instructions(ctx: RunContext[CharacterContext]) -> str:
    return (
        _who_i_am(ctx.deps)
        + '\n\nTu parles en français, une seule réplique à la fois, avec ta voix bien à toi. '
        'Tu peux utiliser tes souvenirs: blagues récurrentes, petites dettes, ragots sur les autres. '
        'Mets leave à true quand tu as envie de partir; la conversation dure au moins quatre répliques.'
    )


@reflector.instructions
def _reflector_instructions(ctx: RunContext[CharacterContext]) -> str:
    return (
        _who_i_am(ctx.deps)
        + '\n\nLa conversation est finie. En une phrase, de ton point de vue, dis ce que tu en retiens, '
        'et comment ton sentiment envers l\'autre a changé.'
    )


def _transcript(lines: list[dict]) -> str:
    return '\n'.join(f"{line['speaker']}: {line['text']}" for line in lines)


def _turn_prompt(ctx: CharacterContext, lines: list[dict]) -> str:
    if not lines:
        return f'Tu parles en premier à {ctx.partner.name}.'
    return f'Conversation jusqu\'ici:\n{_transcript(lines)}\n\nÀ toi.'


def run(a: Character, b: Character, *, model: Model, rng: random.Random | None = None) -> Iterator[dict]:
    rng = rng or random.Random()
    contexts = {
        me.pk: CharacterContext(me, partner, Feeling.of(me, partner).score, list(Memory.latest_for(me)))
        for me, partner in ((a, b), (b, a))
    }
    current = rng.choice((a, b))
    lines: list[dict] = []
    usage = Usage()
    try:
        while len(lines) < MAX_LINES:
            ctx = contexts[current.pk]
            yield thinking_event(current)
            result = speaker.run_sync(_turn_prompt(ctx, lines), deps=ctx, model=model)
            usage.add(result)
            line = {'speaker': current.name, 'text': result.output.text, 'emotion': result.output.emotion}
            lines.append(line)
            yield line_event(line)
            if result.output.leave and len(lines) >= MIN_LINES:
                break
            current = ctx.partner

        reflections = {}
        for me in (a, b):
            result = reflector.run_sync(
                f'La conversation:\n{_transcript(lines)}', deps=contexts[me.pk], model=model
            )
            usage.add(result)
            reflections[me.pk] = result.output
    except Exception as exc:  # any model failure ends the stream cleanly
        yield interrupted(a, b, lines=lines, usage=usage, engine='agents', exc=exc)
        return

    ra, rb = reflections[a.pk], reflections[b.pk]
    outcome = Outcome(ra.memory, rb.memory, ra.feeling_delta, rb.feeling_delta)
    yield end_event(record(a, b, lines=lines, usage=usage, engine='agents', outcome=outcome))
