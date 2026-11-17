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

## Make two characters talk

```sh
uv run python manage.py chat                      # random pair
uv run python manage.py chat "Gérard" "Grillon"   # chosen pair
```

Each conversation updates both characters' memories and their relationship score, so running the same pair again continues the story.

## HTTP API

`uv run python manage.py runserver` serves the API at `/api` (interactive docs at `/api/docs`). The Vite dev server proxies `/api` to it.

- `GET /api/characters`: active characters (`id`, `name`, `color`, `accessory`).
- `POST /api/conversations` with `{"a_id": 1, "b_id": 2}`: runs a conversation and returns `{id, lines, score_before, score_after}`. 400 if both ids are the same, 404 if a character is unknown or inactive, 502 if the LLM call fails (nothing is saved).

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
