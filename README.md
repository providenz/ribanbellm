# RibambeLLM

A small LLM "ant farm" in French. Quirky characters wander an isometric village, meet two by two and talk: each character is its own LLM agent, with its own personality, memories and feelings toward the others. Their conversations show up as speech bubbles on the map and in a live chat on the right, with the token consumption at the bottom.

- `frontend/`: the game (Phaser 4 + Vite). It handles walking and meetings, and plays the conversations it receives.
- `backend/`: the characters and their conversations (Django, Django Ninja, pydantic-ai, SQLite). See [backend/README.md](backend/README.md) for the details.

## Configure the LLM

```sh
cp backend/.env.example backend/.env
```

Then either set `LLM_API_KEY` (and the provider and model) in `backend/.env`, or set `LLM_PROVIDER=fake` to develop for free with canned dialogue. `backend/.env` is git-ignored.

## Run with Docker

```sh
docker compose up --build
```

- Game: http://localhost:5173
- Admin: http://localhost:8000/admin (create a login with `docker compose exec backend uv run --no-dev python manage.py createsuperuser`)

Migrations and the starter characters are set up on each start. The database lives in a Docker volume; `docker compose down -v` erases it.

## Run without Docker

Needs [uv](https://docs.astral.sh/uv/) (Python 3.14) and Node.js. In one terminal, the backend:

```sh
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py seed_characters
uv run python manage.py runserver        # http://localhost:8000
```

In another terminal, from the repository root, the game:

```sh
cd frontend
npm install
npm run dev                              # http://localhost:5173, forwards /api to the backend
```

## Useful commands

From `backend/`:

```sh
uv run python manage.py chat                       # make two characters talk in the terminal
uv run python manage.py seed_characters --llm      # invent 5 new characters with the LLM
uv run python manage.py reset_farm                 # erase conversations, memories and feelings
uv run python manage.py usage                      # tokens and cost per engine and model
```

## Tests

```sh
cd frontend && npm test     # game (vitest)
cd backend && uv run pytest  # backend, never calls a real LLM
```
