import random

import pytest

from farm import fake_llm
from farm.director import run_conversation
from farm.models import Character, Memory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(fake_llm, 'DELAY_SECONDS', (0, 0))


def test_fake_model_runs_the_real_pipeline():
    a = Character.objects.create(name='Grillon', personality='p', speech_quirk='q')
    b = Character.objects.create(name='Gérard', personality='p', speech_quirk='q')

    conversation = run_conversation(a, b, model=fake_llm.build_fake_model(random.Random(1)))

    assert 4 <= len(conversation.lines) <= 6
    assert [line['speaker'] for line in conversation.lines[:2]] == ['Grillon', 'Gérard']
    assert 'Gérard' in conversation.lines[0]['text']
    assert conversation.model_name == 'fake'
    assert Memory.objects.get(owner=a).about == b
    assert abs(conversation.score_after - conversation.score_before) <= 3


def test_fake_provider_needs_no_key(settings):
    from farm.llm import build_model

    settings.LLM_PROVIDER = 'fake'
    settings.LLM_API_KEY = ''
    assert build_model().model_name == 'fake'
