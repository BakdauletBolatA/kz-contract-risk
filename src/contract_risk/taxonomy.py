"""Человеческие названия категорий, уровней и ролей — для отчёта и промпта.

Пороги и смысл категорий живут в docs/LABELING_GUIDE.md; здесь только то,
что показывается пользователю. Юридические ссылки ограничены статьями,
номера которых сверены с текстом кодекса.
"""

from __future__ import annotations

from contract_risk.schemas import ContractType, PartyRole, RiskCategory, RiskLevel

CATEGORY_TITLES: dict[RiskCategory, str] = {
    RiskCategory.PENALTY: "Неустойка и штрафы",
    RiskCategory.AUTO_RENEWAL: "Автопродление",
    RiskCategory.LIABILITY: "Ответственность и убытки",
    RiskCategory.FORCE_MAJEURE: "Форс-мажор",
    RiskCategory.JURISDICTION: "Где решаются споры",
    RiskCategory.TERMINATION: "Расторжение и выход из договора",
    RiskCategory.UNILATERAL_CHANGE: "Одностороннее изменение условий",
    RiskCategory.PAYMENT: "Условия оплаты",
    RiskCategory.ACCEPTANCE: "Приёмка и претензии",
}

CATEGORY_DESCRIPTIONS: dict[RiskCategory, str] = {
    RiskCategory.PENALTY: "размер пени и штрафов, которые платит сторона, и есть ли у них потолок",
    RiskCategory.AUTO_RENEWAL: "продлевается ли договор сам и как от этого отказаться",
    RiskCategory.LIABILITY: "за что и в каком объёме сторона отвечает деньгами",
    RiskCategory.FORCE_MAJEURE: "что будет при обстоятельствах, от сторон не зависящих",
    RiskCategory.JURISDICTION: "в каком суде и по какому праву решаются споры",
    RiskCategory.TERMINATION: "кто и на каких условиях может выйти из договора",
    RiskCategory.UNILATERAL_CHANGE: "может ли одна сторона менять цену или условия без согласия другой",
    RiskCategory.PAYMENT: "когда и сколько платят, риск не получить деньги или товар",
    RiskCategory.ACCEPTANCE: "как принимается результат и сколько времени на претензии",
}

LEVEL_TITLES: dict[RiskLevel, str] = {
    RiskLevel.HIGH: "Высокий риск",
    RiskLevel.MEDIUM: "Средний риск",
    RiskLevel.LOW: "Низкий риск",
}

LEVEL_ADVICE: dict[RiskLevel, str] = {
    RiskLevel.HIGH: "Не подписывать в таком виде: добиться изменения или показать юристу.",
    RiskLevel.MEDIUM: "Обсудить с контрагентом: условие хуже обычной практики.",
    RiskLevel.LOW: "Знать и помнить: условие распространено, но не нейтрально.",
}

CONTRACT_TYPE_TITLES: dict[ContractType, str] = {
    ContractType.LEASE: "Аренда",
    ContractType.SUPPLY: "Поставка",
    ContractType.WORKS: "Подряд / услуги",
}

ROLE_TITLES: dict[PartyRole, str] = {
    PartyRole.LANDLORD: "Арендодатель",
    PartyRole.TENANT: "Арендатор",
    PartyRole.SUPPLIER: "Поставщик",
    PartyRole.BUYER: "Покупатель",
    PartyRole.CONTRACTOR: "Подрядчик / исполнитель",
    PartyRole.CUSTOMER: "Заказчик",
}

# Статьи, номера и смысл которых сверены с текстом кодекса (adilet.zan.kz).
# Ссылка в отчёте — подсказка, куда смотреть, а не юридическое заключение.
LEGAL_REFS: dict[str, str] = {
    "penalty_reduction": "ст. 297 ГК РК — суд вправе уменьшить чрезмерно высокую неустойку",
    "penalty_definition": "ст. 293 ГК РК — понятие неустойки",
    "force_majeure": "п. 2 ст. 359 ГК РК — освобождение предпринимателя от ответственности при непреодолимой силе",
    "adhesion": "ст. 389 ГК РК — договор присоединения и явно обременительные условия",
    "unilateral_refusal": "ст. 404 ГК РК — односторонний отказ от договора и предупреждение не позднее чем за месяц",
}

DISCLAIMER = (
    "Это автоматический первичный скрининг, а не юридическое заключение. "
    "Система может пропустить рискованный пункт или ошибиться в оценке. "
    "Перед подписанием договора на существенную сумму покажите его юристу."
)
