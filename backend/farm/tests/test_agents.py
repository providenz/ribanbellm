import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import re

from farm.agents import MAX_LINES, MIN_LINES, TOPICS, pick_topic, run
from farm.models import Character, Conversation, Feeling, Memory

pytestmark = pytest.mark.django_db


class Scripted(FunctionModel):
    """Answers turns and reflections from queues, and records what each call saw."""

    def __init__(self, turns: list[dict | Exception], reflections: list[dict | Exception] | None = None):
        self.turns = list(turns)
        self.reflections = list(reflections or [reflection(0), reflection(0)])
        self.calls: list[str] = []  # instructions + prompt of each call
        super().__init__(self._respond)

    def _respond(self, messages, info: AgentInfo) -> ModelResponse:
        prompt = ' '.join(str(getattr(part, 'content', '')) for part in messages[-1].parts)
        self.calls.append(f'{info.instructions}\n{prompt}')
        tool = info.output_tools[0]
        queue = self.turns if 'leave' in tool.parameters_json_schema['properties'] else self.reflections
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ModelResponse(parts=[ToolCallPart(tool.name, answer)])


def turn(text='Bonjour.', emotion='neutral', leave=False) -> dict:
    return {'text': text, 'emotion': emotion, 'leave': leave}


def reflection(delta: int, text='Souvenir.') -> dict:
    return {'memory': {'text': text}, 'feeling_delta': delta}


class First:
    """rng stub: choice() returns the given character when offered it, else the first option."""

    def __init__(self, character, roll=0.9):
        self.character = character
        self.roll = roll

    def choice(self, options):
        return self.character if self.character in options else options[0]

    def random(self):
        return self.roll


@pytest.fixture
def pair():
    return (
        Character.objects.create(name='Gérard', personality='Caillou philosophe.', speech_quirk='Bof.'),
        Character.objects.create(name='Grillon', personality='Grille-pain anxieux.', speech_quirk='Pourquoi?'),
    )


def lines_of(events):
    return [e for e in events if e['type'] == 'line']


def test_turns_alternate_from_the_chosen_first_speaker(pair):
    a, b = pair
    events = list(run(a, b, model=Scripted([turn(leave=True)] * MIN_LINES), rng=First(b)))

    assert [e['speaker'] for e in lines_of(events)] == ['Grillon', 'Gérard', 'Grillon', 'Gérard']
    assert events[0] == {'type': 'thinking', 'speaker': 'Grillon'}
    assert [e['type'] for e in events[:4]] == ['thinking', 'line', 'thinking', 'line']


def test_leave_is_ignored_before_min_lines_then_honoured(pair):
    events = list(run(*pair, model=Scripted([turn(leave=True)] * MAX_LINES), rng=First(pair[0])))

    assert len(lines_of(events)) == MIN_LINES == 4


def test_hard_stop_at_max_lines(pair):
    events = list(run(*pair, model=Scripted([turn()] * 20), rng=First(pair[0])))

    assert len(lines_of(events)) == MAX_LINES == 8


def test_each_agent_sees_only_its_own_memories(pair):
    a, b = pair
    Memory.remember(owner=a, about=b, text='secret de Gérard')
    Memory.remember(owner=b, about=a, text='secret de Grillon')
    model = Scripted([turn(leave=True)] * MIN_LINES)

    list(run(a, b, model=model, rng=First(a)))

    assert 'secret de Gérard' in model.calls[0] and 'secret de Grillon' not in model.calls[0]
    assert 'secret de Grillon' in model.calls[1] and 'secret de Gérard' not in model.calls[1]
    assert 'Grille-pain anxieux' in model.calls[0]  # the partner's public personality is visible


def test_later_turns_see_the_transcript(pair):
    a, b = pair
    model = Scripted([turn('Il pleut des cailloux.', leave=True)] + [turn(leave=True)] * 3)

    list(run(a, b, model=model, rng=First(a)))

    assert 'Il pleut des cailloux.' in model.calls[1]


def test_reflections_apply_one_sided_feelings_and_memories(pair):
    a, b = pair
    model = Scripted([turn(leave=True)] * MIN_LINES, [reflection(2, 'A retient'), reflection(-1, 'B retient')])

    events = list(run(a, b, model=model, rng=First(a)))

    assert Feeling.of(a, b).score == 2
    assert Feeling.of(b, a).score == -1
    assert Memory.latest_for(a).get().text == 'A retient'
    assert Memory.latest_for(b).get().text == 'B retient'
    end = events[-1]
    assert end['type'] == 'end'
    assert end['feelings'] == {'Gérard': {'before': 0, 'after': 2}, 'Grillon': {'before': 0, 'after': -1}}
    conversation = Conversation.objects.get(pk=end['conversation_id'])
    assert conversation.engine == 'agents'
    assert not conversation.interrupted
    assert conversation.input_tokens > 0 and conversation.output_tokens > 0


def test_failure_mid_conversation_keeps_lines_without_consequences(pair):
    a, b = pair
    model = Scripted([turn(), turn(), RuntimeError('LLM down')])

    events = list(run(a, b, model=model, rng=First(a)))

    assert events[-1] == {'type': 'error', 'message': 'LLM down'}
    conversation = Conversation.objects.get()
    assert conversation.interrupted
    assert conversation.error == 'LLM down'
    assert len(conversation.lines) == 2
    assert Memory.objects.count() == 0
    assert not Feeling.objects.exclude(score=0).exists()


def test_failure_on_first_call_saves_an_empty_interrupted_conversation(pair):
    events = list(run(*pair, model=Scripted([RuntimeError('LLM down')]), rng=First(pair[0])))

    assert [e['type'] for e in events] == ['thinking', 'error']
    assert Conversation.objects.get().lines == []


def test_abandoned_before_wrap_up_saves_nothing(pair):
    events = run(*pair, model=Scripted([turn()] * 20), rng=First(pair[0]))
    for _ in range(3):
        next(events)
    events.close()

    assert Conversation.objects.count() == 0


def test_they_greet_each_other_first(pair):
    a, b = pair
    model = Scripted([turn(leave=True)] * MIN_LINES)

    list(run(a, b, model=model, rng=First(a)))

    assert 'Salue Grillon' in model.calls[0]
    assert 'Salue Gérard en retour' in model.calls[1]


def test_leaving_is_offered_only_after_the_greetings(pair):
    model = Scripted([turn(leave=True)] * MIN_LINES)

    events = list(run(*pair, model=model, rng=First(pair[0])))

    assert len(lines_of(events)) == MIN_LINES  # greet, greet back, leave, goodbye back
    assert not any('Tu peux partir' in call for call in model.calls[:2])
    assert 'Tu peux partir' in model.calls[2]


def test_the_one_who_stays_says_goodbye_back(pair):
    a, b = pair
    model = Scripted([turn(), turn(), turn(), turn('Bon, je file.', leave=True), turn('Au revoir!')])

    events = list(run(a, b, model=model, rng=First(a)))

    assert [e['text'] for e in lines_of(events)][-2:] == ['Bon, je file.', 'Au revoir!']
    assert 'Grillon s\'en va. Dis-lui au revoir' in model.calls[4]


def test_at_the_limit_the_second_to_last_speaker_leaves(pair):
    model = Scripted([turn()] * 20)

    events = list(run(*pair, model=model, rng=First(pair[0])))

    assert len(lines_of(events)) == MAX_LINES
    assert 'dernière réplique' in model.calls[MAX_LINES - 2]
    assert 'Dis-lui au revoir' in model.calls[MAX_LINES - 1]


def test_both_agents_get_the_same_topic(pair):
    model = Scripted([turn(leave=True)] * MIN_LINES)

    list(run(*pair, model=model, rng=First(pair[0])))

    topics = [re.search(r'Sujet du jour: (.+)', call).group(1) for call in model.calls[:2]]
    assert topics[0] == topics[1] == TOPICS[0]


def test_quirk_is_only_offered_on_the_greeting_unless_the_dice_say_so(pair):
    a, b = pair  # Gérard's quirk is "Bof."
    model = Scripted([turn()] * 20)

    list(run(a, b, model=model, rng=First(a, roll=0.9)))

    assert 'Bof.' in model.calls[0]  # Gérard greets
    assert all('Bof.' not in call for call in model.calls[2:MAX_LINES:2])  # Gérard's later turns
    assert 'sans ton tic de langage' in model.calls[2]


def test_quirk_comes_back_now_and_then(pair):
    a, b = pair
    model = Scripted([turn()] * 20)

    list(run(a, b, model=model, rng=First(a, roll=0.1)))

    assert 'Bof.' in model.calls[2]


def test_each_turn_keeps_the_topic_in_view(pair):
    model = Scripted([turn()] * 20)

    list(run(*pair, model=model, rng=First(pair[0])))

    talk_turns = model.calls[2:MAX_LINES - 2]
    assert talk_turns and all(TOPICS[0] in call.split('\n')[-1] for call in talk_turns)
    assert 'ne parles pas de toi' in model.calls[0]


def test_pick_topic_is_sometimes_gossip_about_another_villager():
    assert pick_topic(First(None, roll=0.9), ['Zigzag']) == TOPICS[0]
    assert 'Zigzag' in pick_topic(First(None, roll=0.1), ['Zigzag'])
    assert pick_topic(First(None, roll=0.1), []) == TOPICS[0]  # nobody to gossip about
