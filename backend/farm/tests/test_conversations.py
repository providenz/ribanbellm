import pytest
from django.core.exceptions import ImproperlyConfigured
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from farm.conversations import stream
from farm.models import Character, Conversation, Memory

pytestmark = pytest.mark.django_db

VALID = {
    'lines': [
        {'speaker': 'A', 'text': 'Salut.', 'emotion': 'happy'},
        {'speaker': 'B', 'text': 'Bof, déjà vu.', 'emotion': 'neutral'},
    ],
    'memory_a': {'text': 'Il a dit bof.'},
    'memory_b': {'text': 'Il a dit salut.'},
    'score_delta': 1,
}


def answering(args: dict) -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    return FunctionModel(respond)


@pytest.fixture
def pair(settings):
    settings.CONVERSATION_ENGINE = 'director'
    return (
        Character.objects.create(name='Gérard', personality='Caillou.', speech_quirk='Bof.'),
        Character.objects.create(name='Grillon', personality='Grille-pain.', speech_quirk='Pourquoi?'),
    )


def test_director_stream_events(pair):
    events = list(stream(*pair, model=answering(VALID)))

    assert [e['type'] for e in events] == ['thinking', 'thinking', 'line', 'thinking', 'line', 'end']
    assert events[0] == {'type': 'thinking', 'speaker': 'Gérard'}
    assert events[2] == {'type': 'line', 'speaker': 'Gérard', 'text': 'Salut.', 'emotion': 'happy'}
    assert events[3] == {'type': 'thinking', 'speaker': 'Grillon'}
    end = events[-1]
    assert end['conversation_id'] == Conversation.objects.get().id
    assert end['feelings'] == {'Gérard': {'before': 0, 'after': 1}, 'Grillon': {'before': 0, 'after': 1}}


def test_director_failure_records_interrupted_conversation(pair):
    events = list(stream(*pair, model=answering({**VALID, 'score_delta': 99})))

    assert events[-1]['type'] == 'error'
    conversation = Conversation.objects.get()
    assert conversation.interrupted
    assert conversation.lines == []
    assert conversation.feeling_a_after == conversation.feeling_a_before
    assert Memory.objects.count() == 0


def test_unexpected_model_exception_ends_with_error_event(pair):
    def broken(messages, info):
        raise RuntimeError('LLM down')

    events = list(stream(*pair, model=FunctionModel(broken)))

    assert events[-1] == {'type': 'error', 'message': 'LLM down'}
    assert Conversation.objects.get().interrupted


def test_abandoned_stream_saves_nothing(pair):
    events = stream(*pair, model=answering(VALID))
    next(events)
    events.close()

    assert Conversation.objects.count() == 0


def test_unknown_engine_is_rejected(pair, settings):
    settings.CONVERSATION_ENGINE = 'nope'

    with pytest.raises(ImproperlyConfigured):
        list(stream(*pair, model=answering(VALID)))


def test_cannot_talk_to_oneself(pair):
    with pytest.raises(ValueError):
        list(stream(pair[0], pair[0], model=answering(VALID)))
