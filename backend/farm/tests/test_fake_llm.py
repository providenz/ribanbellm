import random

import pytest

from farm import fake_llm
from farm.models import Character, Conversation, Memory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake_llm, 'DELAY_SECONDS', (0, 0))


def test_fake_provider_needs_no_key(settings):
    from farm.llm import build_model

    settings.LLM_PROVIDER = 'fake'
    settings.LLM_API_KEY = ''
    assert build_model().model_name == 'fake'


def test_fake_model_drives_the_agents_engine():
    from farm import agents

    a = Character.objects.create(name='Grillon', personality='p', speech_quirk='q')
    b = Character.objects.create(name='Gérard', personality='p', speech_quirk='q')

    events = list(agents.run(a, b, model=fake_llm.build_fake_model(random.Random(1))))

    lines = [e for e in events if e['type'] == 'line']
    assert agents.MIN_LINES <= len(lines) <= agents.MAX_LINES
    assert events[-1]['type'] == 'end'
    conversation = Conversation.objects.get(pk=events[-1]['conversation_id'])
    assert conversation.engine == 'agents' and conversation.model_name == 'fake'
    assert Memory.objects.filter(owner=a).count() == 1
    assert all(abs(f['after'] - f['before']) <= 2 for f in events[-1]['feelings'].values())


def test_fake_agents_greet_first_and_say_goodbye_last():
    from farm import agents

    a = Character.objects.create(name='Grillon', personality='p', speech_quirk='q')
    b = Character.objects.create(name='Gérard', personality='p', speech_quirk='q')
    openers = {text.format(other=name) for text, _ in fake_llm.OPENERS for name in ('Grillon', 'Gérard')}
    closers = {text for text, _ in fake_llm.CLOSERS}

    for seed in range(5):
        events = list(agents.run(a, b, model=fake_llm.build_fake_model(random.Random(seed)), rng=random.Random(seed)))
        texts = [e['text'] for e in events if e['type'] == 'line']
        assert texts[0] in openers and texts[1] in openers
        assert texts[-2] in closers and texts[-1] in closers
