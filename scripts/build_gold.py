"""Собирает эталон извлечения: черновик `draft_gold.py` + ручные правки.

Черновик (регулярки) закрывает номер, дату, город, стороны и БИН — то, что
в шаблонах стоит на предсказуемых местах. Условия (срок, пеня, подсудность,
уведомление) проверены по тексту каждого договора, правки записаны ниже.
Правила разметки — docs/LABELING_EXTRACTION.md.

    python scripts/build_gold.py   # пишет data/extraction_gold/{dev,test,hard}.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import draft_gold  # noqa: E402

from contract_risk.extraction.schema import ContractExtraction  # noqa: E402

OUT = ROOT / "data/extraction_gold"
KZ, CP, FA = "kz_courts", "counterparty_location_court", "foreign_arbitration"


def f(term=None, renew=False, deadline=None, pen=None, cap=None, forum=KZ, notice=None, **extra):
    d = {
        "term_months": term,
        "auto_renewal": renew,
        "payment_deadline_days": deadline,
        "payment_penalty_rate_percent_per_day": pen,
        "payment_penalty_cap_percent": cap,
        "dispute_forum": forum,
        "termination_notice_days": notice,
    }
    d.update(extra)
    return d


# --- условия по документам; None-значения здесь значимы (в тексте нет) ---------
OVERRIDES: dict[str, dict] = {}
for n, notice in {"001": 30, "002": 0, "003": 30, "006": 0, "007": 0, "011": 30}.items():
    OVERRIDES[f"lease_kk_dev_{n}"] = f(11, renew=(n == "007"), pen=0.1, cap=10, notice=notice)
OVERRIDES["lease_ru_dev_003"] = f(11, pen=0.1, cap=10, forum=FA, notice=30)
# остальные dev-договоры: условия из черновика проверены по тексту и приняты как есть

for n, (notice, pen, cap, forum) in {
    "001": (None, 0.05, 10, FA),
    "002": (30, 0.05, 10, KZ),
    "003": (30, 1.0, None, KZ),
    "006": (None, 0.05, 10, KZ),
    "007": (None, 0.05, 10, KZ),
    "011": (30, 0.05, 10, KZ),
}.items():
    OVERRIDES[f"lease_kk_test_{n}"] = f(
        11, pen=pen, cap=cap, forum=forum, notice=notice, price_period="monthly"
    )
for n, (renew, pen, cap, notice) in {
    "003": (True, 0.05, 10, 30),
    "004": (False, 0.05, 10, 30),
    "006": (False, 0.5, None, 30),
    "007": (False, 0.05, 10, 14),
    "014": (False, 0.05, 10, 30),
    "024": (False, 0.05, 10, 14),
    "033": (False, 0.05, 10, 30),
    "035": (True, 0.4, None, 30),
}.items():
    OVERRIDES[f"lease_ru_test_{n}"] = f(11, renew=renew, pen=pen, cap=cap, notice=notice)
for n, (renew, dl, pen, cap, forum, notice) in {
    "004": (False, 20, 0.05, 10, KZ, 30),
    "005": (False, None, 0.05, 10, KZ, 30),
    "006": (False, 75, None, None, KZ, 30),
    "008": (True, 20, None, None, KZ, 5),
    "016": (False, 20, None, None, FA, 30),
    "027": (False, 20, None, None, CP, 5),
    "028": (False, 120, 0.05, 10, KZ, 30),
    "040": (False, 20, 0.05, 10, CP, 30),
}.items():
    OVERRIDES[f"supply_ru_test_{n}"] = f(
        renew=renew, deadline=dl, pen=pen, cap=cap, forum=forum, notice=notice
    )
for n, (dl, pen, cap, forum, notice) in {
    "003": (150, 0.1, None, KZ, 7),
    "004": (20, None, None, CP, 30),
    "015": (20, 0.05, 10, KZ, 30),
    "026": (20, 0.1, None, KZ, 7),
    "037": (20, None, None, KZ, 30),
    "038": (20, 0.05, 10, KZ, 30),
    "039": (20, None, None, KZ, 30),
    "040": (20, 0.05, 10, KZ, 30),
}.items():
    OVERRIDES[f"works_ru_test_{n}"] = f(deadline=dl, pen=pen, cap=cap, forum=forum, notice=notice)


def P(role, name, bin_):
    return {"role": role, "name": name, "bin": bin_}


def full(number, date, city, parties, contract_type, price=None, period=None, **cond):
    return {
        "contract_type": contract_type,
        "contract_number": number,
        "contract_date": date,
        "city": city,
        "parties": parties,
        "price_amount": price,
        "price_period": period,
        **f(**cond),
    }


# рукописный и стресс-срезы: разметка целиком вручную
HARD: dict[str, dict] = {
    "hw_lease_01": full(
        "БЦ-17/26",
        "2026-02-10",
        "Астана",
        [
            P("landlord", "ТОО «Есиль Бизнес Центр»", "000000000017"),
            P("tenant", "ИП Калиев Д.С.", "000000000026"),
        ],
        "lease",
        renew=True,
        pen=0.5,
        forum=CP,
    ),
    "hw_lease_kk_01": full(
        "8",
        "2026-04-20",
        "Шымкент",
        [
            P("landlord", "«Оңтүстік Сауда Үйі» ЖШС", "000000000071"),
            P("tenant", "«Әлем Тігін» ЖК", "000000000080"),
        ],
        "lease",
        280000,
        "monthly",
        term=11,
        renew=True,
        pen=1.0,
    ),
    "hw_supply_01": full(
        "45-П",
        "2026-03-03",
        "Караганда",
        [
            P("supplier", "ТОО «Сары-Арка Продукт»", "000000000035"),
            P("buyer", "ИП «Мадина»", "000000000044"),
        ],
        "supply",
        pen=0.3,
    ),
    "hw_supply_02": full(
        "2026/118",
        "2026-05-05",
        "Усть-Каменогорск",
        [
            P("supplier", "ТОО «Восток Металл»", "000000000099"),
            P("buyer", "ТОО «СтройМаркет»", "000000000108"),
        ],
        "supply",
        deadline=100,
        forum=CP,
        notice=0,
    ),
    "hw_works_02_clean": full(
        "31",
        "2026-06-02",
        "Актобе",
        [
            P("customer", "ТОО «Ақтөбе Логистика»", "000000000117"),
            P("contractor", "ТОО «Батыс Құрылыс»", "000000000126"),
        ],
        "works",
        6400000,
        "total",
        deadline=15,
        pen=0.1,
        cap=10,
        notice=30,
    ),
    "st_lease_01": full(
        "14-ТЦ",
        "2026-10-01",
        "Алматы",
        [
            P("landlord", "ТОО «Мега Плаза»", "000000000135"),
            P("tenant", "ИП Жаксылыкова А.Н.", "000000000144"),
        ],
        "lease",
        540000,
        "monthly",
        term=11,
        renew=True,
        notice=5,
    ),
    "st_lease_02_clean": full(
        "40",
        "2026-11-02",
        "Павлодар",
        [
            P("landlord", "ТОО «Иртыш Недвижимость»", "000000000235"),
            P("tenant", "ТОО «Пекарня Нан»", "000000000244"),
        ],
        "lease",
        700000,
        "monthly",
        term=11,
        pen=0.1,
        cap=10,
        forum=CP,
        notice=30,
    ),
    "st_lease_kk_01": full(
        "3",
        "2026-10-05",
        "Ақтөбе",
        [
            P("landlord", "«Ақтөбе Сауда» ЖШС", "000000000199"),
            P("tenant", "«Нұр Сұлу» ЖК", "000000000208"),
        ],
        "lease",
        300000,
        "monthly",
        renew=True,
        pen=0.5,
    ),
    "st_supply_01": full(
        "77/С",
        "2026-10-12",
        "Шымкент",
        [
            P("supplier", "ТОО «Юг Опт Трейд»", "000000000153"),
            P("buyer", "ТОО «Магазин у дома»", "000000000162"),
        ],
        "supply",
        pen=0.5,
        forum=CP,
    ),
    "st_supply_02": full(
        "9/К",
        "2026-10-25",
        "Караганда",
        [
            P("supplier", "ТОО «Сарыарка Молоко»", "000000000217"),
            P("buyer", "ТОО «Сеть Минимаркетов Береке»", "000000000226"),
        ],
        "supply",
    ),
}


def main() -> None:
    plan = {
        "dev": {"lease_kk": 6, "lease_ru": 8, "supply_ru": 8, "works_ru": 8},
        "test": {"lease_kk": 6, "lease_ru": 8, "supply_ru": 8, "works_ru": 8},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict]] = {"dev": [], "test": [], "hard": []}
    for split, per in plan.items():
        for path in (p for s in [split] for p in draft_gold.sample(s, per)):
            d = draft_gold.draft(path)
            d.pop("_lines")
            labels = {k: v for k, v in d.items() if k not in ("doc_id", "split")}
            labels.update(OVERRIDES.get(d["doc_id"], {}))
            rows[split].append(
                {"doc_id": d["doc_id"], "path": str(path.relative_to(ROOT)), "labels": labels}
            )
    for sub in ("handwritten", "stress"):
        for path in sorted((ROOT / "data/eval" / sub).glob("*.txt")):
            if path.stem in HARD:
                rows["hard"].append(
                    {
                        "doc_id": path.stem,
                        "path": str(path.relative_to(ROOT)),
                        "labels": HARD[path.stem],
                    }
                )
    assert set(HARD) == {r["doc_id"] for r in rows["hard"]}
    for split, items in rows.items():
        for r in items:
            r["labels"] = ContractExtraction.model_validate(r["labels"]).model_dump(mode="json")
        (OUT / f"{split}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in items) + "\n", encoding="utf-8"
        )
        print(split, len(items))


if __name__ == "__main__":
    main()
