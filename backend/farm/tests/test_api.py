import json

import pytest

from farm.agents import MIN_LINES
from farm.models import Character, Conversation
from farm.tests.scripted import Scripted, turn

pytestmark = pytest.mark.django_db

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


def test_create_conversation_streams_ndjson_events(client, cast, monkeypatch):
    monkeypatch.setattr('farm.conversations.build_model', lambda: Scripted([turn('Salut.', 'happy', leave=True)] * MIN_LINES))
    gerard, grillon, _ = cast

    response = post_conversation(client, gerard.id, grillon.id)

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/x-ndjson'
    raw, events = events_of(response)
    assert 'Gérard' in raw  # accents are not escaped
    assert [e['type'] for e in events] == ['thinking', 'line'] * MIN_LINES + ['end']
    assert {e['speaker'] for e in events if e['type'] == 'line'} == {'Gérard', 'Grillon'}
    assert events[1]['text'] == 'Salut.' and events[1]['emotion'] == 'happy'
    assert events[-1]['conversation_id'] == Conversation.objects.get().id


def test_create_conversation_with_unknown_or_inactive_character_is_404(client, cast):
    gerard, _, absent = cast

    assert post_conversation(client, gerard.id, 99999).status_code == 404
    assert post_conversation(client, gerard.id, absent.id).status_code == 404


def test_create_conversation_with_same_character_is_400(client, cast):
    assert post_conversation(client, cast[0].id, cast[0].id).status_code == 400


def test_llm_failure_ends_the_stream_with_an_error_event(client, cast, monkeypatch):
    monkeypatch.setattr('farm.conversations.build_model', lambda: Scripted([RuntimeError('LLM down')]))

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


def test_usage_totals_every_conversation(client, cast):
    a, b = cast[0], cast[1]
    Conversation.objects.create(a=a, b=b, lines=[], input_tokens=100, output_tokens=10, cost_usd='0.0125')
    Conversation.objects.create(a=a, b=b, lines=[], input_tokens=50, output_tokens=5, cost_usd=None)

    response = client.get('/api/usage')

    assert response.status_code == 200
    assert response.json() == {
        'conversations': 2, 'input_tokens': 150, 'output_tokens': 15, 'cost_usd': 0.0125, 'unpriced': 1,
    }


def test_usage_with_no_conversation_yet(client):
    assert client.get('/api/usage').json() == {
        'conversations': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': None, 'unpriced': 0,
    }
