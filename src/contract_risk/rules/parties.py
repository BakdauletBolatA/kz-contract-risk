"""Кто в пункте обременён, а кто получает право.

Одна и та же фраза «пеня 1% в день» — ловушка для арендатора и выгода для
арендодателя. Поэтому до того, как решать, рискован ли пункт, нужно понять:
кто платит, кто вправе расторгнуть, кто освобождает себя от ответственности.

Эвристики (русский):

- подлежащее — роль в именительном падеже («Арендатор уплачивает»);
- «с Арендатора взыскивается», «для Поставщика» — родительный после
  предлога: платит названная сторона;
- «уплачиваемый Арендатором», «пересматриваться Арендодателем» —
  творительный в пассиве: действует названная сторона;
- «не освобождает Арендатора от возмещения» — обременена названная сторона;
- «Стороны», «каждая из Сторон», «виновная Сторона» — взаимный пункт.

Казахский — порядок слов SOV, подлежащее в атау септігі: «Жалға алушы …
төлейді»; «Жалға алушыдан … өндіріп алуға» (шығыс септік) — платит
названная сторона.

Это эвристики, а не синтаксический разбор. Ошибки видны в eval как ложные
тревоги на зеркальных ловушках и пропуски в пунктах с пассивом.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from contract_risk.rules import lexicon as lx
from contract_risk.schemas import ROLES_BY_TYPE, ContractType, Language, PartyRole


@dataclass(frozen=True)
class Mention:
    role: PartyRole
    case: str
    start: int
    end: int


@lru_cache(maxsize=16)
def _role_pattern(contract_type: ContractType, lang: Language) -> re.Pattern:
    stems = lx.KK_ROLE_STEMS if lang == Language.KK else lx.RU_ROLE_STEMS
    alternatives = []
    for role in ROLES_BY_TYPE[contract_type]:
        for i, (stem, endings) in enumerate(stems[role]):
            ends = "|".join(sorted((re.escape(e) for e in endings if e), key=len, reverse=True))
            group = f"{role.value}_{i}"
            alternatives.append(rf"(?P<{group}>{stem})(?P<{group}_end>{ends})?(?![{lx.LETTERS}])")
    return re.compile(rf"(?<![{lx.LETTERS}])(?:{'|'.join(alternatives)})", re.IGNORECASE)


def find_mentions(text: str, contract_type: ContractType, lang: Language) -> list[Mention]:
    stems = lx.KK_ROLE_STEMS if lang == Language.KK else lx.RU_ROLE_STEMS
    out = []
    for m in _role_pattern(contract_type, lang).finditer(text):
        group = next(g for g, v in m.groupdict().items() if v and not g.endswith("_end"))
        role_value, index = group.rsplit("_", 1)
        role = PartyRole(role_value)
        ending = (m.group(f"{group}_end") or "").lower()
        case = stems[role][int(index)][1][ending]
        if lx.THIRD_PARTY_PREFIX.search(text[max(0, m.start() - 30) : m.start()]):
            continue
        out.append(Mention(role, case, m.start(), m.end()))
    return out


def is_mutual(text: str, lang: Language) -> bool:
    pattern = lx.MUTUAL_KK if lang == Language.KK else lx.MUTUAL_RU
    return bool(pattern.search(text))


@dataclass
class PartyView:
    """Разбор ролей одного пункта."""

    text: str
    contract_type: ContractType
    lang: Language
    mentions: list[Mention]
    mutual: bool

    @classmethod
    def of(cls, text: str, contract_type: ContractType, lang: Language) -> PartyView:
        return cls(
            text,
            contract_type,
            lang,
            find_mentions(text, contract_type, lang),
            is_mutual(text, lang),
        )

    def roles(self, *cases: str) -> list[PartyRole]:
        seen: list[PartyRole] = []
        for m in self.mentions:
            if (not cases or m.case in cases) and m.role not in seen:
                seen.append(m.role)
        return seen

    def _followed_by(self, mention: Mention, pattern: str, window: int = 80) -> bool:
        tail = self.text[mention.end : mention.end + window]
        return re.search(rf"^[^.;]*?{pattern}", tail, re.IGNORECASE) is not None

    def _preceded_by(self, mention: Mention, pattern: str, window: int = 40) -> bool:
        head = self.text[max(0, mention.start - window) : mention.start]
        return re.search(rf"{pattern}\s*$", head, re.IGNORECASE) is not None

    # --- кто платит / обременён ------------------------------------------------

    def payers(self) -> set[PartyRole]:
        """Стороны, которые платят неустойку или возмещают убытки по пункту."""
        found: set[PartyRole] = set()
        for m in self.mentions:
            if self.lang == Language.KK:
                if m.case == "abl":
                    found.add(m.role)
                elif m.case == "nom" and self._followed_by(m, lx.PAY_VERBS_KK, 250):
                    found.add(m.role)
                continue
            if m.case == "gen" and self._preceded_by(m, r"(?:\bс|\bсо|\bдля)"):
                found.add(m.role)
            elif m.case in ("gen", "nom") and self._preceded_by(
                m, r"не\s+освобождает(?:\s+\w+){0,2}"
            ):
                found.add(m.role)
            elif m.case == "ins" and self._preceded_by(
                m, r"(?:уплачиваем\w*|выплачиваем\w*|оплачивается|уплачивается|выплачивается)"
            ):
                found.add(m.role)
            elif m.case == "nom" and self._followed_by(m, lx.PAY_VERBS_RU):
                found.add(m.role)
        if not found:
            nominative = self.roles("nom")
            if len(nominative) == 1 and not self._has_right_holder(nominative[0]):
                found.add(nominative[0])
        return found

    def _has_right_holder(self, role: PartyRole) -> bool:
        right = lx.RIGHT_KK if self.lang == Language.KK else lx.RIGHT_RU
        return any(
            m.role == role and m.case == "nom" and self._followed_by(m, right, 60)
            for m in self.mentions
        )

    # --- кто вправе ------------------------------------------------------------

    def right_holders(self, action: str) -> set[PartyRole]:
        """Стороны, которым пункт даёт право на действие `action` (regex)."""
        found: set[PartyRole] = set()
        right = lx.RIGHT_KK if self.lang == Language.KK else lx.RIGHT_RU
        for m in self.mentions:
            if m.case == "nom":
                if self.lang == Language.KK:
                    if self._followed_by(m, rf"{action}", 250):
                        found.add(m.role)
                elif self._followed_by(m, rf"{right}[^.;]{{0,80}}?{action}", 200):
                    found.add(m.role)
            elif m.case == "ins" and self.lang == Language.RU:
                # пассив: «может быть пересмотрена Поставщиком», «индексируется Арендодателем»
                if self._preceded_by(m, rf"{action}\w*(?:\s+\w+){{0,3}}", 80):
                    found.add(m.role)
        return found

    def released(self, pattern: re.Pattern) -> set[PartyRole]:
        """Стороны-подлежащие при «не несёт ответственности», «освобождается»."""
        found: set[PartyRole] = set()
        for m in self.mentions:
            if m.case != "nom":
                continue
            window = self.text[max(0, m.start - 120) : m.end + 150]
            local = pattern.search(window)
            if local is None:
                continue
            # подлежащее — ближайшая к глаголу роль в именительном падеже
            verb_pos = max(0, m.start - 120) + local.start()
            nearest = min(
                (x for x in self.mentions if x.case == "nom"),
                key=lambda x: abs(x.start - verb_pos),
            )
            if nearest is m:
                found.add(m.role)
        return found
