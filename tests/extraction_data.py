"""Общие данные тестов извлечения (модуль, а не импорт из test_*.py: tests — не пакет)."""

VALID = {
    "contract_type": "supply",
    "contract_number": "189",
    "contract_date": "2026-12-21",
    "city": "Алматы",
    "parties": [
        {"role": "supplier", "name": "ТОО «А»", "bin": "467792152403"},
        {"role": "buyer", "name": "ТОО «Б»", "bin": None},
    ],
    "term_months": None,
    "auto_renewal": True,
    "price_amount": None,
    "price_period": None,
    "payment_deadline_days": 30,
    "payment_penalty_rate_percent_per_day": 0.1,
    "payment_penalty_cap_percent": None,
    "dispute_forum": "kz_courts",
    "termination_notice_days": 0,
}
