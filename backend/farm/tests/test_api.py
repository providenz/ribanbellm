import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from farm.models import Character, Conversation

pytestmark = pytest.mark.django_db

VALID_OUTPUT = {
    'lines': [
        {'speaker': 'A', 'text': 'Salut.', 'emotion': 'happy'},
        {'speaker': 'B', 'text': 'Bof.', 'emotion': 'neutral'},
    ],
    'memory_a': {'text': 'Il a dit bof.'},
    'memory_b': {'text': 'Il a dit salut.'},
    'score_delta': 1,
}


def model_returning(args: dict) -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    return FunctionModel(respond)


@pytest.fixture
def cast():
    return [
        Character.objects.create(name='Gérard', personality='Caillou.', speech_quirk='Bof.', color='#6e6a66'),
        Character.objects.create(name='Grillon', personality='Grille-pain.', speech_quirk='Pourquoi?', accessory='hat'),
        Character.objects.create(name='Absent', personality='-', speech_quirk='-', is_active=False),
    ]


def post_conversation(client, a_id, b_id):
    return client.post(
        '/api/conversations', data=json.dumps({'a_id': a_id, 'b_id': b_id}), content_type='application/json'
    )


def test_list_characters_returns_active_ones_in_stable_order(client, cast):
    response = client.get('/api/characters')

    assert response.status_code == 200
    assert response.json() == [
        {'id': cast[0].id, 'name': 'Gérard', 'color': '#6e6a66', 'accessory': 'none'},
        {'id': cast[1].id, 'name': 'Grillon', 'color': '#e0604a', 'accessory': 'hat'},
    ]


def events_of(response) -> tuple[str, list[dict]]:
    raw = b''.join(response.streaming_content).decode()
    return raw, [json.loads(line) for line in raw.splitlines()]


def test_create_conversation_streams_ndjson_events(client, cast, monkeypatch, settings):
    settings.CONVERSATION_ENGINE = 'director'
    monkeypatch.setattr('farm.conversations.build_model', lambda: model_returning(VALID_OUTPUT))
    gerard, grillon, _ = cast

    response = post_conversation(client, gerard.id, grillon.id)

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/x-ndjson'
    raw, events = events_of(response)
    assert 'Gérard' in raw  # accents are not escaped
    assert [e['type'] for e in events] == ['thinking', 'thinking', 'line', 'thinking', 'line', 'end']
    assert events[2] == {'type': 'line', 'speaker': 'Gérard', 'text': 'Salut.', 'emotion': 'happy'}
    assert events[-1]['conversation_id'] == Conversation.objects.get().id


def test_create_conversation_with_unknown_or_inactive_character_is_404(client, cast):
    gerard, _, absent = cast

    assert post_conversation(client, gerard.id, 99999).status_code == 404
    assert post_conversation(client, gerard.id, absent.id).status_code == 404


def test_create_conversation_with_same_character_is_400(client, cast):
    assert post_conversation(client, cast[0].id, cast[0].id).status_code == 400


def test_llm_failure_ends_the_stream_with_an_error_event(client, cast, monkeypatch, settings):
    settings.CONVERSATION_ENGINE = 'director'
    invalid = {**VALID_OUTPUT, 'score_delta': 99}  # out of range on every attempt
    monkeypatch.setattr('farm.conversations.build_model', lambda: model_returning(invalid))

    response = post_conversation(client, cast[0].id, cast[1].id)

    assert response.status_code == 200
    _, events = events_of(response)
    assert events[-1]['type'] == 'error'
    assert Conversation.objects.get().interrupted


def test_missing_api_key_is_500_before_streaming(client, cast, settings):
    settings.LLM_PROVIDER = 'anthropic'
    settings.LLM_API_KEY = ''

    response = post_conversation(client, cast[0].id, cast[1].id)

    assert response.status_code == 500
    assert 'LLM_API_KEY' in response.json()['detail']
