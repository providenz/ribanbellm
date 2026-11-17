import json

from django.core.exceptions import ImproperlyConfigured
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from . import conversations
from .models import Character

api = NinjaAPI(title='Ant farm')


class CharacterOut(Schema):
    id: int
    name: str
    color: str
    accessory: str


class ConversationIn(Schema):
    a_id: int
    b_id: int


@api.get('/characters', response=list[CharacterOut])
def list_characters(request):
    return Character.objects.filter(is_active=True)


@api.post('/conversations')
def create_conversation(request, payload: ConversationIn):
    """Stream the conversation as NDJSON events: thinking/line pairs, then end or error."""
    if payload.a_id == payload.b_id:
        raise HttpError(400, 'A character cannot talk to itself.')
    a = get_object_or_404(Character, pk=payload.a_id, is_active=True)
    b = get_object_or_404(Character, pk=payload.b_id, is_active=True)
    try:
        events = conversations.stream(a, b, model=conversations.build_model())
    except ImproperlyConfigured as exc:
        raise HttpError(500, str(exc)) from exc
    return StreamingHttpResponse(
        (json.dumps(event, ensure_ascii=False) + '\n' for event in events), content_type='application/x-ndjson'
    )
