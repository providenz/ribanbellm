# Backend

Django app holding the characters, their memories and relationships, and the LLM "director" that writes their conversations.

## Setup

```sh
cd backend
cp .env.example .env        # then set LLM_API_KEY
uv sync
uv run python manage.py migrate
uv run python manage.py seed_characters
```

To develop without spending tokens, set `LLM_PROVIDER=fake` in `.env`: a stand-in model returns random canned French dialogue after a short delay (0.8 to 2.5 s), with no API key needed. Memories and feelings are still updated as with a real model, with either engine.

## How conversations are written

Two engines, chosen with `CONVERSATION_ENGINE` in `.env`:

- `agents` (default): each character is its own agent. It only knows its own personality, memories and feeling toward the other, speaks in turns (4 to 8 lines, it decides when to leave), then reflects on what it remembers and how its feeling changed. Feelings are one-sided.
- `director`: one call writes the whole scene for both characters.

`POST /api/conversations` streams the conversation as NDJSON events (`thinking`, `line`, then `end` or `error`), so the frontend can show each line as soon as it is written.

## Make two characters talk

```sh
uv run python manage.py chat                      # random pair
uv run python manage.py chat "Gérard" "Grillon"   # chosen pair
```

Each conversation updates both characters' memories and each one's feeling toward the other, so running the same pair again continues the story.

## HTTP API

`uv run python manage.py runserver` serves the API at `/api` (interactive docs at `/api/docs`). The Vite dev server proxies `/api` to it.

- `GET /api/characters`: active characters (`id`, `name`, `color`, `accessory`).
- `POST /api/conversations` with `{"a_id": 1, "b_id": 2}`: runs a conversation and streams NDJSON events, one JSON object per line: `{"type": "thinking", "speaker"}` and `{"type": "line", "speaker", "text", "emotion"}` pairs, then `{"type": "end", "conversation_id", "feelings": {name: {before, after}}}` or `{"type": "error", "message"}` (the lines said so far are saved, marked interrupted, with no memory or feeling change). 400 if both ids are the same, 404 if a character is unknown or inactive, 500 if the LLM is not configured.

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
