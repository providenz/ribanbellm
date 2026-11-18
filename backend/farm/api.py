import json

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q, Sum
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from . import conversations
from .models import Character, Conversation

api = NinjaAPI(title='Ant farm')


class CharacterOut(Schema):
    id: int
    name: str
    color: str
    accessory: str


class UsageOut(Schema):
    conversations: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None  # sum of the known costs, None if none is known
    unpriced: int  # conversations whose model has no known price


class ConversationIn(Schema):
    a_id: int
    b_id: int


@api.get('/characters', response=list[CharacterOut])
def list_characters(request):
    return Character.objects.filter(is_active=True)


@api.get('/usage', response=UsageOut)
def usage(request):
    """Token consumption and cost over every stored conversation."""
    totals = Conversation.objects.aggregate(
        conversations=Count('id'),
        input_tokens=Sum('input_tokens', default=0),
        output_tokens=Sum('output_tokens', default=0),
        cost=Sum('cost_usd'),
        unpriced=Count('id', filter=Q(cost_usd__isnull=True)),
    )
    cost = totals.pop('cost')
    return {**totals, 'cost_usd': None if cost is None else float(cost)}


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
