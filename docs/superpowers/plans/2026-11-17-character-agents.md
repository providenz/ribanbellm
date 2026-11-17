# Character Agents and Choreographed Meetings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each character talks as its own LLM agent, with lines streamed to the browser as they're written, and the browser choreographs meetings (random pair walks together, talks, splits).

**Architecture:** The backend gets a shared conversation layer (`farm/conversations.py`) that picks an engine (`agents` or the existing `director`). Each engine is a generator of events that also saves the result. The API streams those events as NDJSON. Feelings become one-sided (`Feeling` replaces `Relationship`). The frontend replaces the "adjacent by chance" rule with pure, tested choreography helpers in `sim.js` plus an NDJSON reader, wired into the Phaser scene.

**Tech Stack:** Django 6.1 + Django Ninja 1.8 + pydantic-ai 2.69 + SQLite (uv, pytest-django); Phaser 4 + Vite 8 (vitest).

**Spec:** `docs/superpowers/specs/2026-11-17-character-agents-design.md`

## Global Constraints

- Tone: never hate, insults, contempt or "can't stand you". Disagreements stay playful. This applies to prompts, feeling labels, fake model lines, emoji and icons.
- Emotions: `neutral | happy | annoyed | sad | surprised | smug | scared` (`angry` is gone). Emoji: neutral none, happy 😄, annoyed 😤, sad 😢, surprised 😮, smug 😏, scared 😱.
- `MIN_LINES = 4`, `MAX_LINES = 8`. A `leave` before `MIN_LINES` lines is ignored.
- Reflection `feeling_delta` in -2..+2; `Feeling.score` clamped to -10..+10. Director `score_delta` becomes -2..+2 and applies to both feelings.
- Agents keep `retries=1`. Schemas are lenient: text over 200 characters is trimmed, an unknown emotion becomes `neutral`.
- Pacing constants (unchanged): 1 conversation in flight, 20 s global gap, 60 s pair cooldown, meeting check every 250 ms.
- Line on screen: `1.5 s + 50 ms per character`. Icon after the chat: ❤️ if the character's own feeling rose, 😕 if it fell, nothing otherwise.
- Setting `CONVERSATION_ENGINE` (`agents` default | `director`); `LLM_PROVIDER=fake` must work with both engines.
- Dialogue and prompts in French. No AI attribution in commits, code or docs. No em dashes.
- Commit message style: imperative sentence, like `Add ...` (see `git log`).

## Event shapes (shared by backend and frontend)

```
{"type": "thinking", "speaker": "<name>"}
{"type": "line", "speaker": "<name>", "text": "...", "emotion": "<emotion>"}
{"type": "end", "conversation_id": 12, "feelings": {"<name a>": {"before": 2, "after": 3}, "<name b>": {"before": 0, "after": -1}}}
{"type": "error", "message": "..."}
```

`end` or `error` is always the last event. `feelings[name]` is that character's own feeling toward the other.

## Review Focus

1. An agent that wants to leave on every turn: the conversation still reaches 4 lines, then stops at the first `leave` (test in Task 3).
2. An LLM failure on the very first call: zero lines, an `interrupted` conversation saved with no consequences, `error` as the last event, and the browser shows "bof..." and splits (tests in Tasks 2 and 3; manual check in Task 6).
3. Accented text (é, è, ç) split across network chunks in the NDJSON stream: decoded correctly (test in Task 5).
4. A pair that can't reach each other (boxed in by blocks or other characters): skipped, the next candidate is tried, nothing hangs (test in Task 4).
5. A character removed by the slider while approaching or talking: the request is aborted and the partner splits off alone; abandoning the stream before wrap-up saves nothing (backend test in Task 2; manual check in Task 6).

---

### Task 1: One-sided feelings, soft tone, conversation fields

**Files:**
- Create: `backend/farm/common.py`
- Modify: `backend/farm/models.py` (replace `Relationship` with `Feeling`, change `Conversation`)
- Create: `backend/farm/migrations/0003_feelings.py`
- Modify: `backend/farm/director.py`, `backend/farm/admin.py`, `backend/farm/management/commands/chat.py`, `backend/farm/management/commands/usage.py`
- Test: `backend/farm/tests/test_models.py`, `test_director.py`, `test_commands.py`, `test_api.py`, `test_fake_llm.py` (update for the new fields)

**Interfaces:**
- Produces in `farm/common.py`:
  - `Emotion = Literal['neutral','happy','annoyed','sad','surprised','smug','scared']`
  - `LenientEmotion`: an `Annotated[Emotion, BeforeValidator(...)]` that maps any unknown value to `'neutral'`
  - `ShortText`: an `Annotated[str, AfterValidator(...)]` that trims to 200 characters
  - `class MemoryNote(BaseModel)`: `text: ShortText`, `about: str | None = None` (moved from director)
  - `TONE_RULES: str`: the French "nothing nasty, playful disagreements" rules
  - `feeling_label(score: int) -> str`: from low to high, "pas vraiment sur la même longueur d'onde", "un peu froid", "connaissance", "bon copain", "meilleur ami" (cut points are the builder's call)
  - `resolve_about(note: MemoryNote, partner: Character, a: Character, b: Character) -> Character` (moved from `director._resolve_about`)
  - `cost_of(responses) -> Decimal | None` (moved from director)
  - `@dataclass class Usage`: `input_tokens: int = 0`, `output_tokens: int = 0`, `cost_usd: Decimal | None = Decimal(0)`, `model_name: str = ''`; `add(self, run) -> None` adds a pydantic-ai run result's `run.usage` tokens, adds its cost (`cost_usd` becomes and stays `None` once any response is unpriced), and sets `model_name` from the last response.
- Produces in `farm/models.py`:
  - `Feeling(owner FK Character related_name='feelings', toward FK Character related_name='+', score SmallInt default 0)`, `MIN_SCORE = -10`, `MAX_SCORE = 10`, unique on `(owner, toward)`, check `owner != toward`; `Feeling.of(owner, toward) -> Feeling` (get-or-create); `apply_delta(delta: int) -> None` (clamp + save).
  - `Conversation`: remove `score_before`/`score_after`; add `feeling_a_before`, `feeling_a_after`, `feeling_b_before`, `feeling_b_after` (SmallInt, default 0; "a" is a's feeling toward b), `interrupted` (Bool, default False), `engine` (CharField max 10, default `'director'`).

- [ ] **Step 1: Replace the Relationship tests in `test_models.py` with Feeling tests**

```python
def test_feeling_is_one_sided(make):
    a, b = make('Alice'), make('Bob')
    Feeling.of(a, b).apply_delta(3)
    assert Feeling.of(a, b).score == 3
    assert Feeling.of(b, a).score == 0
    assert Feeling.objects.count() == 2

def test_feeling_is_clamped(make):
    f = Feeling.of(make('Alice'), make('Bob'))
    f.apply_delta(50); assert f.score == Feeling.MAX_SCORE
    f.apply_delta(-50); assert f.score == Feeling.MIN_SCORE

def test_feeling_labels_are_soft():
    labels = [feeling_label(s) for s in range(-10, 11)]
    assert labels[0] == "pas vraiment sur la même longueur d'onde"
    assert labels[-1] == 'meilleur ami'
    assert not any(word in ' '.join(labels) for word in ('ennemi', 'supporte', 'déteste'))

def test_lenient_schema_trims_text_and_defaults_emotion():
    class Probe(BaseModel):
        text: ShortText
        emotion: LenientEmotion
    p = Probe(text='x' * 300, emotion='furious')
    assert len(p.text) == 200 and p.emotion == 'neutral'
```

(`make` is the existing character factory in that file; adapt to its current form.)

- [ ] **Step 2: Run them and see them fail**

Run: `cd backend && uv run pytest farm/tests/test_models.py -q`
Expected: FAIL with an ImportError on `Feeling` / `farm.common`.

- [ ] **Step 3: Implement `farm/common.py` and the model changes, then generate the migration**

Run `uv run python manage.py makemigrations farm --name feelings`, then edit `0003_feelings.py` so the operations run in this order: create `Feeling`; add the new `Conversation` fields; a `RunPython` that copies each `Relationship.score` into both `Feeling` directions and each conversation's `score_before`/`score_after` into both `feeling_*_before`/`feeling_*_after`; remove `score_before`/`score_after`; delete `Relationship`. Existing conversations keep `engine='director'` from the default.

- [ ] **Step 4: Adapt the director to the new world (it stays synchronous in this task)**

In `director.py`: import `Emotion`, `MemoryNote`, `TONE_RULES`, `feeling_label`, `resolve_about`, `cost_of` from `common`; `Line.text: ShortText`, `Line.emotion: LenientEmotion`; `score_delta` becomes `Field(ge=-2, le=2)`; the instructions append `TONE_RULES` and lose "rancunes"; `build_prompt` states both one-sided feelings ("A envers B: <label> (<score>)", and the same for B toward A); `run_conversation` applies `score_delta` to `Feeling.of(a, b)` and `Feeling.of(b, a)` and fills the four `feeling_*` fields and `engine='director'`.

- [ ] **Step 5: Update the admin and commands**

Admin: register `Feeling` (list `owner`, `toward`, `score`; `score` editable; filter by `owner`); `Conversation` list and readonly fields use the new fields plus `engine` and `interrupted`. `chat` prints `"<name> -> <other>: <before> -> <after>"` for each character instead of `Relation:`. `usage` groups by `('engine', 'model_name')` and prints an `engine` column first.

- [ ] **Step 6: Update the existing tests to the new fields and tone**

Replace `score_before`/`score_after` assertions with `feeling_*` ones; replace `'angry'` in fake outputs with `'annoyed'`; in `test_commands.py` assert `f'{a.name} -> {b.name}: 0 -> -1'` and `f'{b.name} -> {a.name}: 0 -> -1'` are in the output; keep the `score_delta: 99` invalid-output test (still out of range).

- [ ] **Step 7: Run the whole backend suite**

Run: `cd backend && uv run pytest -q && uv run python manage.py migrate && uv run python manage.py chat`
Expected: all tests pass; the migration applies to the dev database; `chat` (fake model) prints both feeling changes.

- [ ] **Step 8: Commit**

```bash
git add backend/farm
git commit -m "Replace shared relationship scores with one-sided feelings and soften the tone"
```

---

### Task 2: Event stream, conversation layer and NDJSON API (director engine)

**Files:**
- Create: `backend/farm/conversations.py`
- Modify: `backend/farm/director.py`, `backend/farm/api.py`, `backend/farm/management/commands/chat.py`, `backend/config/settings.py`
- Test: `backend/farm/tests/test_conversations.py` (new), `test_api.py`, `test_director.py`, `test_commands.py`

**Interfaces:**
- Consumes: Task 1's `Feeling`, `Usage`, `MemoryNote`, `resolve_about`.
- Produces in `farm/conversations.py`:
  - `@dataclass class Outcome`: `memory_a: MemoryNote`, `memory_b: MemoryNote`, `delta_a: int`, `delta_b: int` (`delta_a` changes a's feeling toward b)
  - `record(a, b, *, lines: list[dict], usage: Usage, engine: str, outcome: Outcome | None) -> Conversation`: in one transaction. With an outcome, it applies both deltas and stores both memories (`resolve_about`). With `None`, it saves `interrupted=True` with before = after and no memories.
  - `end_event(conversation: Conversation) -> dict` and `error_event(message: str) -> dict`, in the shapes above.
  - `build_model` re-exported here (`from .llm import build_model`), so tests patch `farm.conversations.build_model`.
  - `stream(a, b, *, model: Model | None = None) -> Iterator[dict]`: raises `ValueError` if `a == b`; picks the engine from `settings.CONVERSATION_ENGINE` (`ImproperlyConfigured` if unknown); `model = model or build_model()`; then yields the engine's events.
- Produces in `farm/director.py`: `run(a, b, *, model: Model) -> Iterator[dict]`, which replaces `run_conversation`. It yields `thinking` for `a` before its single call. Then, for each line, it yields `thinking` for that speaker followed by `line`. It records with `engine='director'` and yields `end`. On `AgentRunError` it records `outcome=None`, `lines=[]` and yields `error`.
- Settings: `CONVERSATION_ENGINE = os.environ.get('CONVERSATION_ENGINE', 'agents')`. Until Task 3, `stream` maps only `'director'`, so the tests set `settings.CONVERSATION_ENGINE = 'director'`.

- [ ] **Step 1: Write the failing tests**

`test_conversations.py` (director engine, `FunctionModel` answering the existing valid output):

```python
def test_director_stream_events(settings, pair):
    settings.CONVERSATION_ENGINE = 'director'
    events = list(stream(*pair, model=answering(VALID)))
    assert [e['type'] for e in events] == ['thinking', 'thinking', 'line', 'thinking', 'line', 'end']
    assert events[2] == {'type': 'line', 'speaker': 'Gérard', 'text': 'Salut.', 'emotion': 'happy'}
    end = events[-1]
    assert end['conversation_id'] == Conversation.objects.get().id
    assert end['feelings'] == {'Gérard': {'before': 0, 'after': 1}, 'Grillon': {'before': 0, 'after': 1}}

def test_director_failure_records_interrupted_conversation(settings, pair):
    settings.CONVERSATION_ENGINE = 'director'
    events = list(stream(*pair, model=answering({**VALID, 'score_delta': 99})))
    assert events[-1]['type'] == 'error'
    c = Conversation.objects.get()
    assert c.interrupted and c.lines == [] and c.feeling_a_after == c.feeling_a_before
    assert Memory.objects.count() == 0

def test_abandoned_stream_saves_nothing(settings, pair):
    settings.CONVERSATION_ENGINE = 'director'
    events = stream(*pair, model=answering(VALID))
    next(events); events.close()
    assert Conversation.objects.count() == 0

def test_unknown_engine_is_rejected(settings, pair):
    settings.CONVERSATION_ENGINE = 'nope'
    with pytest.raises(ImproperlyConfigured):
        list(stream(*pair, model=answering(VALID)))
```

`test_api.py`: `test_create_conversation` reads `b''.join(response.streaming_content).decode().splitlines()`, parses each line with `json.loads`, asserts `response['Content-Type'] == 'application/x-ndjson'`, the same event types as above and that accents arrive unescaped (`'é' in raw text`). The 400 and 404 tests stay. The LLM failure test now expects status 200 with a last event of `error`. Patch `farm.conversations.build_model`.

- [ ] **Step 2: Run them and see them fail**

Run: `cd backend && uv run pytest farm/tests -q`
Expected: FAIL (no `farm.conversations`).

- [ ] **Step 3: Implement `conversations.py`, `director.run`, and the API**

API: validate as today, then `model = conversations.build_model()` before streaming (an `ImproperlyConfigured` becomes `HttpError(500, str(exc))`), and return `StreamingHttpResponse((json.dumps(e, ensure_ascii=False) + '\n' for e in conversations.stream(a, b, model=model)), content_type='application/x-ndjson')`. Remove `ConversationOut`/`LineOut`.

- [ ] **Step 4: Make `chat` consume the stream**

It prints each `line` event as it arrives (`<speaker>: <text>  (<emotion>)`). On `end`, it loads the `Conversation` and prints memories, feelings, tokens and cost as before. On `error`, it prints the message in the error style.

- [ ] **Step 5: Run the backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "Stream conversations as NDJSON events through a shared conversation layer"
```

---

### Task 3: Character agents engine and fake model support

**Files:**
- Create: `backend/farm/agents.py`
- Modify: `backend/farm/conversations.py` (map `'agents'`), `backend/farm/fake_llm.py`, `backend/.env.example`, `backend/README.md`
- Test: `backend/farm/tests/test_agents.py` (new), `test_fake_llm.py`

**Interfaces:**
- Consumes: Task 1's `common` helpers, `Feeling`, `Memory.latest_for`; Task 2's `record`, `Outcome`, `end_event`, `error_event`.
- Produces in `farm/agents.py`:
  - `MIN_LINES = 4`, `MAX_LINES = 8`
  - `class Turn(BaseModel)`: `text: ShortText`, `emotion: LenientEmotion`, `leave: bool = False`
  - `class Reflection(BaseModel)`: `memory: MemoryNote`, `feeling_delta: int = Field(ge=-2, le=2)`
  - `@dataclass class CharacterContext`: `me: Character`, `partner: Character`, `feeling: int`, `memories: list[Memory]` (snapshot taken at the start of the conversation)
  - `speaker = Agent(output_type=Turn, deps_type=CharacterContext, name='character', retries=1)` and `reflector = Agent(output_type=Reflection, deps_type=CharacterContext, name='reflection', retries=1)`. Each one has `@agent.instructions` built from deps: who I am (name, personality, quirk), the partner's name and personality ("ce que tout le monde voit"), `feeling_label(feeling)`, my memories (with "à propos de X" for gossip), and `TONE_RULES`. The speaker is told one short line per turn and that `leave` means "je m'en vais après cette réplique".
  - `run(a, b, *, model: Model, rng: random.Random | None = None) -> Iterator[dict]`: the first speaker is `rng.choice((a, b))`, then turns alternate. Each turn yields `thinking`, calls `speaker.run_sync(<transcript prompt>, deps=..., model=model)`, adds to `Usage` and yields `line`. It stops when `leave` and `len(lines) >= MIN_LINES`, or at `MAX_LINES`. Then it calls `reflector` for a, then b, records (`engine='agents'`, `delta_a`/`delta_b` from each reflection) and yields `end`. On `AgentRunError` at any point it records `outcome=None` with the lines so far and yields `error`.
- Produces in `farm/fake_llm.py`: `respond` dispatches on `info.output_tools[0].parameters_json_schema['properties']`. If it has `leave`, it answers a Turn (a random soft canned line and emotion, `leave` with probability 0.35). If it has `feeling_delta`, it answers a Reflection (a soft canned memory, delta in -2..+2). Otherwise it answers the director output as today, with the mean lines ("m'a encore vexé") replaced by soft ones and `score_delta` in -2..+2.

- [ ] **Step 1: Write the failing tests in `test_agents.py`**

Use a scripted `FunctionModel` that records each call's messages and answers from queues: a list of Turn args (consumed in order) for calls whose output tool has `leave`, and Reflection args for the others.

```python
def test_turns_alternate_from_the_chosen_first_speaker(pair): ...
    # rng=random.Random(0) or a stub whose choice() returns b; lines' speakers alternate b, a, b, a

def test_leave_is_ignored_before_min_lines_then_honoured(pair):
    events = list(run(*pair, model=scripted(turns=[leave(True)] * 8)))
    assert len([e for e in events if e['type'] == 'line']) == 4

def test_hard_stop_at_max_lines(pair):
    events = list(run(*pair, model=scripted(turns=[leave(False)] * 20)))
    assert len([e for e in events if e['type'] == 'line']) == 8

def test_each_agent_sees_only_its_own_memories(pair):
    a, b = pair
    Memory.remember(a, 'secret de A'); Memory.remember(b, 'secret de B')
    model = scripted(turns=[leave(True)] * 4)
    list(run(a, b, model=model, rng=first_is(a)))
    assert 'secret de A' in model.calls[0] and 'secret de B' not in model.calls[0]
    assert 'secret de B' in model.calls[1] and 'secret de A' not in model.calls[1]

def test_reflections_apply_one_sided_feelings_and_memories(pair):
    # reflections: a +2 with memory 'A retient', b -1 with memory 'B retient'
    # assert Feeling.of(a, b).score == 2, Feeling.of(b, a).score == -1, memories stored, end event feelings match,
    # Conversation.engine == 'agents', tokens > 0

def test_failure_mid_conversation_keeps_lines_without_consequences(pair):
    # the third turn call raises / returns invalid output twice -> last event 'error',
    # Conversation.interrupted, len(lines) == 2, no Memory, feelings unchanged

def test_fake_model_drives_the_agents_engine(pair, monkeypatch):  # in test_fake_llm.py, DELAY_SECONDS=(0,0)
    events = list(run(*pair, model=build_fake_model(random.Random(1))))
    lines = [e for e in events if e['type'] == 'line']
    assert 4 <= len(lines) <= 8 and events[-1]['type'] == 'end'
```

`model.calls[i]` is the text of all message parts (instructions included) of call i. Check `messages[0]` and `info` in the pydantic-ai `FunctionModel` to see where the instructions land, and assert on that.

- [ ] **Step 2: Run them and see them fail**

Run: `cd backend && uv run pytest farm/tests/test_agents.py farm/tests/test_fake_llm.py -q`
Expected: FAIL (no `farm.agents`).

- [ ] **Step 3: Implement `agents.py`, map `'agents'` in `conversations.stream`, and extend the fake model**

- [ ] **Step 4: Run the whole suite and a real terminal chat with the fake**

Run: `cd backend && uv run pytest -q && uv run python manage.py chat`
Expected: all pass. `chat` prints 4 to 8 alternating lines, then both memories and both feeling changes, with model `fake`.

- [ ] **Step 5: Document the setting**

In `.env.example`, add `CONVERSATION_ENGINE=agents` with a comment saying `director` is the alternative. In the README, add one paragraph on the two engines and the NDJSON stream.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "Add character agents that talk turn by turn"
```

---

### Task 4: Choreography helpers in `sim.js`

**Files:**
- Modify: `src/sim.js` (remove `findMeeting`, add the helpers below; keep `pairKey`, `isAdjacent`, `lineDuration`)
- Test: `src/sim.test.js`

**Interfaces:**
- Consumes: existing `tileKey`, `isWalkable`, `pairKey`, `DIRECTIONS` in `sim.js`.
- Produces (all pure; tiles are `{ col, row }`, `blocked` is a `Set` of `tileKey`):
  - `candidatePairs(walkers, { now, inFlight, lastEndedAt, pairCooldownUntil }, { maxConcurrent, globalGapMs }, rng) -> Array<[a, b]>`: every pair of walkers whose `state` is `'idle'` or `'moving'` and whose pair is not on cooldown, shuffled with `rng`. It returns `[]` when a conversation is in flight or the gap hasn't passed.
  - `findPath(map, blocked, from, to) -> Array<tile> | null`: BFS on 4 neighbours. The result excludes `from` and includes `to`. It returns `[]` when `from` equals `to`, and `null` when `to` is unwalkable, blocked or unreachable.
  - `pickMeetingSpot(map, blocked, a, b) -> { a: tile, b: tile } | null`: two adjacent free walkable tiles, the pair closest (Manhattan) to the midpoint of `a` and `b`, such that `findPath(a -> spot.a)` and `findPath(b -> spot.b)` both exist. The caller passes `blocked` without a's and b's own tiles.
  - `pickSplitTargets(map, blocked, a, b, rng) -> { a: tile | null, b: tile | null }`: for each character, a free reachable tile 3 to 5 steps (Manhattan) from its current tile and farther from the partner than it is now. `null` when there is none. The two targets are distinct.

- [ ] **Step 1: Write the failing tests (replace the `findMeeting` block)**

```js
describe('candidatePairs', () => {
  // idle and moving walkers both qualify, talking/approaching/leaving don't
  // [] when inFlight >= maxConcurrent or now - lastEndedAt < globalGapMs
  // a pair on cooldown (either id order) is excluded; others remain
});

describe('findPath', () => {
  it('walks around a block', () => {
    const map = [[0, 1, 0], [0, 0, 0]];
    expect(findPath(map, new Set(), { col: 0, row: 0 }, { col: 2, row: 0 }))
      .toEqual([{ col: 0, row: 1 }, { col: 1, row: 1 }, { col: 2, row: 1 }, { col: 2, row: 0 }]);
  });
  it('returns null when boxed in', () => {
    const map = [[0, 0, 0]];
    expect(findPath(map, new Set([tileKey(1, 0)]), { col: 0, row: 0 }, { col: 2, row: 0 })).toBeNull();
  });
  it('returns [] when already there', () => { /* from === to */ });
});

describe('pickMeetingSpot', () => {
  // open 5x5 map, a at (0,0), b at (4,4): spots are adjacent, free, and near (2,2)
  // returns null when b is boxed in (Review Focus 4)
});

describe('pickSplitTargets', () => {
  // targets distinct, not blocked, 3..5 steps away, each farther from the partner's tile than before
});
```

Use exact BFS neighbour order `[1,0],[-1,0],[0,1],[0,-1]` (same as `DIRECTIONS`) so the expected path above is deterministic. Adjust the expected path if this order gives another shortest path, but keep it a 4-step path that avoids the block.

- [ ] **Step 2: Run them and see them fail**

Run: `npm test`
Expected: FAIL (functions not exported).

- [ ] **Step 3: Implement the four helpers in `src/sim.js`**

- [ ] **Step 4: Run the tests**

Run: `npm test`
Expected: all pass. Keep `findMeeting` and its tests in this task: `main.js` still uses it, and Task 6 removes it.

- [ ] **Step 5: Commit**

```bash
git add src/sim.js src/sim.test.js
git commit -m "Add pathfinding and pairing helpers for choreographed meetings"
```

---

### Task 5: NDJSON reader

**Files:**
- Create: `src/stream.js`
- Test: `src/stream.test.js`

**Interfaces:**
- Produces: `readEvents(response: Response, onEvent: (event) => void) -> Promise<void>`. It reads `response.body` with a `TextDecoder('utf-8')` in streaming mode, splits on `\n`, skips empty lines, `JSON.parse`s each line and calls `onEvent`, and handles a final line without a trailing newline. The promise rejects if the stream errors (for example an abort).

- [ ] **Step 1: Write the failing tests**

```js
const responseOf = (...chunks) => new Response(new ReadableStream({
  start(c) { chunks.forEach((x) => c.enqueue(typeof x === 'string' ? new TextEncoder().encode(x) : x)); c.close(); },
}));

it('emits one event per line across chunk boundaries', async () => {
  const events = [];
  await readEvents(responseOf('{"type":"thin', 'king","speaker":"A"}\n{"type":"end"}'), (e) => events.push(e));
  expect(events).toEqual([{ type: 'thinking', speaker: 'A' }, { type: 'end' }]);
});

it('decodes accents split across chunks', async () => {
  const bytes = new TextEncoder().encode('{"type":"line","text":"Gérard"}\n');
  const cut = bytes.indexOf(0xc3) + 1; // split inside "é"
  const events = [];
  await readEvents(responseOf(bytes.slice(0, cut), bytes.slice(cut)), (e) => events.push(e));
  expect(events[0].text).toBe('Gérard');
});
```

- [ ] **Step 2: Run them and see them fail**

Run: `npm test`
Expected: FAIL (no `src/stream.js`).

- [ ] **Step 3: Implement `readEvents`**

- [ ] **Step 4: Run the tests**

Run: `npm test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/stream.js src/stream.test.js
git commit -m "Add a streaming NDJSON reader"
```

---

### Task 6: Choreographed meetings in the scene

**Files:**
- Modify: `src/main.js`, `src/sim.js` (remove `findMeeting` and its tests)
- Test: manual in the browser (fake model), plus `npm test` and `npx vite build`

**Interfaces:**
- Consumes: Task 4's `candidatePairs`, `findPath`, `pickMeetingSpot`, `pickSplitTargets`; Task 5's `readEvents`; the event shapes above.
- Walker `state`: `'idle' | 'moving' | 'approaching' | 'talking' | 'leaving'`.

- [ ] **Step 1: Replace `checkMeetings`**

Go through `candidatePairs(...)`. For each pair, build `blocked` from `occupied` minus both walkers' tiles (and their move targets) and call `pickMeetingSpot`. Start `meet(a, b, spot)` with the first pair that has a spot. Pairs without a spot are skipped this tick.

- [ ] **Step 2: Implement `meet(a, b, spot)`**

1. Mark both `approaching`, cancel their wander timers (a walker mid-step finishes its tween first), `inFlight++`.
2. Send `fetch('/api/conversations', { method: 'POST', signal })` with an `AbortController` stored on the conversation object, and `readEvents` into a queue.
3. Each walker follows its path one tile at a time, using the existing step tween generalized as `moveTo(walker, tile, onDone)` and reserving tiles as today. If the next tile is taken, it recomputes the path with `findPath`; after 3 failed tries it gives up, which counts as an error (builder's call on the exact retry policy).
4. When both have arrived: face each other, state `talking`, play the queue. `thinking` shows "..." above that speaker. `line` shows the bubble with emoji and reaction for `lineDuration(text)`, and only one line is on screen at a time. `end` shows each character's icon from `feelings[name]`: ❤️ if `after > before`, 😕 if `after < before`, nothing otherwise.
5. On an `error` event, a fetch rejection, a non-OK status or a path failure: "🤷 bof..." above both for 2 s.
6. Finally: `inFlight--`, set `lastEndedAt` and the pair's cooldown, then split. Each walker walks to its `pickSplitTargets` tile (state `leaving`; if it has none, it just goes back to `idle`), then `idle` wandering resumes.
7. Removing a walker (slider) during `approaching` or `talking` aborts the fetch, clears bubbles, and makes the partner split alone. The `finally` must not touch the removed walker.

Update `EMOJI`: replace `angry: '😠'` with `annoyed: '😤'`. Remove `findMeeting` from `sim.js`, its import and its tests.

- [ ] **Step 3: Build and run the unit tests**

Run: `npm test && npx vite build`
Expected: all tests pass, the build succeeds.

- [ ] **Step 4: Manual check in the browser with the fake model**

Start `cd backend && uv run python manage.py runserver` and `npm run dev`, open the page with 10 characters, and check:
- a pair walks toward each other around blocks and meets on adjacent tiles, facing each other
- "..." above the speaker who is thinking, then lines one at a time
- per-character ❤️ / 😕 icons
- the pair splits in roughly opposite directions, then wanders
- the next pair meets about 20 s later
- slider down to 2 while a pair is approaching, and again while talking: no console error, the remaining partner walks off
- stop the backend: "bof..." and the pair splits

The console must only show the favicon 404 and the expected 502 while the backend is down.

- [ ] **Step 5: Commit**

```bash
git add src/main.js src/sim.js src/sim.test.js
git commit -m "Choreograph meetings: walk together, stream the talk, split up"
```
