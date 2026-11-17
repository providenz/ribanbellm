"""Invent new characters with the LLM (seed_characters --llm)."""

import random
import re
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from .common import TONE_RULES
from .models import Character

Accessory = Literal['none', 'hat', 'glasses', 'bow', 'antenna', 'mustache', 'crown']
PALETTE = ['#e0604a', '#4a90b0', '#7ab04a', '#b04a8c', '#c9a04a', '#6a5acd', '#4ab09a', '#b07a4a']


def _color(value) -> str:
    return value if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) else random.choice(PALETTE)


# Lenient schema: a slightly off answer is fixed up instead of costing a retry call
class CharacterIdea(BaseModel):
    name: Annotated[str, AfterValidator(lambda s: s.strip()[:60])] = Field(description='Nom court et drôle.')
    personality: Annotated[str, AfterValidator(lambda s: s[:300])] = Field(
        description='Une ou deux phrases: qui ou quoi il est, son obsession.'
    )
    speech_quirk: Annotated[str, AfterValidator(lambda s: s[:200])] = Field(
        description='Son tic de langage, utilisé de temps en temps (pas à chaque phrase).'
    )
    color: Annotated[str, BeforeValidator(_color)] = Field(
        default_factory=lambda: random.choice(PALETTE), description='Couleur hexadécimale, ex. #7ab04a.'
    )
    accessory: Annotated[Accessory, BeforeValidator(lambda v: v if v in get_args(Accessory) else 'none')] = 'none'


class Cast(BaseModel):
    characters: list[CharacterIdea]


casting = Agent(output_type=Cast, deps_type=tuple, name='casting', retries=1)


@casting.instructions
def _casting_instructions(ctx: RunContext[tuple]) -> str:
    count, existing = ctx.deps
    return '\n'.join(
        [
            f'Invente {count} nouveaux personnages pour une petite ferme de personnages excentriques qui '
            'se croisent et bavardent: animaux, objets ou légumes avec une personnalité marquée.',
            'Tout en français. Chacun doit être très différent des autres.',
            'Personnages déjà présents (ne les répète pas): ' + (', '.join(existing) or 'aucun') + '.',
            '',
            TONE_RULES,
        ]
    )


def generate_characters(count: int, *, model: Model, existing: list[str]) -> list[dict]:
    """Up to `count` new characters as Character field dicts, skipping names already taken."""
    result = casting.run_sync('Présente la nouvelle troupe.', deps=(count, existing), model=model)
    taken = {name.casefold() for name in existing}
    ideas = []
    for idea in result.output.characters:
        if idea.name and idea.name.casefold() not in taken and len(ideas) < count:
            taken.add(idea.name.casefold())
            ideas.append(idea.model_dump())
    return ideas


assert set(get_args(Accessory)) == set(Character.Accessory.values)
