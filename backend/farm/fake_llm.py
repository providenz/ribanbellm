"""A free stand-in for the LLM (LLM_PROVIDER=fake): random canned French dialogue, no API call.

It answers the character agents (turns and reflections) and seed_characters --llm through the
real pipeline (structured output, memories, feelings), so everything downstream behaves as
with a real model.
"""

import random
import re
import time

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

# Simulated thinking time, so the frontend's "..." bubble has something to show
DELAY_SECONDS = (0.8, 2.5)
LEAVE_PROBABILITY = 0.35

OPENERS = [
    ('Tiens, {other}! Justement je pensais à toi.', 'happy'),
    ('Encore toi, {other}? Le monde est petit.', 'smug'),
    ('{other}! Tu tombes à pic, j\'ai un secret.', 'surprised'),
    ('Ah. {other}. Bonjour, je suppose.', 'neutral'),
]
REPLIES = [
    ('Tu as encore marché sur mes plates-bandes, coquin.', 'annoyed'),
    ('Je n\'ai rien fait, je le jure sur ma moustache imaginaire.', 'scared'),
    ('C\'est exactement ce que dirait un espion.', 'smug'),
    ('J\'ai perdu mon chapeau, l\'as-tu vu?', 'sad'),
    ('Quelle coïncidence, moi aussi j\'adore le fromage!', 'happy'),
    ('Pardon? Je n\'ai rien compris, mais j\'approuve.', 'surprised'),
    ('On en reparlera quand tu m\'auras rendu ma cuillère.', 'annoyed'),
    ('Chut! Les murs ont des oreilles.', 'scared'),
]
CLOSERS = [
    ('Bon, je file. Ne dis rien à personne!', 'smug'),
    ('À la prochaine, et pas un mot sur la cuillère.', 'neutral'),
    ('Je m\'en vais bouder ailleurs.', 'sad'),
    ('Quelle conversation passionnante. Adieu!', 'happy'),
]
MEMORIES = [
    '{other} m\'a parlé d\'une cuillère disparue.',
    '{other} cache sûrement quelque chose.',
    '{other} est plus drôle que je ne pensais.',
    '{other} m\'a taquiné, je lui rendrai la pareille.',
]


def _partner(instructions: str | None) -> str:
    match = re.search(r'Tu croises (.+?)\.', instructions or '')
    return match.group(1) if match else 'toi'


def fake_turn(partner: str, prompt: str, rng: random.Random) -> dict:
    """One character agent's line, following the turn's instruction (greet, talk, leave, goodbye)."""
    if 'Salue' in prompt:
        pool, leave = OPENERS, False
    elif 'dernière réplique' in prompt or 'Dis-lui au revoir' in prompt:
        pool, leave = CLOSERS, True
    elif 'Tu peux partir' in prompt and rng.random() < LEAVE_PROBABILITY:
        pool, leave = CLOSERS, True
    else:
        pool, leave = REPLIES, False
    text, emotion = rng.choice(pool)
    return {'text': text.format(other=partner), 'emotion': emotion, 'leave': leave}


def fake_reflection(partner: str, rng: random.Random) -> dict:
    return {'memory': {'text': rng.choice(MEMORIES).format(other=partner)}, 'feeling_delta': rng.randint(-2, 2)}


CAST_NOUNS = ['Théière', 'Radis', 'Hibou', 'Parapluie', 'Cornichon', 'Taupe', 'Bougie', 'Homard', 'Brosse', 'Navet']
CAST_TITLES = ['Professeur', 'Tante', 'Capitaine', 'Duchesse', 'Maître', 'Petit', 'Docteur', 'Sire']
CAST_TRAITS = [
    'persuadé d\'être une star de cinéma',
    'qui collectionne les bruits bizarres',
    'terrifié par les mardis',
    'qui se prend pour un grand explorateur',
    'convaincu que la Lune le suit',
]
CAST_QUIRKS = ['Finit chaque phrase par "et voilà le travail".', 'Rime sans le vouloir.', 'Chuchote les mots importants.']


def fake_cast(rng: random.Random, size: int = 10) -> dict:
    """Arguments for generation.Cast: distinct made-up characters."""
    names = rng.sample([f'{t} {n}' for t in CAST_TITLES for n in CAST_NOUNS], size)
    return {
        'characters': [
            {
                'name': name,
                'personality': f'{name.split()[-1]} {rng.choice(CAST_TRAITS)}.',
                'speech_quirk': rng.choice(CAST_QUIRKS),
                'color': '#%06x' % rng.randrange(0x1000000),
                'accessory': rng.choice(['none', 'hat', 'glasses', 'bow', 'antenna', 'mustache', 'crown']),
            }
            for name in names
        ]
    }


def build_fake_model(rng: random.Random | None = None) -> FunctionModel:
    rng = rng or random.Random()

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        time.sleep(rng.uniform(*DELAY_SECONDS))
        tool = info.output_tools[0]
        fields = tool.parameters_json_schema['properties']
        prompt = '\n'.join(str(part.content) for part in messages[-1].parts if hasattr(part, 'content'))
        if 'leave' in fields:  # a character agent's turn
            args = fake_turn(_partner(info.instructions), prompt, rng)
        elif 'characters' in fields:  # seed_characters --llm
            args = fake_cast(rng)
        else:  # a character agent's reflection
            args = fake_reflection(_partner(info.instructions), rng)
        return ModelResponse(parts=[ToolCallPart(tool.name, args)])

    return FunctionModel(respond, model_name='fake')
