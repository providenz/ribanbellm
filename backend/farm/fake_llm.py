"""A free stand-in for the LLM (LLM_PROVIDER=fake): random canned French dialogue, no API call.

It answers both engines (director scenes, character agent turns and reflections) through the
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


def _names(prompt: str) -> tuple[str, str]:
    a = re.search(r'^A = (.+)$', prompt, re.MULTILINE)
    b = re.search(r'^B = (.+)$', prompt, re.MULTILINE)
    return (a.group(1) if a else 'toi', b.group(1) if b else 'toi')


def fake_conversation(prompt: str, rng: random.Random) -> dict:
    """Arguments for ConversationResult: 4 to 6 alternating lines, A speaks first."""
    a, b = _names(prompt)
    count = rng.randint(4, 6)
    middle = rng.sample(REPLIES, count - 2)
    picks = [rng.choice(OPENERS), *middle, rng.choice(CLOSERS)]
    lines = []
    for i, (text, emotion) in enumerate(picks):
        speaker = 'AB'[i % 2]
        lines.append({'speaker': speaker, 'text': text.format(other=b if speaker == 'A' else a), 'emotion': emotion})
    return {
        'lines': lines,
        'memory_a': {'text': rng.choice(MEMORIES).format(other=b)},
        'memory_b': {'text': rng.choice(MEMORIES).format(other=a)},
        'score_delta': rng.randint(-2, 2),
    }


def _partner(instructions: str | None) -> str:
    match = re.search(r'Tu croises (.+?)\.', instructions or '')
    return match.group(1) if match else 'toi'


def fake_turn(partner: str, rng: random.Random) -> dict:
    """One character agent's line; wants to leave about a third of the time."""
    text, emotion = rng.choice(OPENERS + REPLIES + CLOSERS)
    return {'text': text.format(other=partner), 'emotion': emotion, 'leave': rng.random() < LEAVE_PROBABILITY}


def fake_reflection(partner: str, rng: random.Random) -> dict:
    return {'memory': {'text': rng.choice(MEMORIES).format(other=partner)}, 'feeling_delta': rng.randint(-2, 2)}


def build_fake_model(rng: random.Random | None = None) -> FunctionModel:
    rng = rng or random.Random()

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        time.sleep(rng.uniform(*DELAY_SECONDS))
        tool = info.output_tools[0]
        fields = tool.parameters_json_schema['properties']
        if 'leave' in fields:  # a character agent's turn
            args = fake_turn(_partner(info.instructions), rng)
        elif 'feeling_delta' in fields:  # a character agent's reflection
            args = fake_reflection(_partner(info.instructions), rng)
        else:  # the director's whole scene
            prompt = '\n'.join(str(part.content) for part in messages[-1].parts if hasattr(part, 'content'))
            args = fake_conversation(prompt, rng)
        return ModelResponse(parts=[ToolCallPart(tool.name, args)])

    return FunctionModel(respond, model_name='fake')
