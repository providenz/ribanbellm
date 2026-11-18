# Docker shortcuts for RibambeLLM. Run `make` or `make help` to list them.

COMPOSE = docker compose
MANAGE = $(COMPOSE) exec backend uv run --no-dev python manage.py
COUNT ?= 5

.DEFAULT_GOAL := help
.PHONY: help up down restart logs ps shell manage migrate seed invent chat reset usage superuser clean

help: ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-10s %s\n", $$1, $$2}'

up: ## Build and start the app in the background (game :5173, admin :8000/admin)
	$(COMPOSE) up --build -d
	@echo "Game: http://localhost:5173   Admin: http://localhost:8000/admin"

down: ## Stop the app (the database is kept)
	$(COMPOSE) down

restart: ## Recreate the containers, e.g. after editing backend/.env
	$(COMPOSE) up --build -d --force-recreate

logs: ## Follow the logs of both services (Ctrl+C to stop)
	$(COMPOSE) logs -f

ps: ## Show the running containers
	$(COMPOSE) ps

shell: ## Open a shell in the backend container
	$(COMPOSE) exec backend sh

manage: ## Run any Django command: make manage CMD="showmigrations"
	$(MANAGE) $(CMD)

migrate: ## Apply database migrations (also done on each start)
	$(MANAGE) migrate

seed: ## Create or update the starter characters (also done on each start)
	$(MANAGE) seed_characters

invent: ## Invent new characters with the LLM: make invent COUNT=3 (default 5)
	$(MANAGE) seed_characters --llm --count $(COUNT)

chat: ## Make two characters talk in the terminal: make chat A="Grillon" B="Zigzag" (random pair without A and B)
	$(MANAGE) chat $(if $(A),"$(A)" "$(B)")

reset: ## Erase conversations, memories and feelings, keep the characters (asks first)
	$(MANAGE) reset_farm

usage: ## Tokens and cost per engine and model
	$(MANAGE) usage

superuser: ## Create a login for the admin
	$(MANAGE) createsuperuser

clean: ## Stop the app and ERASE the Docker database (asks first)
	@printf "Erase the Docker database (characters included)? [y/N] " && read answer && [ "$$answer" = y ]
	$(COMPOSE) down -v
