"""Генератор синтетического eval-датасета из шаблонов.

Шаблон (`data/eval/templates/*.yaml`) — это разделы договора, в каждом
разделе — слоты, в каждом слоте — варианты формулировок. Вариант либо
нейтральный, либо ловушка с разметкой по docs/LABELING_GUIDE.md:
категория, уровень и **против кого** она работает.

Почему так, а не «сгенерировать LLM-ом»:

- разметка известна по построению, а не после взгляда на выдачу системы;
- у каждого варианта есть срез (`dev`/`test`). Правила и пороги подбираются
  на `dev`, заголовочные цифры считаются на `test`, чьих формулировок
  система не видела. Это единственное, что отделяет замер обобщения от
  замера запоминания шаблонов;
- ловушка против контрагента (зеркальная) попадает в текст, но не
  в разметку: система, которая реагирует на формулировку, а не на сторону,
  получит на ней ложную тревогу;
- отсутствие раздела о форс-мажоре и односторонняя ответственность —
  документные находки, их разметка тоже выводится из построения.

Честное ограничение: шаблоны и правила пишет один автор, поэтому даже
test-срез оценивает систему оптимистично. Рукописный срез и (в будущем)
публичные договоры нужны именно для этого.
"""

from __future__ import annotations

import random
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from contract_risk.evaluation.dataset import EvalDoc, GoldFinding, dump_labels
from contract_risk.schemas import (
    ROLES_BY_TYPE,
    ContractType,
    Language,
    PartyRole,
    RiskCategory,
    RiskLevel,
    counterparty,
)

GEN_SPLITS = ("dev", "test")
# Доли: чистые договоры и вероятность ловушки в слоте, где она возможна.
CLEAN_SHARE = 0.2
TRAP_PROBABILITY = 0.3
OPTIONAL_SKIP = 0.35
FM_MISSING_PROBABILITY = 0.25
BURDEN_TOPICS = {RiskCategory.PENALTY.value, RiskCategory.LIABILITY.value}


@dataclass
class Variant:
    split: str
    text: str
    params: dict[str, list[str]] = field(default_factory=dict)
    risk: dict[str, str] | None = None
    burdens: str | None = None


@dataclass
class Slot:
    key: str
    topic: str
    variants: list[Variant]
    optional: bool = False


@dataclass
class Section:
    key: str
    titles: list[str]
    slots: list[Slot]
    force_majeure: bool = False


@dataclass
class Template:
    name: str
    contract_type: ContractType
    language: Language
    user_roles: dict[PartyRole, float]
    titles: list[str]
    preambles: list[str]
    sections: list[Section]
    requisites_title: list[str]
    requisites: list[str]
    params: dict[str, list[str]]
    styles: list[str]


def load_template(path: Path) -> Template:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    ctype = ContractType(raw["contract_type"])
    roles = {PartyRole(k): float(v) for k, v in raw["user_roles"].items()}
    allowed_roles = {r.value for r in ROLES_BY_TYPE[ctype]} | {"both", "none"}
    sections = []
    for s in raw["sections"]:
        slots = []
        for sl in s["slots"]:
            variants = []
            for v in sl["variants"]:
                variant = Variant(
                    split=v["split"],
                    text=v["text"].strip(),
                    params=v.get("params", {}),
                    risk=v.get("risk"),
                    burdens=v.get("burdens"),
                )
                _validate_variant(path.name, sl, variant, allowed_roles)
                variants.append(variant)
            slots.append(Slot(sl["key"], sl["topic"], variants, optional=sl.get("optional", False)))
        sections.append(
            Section(s["key"], s["titles"], slots, force_majeure=s.get("force_majeure", False))
        )
    return Template(
        name=path.stem,
        contract_type=ctype,
        language=Language(raw["language"]),
        user_roles=roles,
        titles=raw["titles"],
        preambles=raw["preambles"],
        sections=sections,
        requisites_title=raw["requisites_title"],
        requisites=raw["requisites"],
        params=raw.get("params", {}),
        styles=raw.get("styles", ["classic"]),
    )


def _validate_variant(name: str, slot: dict, v: Variant, allowed_roles: set[str]) -> None:
    where = f"{name}:{slot['key']}"
    if v.split not in GEN_SPLITS:
        raise ValueError(f"{where}: неизвестный срез {v.split}")
    if v.risk is not None:
        RiskCategory(v.risk["category"])
        RiskLevel(v.risk["level"])
        if v.risk["against"] not in allowed_roles - {"none"}:
            raise ValueError(f"{where}: against={v.risk['against']} не роль этого договора")
        if not v.risk.get("trap"):
            raise ValueError(f"{where}: у ловушки нет id")
    if slot["topic"] in BURDEN_TOPICS and v.burdens not in allowed_roles:
        raise ValueError(f"{where}: в слоте {slot['topic']} у варианта нужен burdens")


# --- генерация ---------------------------------------------------------------


@dataclass
class _Rendered:
    number: str
    text: str
    gold: list[GoldFinding]


def _fill(text: str, params: dict[str, str], rng: random.Random, local: dict[str, list[str]]):
    values = dict(params)
    for key, options in local.items():
        values[key] = rng.choice(options)
    return text.format_map(values)


def _pick_role(template: Template, rng: random.Random) -> PartyRole:
    roles, weights = zip(*template.user_roles.items(), strict=True)
    return rng.choices(roles, weights=weights)[0]


def generate_doc(template: Template, split: str, index: int) -> EvalDoc:
    rng = random.Random(f"{template.name}:{split}:{index}")
    user = _pick_role(template, rng)
    other = counterparty(user)
    clean = rng.random() < CLEAN_SHARE
    style = rng.choice(template.styles)
    params = {k: rng.choice(v) for k, v in template.params.items()}
    params["num"] = str(rng.randint(1, 250))
    for key in ("bin1", "bin2"):
        params[key] = "".join(str(rng.randint(0, 9)) for _ in range(12))

    lines = [_fill(rng.choice(template.titles), params, rng, {})]
    lines.append(_fill(rng.choice(template.preambles), params, rng, {}))
    lines.append("")

    gold: list[GoldFinding] = []
    burdened: set[str] = set()
    has_fm = True
    section_no = 0
    for section in template.sections:
        if section.force_majeure and not clean and rng.random() < FM_MISSING_PROBABILITY:
            has_fm = False
            continue
        rendered: list[_Rendered] = []
        for slot in section.slots:
            candidates = [v for v in slot.variants if v.split == split]
            neutral = [v for v in candidates if v.risk is None]
            risky = [v for v in candidates if v.risk is not None]
            if slot.optional and rng.random() < OPTIONAL_SKIP:
                continue
            if risky and not clean and rng.random() < TRAP_PROBABILITY:
                variant = rng.choice(risky)
            elif neutral:
                variant = rng.choice(neutral)
            else:
                continue
            text = _fill(variant.text, params, rng, variant.params)
            findings = []
            if variant.risk and variant.risk["against"] in (user.value, "both"):
                findings.append(
                    GoldFinding(
                        clause="",
                        category=variant.risk["category"],
                        level=variant.risk["level"],
                        trap_id=variant.risk["trap"],
                    )
                )
            if slot.topic in BURDEN_TOPICS and variant.burdens not in (None, "none"):
                burdened.add(variant.burdens)
            rendered.append(_Rendered("", text, findings))
        if not rendered:
            continue

        section_no += 1
        title = rng.choice(section.titles)
        lines.append(_heading(style, section_no, title, template.language))
        for j, item in enumerate(rendered, start=1):
            cid = f"{section_no}.{j}"
            number = f"{cid} " if style == "article" else f"{cid}. "
            lines.extend(_clause_lines(style, number, item.text))
            for g in item.gold:
                gold.append(g.model_copy(update={"clause": cid}))

    requisites_title = rng.choice(template.requisites_title)
    lines.append(_heading(style, section_no + 1, requisites_title, template.language))
    lines.extend(_fill(r, params, rng, {}) for r in template.requisites)

    if not has_fm:
        gold.append(
            GoldFinding(clause=None, category="force_majeure", level="medium", trap_id="fm_missing")
        )
    other_side = other.value in burdened or "both" in burdened
    if user.value in burdened and not other_side:
        gold.append(
            GoldFinding(
                clause=None, category="liability", level="medium", trap_id="liability_one_sided"
            )
        )

    return EvalDoc(
        doc_id=f"{template.name}_{split}_{index:03d}",
        split=split,
        contract_type=template.contract_type,
        language=template.language,
        party_role=user,
        origin="synthetic",
        findings=gold,
        text="\n".join(lines) + "\n",
    )


def _heading(style: str, n: int, title: str, language: Language) -> str:
    if style == "article":
        word = "бап" if language == Language.KK else "Статья"
        title = title.capitalize()
        return f"{n}-{word}. {title}" if language == Language.KK else f"{word} {n}. {title}"
    if style == "titlecase":
        return f"{n}. {title.capitalize()}"
    return f"{n}. {title.upper()}"


def _clause_lines(style: str, number: str, text: str) -> list[str]:
    first, *rest = text.split("\n")
    lines = [number + first, *rest]
    if style != "wrapped":
        return lines
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=78, break_long_words=False) or [""])
    return wrapped


def generate(
    templates_dir: Path, out_root: Path, counts: dict[str, dict[str, int]]
) -> dict[str, Any]:
    """Пишет договоры и разметку в out_root/<split>/; возвращает сводку."""
    summary: dict[str, Any] = {}
    for split in GEN_SPLITS:
        split_dir = out_root / split
        split_dir.mkdir(parents=True, exist_ok=True)
        for old in list(split_dir.glob("*.txt")) + list(split_dir.glob("*.yaml")):
            old.unlink()
    for path in sorted(templates_dir.glob("*.yaml")):
        template = load_template(path)
        for split in GEN_SPLITS:
            n = counts.get(template.name, {}).get(split, 0)
            for i in range(1, n + 1):
                doc = generate_doc(template, split, i)
                base = out_root / split / doc.doc_id
                base.with_suffix(".txt").write_text(doc.text, encoding="utf-8")
                base.with_suffix(".yaml").write_text(dump_labels(doc), encoding="utf-8")
            summary[f"{template.name}/{split}"] = n
    return summary
