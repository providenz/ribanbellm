from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from farm.models import Character, Conversation, Feeling, Memory
from farm.tests.scripted import Scripted, reflection, turn

pytestmark = pytest.mark.django_db


def fake_model() -> Scripted:
    turns = [turn('Bonjour, voisin.'), turn('Bonjour, cher voisin.'), turn('Bon, je file.', leave=True), turn('Au revoir.')]
    return Scripted(turns, [reflection(-1), reflection(-1)])


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr('farm.conversations.build_model', fake_model)


@pytest.fixture
def cast():
    return [
        Character.objects.create(name=name, personality='Rêveur.', speech_quirk='Hmm.')
        for name in ('Théa', 'Bob', 'Ondine')
    ]


def test_chat_prints_dialogue_and_persists(no_llm, cast):
    a, b = Character.objects.all()[:2]
    out = StringIO()

    call_command('chat', a.name, b.name, stdout=out)

    output = out.getvalue()
    assert ': Bonjour, voisin.' in output  # the first speaker is drawn at random
    assert ': Au revoir.' in output
    assert f'{a.name} -> {b.name}: 0 -> -1' in output
    assert f'{b.name} -> {a.name}: 0 -> -1' in output
    assert Conversation.objects.count() == 1


def test_chat_picks_random_pair_when_no_names(no_llm, cast):

    call_command('chat', stdout=StringIO())

    conversation = Conversation.objects.get()
    assert conversation.a != conversation.b


def test_chat_rejects_unknown_character(no_llm):
    with pytest.raises(CommandError):
        call_command('chat', 'Nobody', 'Ghost', stdout=StringIO())


def test_chat_prints_token_usage(no_llm, cast):
    out = StringIO()

    call_command('chat', stdout=out)

    assert 'Tokens:' in out.getvalue()
    assert 'coût inconnu' in out.getvalue()


def test_usage_totals_per_model(cast):
    from decimal import Decimal

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


@pytest.fixture
def lived_in_farm(cast):
    a, b = Character.objects.all()[:2]
    Feeling.of(a, b).apply_delta(3)
    Memory.objects.create(owner=a, about=b, text='Il me doit une cuillère.')
    Conversation.objects.create(a=a, b=b, lines=[])
    return Character.objects.count()


def test_reset_farm_clears_content_and_keeps_characters(lived_in_farm):
    out = StringIO()
    call_command('reset_farm', '--yes', stdout=out)

    assert Conversation.objects.count() == 0
    assert Memory.objects.count() == 0
    assert Feeling.objects.count() == 0
    assert Character.objects.count() == lived_in_farm
    assert '1 conversation' in out.getvalue()


def test_reset_farm_does_nothing_unless_confirmed(lived_in_farm, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: 'n')
    call_command('reset_farm', stdout=StringIO())

    assert Conversation.objects.count() == 1
    assert Memory.objects.count() == 1
