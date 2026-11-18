"""Character agents engine: each character is its own agent and speaks in turns.

A character only knows its own personality, its own memories and its own feeling toward the
partner (plus what anyone can see of the partner). It decides what to say, with which emotion,
and when to leave. Afterwards each one reflects: what it remembers and how its feeling changed.
"""

import random
import re
from collections.abc import Iterator
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from .common import TONE_RULES, LenientEmotion, MemoryNote, ShortText, Usage, feeling_label
from .conversations import Outcome, end_event, interrupted, line_event, record, thinking_event
from .models import Character, Feeling, Memory

MIN_LINES = 4  # greetings and goodbyes included
MAX_LINES = 8
GOSSIP_PROBABILITY = 0.35

VILLAGE = (
    'Vous vivez dans un petit village: quelques maisons, un puits sur la place, des bancs, des lampadaires, '
    'une mare bordée de sable, des arbres fruitiers et des chemins de terre.'
)
# Dreamy, philosophical questions rooted in the village, so the talk is about something other than the characters
TOPICS = [
    'où vont les reflets de la mare quand la nuit tombe',
    'ce dont se souvient le puits de toutes les choses tombées dedans',
    'si les chemins savent où ils mènent',
    'le rêve qu\'on a fait cette nuit et qui continue un peu le jour',
    'ce que pensent les arbres fruitiers pendant l\'hiver',
    'pourquoi le lampadaire de la place ne s\'éteint jamais tout à fait',
    'si une maison vide rêve de ses habitants',
    'ce qui reste d\'une conversation quand on l\'a oubliée',
    'le bruit que fait le temps qui passe sur un banc',
    'si l\'on est la même personne avant et après une sieste',
    'ce que le sable de la mare a vu avant d\'être du sable',
    'les choses qu\'on cherche et qui nous cherchent aussi',
]


QUOTED = re.compile(r'«\s*(.+?)\s*»|"(.+?)"|“(.+?)”')
STAGE_DIRECTION = re.compile(r'\*[^*]+\*')
TRAILING = r'[\s.…,!?]*'


def strip_quirk(text: str, quirk: str) -> str:
    """The line without the quirk's quoted catchphrases and without *stage directions*.

    Models keep copying a quirk once it is in the conversation, even when told not to; this is the
    safety net for the turns where it is not allowed. A line that would be left empty is kept as is.
    """
    cleaned = STAGE_DIRECTION.sub(' ', text)
    for groups in QUOTED.findall(quirk):
        phrase = next(g for g in groups if g).strip(' .…')
        if len(phrase) >= 4:
            cleaned = re.sub(TRAILING + re.escape(phrase) + TRAILING, ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;')
    if not re.search(r'\w', cleaned):
        return text
    return cleaned + '.' if cleaned[-1].isalnum() else cleaned


def pick_topic(rng, others: list[str]) -> str:
    """The day's topic, shared by both: gossip about another villager now and then, else an everyday subject."""
    if others and rng.random() < GOSSIP_PROBABILITY:
        return f'ce que {rng.choice(others)} a vu en rêve, paraît-il (un ragot)'
    return rng.choice(TOPICS)


class Turn(BaseModel):
    text: ShortText = Field(description='Ta réplique: courte (moins de 120 caractères), imagée, en français.')
    emotion: LenientEmotion = Field(
        description='L\'émotion de CETTE réplique, selon ce que tu dis: agacé, surpris, triste, fier de toi, inquiet... '
        'happy seulement si tu es vraiment content.'
    )
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
    topic: str
    quirk_now: bool | None = None  # this turn: use the quirk (True), avoid it (False); None outside turns


def _who_i_am(ctx: CharacterContext) -> str:
    memories = [
        f'- {m.text}' + (f' (à propos de {m.about.name})' if m.about else '') for m in ctx.memories
    ] or ['- aucun']
    return '\n'.join(
        [
            f'Tu es {ctx.me.name}. Personnalité: {ctx.me.personality}',
            *{
                True: [f'Ton tic de langage, à glisser dans cette réplique: {ctx.me.speech_quirk}'],
                False: [
                    f'Cette réplique, SANS ton tic de langage ({ctx.me.speech_quirk}) et sans geste entre astérisques: '
                    'juste ce que tu as à dire.'
                ],
                None: [],
            }[ctx.quirk_now],
            f'Tu croises {ctx.partner.name}. Ce que tout le monde voit de lui: {ctx.partner.personality}',
            f'Ce que tu ressens pour {ctx.partner.name}: {feeling_label(ctx.feeling)}.',
            'Tes souvenirs (toi seul les connais):',
            *memories,
            '',
            VILLAGE,
            f'Sujet du jour: {ctx.topic}',
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
        'Quand on se croise, on se salue; quand on se quitte, on se dit au revoir. '
        'Suis la consigne donnée à chaque tour.\n'
        'Ta personnalité colore ta façon de parler, mais tu ne parles pas de toi ni de ton nom: '
        'parle du sujet du jour, des autres habitants, de la vie du village. Réponds vraiment à ce que '
        'l\'autre vient de dire. Ne reprends pas les mots ni la tournure de tes répliques précédentes. '
        'Choisis l\'émotion qui colle vraiment à ta réplique, pas toujours happy.\n'
        'Style: une conversation philosophique et onirique, mais jamais académique. Des questions simples et '
        'profondes, des images de rêve, une logique de rêve où les choses glissent les unes dans les autres. '
        'Pas de jargon, pas de grands mots, pas de noms de philosophes: des mots de tous les jours qui ouvrent '
        'sur quelque chose de plus grand.'
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


def _turn_prompt(ctx: CharacterContext, lines: list[dict], phase: str) -> str:
    """What this turn is for: greeting, greeting back, talking (may leave), last line, or goodbye back."""
    other = ctx.partner.name
    instruction = {
        'greet': f'Tu croises {other}: tu parles en premier. Salue {other}, puis lance le sujet du jour: {ctx.topic}.',
        'greet_back': f'Salue {other} en retour, à ta façon, et réagis à ce qu\'il vient de dire.',
        'free': f'Réponds à ce que {other} vient de dire, en restant sur le sujet du jour ({ctx.topic}). '
        'Tu peux partir si tu veux: dans ce cas ta réplique est un au revoir et leave vaut true.',
        'last': f'C\'est ta dernière réplique: tu t\'en vas, dis au revoir à {other}.',
        'goodbye_back': f'{other} s\'en va. Dis-lui au revoir.',
    }[phase]
    if not lines:
        return instruction
    return f'Conversation jusqu\'ici:\n{_transcript(lines)}\n\n{instruction}'


def _phase(lines: list[dict], partner_left: bool) -> str:
    if partner_left:
        return 'goodbye_back'
    if not lines:
        return 'greet'
    if len(lines) == 1:
        return 'greet_back'
    if len(lines) >= MAX_LINES - 2:
        return 'last'
    return 'free'  # leaving after the greetings still makes MIN_LINES with the goodbye back


def run(a: Character, b: Character, *, model: Model, rng: random.Random | None = None) -> Iterator[dict]:
    rng = rng or random.Random()
    others = list(Character.objects.filter(is_active=True).exclude(pk__in=[a.pk, b.pk]).values_list('name', flat=True))
    topic = pick_topic(rng, others)
    contexts = {
        me.pk: CharacterContext(me, partner, Feeling.of(me, partner).score, list(Memory.latest_for(me)), topic)
        for me, partner in ((a, b), (b, a))
    }
    current = rng.choice((a, b))
    lines: list[dict] = []
    usage = Usage()
    try:
        partner_left = False
        while True:
            ctx = contexts[current.pk]
            phase = _phase(lines, partner_left)
            # Models copy a quirk into every line once they have seen it: once each, on the first line
            ctx.quirk_now = len(lines) < 2
            yield thinking_event(current)
            result = speaker.run_sync(_turn_prompt(ctx, lines, phase), deps=ctx, model=model)
            usage.add(result)
            text = result.output.text if ctx.quirk_now else strip_quirk(result.output.text, current.speech_quirk)
            line = {'speaker': current.name, 'text': text, 'emotion': result.output.emotion}
            lines.append(line)
            yield line_event(line)
            if phase == 'goodbye_back':
                break
            partner_left = phase == 'last' or (phase == 'free' and result.output.leave)
            current = ctx.partner

        reflections = {}
        for me in (a, b):
            contexts[me.pk].quirk_now = None
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
