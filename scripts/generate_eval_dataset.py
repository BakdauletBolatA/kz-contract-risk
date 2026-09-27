"""Пересобрать синтетическую часть eval-датасета.

Генерация детерминирована: seed каждого договора — имя шаблона, срез и номер.
Повторный запуск без правки шаблонов даёт побайтно те же файлы, поэтому
датасет в репозитории можно проверить на «не подправлен ли руками» одной
командой: make dataset && git diff --exit-code data/eval.
"""

from pathlib import Path

from contract_risk.evaluation.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {
    "lease_ru": {"dev": 40, "test": 40},
    "supply_ru": {"dev": 40, "test": 40},
    "works_ru": {"dev": 40, "test": 40},
    "lease_kk": {"dev": 15, "test": 15},
}

if __name__ == "__main__":
    summary = generate(ROOT / "data/eval/templates", ROOT / "data/eval", COUNTS)
    for key, n in summary.items():
        print(f"{key}: {n}")
