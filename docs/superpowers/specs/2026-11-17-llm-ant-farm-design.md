# LLM ant farm: design

Date: 2026-11-17

## Intent

A fun toy: a small isometric world where 2 to 10 quirky characters wander around on their own. When two of them meet, they have a short conversation in French, written by an LLM, shown as speech bubbles. Conversations have light consequences: characters remember things about each other and pairs drift toward friendship or feud, so running jokes and grudges build up over a viewing session.

The user is a passive viewer (ant farm style). There is no player character.

## Goals

- Watching it for 20+ minutes stays entertaining: characters refer back to past chats, feuds and friendships emerge.
- Dialogue is funny and strongly in character, in French.
- The LLM provider is swappable by config: Albert API (OpenAI-compatible) or a cloud API (Anthropic, OpenAI, ...).
- Characters are editable without touching code (Django admin).
- The simulation's "inner state" (memories, relationship scores, conversation log) is inspectable in the admin.

## Non-goals

- No player control, no user chatting with characters.
- No always-on server simulation: the world only runs while a browser tab is open. Design the data so moving to always-on later stays possible, but do not build it.
- No auth, no multi-user, no deployment.
- No real 3D: 2.5D isometric sprites in Phaser.
- No sprite art, no TTS, no streaming of tokens.

## Anti-goals (failure even if it technically works)

- Bland, polite, generic dialogue.
- Long dead time on screen while waiting for the LLM with no visual feedback.
- Runaway token cost (constant conversations).
- Characters that forget everything (consequences not visible).

## Constraints

- Existing frontend: Vite + Phaser 4 in this repo (`src/main.js`), already has a 12x12 isometric grid with raised blocks, grid/screen conversion, depth sorting, procedural textures. Build on it.
- Backend: Python, Django, Django Ninja, pydantic-ai, SQLite.
- Albert API: OpenAI-compatible, base URL `https://albert.api.etalab.gouv.fr/v1/`. Known working models: `mistral-medium-2508`, `mistral-medium-3-5`, `openai/gpt-oss-120b`. Default to `mistral-medium-2508`.
- Secrets in a `.env` file, never committed.

## Approaches considered

**Backend framework**

- A. Django + Django Ninja + SQLite. Admin doubles as character editor and simulation inspector; Ninja schemas are Pydantic, matching pydantic-ai output models. More boilerplate. **Picked by the user.**
- B. FastAPI + SQLModel + SQLite. Lighter, natively async, but no admin; characters in a YAML seed file. Rejected: loses the "look inside their heads" tool.

**Dialogue generation** (my call, user did not object)

- One "director" call per conversation: a single agent gets both characters, their memories and the relationship, returns the full exchange as structured lines. One round trip, coherent comedic timing, cheap. **Chosen.**
- One agent per character, taking turns: more authentic voices but ~5x calls and latency, drift and repetition with smaller models. Rejected.

## Design

### Repo layout (my call)

- Frontend stays at the repo root (existing Vite project, `src/`).
- Backend in `backend/` (Django project `backend/config`, app `backend/farm`), managed with `uv`.
- Vite dev server proxies `/api` to Django (`localhost:8000`).
- `.env.example` documents the LLM settings.

### LLM configuration

Three env vars, read in Django settings:

| Var | Example (Albert) | Example (Anthropic) |
|-----|------------------|---------------------|
| `LLM_PROVIDER` | `openai` (OpenAI-compatible) | `anthropic` |
| `LLM_MODEL` | `mistral-medium-2508` | a current Claude Haiku model id |
| `LLM_BASE_URL` | `https://albert.api.etalab.gouv.fr/v1/` | (empty) |
| `LLM_API_KEY` | Albert key | Anthropic key |

One small factory function builds the pydantic-ai model from these. Model settings: temperature ~0.9, max output tokens capped (~800).

### Data model

- **Character**: `name`, `personality` (short blurb, French), `speech_quirk` (tic, catchphrase, obsession), `color` (hex), `accessory` (choice: none, hat, glasses, bow, antenna, mustache, crown), `is_active`.
- **Relationship**: one row per unordered pair (store with `a_id < b_id`, unique together), `score` integer clamped to -10..+10, default 0. Symmetric (my call, simpler; asymmetric "unrequited" feelings are a possible later step).
- **Memory**: `owner` (Character), `about` (Character, nullable, for gossip about a third party), `text` (one short French sentence), `created_at`. Keep the latest 8 per owner; older ones are deleted on insert.
- **Conversation**: `a`, `b`, `lines` (JSON), `score_before`, `score_after`, `created_at`. For the admin log only.

Seed: a data migration or `seed_characters` management command inserting 10 starter characters with distinct, clashing quirks, written in French (e.g. a pigeon convinced it's a secret agent, a melodramatic retired opera singer, a toaster philosopher). Idempotent.

### Director agent

Input (built by the backend): both characters' name, personality and quirk; each one's memories (including memories about the other and about third parties); current relationship score with a plain-language label (ennemis jurés ... meilleurs amis).

Output (pydantic model, structured output):

```
ConversationResult:
  lines: list[Line]        # 4 to 6 items
    Line: speaker ("a" | "b"), text (<= 120 chars, French), emotion (enum: neutral, happy, angry, sad, surprised, smug, scared)
  memory_a: str            # what A will remember from this, one sentence
  memory_b: str            # what B will remember
  gossip_about: optional character name mentioned as a third party (resolved to `about` if it matches an existing character)
  score_delta: int         # -3..+3
```

This merges dialogue and the "reflection" step into one call (my call: halves latency and cost; the earlier conversation described a second call).

System prompt (French) stresses: comedy, strong voice per character, short punchy lines, use memories and the relationship explicitly when relevant, no polite assistant tone, family-friendly.

Failure handling: pydantic-ai output validation with 1 retry; on failure the endpoint returns an error and nothing is persisted.

### API (Django Ninja)

- `GET /api/characters` returns active characters (id, name, color, accessory).
- `POST /api/conversations` with `{a_id, b_id}`: loads context, runs the director agent, persists memories, score, conversation log in one transaction, returns `{lines, score_after}`.
- Async view or sync view calling `agent.run_sync`; left to the builder. Single-user toy, no concurrency concerns beyond the frontend limit below.

### Frontend simulation (Phaser)

- Remove the arrow-key player. Spawn N characters (N from a 2..10 slider overlay, default 5; changing it adds/removes characters live) on random free floor tiles.
- Character sprite: procedural blob in the character's color with eyes and its accessory, drawn like the current player texture.
- Wandering: each idle character picks a random free adjacent tile every 1 to 3 s and tweens there. No pathfinding needed.
- Meeting rule: two idle characters on adjacent tiles, pair not on cooldown (60 s), and fewer than 1 conversation in flight (global max, constant `MAX_CONCURRENT = 1`, easy to raise). Then both stop and face each other.
- While waiting for the backend: a "..." thinking bubble above both, so there is no dead time.
- Playback: lines shown one by one in a bubble above the speaker; duration ~ 1.5 s + 50 ms per character. Emotion shown with a small reaction (bounce for happy, shake for angry, tint, or a tiny emoji in the bubble; builder picks).
- After the chat: a brief floating icon showing the score change (heart for positive, lightning for negative), then both resume wandering.
- On backend error: both shrug ("bof..." bubble), pair goes on cooldown.
- Pure simulation logic (meeting detection, cooldowns, concurrency limit) kept separate from Phaser rendering so it can be unit-tested.

### Testing

- Backend: pytest + pytest-django. Agent tested with pydantic-ai `TestModel` / `FunctionModel`, never a real LLM in tests. Cover: context building, persistence (memory pruning to 8, score clamping, pair ordering), endpoint happy path and failure path (nothing persisted).
- Frontend: vitest on the pure simulation logic.
- Manual check: run both servers, watch a few conversations with Albert.

### Settled after review (my calls)

- Pacing: global minimum gap of 20 s between conversations, on top of the 60 s pair cooldown and 1 in flight. Sim pauses when the tab is hidden. All constants.
- Structured output on Albert is unverified: first real run checks it; fall back to `PromptedOutput` if tool calling is flaky.
- Gossip: a memory may carry `about` = third character; that character does not learn it.
- Slider below cast size: stable order (admin ordering), shrinking removes the same characters each time.
- Persistence across sessions: still open (user's call). Default until decided: persist forever.

### Build order

- v1 (backend only): models, seed command, director agent, and a `chat` management command printing a conversation between two characters in the terminal. Memories and scores persist so consequences can be checked from the terminal.
- v2: Django Ninja API and the Phaser frontend.

## Left to the builder

- Exact French wording of the system prompt and the 10 seed characters (keep them funny and contrasting).
- Sync vs async Django view.
- Visual details: bubble style, emotion reactions, sprite shapes.
- Whether to split `src/main.js` into modules (likely yes, once characters and sim logic are added).
