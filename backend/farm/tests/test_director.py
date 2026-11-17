import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from farm.director import build_prompt, run_conversation
from farm.models import Character, Conversation, Memory, Relationship

pytestmark = pytest.mark.django_db


@pytest.fixture
def pigeon():
    return Character.objects.create(
        name='Agent Roucoule', personality='Pigeon persuadé d\'être espion.', speech_quirk='Code secret'
    )


@pytest.fixture
def diva():
    return Character.objects.create(
        name='Madame Vibrato', personality='Diva d\'opéra à la retraite.', speech_quirk='Chante tout'
    )


def answering(args: dict) -> FunctionModel:
    """A fake model that immediately returns `args` as the structured output."""

    def respond(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    return FunctionModel(respond)


def result_args(**overrides) -> dict:
    args = {
        'lines': [
            {'speaker': 'A', 'text': 'Le hibou chante à minuit.', 'emotion': 'smug'},
            {'speaker': 'B', 'text': 'Moi aussi, je chante! Laaa!', 'emotion': 'happy'},
            {'speaker': 'A', 'text': 'Couverture grillée...', 'emotion': 'scared'},
            {'speaker': 'B', 'text': 'Quel public ingrat.', 'emotion': 'angry'},
        ],
        'memory_a': {'text': 'Vibrato a failli griller ma couverture.'},
        'memory_b': {'text': 'Ce pigeon ne connaît rien à l\'opéra.'},
        'score_delta': -2,
    }
    args.update(overrides)
    return args


def test_build_prompt_includes_characters_memories_and_relationship(pigeon, diva):
    Memory.remember(owner=pigeon, about=diva, text='Vibrato m\'a volé mon pain.')
    Relationship.between(pigeon, diva).apply_delta(-8)

    prompt = build_prompt(pigeon, diva)

    assert 'Agent Roucoule' in prompt and 'Madame Vibrato' in prompt
    assert 'Pigeon persuadé' in prompt and 'Chante tout' in prompt
    assert 'Vibrato m\'a volé mon pain.' in prompt
    assert '-8' in prompt
    assert 'ennemis' in prompt


def test_run_conversation_persists_log_memories_and_score(pigeon, diva):
    conversation = run_conversation(pigeon, diva, model=answering(result_args()))

    assert Conversation.objects.count() == 1
    assert conversation.lines[0] == {'speaker': 'Agent Roucoule', 'text': 'Le hibou chante à minuit.', 'emotion': 'smug'}
    assert conversation.score_before == 0
    assert conversation.score_after == -2
    assert Relationship.between(pigeon, diva).score == -2

    pigeon_memory = Memory.latest_for(pigeon).get()
    assert pigeon_memory.text == 'Vibrato a failli griller ma couverture.'
    assert pigeon_memory.about == diva
    assert Memory.latest_for(diva).get().about == pigeon


def test_memory_about_a_third_character_is_gossip(pigeon, diva):
    toaster = Character.objects.create(name='Grillon', personality='Grille-pain.', speech_quirk='Tic')
    args = result_args(memory_a={'text': 'Grillon espionne pour l\'ennemi.', 'about': 'grillon'})

    run_conversation(pigeon, diva, model=answering(args))

    assert Memory.latest_for(pigeon).get().about == toaster


def test_memory_about_unknown_name_falls_back_to_partner(pigeon, diva):
    args = result_args(memory_a={'text': 'Bizarre.', 'about': 'Personne Inconnue'})

    run_conversation(pigeon, diva, model=answering(args))

    assert Memory.latest_for(pigeon).get().about == diva


def test_model_failure_persists_nothing(pigeon, diva):
    def broken(messages, info):
        raise RuntimeError('LLM down')

    with pytest.raises(RuntimeError):
        run_conversation(pigeon, diva, model=FunctionModel(broken))

    assert Conversation.objects.count() == 0
    assert Memory.objects.count() == 0
    assert not Relationship.objects.exclude(score=0).exists()


def test_cannot_talk_to_oneself(pigeon):
    with pytest.raises(ValueError):
        run_conversation(pigeon, pigeon, model=answering(result_args()))


def test_run_conversation_records_token_usage(pigeon, diva):
    conversation = run_conversation(pigeon, diva, model=answering(result_args()))

    assert conversation.model_name == 'function:respond:'
    assert conversation.input_tokens > 0
    assert conversation.output_tokens > 0
    assert conversation.cost_usd is None  # fake model has no known price


def test_cost_of_known_and_unknown_models():
    from decimal import Decimal

    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.usage import RequestUsage

    from farm.director import cost_of

    def response(model_name, provider_name):
        return ModelResponse(
            parts=[TextPart('x')],
            usage=RequestUsage(input_tokens=1000, output_tokens=500),
            model_name=model_name,
            provider_name=provider_name,
        )

    claude = response('claude-opus-5-5', 'anthropic')
    assert cost_of([claude, claude]) == Decimal('0.028')  # 2 x (1000 * $4/M + 500 * $20/M)
    assert cost_of([claude, response('mistral-medium-2508', 'openai')]) is None  # one unpriced: total unknown
