"""Shared conversation layer: picks the engine, defines the streamed events, saves the result.

An engine is a generator of event dicts (see `thinking_event`, `line_event`, `end_event`,
`error_event`); it records the conversation itself before yielding `end` or `error`.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from pydantic_ai.models import Model

from .common import MemoryNote, Usage, resolve_about
from .llm import build_model  # re-exported: tests patch farm.conversations.build_model
from .models import Character, Conversation, Feeling, Memory

logger = logging.getLogger(__name__)


@dataclass
class Outcome:
    memory_a: MemoryNote
    memory_b: MemoryNote
    delta_a: int  # change of a's feeling toward b
    delta_b: int  # change of b's feeling toward a


def record(
    a: Character,
    b: Character,
    *,
    lines: list[dict],
    usage: Usage,
    engine: str,
    outcome: Outcome | None,
    error: str = '',
) -> Conversation:
    """Save the conversation. Without an outcome it was interrupted: no memories, no feeling change."""
    with transaction.atomic():
        a_to_b, b_to_a = Feeling.of(a, b), Feeling.of(b, a)
        a_before, b_before = a_to_b.score, b_to_a.score
        if outcome:
            a_to_b.apply_delta(outcome.delta_a)
            b_to_a.apply_delta(outcome.delta_b)
            Memory.remember(owner=a, text=outcome.memory_a.text, about=resolve_about(outcome.memory_a, b, a, b))
            Memory.remember(owner=b, text=outcome.memory_b.text, about=resolve_about(outcome.memory_b, a, a, b))
        return Conversation.objects.create(
            a=a,
            b=b,
            lines=lines,
            feeling_a_before=a_before,
            feeling_a_after=a_to_b.score,
            feeling_b_before=b_before,
            feeling_b_after=b_to_a.score,
            interrupted=outcome is None,
            engine=engine,
            error=error,
            model_name=usage.model_name,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )


def interrupted(a: Character, b: Character, *, lines: list[dict], usage: Usage, engine: str, exc: Exception) -> dict:
    """Log the failure, save what was said with no consequences, and return the error event."""
    logger.exception('%s conversation between %s and %s failed', engine, a.name, b.name)
    conversation = record(a, b, lines=lines, usage=usage, engine=engine, outcome=None, error=str(exc))
    return error_event(str(exc), conversation)


def thinking_event(speaker: Character) -> dict:
    return {'type': 'thinking', 'speaker': speaker.name}


def line_event(line: dict) -> dict:
    return {'type': 'line', **line}


def usage_of(conversation: Conversation) -> dict:
    """Tokens and USD cost of one conversation (cost None when the model has no known price)."""
    cost = conversation.cost_usd
    return {
        'input_tokens': conversation.input_tokens,
        'output_tokens': conversation.output_tokens,
        'cost_usd': None if cost is None else float(cost),
    }


def end_event(conversation: Conversation) -> dict:
    return {
        'type': 'end',
        'conversation_id': conversation.id,
        'feelings': {
            conversation.a.name: {'before': conversation.feeling_a_before, 'after': conversation.feeling_a_after},
            conversation.b.name: {'before': conversation.feeling_b_before, 'after': conversation.feeling_b_after},
        },
        'usage': usage_of(conversation),
    }


def error_event(message: str, conversation: Conversation) -> dict:
    """The failure message, and what the calls made before it consumed."""
    return {'type': 'error', 'message': message, 'usage': usage_of(conversation)}


def stream(a: Character, b: Character, *, model: Model | None = None) -> Iterator[dict]:
    """Validate, then return the configured engine's event generator."""
    if a.pk == b.pk:
        raise ValueError('A character cannot talk to itself.')
    from . import agents, director  # engines import this module

    engines = {'agents': agents.run, 'director': director.run}
    engine = engines.get(settings.CONVERSATION_ENGINE)
    if engine is None:
        raise ImproperlyConfigured(
            f'Unknown CONVERSATION_ENGINE {settings.CONVERSATION_ENGINE!r} (expected {" or ".join(engines)}).'
        )
    return engine(a, b, model=model or build_model())
