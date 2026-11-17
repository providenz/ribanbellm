from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from farm.models import Character, Conversation

pytestmark = pytest.mark.django_db


def fake_model() -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        args = {
            'lines': [
                {'speaker': 'A', 'text': 'Bonjour, ennemi.', 'emotion': 'smug'},
                {'speaker': 'B', 'text': 'Bonjour, pire ennemi.', 'emotion': 'annoyed'},
            ],
            'memory_a': {'text': 'Il m\'a appelé ennemi.'},
            'memory_b': {'text': 'Il a commencé.'},
            'score_delta': -1,
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    return FunctionModel(respond)


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr('farm.director.build_model', fake_model)


def test_seed_characters_is_idempotent():
    call_command('seed_characters', stdout=StringIO())
    count = Character.objects.count()
    call_command('seed_characters', stdout=StringIO())

    assert count >= 10
    assert Character.objects.count() == count


def test_chat_prints_dialogue_and_persists(no_llm):
    call_command('seed_characters', stdout=StringIO())
    a, b = Character.objects.all()[:2]
    out = StringIO()

    call_command('chat', a.name, b.name, stdout=out)

    output = out.getvalue()
    assert f'{a.name}: Bonjour, ennemi.' in output
    assert f'{b.name}: Bonjour, pire ennemi.' in output
    assert f'{a.name} -> {b.name}: 0 -> -1' in output
    assert f'{b.name} -> {a.name}: 0 -> -1' in output
    assert Conversation.objects.count() == 1


def test_chat_picks_random_pair_when_no_names(no_llm):
    call_command('seed_characters', stdout=StringIO())

    call_command('chat', stdout=StringIO())

    conversation = Conversation.objects.get()
    assert conversation.a != conversation.b


def test_chat_rejects_unknown_character(no_llm):
    with pytest.raises(CommandError):
        call_command('chat', 'Nobody', 'Ghost', stdout=StringIO())


def test_chat_prints_token_usage(no_llm):
    call_command('seed_characters', stdout=StringIO())
    out = StringIO()

    call_command('chat', stdout=out)

    assert 'Tokens:' in out.getvalue()
    assert 'coût inconnu' in out.getvalue()


def test_usage_totals_per_model():
    from decimal import Decimal

    call_command('seed_characters', stdout=StringIO())
    a, b = Character.objects.all()[:2]
    common = dict(a=a, b=b, lines=[])
    Conversation.objects.create(**common, model_name='claude-opus-5-5', input_tokens=100, output_tokens=50, cost_usd=Decimal('0.01'))
    Conversation.objects.create(**common, model_name='claude-opus-5-5', input_tokens=200, output_tokens=70, cost_usd=Decimal('0.02'))
    Conversation.objects.create(**common, model_name='mistral-medium-2508', input_tokens=10, output_tokens=5, cost_usd=None)
    out = StringIO()

    call_command('usage', stdout=out)

    lines = out.getvalue().splitlines()
    assert any('claude-opus-5-5' in l and '2' in l and '300' in l and '120' in l and '$0.0300' in l for l in lines)
    assert any('mistral-medium-2508' in l and 'inconnu' in l for l in lines)
