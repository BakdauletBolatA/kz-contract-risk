"""Каталог правил: явные формулировки рисков по docs/LABELING_GUIDE.md.

Каждое правило — функция, которая по пункту возвращает находки с тем,
**против кого** работает условие. Движок оставляет только находки против
стороны пользователя. У каждого правила есть примеры «срабатывает /
не срабатывает» — они же автотесты (tests/test_rules.py): правило без
примеров не пройдёт CI.

Правила пишутся и настраиваются только на dev-срезе. Объяснения — для
человека без юридического образования: что написано, чем грозит в
деньгах или сроках, как обычно пишут.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property

from contract_risk.rules import lexicon as lx
from contract_risk.rules.features import (
    months_amount,
    notice_days,
    penalty_terms,
    term_days,
)
from contract_risk.rules.parties import PartyView
from contract_risk.schemas import (
    ROLES_BY_TYPE,
    Clause,
    ContractType,
    Language,
    PartyRole,
    RiskCategory,
    RiskLevel,
    counterparty,
)
from contract_risk.taxonomy import LEGAL_REFS, ROLE_TITLES

C = RiskCategory
HIGH, MEDIUM, LOW = RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW
ALL_TYPES = frozenset(ContractType)


@dataclass
class RuleContext:
    clause: Clause
    contract_type: ContractType
    user: PartyRole

    @property
    def text(self) -> str:
        return self.clause.text

    @property
    def lang(self) -> Language:
        return self.clause.lang

    @property
    def other(self) -> PartyRole:
        return counterparty(self.user)

    @cached_property
    def parties(self) -> PartyView:
        return PartyView.of(self.text, self.contract_type, self.lang)

    @property
    def roles(self) -> tuple[PartyRole, PartyRole]:
        return ROLES_BY_TYPE[self.contract_type]


@dataclass
class Hit:
    rule_id: str
    category: RiskCategory
    level: RiskLevel
    against: frozenset[PartyRole]
    spans: list[tuple[int, int]]
    title: str
    explanation: str
    safer_wording: str | None = None
    legal_basis: str | None = None
    details: dict = field(default_factory=dict)


@dataclass
class Example:
    text: str
    contract_type: str
    role: str
    level: str | None
    lang: str = "ru"


@dataclass
class Rule:
    id: str
    category: RiskCategory
    fn: Callable[[RuleContext], list[Hit]]
    examples: list[Example]
    contract_types: frozenset[ContractType] = ALL_TYPES
    description: str = ""


def _span(m: re.Match | None) -> list[tuple[int, int]]:
    return [(m.start(), m.end())] if m else []


def _fmt(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _both(ctx: RuleContext) -> frozenset[PartyRole]:
    return frozenset(ctx.roles)


def _burden(ctx: RuleContext) -> tuple[frozenset[PartyRole], bool] | None:
    """Кого обременяет пункт о деньгах: (стороны, взаимно ли). None — не понять."""
    payers = ctx.parties.payers()
    if payers:
        return frozenset(payers), False
    if ctx.parties.mutual:
        return _both(ctx), True
    mentioned = ctx.parties.roles()
    if len(mentioned) == 1:
        return frozenset(mentioned), False
    return None


def _title(role: PartyRole) -> str:
    return ROLE_TITLES[role].split(" /")[0].lower()


# --- penalty -----------------------------------------------------------------

_TERMINATION_CONTEXT = re.compile(
    r"(?:досрочн\w+\s+(?:расторжени|прекращени)|прекраща\w+\s+аренду\s+досрочно|до\s+истечения\s+срока"
    r"|мерзімінен\s+бұрын|обеспечительн|гарантийн\w+\s+взнос|депозит|кепілдік)",
    re.IGNORECASE,
)


def penalty_daily_rate(ctx: RuleContext) -> list[Hit]:
    terms = penalty_terms(ctx.text)
    rate = terms.max_daily_rate
    if rate is None:
        return []
    r = rate.value
    if r >= 0.5:
        level = HIGH
    elif r > 0.1:
        level = MEDIUM
    elif not terms.capped:
        level = LOW
    else:
        return []
    burden = _burden(ctx)
    if burden is None:
        return []
    against, mutual = burden
    if mutual:
        lowered = level.lowered()
        if lowered is None:
            return []
        level = lowered
    cap = max(terms.caps, key=lambda s: s.value, default=None)
    cap_text = (
        f" Потолок — {_fmt(cap.value)}%."
        if cap
        else " Потолка нет: сумма растёт каждый день, пока долг не погашен."
    )
    explanation = (
        f"Пеня {_fmt(r)}% за каждый день — это около {_fmt(r * 30)}% суммы долга за месяц "
        f"и {_fmt(r * 365)}% за год.{cap_text} Сбалансированный ориентир — 0,1% в день "
        f"с ограничением 10% суммы долга."
    )
    if mutual:
        explanation += " Условие взаимное, поэтому риск ниже, но размер всё равно высокий."
    spans = [(rate.start, rate.end)] + ([(cap.start, cap.end)] if cap else [])
    return [
        Hit(
            "penalty.daily_rate",
            C.PENALTY,
            level,
            against,
            spans,
            f"Пеня {_fmt(r)}% в день" + ("" if cap else " без потолка"),
            explanation,
            "Пеня 0,1% от суммы просроченного платежа за каждый день просрочки, "
            "но не более 10% от этой суммы.",
            LEGAL_REFS["penalty_reduction"],
            {"daily_rate": r, "capped": terms.capped, "mutual": mutual},
        )
    ]


def penalty_fine(ctx: RuleContext) -> list[Hit]:
    if _TERMINATION_CONTEXT.search(ctx.text):
        return []
    terms = penalty_terms(ctx.text)
    fine = terms.max_fine
    if fine is None or terms.daily_rates:
        return []
    f = fine.value
    if f >= 30:
        level = HIGH
    elif f > 10:
        level = MEDIUM
    else:
        return []
    burden = _burden(ctx)
    if burden is None:
        return []
    against, mutual = burden
    if mutual and (level := level.lowered()) is None:
        return []
    return [
        Hit(
            "penalty.fine",
            C.PENALTY,
            level,
            against,
            [(fine.start, fine.end)],
            f"Штраф {_fmt(f)}%",
            f"Разовый штраф {_fmt(f)}% — это заметная сумма за одно нарушение, "
            f"независимо от реального ущерба. Обычно штраф не превышает 10% "
            f"от суммы платежа или договора.",
            "Штраф не более 10% от суммы, к которой относится нарушение; "
            "штраф засчитывается в сумму убытков.",
            LEGAL_REFS["penalty_reduction"],
            {"fine_percent": f},
        )
    ]


# --- auto_renewal ------------------------------------------------------------

_AUTO_RENEWAL = re.compile(
    r"(?:считается\s+(?:продлен|пролонгирован|возобновлен)\w*|считать\s+продлен\w*"
    r"|продлева\w+\s+автоматически|автоматически\s+(?:продлева|пролонгир|продлит)\w*"
    r"|пролонгиру\w+\s+автоматически|ежегодно\s+пролонгир\w+|(?<!быть\s)пролонгируется"
    r"|продлевается\s+на\s+(?:тот\s+же|следующ|кажд|новый)"
    r"|ұзартылды\s+деп\s+есептеледі|автоматты\s+түрде\s+ұзартылады)",
    re.IGNORECASE,
)
_RENEWAL_BY_AGREEMENT = re.compile(
    r"(?:по\s+(?:письменному\s+)?(?:заявлению|соглашению)|дополнительн\w+\s+соглашени|может\s+быть\s+продл)",
    re.IGNORECASE,
)
_DISCRETION = re.compile(
    r"(?:самостоятельно|по\s+своему\s+усмотрению|которые\s+определит|устанавлива\w+\s+\w+ем\b"
    r"|установить\s+новые|вправе\s+установить|өз\s+бетінше)",
    re.IGNORECASE,
)
_PRICE = re.compile(r"(?:цен\w*|ставк\w*|арендн\w+\s+плат\w*|стоимост\w*|жалдау\s+ақы\w*)", re.I)
_MUST_NOTIFY = re.compile(r"не\s+(?:уведом|направ|заяв|сообщ)\w*", re.IGNORECASE)


def auto_renewal(ctx: RuleContext) -> list[Hit]:
    m = _AUTO_RENEWAL.search(ctx.text)
    if m is None or (
        _RENEWAL_BY_AGREEMENT.search(ctx.text) and "автоматически" not in ctx.text.lower()
    ):
        return []
    spans = _span(m)
    discretion = _DISCRETION.search(ctx.text)
    if discretion and _PRICE.search(ctx.text):
        mentions = ctx.parties.mentions
        setter = (
            min(mentions, key=lambda x: abs(x.start - discretion.start())).role
            if mentions
            else None
        )
        if setter is not None:
            return [
                Hit(
                    "auto_renewal.price_on_renewal",
                    C.AUTO_RENEWAL,
                    HIGH,
                    frozenset({counterparty(setter)}),
                    spans + _span(discretion),
                    "Автопродление по цене, которую назначит контрагент",
                    f"Договор продлится сам, а цену на новый срок {_title(setter)} "
                    f"определяет в одиночку. Если пропустить момент отказа, вы окажетесь "
                    f"связаны договором по цене, которую не согласовывали.",
                    "Договор может быть продлён на новый срок по соглашению Сторон; "
                    "условия и цена нового срока согласуются письменно.",
                    None,
                    {"setter": setter.value},
                )
            ]
    notices = notice_days(ctx.text)
    longest = max(notices, key=lambda s: s.value, default=None)
    if longest is not None and longest.value >= 60:
        notifier = None
        must = _MUST_NOTIFY.search(ctx.text)
        if must and not ctx.parties.mutual:
            nominative = [x for x in ctx.parties.mentions if x.case == "nom"]
            before = [x for x in nominative if x.start < must.start()]
            notifier = before[-1].role if before else None
        against = frozenset({notifier}) if notifier else _both(ctx)
        return [
            Hit(
                "auto_renewal.long_notice",
                C.AUTO_RENEWAL,
                MEDIUM,
                against,
                spans + [(longest.start, longest.end)],
                "Автопродление с долгим сроком отказа",
                f"Договор продлевается сам, а отказаться можно только уведомлением "
                f"за {int(longest.value)} дней до окончания срока. Пропустили дату — "
                f"ещё один срок обязательств и платежей.",
                "Договор продлевается на тот же срок, если ни одна из Сторон не уведомит "
                "другую об отказе не позднее чем за 30 дней до окончания срока.",
                None,
                {"notice_days": longest.value},
            )
        ]
    return [
        Hit(
            "auto_renewal.silent",
            C.AUTO_RENEWAL,
            LOW,
            _both(ctx),
            spans,
            "Договор продлевается автоматически",
            "Если вовремя не заявить об отказе, договор продлится на новый срок "
            "на тех же условиях. Поставьте напоминание о дате отказа.",
            None,
            None,
        )
    ]


# --- liability ---------------------------------------------------------------


def liability_lost_profit(ctx: RuleContext) -> list[Hit]:
    m = lx.LOST_PROFIT.search(ctx.text)
    if m is None or lx.LOST_PROFIT_EXCLUDED.search(ctx.text):
        return []
    burden = _burden(ctx)
    if burden is None:
        return []
    against, mutual = burden
    over = lx.OVER_PENALTY.search(ctx.text)
    level = HIGH if over else MEDIUM
    if mutual and (level := level.lowered()) is None:
        return []
    explanation = (
        "Вы отвечаете не только за реальный ущерб, но и за доходы, которые другая "
        "сторона «могла бы получить». Такую сумму трудно предсказать, и она может "
        "многократно превысить цену договора."
    )
    if over:
        explanation += " Убытки взыскиваются сверх неустойки — то есть платить придётся дважды."
    return [
        Hit(
            "liability.lost_profit",
            C.LIABILITY,
            level,
            against,
            _span(m) + _span(over),
            "Возмещение упущенной выгоды" + (" сверх неустойки" if over else ""),
            explanation,
            "Сторона возмещает реальный ущерб; упущенная выгода не возмещается; "
            "неустойка засчитывается в сумму убытков.",
            None,
            {"over_penalty": bool(over)},
        )
    ]


def liability_exclusion(ctx: RuleContext) -> list[Hit]:
    if lx.FORCE_MAJEURE.search(ctx.text):
        return []
    pattern = lx.NOT_LIABLE_KK if ctx.lang == Language.KK else lx.NOT_LIABLE_RU
    m = pattern.search(ctx.text)
    if m is None:
        return []
    released = ctx.parties.released(pattern)
    if not released:
        return []
    broad = lx.BROAD_SCOPE.search(ctx.text)
    hits = []
    for role in released:
        hits.append(
            Hit(
                "liability.exclusion",
                C.LIABILITY,
                HIGH if broad else MEDIUM,
                frozenset({counterparty(role)}),
                _span(m) + _span(broad),
                f"{ROLE_TITLES[role].split(' /')[0]} снимает с себя ответственность"
                + (" за любые убытки" if broad else ""),
                (
                    "Контрагент заранее освобождает себя от ответственности"
                    + (
                        " практически за всё. Если он нарушит договор, взыскать ущерб будет "
                        "почти невозможно."
                        if broad
                        else " в определённом случае. Риск этого случая целиком ложится на вас."
                    )
                ),
                "Стороны несут ответственность за неисполнение обязательств в соответствии "
                "с законодательством Республики Казахстан; ограничение ответственности — "
                "одинаковое для обеих Сторон.",
                LEGAL_REFS["adhesion"],
                {"broad": bool(broad)},
            )
        )
    return hits


# --- force_majeure -----------------------------------------------------------


def force_majeure_one_sided(ctx: RuleContext) -> list[Hit]:
    fm = lx.FORCE_MAJEURE.search(ctx.text)
    if fm is None:
        return []
    released = ctx.parties.released(lx.RELEASED_FM)
    if not released or ctx.parties.mutual:
        return []
    return [
        Hit(
            "force_majeure.one_sided",
            C.FORCE_MAJEURE,
            MEDIUM,
            frozenset({counterparty(role)}),
            _span(fm),
            "Форс-мажор только для контрагента",
            f"При чрезвычайных обстоятельствах от ответственности освобождается только "
            f"{_title(role)}. Вы в той же ситуации по договору продолжаете отвечать.",
            "Стороны освобождаются от ответственности за неисполнение обязательств, "
            "вызванное обстоятельствами непреодолимой силы.",
            LEGAL_REFS["force_majeure"],
        )
        for role in released
    ]


# --- jurisdiction ------------------------------------------------------------

_DISPUTE = re.compile(r"(?:спор|суд|арбитраж|разногласи|дау|сот|төрелік)", re.IGNORECASE)
_FOREIGN = re.compile(
    r"(?:лондон\w*|\bLCIA\b|\bICC\b|стокгольм\w*|сингапур\w*|швейцар\w*"
    r"|при\s+(?:ТПП|торгово-промышленной\s+палате)\s+российской"
    r"|прав\w*\s+(?:англии|российской\s+федерации|швеции|сингапура)|английск\w+\s+прав\w*"
    r"|англия\s+құқығы)",
    re.IGNORECASE,
)
_AIFC = re.compile(
    r"(?:МФЦА|\bAIFC\b|международн\w+\s+финансов\w+\s+центр\w*\s+«?астана»?|АХҚО)", re.IGNORECASE
)
_LOCATION_RU = re.compile(r"по\s+месту\s+(?:нахождения|регистрации|жительства)\s+$", re.I)
_LOCATION_KK = re.compile(r"^\s*орналасқан\s+жері\s+бойынша", re.I)


def jurisdiction(ctx: RuleContext) -> list[Hit]:
    if not _DISPUTE.search(ctx.text):
        return []
    foreign = _FOREIGN.search(ctx.text)
    if foreign:
        return [
            Hit(
                "jurisdiction.foreign",
                C.JURISDICTION,
                HIGH,
                _both(ctx),
                _span(foreign),
                "Спор — за рубежом или по иностранному праву",
                "Любой спор придётся вести за границей или по чужому праву: это "
                "иностранные юристы, перевод документов и расходы, которые для малого "
                "бизнеса часто больше самой суммы спора.",
                "Споры разрешаются в суде Республики Казахстан; применимое право — "
                "право Республики Казахстан.",
            )
        ]
    aifc = _AIFC.search(ctx.text)
    if aifc:
        return [
            Hit(
                "jurisdiction.aifc",
                C.JURISDICTION,
                MEDIUM,
                _both(ctx),
                _span(aifc),
                "Спор — в суде или арбитраже МФЦА",
                "Споры рассматривает МФЦА: процесс идёт по особым правилам, как правило "
                "на английском языке, и обычно дороже обычного суда.",
                "Споры разрешаются в суде Республики Казахстан по правилам подсудности.",
            )
        ]
    for mention in ctx.parties.mentions:
        if ctx.lang == Language.KK:
            located = mention.case == "gen" and _LOCATION_KK.search(ctx.text[mention.end :])
        else:
            located = mention.case == "gen" and _LOCATION_RU.search(
                ctx.text[max(0, mention.start - 40) : mention.start]
            )
        if located:
            return [
                Hit(
                    "jurisdiction.counterparty_location",
                    C.JURISDICTION,
                    LOW,
                    frozenset({counterparty(mention.role)}),
                    [(mention.start, mention.end)],
                    "Споры — в суде по месту контрагента",
                    f"Спорить придётся в суде по месту нахождения стороны «{_title(mention.role)}». "
                    f"Если это другой город, каждое заседание — дорога и время.",
                    "Споры разрешаются в суде по месту нахождения ответчика.",
                )
            ]
    return []


# --- termination -------------------------------------------------------------

_TERMINATE_RU = r"(?:расторг\w*|отказ\w*\s+от\s+(?:исполнения\s+)?(?:настоящего\s+)?договор\w*)"
_TERMINATE_KK = r"(?:бұзуға|бұза\s+алады|бас\s+тартуға|бас\s+тарта\s+алады)"
_NO_NOTICE = re.compile(
    r"(?:без\s+(?:\w+\s+){0,2}(?:уведомления|предупреждения)|в\s+любое\s+время|в\s+любой\s+момент"
    r"|без\s+(?:объяснения|указания)\s+причин|в\s+день\s+(?:расторжения|отказа)|немедленно"
    r"|ескертпей|себебін\s+түсіндірмей|кез\s+келген\s+уақытта)",
    re.IGNORECASE,
)
_BREACH_CONDITION = re.compile(
    r"(?:\bесли\b|в\s+случае|при\s+(?:нарушени|просрочк|неуплат|невнесени|неисполнени|повторн|существенн)"
    r"|более\s+двух\s+раз|\bегер\b)",
    re.IGNORECASE,
)
_PAYS_FOR_WORK = re.compile(
    r"(?:уплатив|оплатив|возместив|с\s+оплатой\s+(?:фактически\s+)?выполненн)", re.IGNORECASE
)


def termination_unilateral(ctx: RuleContext) -> list[Hit]:
    action = _TERMINATE_KK if ctx.lang == Language.KK else _TERMINATE_RU
    holders = ctx.parties.right_holders(action)
    if not holders:
        return []
    no_notice = _NO_NOTICE.search(ctx.text)
    notices = notice_days(ctx.text)
    shortest = min(notices, key=lambda s: s.value, default=None)
    if no_notice:
        level, spans = HIGH, _span(no_notice)
        why = "Контрагент может выйти из договора в любой момент, без предупреждения."
    elif shortest is not None and shortest.value < 30:
        level, spans = MEDIUM, [(shortest.start, shortest.end)]
        why = (
            f"Контрагент может выйти из договора, предупредив всего за "
            f"{int(shortest.value)} дней — меньше месяца, который даёт закон по общему правилу."
        )
    elif shortest is None and not _BREACH_CONDITION.search(ctx.text):
        if _PAYS_FOR_WORK.search(ctx.text):
            return []
        level, spans = MEDIUM, []
        why = "Контрагент может выйти из договора в одностороннем порядке, срок предупреждения не указан."
    else:
        return []
    return [
        Hit(
            "termination.unilateral",
            C.TERMINATION,
            level,
            frozenset({counterparty(holder)}),
            spans,
            "Контрагент может расторгнуть договор в одностороннем порядке",
            why + " За это время придётся искать замену: помещение, поставщика или заказ.",
            "Каждая из Сторон вправе отказаться от исполнения Договора, письменно "
            "предупредив другую Сторону не менее чем за 30 календарных дней.",
            LEGAL_REFS["unilateral_refusal"],
            {"holder": holder.value},
        )
        for holder in holders
    ]


_CANNOT_EXIT_RU = re.compile(
    r"(?:не\s+вправе|не\s+имеет\s+права|не\s+может)\s+(?:\w+\s+){0,2}?(?:досрочно\s+)?(?:расторг|отказ\w*\s+от)",
    re.IGNORECASE,
)
_NO_EARLY_EXIT_PASSIVE = re.compile(
    r"досрочн\w+\s+(?:расторжени|прекращени)\w*[^.;]{0,40}по\s+инициативе\s+[^.;]{0,30}не\s+допуска",
    re.IGNORECASE,
)


def termination_user_cannot_exit(ctx: RuleContext) -> list[Hit]:
    m = _CANNOT_EXIT_RU.search(ctx.text) or _NO_EARLY_EXIT_PASSIVE.search(ctx.text)
    if m is None:
        return []
    if m.re is _CANNOT_EXIT_RU:
        nominative = [x for x in ctx.parties.mentions if x.case == "nom" and x.start < m.start()]
        bound = nominative[-1].role if nominative else None
    else:
        inside = [x for x in ctx.parties.mentions if m.start() <= x.start < m.end()]
        bound = inside[0].role if inside else None
    if bound is None:
        return []
    return [
        Hit(
            "termination.cannot_exit",
            C.TERMINATION,
            HIGH,
            frozenset({bound}),
            _span(m),
            "Нельзя выйти из договора досрочно",
            "Если бизнес не пойдёт или условия изменятся, выйти из договора досрочно "
            "не получится: придётся платить до конца срока или судиться.",
            "Каждая из Сторон вправе досрочно отказаться от Договора, предупредив другую "
            "Сторону не менее чем за один месяц.",
            None,
        )
    ]


_EARLY = re.compile(
    r"(?:досрочн\w+\s+(?:расторжени|прекращени|отказ)|прекраща\w+\s+аренду\s+досрочно"
    r"|до\s+истечения\s+срока|раньше\s+(?:окончания|истечения)\s+срок|ранее\s+срока"
    r"|мерзімінен\s+бұрын\s+бұз)",
    re.IGNORECASE,
)
_FEE = re.compile(
    r"(?:уплачивает|выплачивает|компенсаци\w*|штраф\w*|төлейді|өтемақы)", re.IGNORECASE
)
_REMAINDER = re.compile(
    r"(?:весь\s+оставш\w+|оставш\w+\s+(?:срок|период)|до\s+конца\s+срока|қалған\s+бүкіл\s+мерзім)",
    re.IGNORECASE,
)
_NO_FEE = re.compile(r"(?:без\s+(?:уплаты\s+)?компенсаци|без\s+применения|без\s+возмещения)", re.I)
_DEPOSIT = re.compile(
    r"(?:обеспечительн\w+\s+платеж|гарантийн\w+\s+взнос|депозит|кепілдік\s+жарна)", re.I
)


_INITIATIVE_BEFORE = re.compile(r"(?:по\s+(?:инициативе|желанию)|отказа|отказе)\s*$", re.I)
_INITIATIVE_AFTER = re.compile(r"^\s*бастамасы\s+бойынша", re.I)


def _initiator(ctx: RuleContext) -> PartyRole | None:
    """Кто выходит из договора: «по инициативе Арендатора он уплачивает…»."""
    for m in ctx.parties.mentions:
        before = ctx.text[max(0, m.start - 25) : m.start]
        if m.case == "gen" and (
            _INITIATIVE_BEFORE.search(before) or _INITIATIVE_AFTER.search(ctx.text[m.end :])
        ):
            return m.role
    return None


def termination_early_fee(ctx: RuleContext) -> list[Hit]:
    early = _EARLY.search(ctx.text)
    fee = _FEE.search(ctx.text)
    if early is None or fee is None or _NO_FEE.search(ctx.text) or _DEPOSIT.search(ctx.text):
        return []
    if lx.FORCE_MAJEURE.search(ctx.text):
        return []
    initiator = _initiator(ctx)
    burden = (frozenset({initiator}), False) if initiator else _burden(ctx)
    if burden is None or burden[1]:
        return []
    remainder = _REMAINDER.search(ctx.text)
    months = months_amount(ctx.text)
    level = HIGH if remainder or (months is not None and months >= 3) else MEDIUM
    amount = (
        "плату за весь оставшийся срок"
        if remainder
        else f"сумму, равную {_fmt(months)} мес. платы"
        if months
        else "дополнительную сумму"
    )
    return [
        Hit(
            "termination.early_fee",
            C.TERMINATION,
            level,
            burden[0],
            _span(early) + _span(remainder),
            "Плата за досрочный выход из договора",
            f"Чтобы выйти из договора раньше срока, придётся заплатить {amount}. "
            f"Это цена «выхода», которую стоит учитывать заранее.",
            "Сторона вправе досрочно отказаться от Договора, предупредив другую Сторону "
            "не менее чем за один месяц, без уплаты компенсации.",
            None,
            {"months": months, "remainder": bool(remainder)},
        )
    ]


_FORFEIT = re.compile(
    r"(?:не\s+возвраща\w+|возврату\s+не\s+подлежит|не\s+подлежит\s+возврату|оста[её]тся\s+у"
    r"|удерживается|невозвратн\w+|засчитывается\s+в\s+пользу|қайтарылмайды)",
    re.IGNORECASE,
)
_ANY_TERMINATION = re.compile(
    r"(?:ни\s+при\s+каких|при\s+любом\s+(?:прекращении|расторжении)|в\s+том\s+числе\s+при\s+расторжении"
    r"|невозвратн|кез\s+келген\s+жағдайда)",
    re.IGNORECASE,
)


def termination_deposit(ctx: RuleContext) -> list[Hit]:
    deposit = _DEPOSIT.search(ctx.text)
    forfeit = _FORFEIT.search(ctx.text)
    if deposit is None or forfeit is None:
        return []
    anytime = _ANY_TERMINATION.search(ctx.text)
    tenant = PartyRole.TENANT
    return [
        Hit(
            "termination.deposit_forfeit",
            C.TERMINATION,
            HIGH if anytime else MEDIUM,
            frozenset({tenant}),
            _span(deposit) + _span(forfeit),
            "Обеспечительный платёж не возвращается",
            "Депозит, который вы вносите, остаётся у арендодателя"
            + (
                " при любом прекращении договора — даже если его расторгает сам арендодатель."
                if anytime
                else " при досрочном выходе из договора."
            ),
            "Обеспечительный платёж возвращается Арендатору в течение 10 рабочих дней "
            "после прекращения Договора за вычетом подтверждённой задолженности.",
            None,
        )
    ]


# --- unilateral_change -------------------------------------------------------

_CHANGE_RU = r"(?:изменя|измени|увеличива|увелич|пересматрива|пересмотр|индексир|повыша|повыс)"
_CHANGE_KK = r"(?:өзгертуге|арттыра\s+алады|көтеруге|арттыруға)"
_CHANGE_OBJECT = re.compile(
    r"(?:цен\w*|стоимост\w*|арендн\w+\s+плат\w*|ставк\w*|тариф\w*|прайс|жалдау\s+ақы\w*)", re.I
)
_TERMS_OBJECT = re.compile(r"(?:услови\w+\s+(?:настоящего\s+)?договора|настоящий\s+договор)", re.I)
_CAPPED_CHANGE = re.compile(
    r"(?:не\s+более\s+чем\s+на\s+\d|в\s+пределах\s+(?:официального\s+)?уровня\s+инфляции"
    r"|не\s+более\s+\d+\s*%|\d+\s*%\s+в\s+год)",
    re.IGNORECASE,
)


def unilateral_change(ctx: RuleContext) -> list[Hit]:
    action = _CHANGE_KK if ctx.lang == Language.KK else _CHANGE_RU
    obj = _CHANGE_OBJECT.search(ctx.text)
    terms = _TERMS_OBJECT.search(ctx.text)
    if obj is None and terms is None:
        return []
    holders = ctx.parties.right_holders(action)
    if not holders:
        return []
    capped = _CAPPED_CHANGE.search(ctx.text)
    level = LOW if capped and terms is None else HIGH
    what = "условия договора" if terms else "цену"
    return [
        Hit(
            "unilateral_change.price" if terms is None else "unilateral_change.terms",
            C.UNILATERAL_CHANGE,
            level,
            frozenset({counterparty(holder)}),
            _span(terms or obj) + _span(capped),
            f"Контрагент может менять {what} без вашего согласия",
            (
                f"{ROLE_TITLES[holder].split(' /')[0]} вправе изменить {what} в одностороннем порядке"
                + (
                    ", но с ограничением роста — риск умеренный."
                    if level == LOW
                    else ". Сумма, на которую вы рассчитывали, может вырасти в любой момент."
                )
            ),
            "Цена может быть изменена только по письменному соглашению Сторон, "
            "не чаще одного раза в год.",
            None,
            {"holder": holder.value, "capped": bool(capped)},
        )
        for holder in holders
    ]


# --- payment -----------------------------------------------------------------

_PREPAY = re.compile(
    r"(?:100\s*%\s*(?:\([^)]*\)\s*)?(?:предоплат|предварительн\w+\s+оплат|аванс)"
    r"|полн\w+\s+предоплат|полн\w+\s+предварительн\w+\s+оплат|стопроцентн\w+"
    r"|полн\w+\s+(?:стоимост\w+|сумм\w+)\s+(?:\w+\s+){0,2}авансом"
    r"|100\s*%\s+[^.;]{0,40}до\s+(?:отгрузки|поставки|начала))",
    re.IGNORECASE,
)
_PAYMENT = re.compile(r"(?:оплачива|оплат|расч[её]т|рассчитыва|перечисля)", re.IGNORECASE)
_NOT_PAYMENT = re.compile(r"(?:гарантийн\w+\s+срок|претензи|приемк|считаются\s+принят)", re.I)
_PAY_WHEN_PAID = re.compile(
    r"(?:(?:после|с\s+момента)\s+(?:получения|поступления)\s+(?:\w+\s+){0,2}(?:оплаты|денежных\s+средств|средств)"
    r"|поступ\w+\s+(?:на\s+его\s+сч[её]т\s+)?(?:оплат\w+|денежн\w+\s+средств\w*|средств\w*))"
    r"\s+от\s+(?:генеральн|конечн|основн|его|своего|третьих|арендатор|заказчик\w*\s+по|покупател\w*\s+по)",
    re.IGNORECASE,
)


def payment(ctx: RuleContext) -> list[Hit]:
    payee, payer = ctx.roles
    prepay = _PREPAY.search(ctx.text)
    if prepay:
        return [
            Hit(
                "payment.full_prepayment",
                C.PAYMENT,
                MEDIUM,
                frozenset({payer}),
                _span(prepay),
                "Стопроцентная предоплата",
                "Вы платите всю сумму до получения товара или работ. Если контрагент "
                "не исполнит договор, деньги придётся возвращать через претензии и суд.",
                "Предоплата 30%, оставшиеся 70% — в течение 10 банковских дней после "
                "поставки (подписания акта).",
            )
        ]
    pwp = _PAY_WHEN_PAID.search(ctx.text)
    if pwp:
        return [
            Hit(
                "payment.pay_when_paid",
                C.PAYMENT,
                HIGH,
                frozenset({payee}),
                _span(pwp),
                "Оплата — только когда заплатят контрагенту",
                "Вам заплатят только после того, как деньги получит сам контрагент от "
                "третьего лица. Если третье лицо не заплатит, срок вашей оплаты "
                "не наступит вообще.",
                "Оплата производится в течение 15 банковских дней с даты подписания акта "
                "(накладной) независимо от расчётов с третьими лицами.",
            )
        ]
    if not _PAYMENT.search(ctx.text) or _NOT_PAYMENT.search(ctx.text):
        return []
    longest = max(term_days(ctx.text), key=lambda s: s.value, default=None)
    if longest is None or longest.value < 60:
        return []
    return [
        Hit(
            "payment.deferral",
            C.PAYMENT,
            HIGH if longest.value >= 120 else MEDIUM,
            frozenset({payee}),
            [(longest.start, longest.end)],
            f"Оплата через {int(longest.value)} дней",
            f"Деньги за поставку или работу придут только через {int(longest.value)} дней. "
            f"Всё это время вы кредитуете контрагента за свой счёт.",
            "Оплата производится в течение 30 календарных дней с даты поставки (подписания акта).",
            None,
            {"days": longest.value},
        )
    ]


# --- acceptance --------------------------------------------------------------

_SILENT = re.compile(r"(?:считаются|считается|считать)\s+принят\w*", re.IGNORECASE)
_CLAIMS = re.compile(r"(?:претензи\w*|недостатк\w*|дефект\w*|рекламаци\w*)", re.IGNORECASE)
_HIDDEN_WARRANTY = re.compile(
    r"скрыт\w+[^.;]{0,60}(?:гарантийн\w+\s+срок|в\s+пределах\s+гарантийн)", re.IGNORECASE
)
_REFUSAL = re.compile(
    r"(?:отказаться\s+от\s+приемки|не\s+принимать|не\s+подписывать\s+акт|отказыва\w+\s+от\s+подписания\s+акта)",
    re.IGNORECASE,
)
_ARBITRARY = re.compile(
    r"(?:по\s+(?:своему|собственному)\s+усмотрению|без\s+(?:объяснения|указания)\s+(?:причин|мотивов)"
    r"|мотивировать\s+отказ\s+\w*\s*не\s+обязан)",
    re.IGNORECASE,
)


def acceptance(ctx: RuleContext) -> list[Hit]:
    performer, acceptor = ctx.roles
    refusal, arbitrary = _REFUSAL.search(ctx.text), _ARBITRARY.search(ctx.text)
    if refusal and arbitrary:
        return [
            Hit(
                "acceptance.arbitrary_refusal",
                C.ACCEPTANCE,
                HIGH,
                frozenset({performer}),
                _span(refusal) + _span(arbitrary),
                "Приёмку можно не подписывать без причин",
                "Контрагент может отказаться принять результат просто так, без объяснений. "
                "Без подписанного акта сложно доказать, что работа сделана, и получить оплату.",
                "Заказчик в течение 10 рабочих дней подписывает акт либо направляет "
                "мотивированный отказ с перечнем недостатков.",
            )
        ]
    short = [s for s in term_days(ctx.text) if s.value <= 3]
    if not short:
        return []
    silent = _SILENT.search(ctx.text)
    claims = _CLAIMS.search(ctx.text)
    if silent is None and (claims is None or _HIDDEN_WARRANTY.search(ctx.text)):
        return []
    days = short[0]
    return [
        Hit(
            "acceptance.short_deadline",
            C.ACCEPTANCE,
            MEDIUM,
            frozenset({acceptor}),
            [(days.start, days.end)] + _span(silent or claims),
            "Очень короткий срок на проверку и претензии",
            f"На проверку результата и претензии даётся не больше "
            f"{_fmt(days.value)} дн. Скрытые недостатки за это время не обнаружить, "
            f"а после срока претензии не принимаются или всё считается принятым.",
            "Приёмка по качеству — в течение 10 рабочих дней; о скрытых недостатках "
            "можно заявить в течение гарантийного срока.",
            None,
            {"days": days.value},
        )
    ]


# --- реестр ------------------------------------------------------------------
# Примеры — данные: одна строка на пример читается лучше, чем вызов в пять строк.
# fmt: off
E = Example

RULES: list[Rule] = [
    Rule("penalty.daily_rate", C.PENALTY, penalty_daily_rate, [
        E("Арендатор уплачивает Арендодателю пеню в размере 1% от суммы долга за каждый день просрочки.", "lease", "tenant", "high"),
        E("Арендатор уплачивает Арендодателю пеню в размере 1% от суммы долга за каждый день просрочки.", "lease", "landlord", None),
        E("Арендатор уплачивает пеню 0,1% от суммы долга за каждый день просрочки, но не более 10% от суммы долга.", "lease", "tenant", None),
        E("Арендатор уплачивает пеню 0,1% от суммы долга за каждый день просрочки.", "lease", "tenant", "low"),
        E("Арендодатель вправе взыскать с Арендатора неустойку 0,3% за каждый день просрочки.", "lease", "tenant", "medium"),
        E("Виновная Сторона уплачивает пеню 1% за каждый день просрочки.", "lease", "tenant", "medium"),
        E("Жалға алушы әрбір кешіктірілген күн үшін 1% мөлшерінде өсімпұл төлейді.", "lease", "tenant", "high", "kk"),
    ]),
    Rule("penalty.fine", C.PENALTY, penalty_fine, [
        E("За нарушение правил Арендатор уплачивает штраф в размере 50% от месячной арендной платы.", "lease", "tenant", "high"),
        E("За нарушение правил Арендатор уплачивает штраф в размере 5% от месячной арендной платы.", "lease", "tenant", None),
        E("За поставку некачественного Товара Поставщик выплачивает штраф 20% от его стоимости.", "supply", "buyer", None),
    ]),
    Rule("auto_renewal", C.AUTO_RENEWAL, auto_renewal, [
        E("Если ни одна из Сторон не заявит о прекращении Договора, он считается продленным на тот же срок.", "lease", "tenant", "low"),
        E("Договор автоматически продлевается, если Арендатор не уведомит Арендодателя об отказе за 90 дней до окончания срока.", "lease", "tenant", "medium"),
        E("Договор продлевается автоматически, при этом размер арендной платы устанавливается Арендодателем самостоятельно.", "lease", "tenant", "high"),
        E("Договор может быть продлен по письменному соглашению Сторон.", "lease", "tenant", None),
        E("Шарт сол мерзімге ұзартылды деп есептеледі.", "lease", "tenant", "low", "kk"),
    ]),
    Rule("liability.lost_profit", C.LIABILITY, liability_lost_profit, [
        E("Арендатор возмещает Арендодателю все убытки, включая упущенную выгоду.", "lease", "tenant", "medium"),
        E("Убытки, включая упущенную выгоду, взыскиваются с Подрядчика в полной сумме сверх неустойки.", "works", "contractor", "high"),
        E("Стороны возмещают реальный ущерб; упущенная выгода не возмещается.", "lease", "tenant", None),
        E("Поставщик возмещает Покупателю упущенную выгоду.", "supply", "buyer", None),
    ]),
    Rule("liability.exclusion", C.LIABILITY, liability_exclusion, [
        E("Арендодатель не несет ответственности за какие-либо убытки Арендатора.", "lease", "tenant", "high"),
        E("Арендодатель не несет ответственности за сохранность имущества Арендатора.", "lease", "tenant", "medium"),
        E("Ни одна из Сторон не несет ответственности за неисполнение, вызванное форс-мажором.", "lease", "tenant", None),
        E("Арендатор не несет ответственности за перебои электроснабжения.", "lease", "tenant", None),
        E("Жалға беруші Жалға алушының кез келген залалы үшін жауапты болмайды.", "lease", "tenant", "high", "kk"),
    ]),
    Rule("force_majeure.one_sided", C.FORCE_MAJEURE, force_majeure_one_sided, [
        E("Арендодатель освобождается от ответственности при обстоятельствах непреодолимой силы.", "lease", "tenant", "medium"),
        E("Стороны освобождаются от ответственности при обстоятельствах непреодолимой силы.", "lease", "tenant", None),
    ]),
    Rule("jurisdiction", C.JURISDICTION, jurisdiction, [
        E("Споры разрешаются в Лондонском международном арбитражном суде.", "supply", "buyer", "high"),
        E("Споры рассматриваются Судом МФЦА.", "works", "customer", "medium"),
        E("Споры рассматриваются в суде по месту нахождения Арендодателя.", "lease", "tenant", "low"),
        E("Споры рассматриваются в суде по месту нахождения Арендодателя.", "lease", "landlord", None),
        E("Споры разрешаются в суде в соответствии с законодательством Республики Казахстан.", "lease", "tenant", None),
        E("Даулар Жалға берушінің орналасқан жері бойынша сотта қаралады.", "lease", "tenant", "low", "kk"),
    ]),
    Rule("termination.unilateral", C.TERMINATION, termination_unilateral, [
        E("Арендодатель вправе в любое время отказаться от исполнения Договора без уведомления.", "lease", "tenant", "high"),
        E("Арендодатель вправе в одностороннем порядке отказаться от Договора, уведомив Арендатора за 10 дней.", "lease", "tenant", "medium"),
        E("Каждая из Сторон вправе отказаться от Договора, предупредив другую Сторону за 30 дней.", "lease", "tenant", None),
        E("Арендатор вправе в любое время отказаться от исполнения Договора без уведомления.", "lease", "tenant", None),
        E("Арендодатель вправе отказаться от Договора, если Арендатор более двух раз не внес плату, предупредив за один месяц.", "lease", "tenant", None),
        E("Жалға беруші кез келген уақытта Шартты біржақты тәртіппен бұзуға құқылы.", "lease", "tenant", "high", "kk"),
    ]),
    Rule("termination.cannot_exit", C.TERMINATION, termination_user_cannot_exit, [
        E("Арендатор не вправе досрочно расторгнуть Договор.", "lease", "tenant", "high"),
        E("Досрочное прекращение Договора по инициативе Арендатора не допускается.", "lease", "tenant", "high"),
        E("Арендатор не вправе досрочно расторгнуть Договор.", "lease", "landlord", None),
    ]),
    Rule("termination.early_fee", C.TERMINATION, termination_early_fee, [
        E("При досрочном расторжении по инициативе Арендатора он уплачивает арендную плату за весь оставшийся срок.", "lease", "tenant", "high"),
        E("При досрочном расторжении по инициативе Арендатора он уплачивает Арендодателю штраф в размере месячной арендной платы.", "lease", "tenant", "medium"),
        E("При досрочном расторжении по инициативе Арендатора он уплачивает Арендодателю штраф в размере месячной арендной платы.", "lease", "landlord", None),
        E("Если Арендатор прекращает аренду досрочно, он уплачивает компенсацию в размере двухмесячной арендной платы.", "lease", "tenant", "medium"),
        E("Арендатор вправе досрочно отказаться от Договора без уплаты компенсации.", "lease", "tenant", None),
    ]),
    Rule("termination.deposit_forfeit", C.TERMINATION, termination_deposit, [
        E("При досрочном расторжении по инициативе Арендатора обеспечительный платеж возврату не подлежит.", "lease", "tenant", "medium"),
        E("Гарантийный взнос является невозвратным.", "lease", "tenant", "high"),
        E("Обеспечительный платеж возвращается Арендатору в течение 10 дней.", "lease", "tenant", None),
        E("Гарантийный взнос является невозвратным.", "lease", "landlord", None),
    ], frozenset({ContractType.LEASE})),
    Rule("unilateral_change", C.UNILATERAL_CHANGE, unilateral_change, [
        E("Арендодатель вправе в одностороннем порядке изменять размер арендной платы.", "lease", "tenant", "high"),
        E("Цена Товара может быть пересмотрена Поставщиком без согласования с Покупателем.", "supply", "buyer", "high"),
        E("Арендодатель вправе увеличить арендную плату не более чем на 10% в год.", "lease", "tenant", "low"),
        E("Размер арендной платы может быть изменен по соглашению Сторон.", "lease", "tenant", None),
        E("Арендодатель вправе в одностороннем порядке изменять размер арендной платы.", "lease", "landlord", None),
        E("Жалға беруші жалдау ақысын біржақты тәртіппен өзгертуге құқылы.", "lease", "tenant", "high", "kk"),
    ]),
    Rule("payment", C.PAYMENT, payment, [
        E("Покупатель производит 100% предварительную оплату партии.", "supply", "buyer", "medium"),
        E("Покупатель производит 100% предварительную оплату партии.", "supply", "supplier", None),
        E("Покупатель оплачивает Товар в течение 90 дней с даты поставки.", "supply", "supplier", "medium"),
        E("Покупатель оплачивает Товар в течение 180 дней с даты поставки.", "supply", "supplier", "high"),
        E("Покупатель оплачивает Товар в течение 30 дней с даты поставки.", "supply", "supplier", None),
        E("Оплата производится только после получения оплаты от Генерального заказчика.", "works", "contractor", "high"),
    ], frozenset({ContractType.SUPPLY, ContractType.WORKS})),
    Rule("acceptance", C.ACCEPTANCE, acceptance, [
        E("Если Заказчик в течение 2 рабочих дней не подписал акт, работы считаются принятыми.", "works", "customer", "medium"),
        E("Если Заказчик в течение 10 рабочих дней не подписал акт, работы считаются принятыми.", "works", "customer", None),
        E("Претензии по качеству, включая скрытые недостатки, принимаются в течение 24 часов.", "supply", "buyer", "medium"),
        E("Заказчик вправе отказаться от приемки работ без объяснения причин.", "works", "contractor", "high"),
        E("Заказчик вправе отказаться от приемки работ без объяснения причин.", "works", "customer", None),
    ], frozenset({ContractType.SUPPLY, ContractType.WORKS})),
]
# fmt: on
