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
make up      # build and start in the background
make logs    # follow what happens (Ctrl+C to stop following)
make down    # stop (the database is kept)
```

- Game: http://localhost:5173
- Admin: http://localhost:8000/admin (create a login with `make superuser`)

Migrations run on each start. On the first start, when the database has no characters yet, the LLM invents 5 of them (with `LLM_PROVIDER=fake`, they are drawn from canned pieces, for free). The database lives in a Docker volume.

Other commands, all run against the running app (`make help` lists them):

| Command | What it does |
|---|---|
| `make restart` | Rebuild and recreate the containers, e.g. after editing `backend/.env` or the code |
| `make ps` | Show the running containers |
| `make chat` | Make two random characters talk in the terminal; `make chat A="<name>" B="<name>"` picks them |
| `make invent COUNT=3` | Invent new characters with the LLM (default 5) |
| `make usage` | Tokens and cost per engine and model |
| `make reset` | Erase conversations, memories and feelings, keep the characters (asks first) |
| `make migrate` | Apply database migrations |
| `make superuser` | Create a login for the admin |
| `make manage CMD="..."` | Run any other Django command |
| `make shell` | Open a shell in the backend container |
| `make clean` | Stop and erase the Docker database, characters included (asks first) |

Without `make`, the same works with `docker compose`, e.g. `docker compose up --build` and `docker compose exec backend uv run --no-dev python manage.py chat`.

## Run without Docker

Needs [uv](https://docs.astral.sh/uv/) (Python 3.14) and Node.js. In one terminal, the backend:

```sh
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py seed_characters           # the LLM invents 5 characters
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
uv run python manage.py seed_characters            # invent 5 more characters with the LLM
uv run python manage.py reset_farm                 # erase conversations, memories and feelings
uv run python manage.py usage                      # tokens and cost per engine and model
```

## Tests and lint

```sh
cd frontend && npm test             # game (vitest)
cd frontend && npm run lint         # ESLint
cd backend && uv run pytest         # backend, never calls a real LLM
cd backend && uv run ruff check .   # ruff (add --fix for the fixable ones)
```

GitHub Actions (`.github/workflows/ci.yml`) runs all of this on every push to `main` and every pull request, plus the Django checks (`manage.py check`, no missing migration), the game build and the Docker image builds.
