# RibambeLLM backend

Django app holding the characters, their memories and feelings, and the LLM agents that speak for them.

## Setup

```sh
cd backend
cp .env.example .env        # then set LLM_API_KEY
uv sync
uv run python manage.py migrate
uv run python manage.py seed_characters
```

### Or run everything with Docker

From the repository root (`backend/.env` is read if present, never copied into the image):

```sh
docker compose up --build   # game on http://localhost:5173, admin on http://localhost:8000/admin
docker compose exec backend uv run --no-dev python manage.py createsuperuser
docker compose exec backend uv run --no-dev python manage.py chat
```

Migrations and `seed_characters` run on each start. The database lives in the `db` volume (`docker compose down -v` resets it). Code changes need `docker compose up --build`.

To develop without spending tokens, set `LLM_PROVIDER=fake` in `.env`: a stand-in model returns random canned French dialogue after a short delay (0.8 to 2.5 s), with no API key needed. Memories and feelings are still updated as with a real model.

## How conversations are written

Each character is its own agent. It only knows its own personality, memories and feeling toward the other, speaks in turns (4 to 8 lines: they greet each other, talk about a dreamy topic of the day, and whoever decides to leave says goodbye, answered by a goodbye), then reflects on what it remembers and how its feeling changed. Feelings are one-sided.

Older conversations may be marked `director` in the admin and in `usage`: they come from an earlier mode, since removed, where one call wrote the whole scene.

`POST /api/conversations` streams the conversation as NDJSON events (`thinking`, `line`, then `end` or `error`), so the frontend can show each line as soon as it is written.

## Invent new characters

```sh
uv run python manage.py seed_characters --llm             # 5 new characters invented by the LLM
uv run python manage.py seed_characters --llm --count 3   # 1 to 10
```

They are added next to the existing ones (names already taken are skipped). Without `--llm`, `seed_characters` creates or updates the fixed starter cast. With `LLM_PROVIDER=fake`, the names and personalities are drawn from canned pieces.

## Make two characters talk

```sh
uv run python manage.py chat                      # random pair
uv run python manage.py chat "Gérard" "Grillon"   # chosen pair
```

Each conversation updates both characters' memories and each one's feeling toward the other, so running the same pair again continues the story.

To start the story over (characters are kept):

```sh
uv run python manage.py reset_farm         # asks for confirmation; --yes to skip
```

## HTTP API

`uv run python manage.py runserver` serves the API at `/api` (interactive docs at `/api/docs`). The Vite dev server proxies `/api` to it.

- `GET /api/characters`: active characters (`id`, `name`, `color`, `accessory`).
- `POST /api/conversations` with `{"a_id": 1, "b_id": 2}`: runs a conversation and streams NDJSON events, one JSON object per line: `{"type": "thinking", "speaker"}` and `{"type": "line", "speaker", "text", "emotion"}` pairs, then `{"type": "end", "conversation_id", "feelings": {name: {before, after}}, "usage"}` or `{"type": "error", "message", "usage"}`, where `usage` is `{input_tokens, output_tokens, cost_usd}` (`cost_usd` null when the model has no known price) (on error, the lines said so far are saved, marked interrupted, with no memory or feeling change). 400 if both ids are the same, 404 if a character is unknown or inactive, 500 if the LLM is not configured.
- `GET /api/usage`: totals over every stored conversation: `conversations`, `input_tokens`, `output_tokens`, `cost_usd` (sum of the known costs, null if none is known) and `unpriced` (conversations with no known price). The game shows it at the bottom of the sidebar, next to what the open page has used.

## Token consumption and cost

Each conversation stores its model, input/output tokens and USD cost (computed with `genai-prices`; empty when the model has no known price, e.g. on Albert). `chat` prints them after each conversation, and:

```sh
uv run python manage.py usage   # totals per model
```

## Inspect the simulation

```sh
uv run python manage.py createsuperuser
uv run python manage.py runserver   # http://localhost:8000/admin
```

## Tests

```sh
uv run pytest
```

Tests never call a real LLM (pydantic-ai `FunctionModel`).
