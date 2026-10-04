# Короткие команды поверх CLI kzcr и docker compose.
# Makefile ничего не решает сам — он только избавляет от печатания.

.DEFAULT_GOAL := help
VENV := .venv
PY   := $(VENV)/bin/python
KZCR := $(VENV)/bin/kzcr

# Проект требует Python >= 3.12; системный python3 бывает старее, и тогда pip
# падает сообщением резолвера, из которого причина не читается.
PYTHON ?=
PYTHON_CANDIDATES := $(if $(PYTHON),$(PYTHON),python3.12 python3.13 python3)

.PHONY: help
help: ## показать список команд
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- окружение ---------------------------------------------------------------

.PHONY: venv
venv: ## создать venv и поставить проект в режиме разработки
	@found=""; \
	for p in $(PYTHON_CANDIDATES); do \
		command -v "$$p" >/dev/null 2>&1 || continue; \
		"$$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
			2>/dev/null || continue; \
		found="$$p"; break; \
	done; \
	if [ -z "$$found" ]; then \
		echo "Нужен Python >= 3.12. Укажите свой: make venv PYTHON=/путь/к/python3.12" >&2; \
		exit 1; \
	fi; \
	echo "venv на $$("$$found" -V)"; \
	"$$found" -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e '.[dev,ui,pdf]'

# --- проверки ----------------------------------------------------------------

.PHONY: test
test: ## тесты (pgvector-тесты пропустятся без KZCR_TEST_DSN)
	$(PY) -m pytest -q

.PHONY: lint
lint: ## ruff
	$(VENV)/bin/ruff check src/ scripts/ tests/
	$(VENV)/bin/ruff format --check src/ scripts/ tests/

.PHONY: format
format: ## отформатировать код
	$(VENV)/bin/ruff format src/ scripts/ tests/
	$(VENV)/bin/ruff check src/ scripts/ tests/ --fix

.PHONY: check
check: lint test ## линтер плюс тесты

# --- данные ------------------------------------------------------------------

.PHONY: dataset
dataset: ## пересобрать синтетический eval-датасет (детерминированно, seed в скрипте)
	$(PY) scripts/generate_eval_dataset.py

.PHONY: dataset-check
dataset-check: ## целостность датасета: разметка ссылается на существующие пункты
	$(KZCR) dataset check

.PHONY: corpus-audit
corpus-audit: ## лицензии источников и баланс сторон в эталонном корпусе
	$(KZCR) corpus audit

.PHONY: corpus-load
corpus-load: ## загрузить эталонный корпус в pgvector (нужен KZCR_DATABASE_URL)
	$(KZCR) corpus load

# --- оценка ------------------------------------------------------------------

.PHONY: eval
eval: ## прогнать eval: make eval DETECTOR=hybrid SPLIT=test
	$(KZCR) eval run --detector $(or $(DETECTOR),hybrid) --split $(or $(SPLIT),test)

.PHONY: eval-all
eval-all: ## все офлайн-детекторы на dev и test — строки для EVALUATION.md
	for d in null rules ml hybrid; do \
		for s in dev test handwritten stress; do \
			$(KZCR) eval run --detector $$d --split $$s || exit 1; \
		done; \
	done

.PHONY: extract-gold
extract-gold: ## пересобрать эталон извлечения из черновика и ручных правок
	$(PY) scripts/build_gold.py

.PHONY: extract-eval
extract-eval: ## оценка извлечения: make extract-eval MODEL=ollama:qwen2.5:7b SPLIT=dev
	$(KZCR) extract eval --model $(MODEL) --split $(or $(SPLIT),dev)

.PHONY: extract-table
extract-table: ## сводная таблица прогонов извлечения (для README)
	$(KZCR) extract table --fields test | tee evals/extraction/SUMMARY.md

.PHONY: train
train: ## обучить ML-классификаторы на dev-срезе
	$(KZCR) train

# --- сервисы -----------------------------------------------------------------

.PHONY: db
db: ## поднять только pgvector
	docker compose up -d db

.PHONY: api
api: ## FastAPI на :8000
	$(VENV)/bin/uvicorn contract_risk.api.main:app --reload --port 8000

.PHONY: ui
ui: ## Streamlit на :8501 (в API ходит, если задан KZCR_API_URL)
	$(VENV)/bin/streamlit run src/contract_risk/ui/app.py

.PHONY: up
up: ## весь стек в Docker: pgvector, API :8000, интерфейс :8501
	docker compose up -d --build

.PHONY: down
down: ## остановить контейнеры
	docker compose down
