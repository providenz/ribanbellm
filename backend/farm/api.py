from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from pydantic_ai.exceptions import AgentRunError

from . import director
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


class LineOut(Schema):
    speaker: str
    text: str
    emotion: director.Emotion


class ConversationOut(Schema):
    id: int
    lines: list[LineOut]
    score_before: int
    score_after: int


@api.get('/characters', response=list[CharacterOut])
def list_characters(request):
    return Character.objects.filter(is_active=True)


@api.post('/conversations', response=ConversationOut)
def create_conversation(request, payload: ConversationIn):
    if payload.a_id == payload.b_id:
        raise HttpError(400, 'A character cannot talk to itself.')
    a = get_object_or_404(Character, pk=payload.a_id, is_active=True)
    b = get_object_or_404(Character, pk=payload.b_id, is_active=True)
    try:
        return director.run_conversation(a, b)
    except AgentRunError as exc:
        raise HttpError(502, f'LLM call failed: {exc}') from exc
