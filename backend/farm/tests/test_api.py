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


def test_create_conversation(client, cast, monkeypatch):
    monkeypatch.setattr('farm.director.build_model', lambda: model_returning(VALID_OUTPUT))
    gerard, grillon, _ = cast

    response = post_conversation(client, gerard.id, grillon.id)

    assert response.status_code == 200
    body = response.json()
    assert body['lines'] == [
        {'speaker': 'Gérard', 'text': 'Salut.', 'emotion': 'happy'},
        {'speaker': 'Grillon', 'text': 'Bof.', 'emotion': 'neutral'},
    ]
    assert body['score_before'] == 0
    assert body['score_after'] == 1
    assert body['id'] == Conversation.objects.get().id


def test_create_conversation_with_unknown_or_inactive_character_is_404(client, cast):
    gerard, _, absent = cast

    assert post_conversation(client, gerard.id, 99999).status_code == 404
    assert post_conversation(client, gerard.id, absent.id).status_code == 404


def test_create_conversation_with_same_character_is_400(client, cast):
    assert post_conversation(client, cast[0].id, cast[0].id).status_code == 400


def test_llm_failure_is_502_and_persists_nothing(client, cast, monkeypatch):
    invalid = {**VALID_OUTPUT, 'score_delta': 99}  # out of range on every attempt
    monkeypatch.setattr('farm.director.build_model', lambda: model_returning(invalid))

    response = post_conversation(client, cast[0].id, cast[1].id)

    assert response.status_code == 502
    assert 'detail' in response.json()
    assert Conversation.objects.count() == 0
