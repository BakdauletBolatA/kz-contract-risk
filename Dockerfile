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
# ML обучается на dev-срезе при сборке: первый запрос не ждёт обучения.
RUN kzcr train

EXPOSE 8000 8501
CMD ["uvicorn", "contract_risk.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
