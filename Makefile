.DEFAULT_GOAL := help
.PHONY: help up down logs build restart ps once test-telegram test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the listener in the background
	docker compose up -d --build

down: ## Stop and remove the listener container
	docker compose down

logs: ## Follow the listener logs
	docker compose logs -f

build: ## Build the Docker image
	docker compose build

restart: ## Restart the listener
	docker compose restart

ps: ## Show container status
	docker compose ps

once: ## Run a single poll cycle and exit
	docker compose run --rm yad2-listener --once

test-telegram: ## Send a test message to verify Telegram credentials
	docker compose run --rm yad2-listener --test-telegram

test: ## Run the unit tests locally (no Docker)
	python -m pytest
