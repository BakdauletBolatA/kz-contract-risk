"""Черновик эталонной разметки полей: правила на регулярках + ручная проверка.

Запускается один раз, чтобы не набирать JSON руками. Черновик НЕ является
эталоном: каждый документ потом сверяется с текстом и правится вручную
(`data/extraction_gold/*.jsonl`), а регулярки не участвуют в оценке моделей.
    python scripts/draft_gold.py > /tmp/draft.jsonl
"""

# ruff: noqa: E501
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data/eval"
RU_M = {
    m: i
    for i, m in enumerate(
        "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(),
        1,
    )
}
KK_M = {
    m: i
    for i, m in enumerate(
        "қаңтар ақпан наурыз сәуір мамыр маусым шілде тамыз қыркүйек қазан қараша желтоқсан".split(),
        1,
    )
}
ROLE = {
    "Арендодатель": "landlord",
    "Арендатор": "tenant",
    "Поставщик": "supplier",
    "Покупатель": "buyer",
    "Подрядчик": "contractor",
    "Заказчик": "customer",
    "Жалға беруші": "landlord",
    "Жалға алушы": "tenant",
}


def sample(split: str, per: dict[str, int], seed: int = 7) -> list[Path]:
    rng = random.Random(seed)
    out: list[Path] = []
    for prefix, n in per.items():
        files = sorted((EVAL / split).glob(f"{prefix}_{split}_*.txt"))
        out += sorted(rng.sample(files, n))
    return out


def num(s: str) -> float:
    return float(s.replace("\xa0", "").replace(" ", "").replace(",", "."))


def draft(path: Path) -> dict:
    t = path.read_text(encoding="utf-8")
    meta = yaml.safe_load(path.with_suffix(".yaml").read_text(encoding="utf-8"))
    head = "\n".join(t.splitlines()[:6])
    d: dict = {
        "doc_id": path.stem,
        "split": path.parent.name,
        "contract_type": meta["contract_type"],
    }
    m = re.search(r"№\s*([^\s,]+)", head)
    d["contract_number"] = m.group(1) if m else None
    m = re.search(r"[«\"]?(\d{1,2})[»\"]?\s+(" + "|".join(RU_M) + r")\s+(\d{4})", head)
    if m:
        d["contract_date"] = f"{m[3]}-{RU_M[m[2]]:02d}-{int(m[1]):02d}"
    else:
        m = re.search(r"(\d{4})\s+жылғы\s+(\d{1,2})\s+(" + "|".join(KK_M) + ")", head)
        d["contract_date"] = f"{m[1]}-{KK_M[m[3]]:02d}-{int(m[2]):02d}" if m else None
    m = re.search(r"г\.\s*([А-ЯЁ][\w-]+)", head) or re.search(
        r"([А-ЯЁӘҒҚҢӨҰҮҺІ][\w-]+)\s+қ\.", head
    )
    d["city"] = m.group(1) if m else None
    parties = []
    for line in t.splitlines():
        m = re.match(
            r"^(Арендодатель|Арендатор|Поставщик|Покупатель|Подрядчик|Заказчик|Жалға беруші|Жалға алушы):\s*(.+?)(?:,\s*(?:БИН|ИИН|БСН|ЖСН)\s*(\d{12}))?(?:,\s*(?:г\.|[А-ЯЁӘҒҚҢӨҰҮҺІ]\w+\s+қ\.).*)?$",
            line,
        )
        if m:
            parties.append({"role": ROLE[m[1]], "name": m[2].strip().rstrip(","), "bin": m[3]})
    d["parties"] = parties
    body = re.sub(r"\s*\n\s*(?=(?![а-я]\))[а-яёәғқңөұүһі])", " ", t)
    body = re.sub(r"[ \xa0]+", " ", body)
    sents = [
        x.strip() for x in re.split(r"(?<=[.;])\s+(?=\d+\.\d*\s|[а-я]\))|\n", body) if x.strip()
    ]
    d["_lines"] = {}

    def pick(name: str, pattern: str) -> list[str]:
        hits = [x for x in sents if re.search(pattern, x, re.I)]
        d["_lines"][name] = hits
        return hits

    m = re.search(
        r"(\d+)\s*(?:\([^)]*\)\s*)?(месяц|ай)",
        " ".join(
            pick("term", r"срок действия|в течение \d+ \([^)]*\) месяц|бойы әрекет|месяц|ай бойы")
        ),
    )
    d["term_months"] = int(m[1]) if m and d["contract_type"] == "lease" else None
    d["auto_renewal"] = bool(
        pick(
            "renewal",
            r"считается продлен|считается пролонгир|автоматическ\w+ (про)?длен|пролонгируется|ұзартылды деп есептеледі|автоматты",
        )
    )
    hits = pick("price", r"тенге|теңге|₸")
    m = re.search(r"(\d[\d ]*(?:,\d+)?)\s*(?:\([^)]*\)\s*)?(?:тенге|теңге|₸)", " ".join(hits))
    d["price_amount"] = num(m[1]) if m else None
    d["price_period"] = (
        ("monthly" if re.search(r"в месяц|ежемесячн|айына|ай сайын", " ".join(hits)) else "total")
        if m
        else None
    )
    hits = pick("pay_deadline", r"оплачивает|оплат\w+ в течение")
    m = re.search(
        r"в течение\s*(\d+)\s*(?:\([^)]*\)\s*)?(?:календарных|рабочих|банковских)?\s*дн",
        " ".join(x for x in hits if re.search(r"оплат|Покупатель|Заказчик", x)),
    )
    d["payment_deadline_days"] = int(m[1]) if m else None
    hits = pick(
        "penalty",
        r"(просрочк|кешіктір|нарушение сроков).*(оплат|арендной платы|задолженност|ақысын төлеу)|(оплат|арендн).*просрочк",
    )
    hits = [x for x in hits if re.search(r"пен[юя]|неустойк|өсімпұл", x)]
    d["_lines"]["penalty"] = hits
    m = re.search(r"(\d+(?:,\d+)?)\s*%", hits[0]) if hits else None
    d["payment_penalty_rate_percent_per_day"] = num(m[1]) if m else None
    m = (
        re.search(r"не более\s*(\d+(?:,\d+)?)\s*%|(\d+(?:,\d+)?)\s*%-ынан аспайды", hits[0])
        if hits
        else None
    )
    d["payment_penalty_cap_percent"] = num(m[1] or m[2]) if m else None
    hits = pick("forum", r"суд|арбитраж|сот ")
    d["dispute_forum"] = (
        "aifc_court"
        if re.search(r"МФЦА", body)
        else "foreign_arbitration"
        if re.search(r"арбитраж", body, re.I)
        else "counterparty_location_court"
        if re.search(r"по месту нахождения", body)
        else "kz_courts"
        if re.search(r"в суде|судебном порядке|сот тәртібімен", body)
        else None
    )
    hits = pick(
        "notice",
        r"отказаться от (исполнения )?Договора|расторг|ескерт|бұзуға|предупредив|уведомив|прекращени",
    )
    nums = [
        int(x)
        for h in hits
        for x in re.findall(
            r"за\s*(\d+)\s*(?:\([^)]*\)\s*)?(?:календарных|рабочих)?\s*дн|(\d+)\s*(?:\([^)]*\)\s*)?күнтізбелік",
            h,
        )
        for x in x
        if x
    ]
    d["termination_notice_days"] = nums[0] if len(set(nums)) == 1 else None
    if re.search(r"без предварительного уведомления|ескертпей", body):
        d["termination_notice_days"] = 0
    return d


if __name__ == "__main__":
    plan = {
        "dev": {"lease_kk": 6, "lease_ru": 8, "supply_ru": 8, "works_ru": 8},
        "test": {"lease_kk": 6, "lease_ru": 8, "supply_ru": 8, "works_ru": 8},
    }
    paths = [p for s, per in plan.items() for p in sample(s, per)]
    for sub in ("handwritten", "stress"):
        paths += [p for p in sorted((EVAL / sub).glob("*.txt")) if "services" not in p.name]
    for p in paths:
        print(json.dumps(draft(p), ensure_ascii=False))
