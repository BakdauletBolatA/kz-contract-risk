# Образ сервиса: API и Streamlit из одного образа, разные команды в compose.
FROM python:3.12-slim

# pango — для PDF-отчёта (WeasyPrint), tesseract rus+kaz — для сканов,
# DejaVu — шрифт с кириллицей и казахскими буквами.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core \
        tesseract-ocr tesseract-ocr-rus tesseract-ocr-kaz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Медленная или нестабильная сеть: pip по умолчанию сдаётся после 5 попыток по 15 с.
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10

# Сначала только зависимости: слой зависит от pyproject.toml и пересобирается,
# когда меняются зависимости, а не код или README. Пакет-заглушка нужен,
# чтобы pip мог разрешить зависимости проекта без исходников.
COPY pyproject.toml ./
RUN mkdir -p src/contract_risk && touch src/contract_risk/__init__.py README.md \
    && pip install --no-cache-dir '.[pdf,ocr,ui]' \
    && pip uninstall -y kz-contract-risk

# Код: правки здесь пересобирают только быстрые слои ниже.
COPY README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps -e .

COPY data ./data
COPY .streamlit ./.streamlit
# ML обучается на dev-срезе при сборке, чтобы первый запрос не ждал обучения.
# Модель лежит в кэше сборки и переобучается, только если устарела: изменился
# dev-срез, версия признаков (MODEL_VERSION) или scikit-learn. Правка
# остального кода её не трогает.
RUN --mount=type=cache,target=/cache/models \
    KZCR_MODELS_DIR=/cache/models kzcr train --if-stale \
    && mkdir -p models && cp /cache/models/clause_risk.joblib models/

EXPOSE 8000 8501
CMD ["uvicorn", "contract_risk.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
