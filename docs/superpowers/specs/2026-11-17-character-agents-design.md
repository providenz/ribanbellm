# Character agents and choreographed meetings: design

Date: 2026-11-17. Builds on `2026-11-17-llm-ant-farm-design.md` (v1 backend, HTTP API, wandering, step 3 bubbles).

## Intent

Make the characters feel like they have a will of their own. Two changes:

1. **Talking belongs to each character.** Instead of one "director" call writing the whole scene, each character is its own LLM agent: it only knows its own personality, its own memories and its own feeling toward the other, and it decides, turn by turn, what to say, with which emotion, whether to bring up a rumour, and when to leave.
2. **Meetings are choreographed in the browser.** Instead of relying on two characters happening to stand side by side, the browser picks a pair, the two walk toward each other, talk, then split up and walk away. Then another pair meets, and so on. Walking stays in the browser, with no LLM.

## Goals

- Each character has a distinct voice and private knowledge: misunderstandings, secrets and gossip that one side does not know become possible.
- Feelings are one-sided: A can be fond of B while B is lukewarm about A.
- Conversations vary in length because the characters decide when to leave.
- Lines appear on screen as soon as each agent has written them, with almost no dead time.
- The whole thing runs for free in development with the fake model.

## Non-goals

- No LLM-driven movement or LLM choice of whom to meet. Pairing is random.
- No more than one conversation at a time (same pacing constants as before).
- No token-level streaming: the unit sent to the browser is a whole line.
- Persistence across sessions stays as it is (the world persists until reset; still an open question from the first design).

## Anti-goals

- **Nothing nasty.** No hate, insults, contempt or "can't stand you". Characters are odd, teasing and sometimes a bit vexed, always in a playful way. This applies to prompts, relationship labels, the fake model's canned lines and on-screen icons.
- Long "..." waits between lines.
- Runaway cost: calls per conversation are bounded (see Limits).

## Constraints

- Existing stack: Django 6 + Django Ninja + pydantic-ai + SQLite in `backend/`, Phaser 4 + Vite in `src/`, Vite proxies `/api` to Django.
- LLM provider stays switchable by `.env` (`fake`, `anthropic`, `openai`/Albert).
- The world only runs while a tab watches it; Phaser freezes timers and tweens when the tab is hidden.

## Approaches considered

**Who decides what** (user's decision)

- Characters choose everything with the LLM, including where to walk: rejected, an LLM call per movement decision is far too many calls.
- **Walking and pairing in the browser, talking by per-character agents on the backend: picked by the user.**

**How pairs are chosen** (user's decision)

- **Random among available characters, avoiding pairs on cooldown: picked.**
- Driven by feelings (friends seek each other): rejected by the user.

**Tone of feelings** (user's decision)

- Only positive (score can only go up): rejected, everyone would end up best friends.
- **Gentle ups and downs: picked.** The score can go down, but wording stays soft ("un peu froid", "vexé pour rire", "pas sur la même longueur d'onde"). A drop shows as 😕, never ⚡.

**How lines reach the browser** (user's decision)

- One request returning all lines at the end: API unchanged, but a long "..." wait (one LLM call per line plus wrap-up).
- One request per line (`POST /conversations/{id}/turn`): live lines, but conversation state in the database between requests and abandoned conversations to clean up.
- **One request that streams events as newline-delimited JSON: picked.** One backend loop owns the conversation; each line is sent the moment its agent has written it.

## Design

### Backend: character agents

One pydantic-ai `Agent` definition for "a character speaking", with per-character dynamic instructions built from deps (my call: one Agent object with character-specific instructions, rather than one Agent object per character; conceptually each character is still its own agent with its own context).

A character agent's context on each turn:

- Its instructions: who it is (name, personality, speech quirk), tone rules (French, short, funny, in character, never hateful or insulting, disagreements stay playful), and the soft label of its own feeling toward the partner.
- Its own latest memories (`Memory.latest_for`, up to 8, including gossip "about" third characters), and nothing from the partner's memories.
- The partner's name and public look only (name, personality blurb, so it can react to who they are; my call: the personality is treated as "what everyone can see about them").
- The transcript so far.

Turn output (structured):

```
Turn:
  text: str (max 200, aim under 120 characters)
  emotion: neutral | happy | annoyed | sad | surprised | smug | scared
  leave: bool   # "I'm done, I'm leaving after this line"
```

`angry` is replaced by `annoyed` (playful annoyance), in line with the tone anti-goal.

Wrap-up output, one call per character after the last line, with the full transcript:

```
Reflection:
  memory: MemoryNote (text, about: optional third character's name)  # same as today
  feeling_delta: int in -2..+2
```

### Backend: the conversation loop

`run_conversation(a, b)` becomes a generator of events:

1. Who speaks first: random between `a` and `b` (my call).
2. Turns alternate. Before each agent call, yield `thinking` for the speaker; after it, yield `line`.
3. The conversation ends when a speaker sets `leave` and at least `MIN_LINES` lines exist, or at `MAX_LINES`. A `leave` before `MIN_LINES` is ignored.
4. Wrap-up: one Reflection call per character (sequential), then in one transaction: apply each feeling delta to that character's own feeling, store both memories (same `_resolve_about` rule as today), and save the `Conversation`.
5. Yield `end` with both feelings before and after.

On an LLM error in the middle: yield `error`, save the `Conversation` with the lines said so far and `interrupted=True`, and apply no memory or feeling changes (my call: an interrupted chat leaves no consequences).

If the client disconnects (tab closed, slider abort), Django stops consuming the generator at its next write, and nothing is saved. This is best effort, not a guarantee (my call): an LLM call already running still finishes, and a disconnect during the wrap-up may still commit the memories and feelings. Tests only cover "abandoned before wrap-up saves nothing".

### Limits (constants)

- `MIN_LINES = 4`, `MAX_LINES = 8`.
- Calls per conversation: normally at most 8 turns + 2 reflections = 10. Agents keep `retries=1` for genuinely malformed output, so the worst case is 20 (my call). To keep retries rare, the schemas are lenient: over-long text is trimmed instead of rejected, and an unknown emotion becomes `neutral`.

### Data model changes

- Replace `Relationship` (symmetric pair) with `Feeling(owner, toward, score)`: one row per direction, unique on `(owner, toward)`, score clamped to -10..+10, `Feeling.of(owner, toward)` get-or-creates.
- Migration: each existing `Relationship` score is copied into both directions, then `Relationship` is dropped (my call; dev data only).
- Soft labels for a feeling (used in the agent prompt), from low to high: "pas vraiment sur la même longueur d'onde", "un peu froid", "connaissance", "bon copain", "meilleur ami". The exact cut points are left to the builder.
- `Conversation`: replace `score_before`/`score_after` with `feeling_a_before`, `feeling_a_after`, `feeling_b_before`, `feeling_b_after` (a's feeling toward b, and b's toward a); add `interrupted` (bool) and `engine` (`agents` or `director`). Tokens and cost become the sums over every LLM call of the conversation; cost stays `None` if any call has no known price.
- Admin: `Feeling` list with editable score, filterable by owner; `Conversation` shows the new fields.

### Director engine kept behind a setting

`CONVERSATION_ENGINE = agents | director` in settings/.env, default `agents` (my call: kept so the two engines can be compared on real runs, then the loser removed). The director is adapted to the new world: its prompt receives both one-sided feelings, its tone rules get the same "nothing nasty" constraint, its single `score_delta` (-2..+2) is applied to both feelings, and it emits its lines through the same event stream (all lines at once after its single call, each preceded by `thinking` for that speaker so the frontend code path is the same).

### Fake model

`LLM_PROVIDER=fake` keeps working for both engines. For agents it answers Turn and Reflection outputs (it can tell them apart by the output tool's name or schema), with a short random delay per call (0.8 to 2.5 s), and sets `leave` with some probability once `MIN_LINES` is reached. The canned lines that are mean ("m'a encore vexé") are replaced by soft ones.

### API

`POST /api/conversations` with `{a_id, b_id}` returns `application/x-ndjson`, one JSON object per line:

```
{"type": "thinking", "speaker": "Grillon"}
{"type": "line", "speaker": "Grillon", "text": "...", "emotion": "happy"}
... more thinking/line pairs ...
{"type": "end", "conversation_id": 12,
 "feelings": {"Grillon": {"before": 2, "after": 3}, "Gérard": {"before": 0, "after": -1}}}
```

or, on failure mid-way, `{"type": "error", "message": "..."}` as the last event.

Validation errors before the stream starts (same id twice, unknown or inactive character, missing API key) stay plain HTTP errors (400, 404, 500/502) as today.

### `chat` and `usage` commands

- `chat` consumes the same event stream and prints lines as they arrive, then each character's memory and its feeling "before -> after", tokens and cost.
- `usage` keeps working on the summed tokens and cost, grouped by model, and also by engine.

### Frontend: choreography

Walker states: `idle`, `moving`, `approaching`, `talking`, `leaving`.

1. **Pairing.** Every check (250 ms, frozen when the tab is hidden), if no conversation is in flight and the global gap has passed, pick a random pair among `idle`/`moving` walkers whose pair is not on cooldown and who can reach each other (pathfinding below). Same constants as step 3: 1 in flight, 20 s global gap, 60 s pair cooldown.
2. **Request early.** Send `POST /api/conversations` as soon as the pair is chosen, so the first line is being written while they walk.
3. **Approach.** Pick a meeting spot: two adjacent free floor tiles, roughly halfway between them. Each walks there along a shortest path (BFS on the 4-neighbour grid around blocks and other characters' reserved tiles). Then they face each other.
4. **Talk.** Events are queued as they arrive. A `thinking` event shows "..." above that speaker. A `line` event shows the bubble with the emoji and the bounce/shake reaction, for `1.5 s + 50 ms per character`. Playback waits for both characters to have arrived and never shows two lines at once; lines that arrive early wait in the queue.
5. **End.** On `end`, each character shows its own icon according to its own feeling change: ❤️ if it went up, 😕 if it went down, nothing if unchanged.
6. **Split.** Each walks to a random free tile a few tiles away, roughly in opposite directions, then goes back to `idle` wandering. The pair goes on cooldown.
7. **Errors.** On an `error` event, a failed request or a broken stream: both show "🤷 bof...", then split; the pair goes on cooldown.
8. **Slider.** If a talking or approaching character is removed, the request is aborted (`AbortController`) and the partner splits off alone.

Pure logic in `sim.js` with vitest tests: `pickPair`, BFS `findPath`, `pickMeetingSpot`, `pickSplitTargets`, and the existing helpers. The step 3 "meet when adjacent by chance" rule (`findMeeting`) is replaced.

Emotion → emoji: `annoyed` → 😤 (replaces 😠 for `angry`); the others stay as in step 3.

### Testing

- Backend (pytest, FunctionModel fakes per call): turn alternation and first speaker; `leave` honoured only from `MIN_LINES`; hard stop at `MAX_LINES`; each agent's prompt contains its own memories and not the partner's; reflection applies one-sided feelings and memories; interrupted conversation saves lines without consequences; the NDJSON endpoint emits the expected event sequence; the director engine emits the same event shapes; migration of `Relationship` to `Feeling`.
- Frontend (vitest): BFS around blocks and occupied tiles, unreachable pairs skipped, meeting spot adjacency, pair cooldown and gap.
- Manual check in the browser with the fake model: approach, live lines, icons, split, error path, slider removal mid-conversation.

## Left to the builder

- Exact prompts (French) for the character agent and the reflection, within the tone rules above.
- Cut points of the soft feeling labels.
- How far apart "a few tiles away" is for the split, and how the meeting spot is chosen when the exact midpoint is blocked.
- Visual details of the "..." and icons.
