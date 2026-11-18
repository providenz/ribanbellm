import pytest

from farm.agents import MIN_LINES
from farm.conversations import stream
from farm.models import Character, Conversation
from farm.tests.scripted import Scripted, reflection, turn

pytestmark = pytest.mark.django_db


@pytest.fixture
def pair():
    return (
        Character.objects.create(name='Gérard', personality='Caillou.', speech_quirk='Bof.'),
        Character.objects.create(name='Grillon', personality='Grille-pain.', speech_quirk='Pourquoi?'),
    )


def test_stream_runs_the_character_agents(pair):
    model = Scripted([turn('Salut.', leave=True)] * MIN_LINES, [reflection(1), reflection(1)])

    events = list(stream(*pair, model=model))

    assert [e['type'] for e in events] == ['thinking', 'line'] * MIN_LINES + ['end']
    end = events[-1]
    conversation = Conversation.objects.get()
    assert end['conversation_id'] == conversation.id
    assert conversation.engine == 'agents'
    assert end['feelings'] == {'Gérard': {'before': 0, 'after': 1}, 'Grillon': {'before': 0, 'after': 1}}
    assert end['usage'] == {
        'input_tokens': conversation.input_tokens,
        'output_tokens': conversation.output_tokens,
        'cost_usd': None if conversation.cost_usd is None else float(conversation.cost_usd),
    }
    assert end['usage']['input_tokens'] > 0


def test_model_failure_ends_with_an_error_event(pair):
    events = list(stream(*pair, model=Scripted([RuntimeError('LLM down')])))

    assert events[-1]['type'] == 'error' and events[-1]['message'] == 'LLM down'
    assert events[-1]['usage'] == {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0}
    assert Conversation.objects.get().interrupted


def test_failure_is_stored_and_logged(pair, caplog):
    list(stream(*pair, model=Scripted([RuntimeError('LLM down')])))

    assert Conversation.objects.get().error == 'LLM down'
    assert 'LLM down' in caplog.text


def test_abandoned_stream_saves_nothing(pair):
    events = stream(*pair, model=Scripted([turn()] * 20))
    next(events)
    events.close()

    assert Conversation.objects.count() == 0


def test_cannot_talk_to_oneself(pair):
    with pytest.raises(ValueError):
        list(stream(pair[0], pair[0], model=Scripted([])))
