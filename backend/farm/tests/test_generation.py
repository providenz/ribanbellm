import random
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from farm import fake_llm, generation
from farm.models import Character

pytestmark = pytest.mark.django_db


def casting_model(characters: list[dict], seen: list[AgentInfo] | None = None) -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        if seen is not None:
            seen.append(info)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {'characters': characters})])

    return FunctionModel(respond)


def idea(name, **extra):
    return {'name': name, 'personality': 'Une théière anxieuse.', 'speech_quirk': 'Siffle.', **extra}


def test_generated_characters_are_cleaned_up():
    model = casting_model([idea('Théa', color='bleu', accessory='cape'), idea('Bob', color='#12abEF', accessory='hat')])

    ideas = generation.generate_characters(2, model=model, existing=[])

    assert [i['name'] for i in ideas] == ['Théa', 'Bob']
    assert ideas[0]['accessory'] == 'none'  # unknown accessory
    assert ideas[0]['color'].startswith('#') and len(ideas[0]['color']) == 7  # invalid colour replaced
    assert ideas[1]['color'] == '#12abEF'
    assert ideas[1]['accessory'] == 'hat'


def test_generation_skips_taken_and_repeated_names_and_caps_the_count():
    model = casting_model([idea('grillon'), idea('Théa'), idea('THÉA'), idea('Bob'), idea('Zoé')])

    ideas = generation.generate_characters(2, model=model, existing=['Grillon'])

    assert [i['name'] for i in ideas] == ['Théa', 'Bob']


def test_generation_prompt_names_existing_characters():
    seen = []
    generation.generate_characters(1, model=casting_model([idea('Théa')], seen), existing=['Grillon', 'Gérard'])

    assert 'Grillon' in seen[0].instructions and 'Gérard' in seen[0].instructions


def test_fake_model_casts_characters(monkeypatch):
    monkeypatch.setattr(fake_llm, 'DELAY_SECONDS', (0, 0))

    ideas = generation.generate_characters(3, model=fake_llm.build_fake_model(random.Random(1)), existing=[])

    assert len(ideas) == 3
    assert len({i['name'] for i in ideas}) == 3


def test_seed_invents_characters_with_the_llm(monkeypatch):
    Character.objects.create(name='Grillon', personality='p', speech_quirk='q')
    monkeypatch.setattr('farm.llm.build_model', lambda: casting_model([idea('Théa'), idea('Bob')]))
    out = StringIO()

    call_command('seed_characters', '--count', '2', stdout=out)

    assert set(Character.objects.values_list('name', flat=True)) == {'Grillon', 'Théa', 'Bob'}
    assert 'created: Théa' in out.getvalue()


def test_seed_if_empty_invents_only_into_an_empty_farm(monkeypatch):
    monkeypatch.setattr('farm.llm.build_model', lambda: casting_model([idea('Théa'), idea('Bob')]))

    call_command('seed_characters', '--count', '2', '--if-empty', stdout=StringIO())
    call_command('seed_characters', '--count', '2', '--if-empty', stdout=StringIO())

    assert set(Character.objects.values_list('name', flat=True)) == {'Théa', 'Bob'}


def test_seed_count_must_be_between_1_and_10():
    with pytest.raises(CommandError):
        call_command('seed_characters', '--count', '11', stdout=StringIO())
