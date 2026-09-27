"""Разбиение договора на пункты с сохранением нумерации и иерархии.

Главная трудность — отличить номер пункта от числа в начале строки: в PDF
строки переносятся жёстко, и продолжение пункта легко начинается с
«15 (пятнадцать) дней». Поэтому номер принимается только если он
**продолжает текущую нумерацию**: после 4.2 допустимы 4.3, 4.2.1, 5, 5.1
(с запасом на один пропущенный номер — в реальных договорах нумерация
бывает с ошибками). Всё остальное — продолжение текущего пункта.

Решения, которые стоит знать:

- Перечисления внутри пункта (а), б), 1), маркеры) не становятся отдельными
  пунктами: это элементы одного условия, и риск оценивается по условию
  целиком. Подпункты с точечной нумерацией (4.2.1) — отдельные пункты
  с `parent_id`.
- Пункт первого уровня с дочерними пунктами и заголовочным текстом
  («5. ОТВЕТСТВЕННОСТЬ СТОРОН») — заголовок раздела, а не условие.
- Формы «Статья 5», «Раздел 5», «5-бап», «5-бөлім» задают раздел; внутри такого
  раздела нумерация «1.», «2.» читается как 5.1, 5.2.
- После «Приложение №N» / «N-қосымша» нумерация начинается заново,
  id получают префикс «прилN.».
- Раздел реквизитов и подписей не анализируется: условий там нет, а
  персональных данных — больше всего.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from contract_risk.ingestion.language import CLAUSE_THRESHOLD, detect_language
from contract_risk.schemas import Clause

_NUM_RE = re.compile(
    r"^(?:(?:п\.|пункт)\s*)?"
    r"(?P<num>\d{1,3}(?:\.\d{1,3}){0,4})"
    r"(?P<trail>[.)])?"
    r"(?:\s+|(?<=\.)(?=[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ«\"]))"
    r"(?P<body>\S.*)$"
)
_SECTION_WORD_RE = re.compile(
    r"^(?:статья|раздел|глава|бап|бөлім|тарау)\s+(?P<num>\d{1,3})\.?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_SECTION_KK_RE = re.compile(
    r"^(?P<num>\d{1,3})\s*[-‐–]\s*(?:бап|бөлім|тарау)\.?\s*(?P<body>.*)$", re.IGNORECASE
)
_ENUM_RE = re.compile(r"^(?:[а-яёәғқңөұүһіa-z]\)|\d{1,2}\)|[-–—•●▪·*])\s*\S", re.IGNORECASE)
_APPENDIX_RE = re.compile(
    r"^(?:приложение\s*(?:№\s*)?(?P<n1>\d+)?|(?P<n2>\d+)\s*[-‐]\s*қосымша|қосымша\s*(?:№\s*)?(?P<n3>\d+)?)\b",
    re.IGNORECASE,
)
_REQUISITES_RE = re.compile(
    r"(реквизит|юридическ\w*\s+адрес|адреса\s+(?:и|сторон)|подписи\s+сторон|мекенжай|деректеме|қолдары)",
    re.IGNORECASE,
)
# Строка, после которой число в начале следующей строки — ссылка, а не номер:
# «…в порядке, предусмотренном п.» + «5.3 настоящего Договора».
_REFERENCE_TAIL_RE = re.compile(
    r"(?:\bп\.|\bпп\.|\bпункт\w*|\bподпункт\w*|\bст\.|\bстать\w*|\bраздел\w*|№"
    r"|\bтармақ\w*|\bбап\w*)\s*$",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"(?:^|\s)(договор|контракт|шарт|келісімшарт)", re.IGNORECASE)

MAX_SKIP = 2


@dataclass
class _Item:
    kind: str  # numbered | heading | paragraph | requisites
    path: tuple[int, ...] | None
    number: str | None
    head: str
    start: int
    end: int
    prefix: str = ""
    lines: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        if self.path is None:
            return self.number or ""
        return self.prefix + ".".join(str(x) for x in self.path)

    @property
    def body(self) -> str:
        return _join_lines([self.head, *self.lines] if self.head else self.lines)

    def add(self, line: str, end: int) -> None:
        self.lines.append(line)
        self.end = end


@dataclass
class SegmentResult:
    title: str | None
    clauses: list[Clause]
    warnings: list[str]


def _upper_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(c.isupper() for c in letters) / len(letters)


def _heading_like(body: str) -> bool:
    b = body.strip()
    if not 3 <= len(b) <= 90 or not any(c.isalpha() for c in b):
        return False
    if _upper_ratio(b) >= 0.7:
        return True
    return not b.endswith((".", ";", ":", ",")) and len(b.split()) <= 8


def _looks_like_title(head: str, next_line: str | None) -> bool:
    """Заголовок раздела, а не начало пункта, перенесённое на следующую строку.

    «3. Арендатор обязуется вносить плату в размере» + «100 000 тенге.» —
    короткое начало без точки, но продолжение начинается не с заглавной:
    это перенос строки, а не заголовок.
    """
    if not _heading_like(head):
        return False
    if _upper_ratio(head) >= 0.7:
        return True
    return len(head.split()) <= 6 and (next_line is None or next_line[:1].isupper())


def _is_unnumbered_heading(line: str) -> bool:
    return (
        3 <= len(line) <= 100
        and _upper_ratio(line) >= 0.8
        and sum(c.isalpha() for c in line) >= 4
        and not line.endswith(",")
    )


def _continues_title(line: str) -> bool:
    """Вторая строка заголовка: «№ 15» или «нежилого помещения», но не «г. Алматы, 1 мая»."""
    if line.startswith("№"):
        return True
    return line[:1].islower() and not re.match(r"^(?:г\.|город|қ\.|қаласы)", line)


def is_successor(prev: tuple[int, ...] | None, cand: tuple[int, ...]) -> bool:
    """Продолжает ли `cand` нумерацию после `prev`."""
    if prev is None:
        return all(1 <= x <= 3 for x in cand)
    if len(cand) == len(prev) + 1 and cand[:-1] == prev and 1 <= cand[-1] <= MAX_SKIP:
        return True
    for k in range(min(len(prev), len(cand))):
        if cand[k] == prev[k]:
            continue
        if prev[k] < cand[k] <= prev[k] + MAX_SKIP and all(
            1 <= x <= MAX_SKIP for x in cand[k + 1 :]
        ):
            return True
        return False
    return False


def _join(prev: str, line: str, enum: bool) -> str:
    if not prev:
        return line
    if enum or (prev.endswith((".", ";", ":", "!", "?")) and line[:1].isupper()):
        return f"{prev}\n{line}"
    return f"{prev} {line}"


def _join_lines(lines: list[str]) -> str:
    out = ""
    for line in lines:
        out = _join(out, line, enum=bool(_ENUM_RE.match(line)))
    return out


def _match_number(
    line: str, path: tuple[int, ...] | None, article: int | None
) -> tuple[tuple[int, ...], str, str, bool] | None:
    """Номер в начале строки, если он продолжает нумерацию: (путь, номер, текст, раздел?)."""
    sec = _SECTION_WORD_RE.match(line) or _SECTION_KK_RE.match(line)
    if sec:
        body = sec.group("body").strip()
        number = line[: sec.start("body")].strip() if body else line
        return (int(sec.group("num")),), number, body, True
    num = _NUM_RE.match(line)
    if not num:
        return None
    parts = tuple(int(x) for x in num.group("num").split("."))
    body = num.group("body").strip()
    if article is not None and len(parts) == 1:
        parts = (article, parts[0])
    elif len(parts) == 1 and num.group("trail") is None and _upper_ratio(body) < 0.7:
        # «15 (пятнадцать) дней» в начале перенесённой строки — не номер.
        return None
    if not is_successor(path, parts):
        return None
    return parts, line[: num.start("body")].strip(), body, False


def segment(text: str) -> SegmentResult:
    items: list[_Item] = []
    warnings: list[str] = []
    title_lines: list[str] = []
    preamble: _Item | None = None
    current: _Item | None = None
    path: tuple[int, ...] | None = None
    article: int | None = None
    prefix = ""
    mode = "preamble"
    counter = 0
    prev_line = ""

    offset = 0
    for raw in text.split("\n"):
        start, end = offset, offset + len(raw)
        offset = end + 1
        line = raw.strip()
        if not line:
            continue
        after_reference = bool(_REFERENCE_TAIL_RE.search(prev_line))
        prev_line = line

        appendix = _APPENDIX_RE.match(line) if mode != "preamble" else None
        if appendix and len(line) <= 120:
            n = appendix.group("n1") or appendix.group("n2") or appendix.group("n3") or "1"
            prefix, path, article, mode = f"прил{n}.", None, None, "body"
            current = _Item("heading", None, f"прил{n}", line, start, end)
            items.append(current)
            continue

        if mode == "requisites":
            assert current is not None
            current.add(line, end)
            continue

        matched = None if after_reference else _match_number(line, path, article)
        if matched is not None:
            cand, number, body, is_section = matched
            path = cand
            if is_section:
                article = cand[0]
            is_req = bool(body) and bool(_REQUISITES_RE.search(body)) and _heading_like(body)
            current = _Item(
                "requisites" if is_req else "numbered", cand, number, body, start, end, prefix
            )
            items.append(current)
            mode = "requisites" if is_req else "body"
            continue

        if mode == "body" and _is_unnumbered_heading(line) and not _ENUM_RE.match(line):
            if _REQUISITES_RE.search(line):
                current = _Item("requisites", None, "req", line, start, end)
                mode = "requisites"
            else:
                counter += 1
                current = _Item("heading", None, f"h{counter}", line, start, end)
            items.append(current)
            continue

        if mode == "preamble":
            if not title_lines and preamble is None and _TITLE_RE.search(line) and len(line) <= 150:
                title_lines.append(line)
            elif title_lines and preamble is None and _continues_title(line):
                title_lines.append(line)
            elif preamble is None:
                preamble = _Item("preamble", None, "preamble", line, start, end)
            else:
                preamble.add(line, end)
            continue

        assert current is not None
        if current.kind == "heading":
            # Текст сразу под ненумерованным заголовком — абзац без номера.
            counter += 1
            current = _Item("paragraph", None, f"p{counter}", line, start, end)
            items.append(current)
            continue
        current.add(line, end)

    title = " ".join(title_lines) if title_lines else None
    if not any(it.kind == "numbered" for it in items):
        warnings.append("нумерация пунктов не найдена: документ разбит на абзацы")
        return SegmentResult(title, _paragraph_fallback(text), warnings)

    clauses = _to_clauses(items, preamble)
    return SegmentResult(title, _dedupe_ids(clauses, warnings), warnings)


def _clause(it: _Item, cid: str, text: str, **kwargs) -> Clause:
    return Clause(
        id=cid,
        text=text,
        start=it.start,
        end=it.end,
        lang=detect_language(text, CLAUSE_THRESHOLD),
        **kwargs,
    )


def _to_clauses(items: list[_Item], preamble: _Item | None) -> list[Clause]:
    numbered = [it for it in items if it.kind == "numbered"]
    ids = {it.id for it in numbered}
    parents = {
        f"{it.prefix}{'.'.join(map(str, it.path[:k]))}"
        for it in numbered
        if it.path is not None
        for k in range(1, len(it.path))
    }

    clauses: list[Clause] = []
    if preamble is not None:
        clauses.append(_clause(preamble, "preamble", preamble.body, kind="preamble", level=0))

    section_titles: dict[str, str] = {}
    running_title: str | None = None
    for it in items:
        if it.kind == "heading":
            running_title = it.head
            clauses.append(_clause(it, it.id, it.head, kind="heading", level=0))
            continue
        if it.kind == "paragraph":
            clauses.append(
                _clause(it, it.id, it.body, kind="clause", level=1, section_title=running_title)
            )
            continue
        if it.kind == "requisites":
            clauses.append(
                _clause(it, it.id or "req", it.body, number=it.number, kind="requisites", level=1)
            )
            continue

        assert it.path is not None
        cid = it.id
        section_id = f"{it.prefix}{it.path[0]}"
        parent = f"{it.prefix}{'.'.join(map(str, it.path[:-1]))}" if len(it.path) > 1 else None
        head, lines = it.head, list(it.lines)
        if not head and lines and _heading_like(lines[0]):
            # «Статья 5.» на одной строке, название раздела — на следующей.
            head, lines = lines[0], lines[1:]
        top_heading = len(it.path) == 1 and _looks_like_title(head, lines[0] if lines else None)

        if top_heading:
            section_titles[section_id] = head
            running_title = head
        title = section_titles.get(section_id, running_title)
        common = {"number": it.number, "section_id": section_id, "section_title": title}

        if top_heading and cid in parents:
            clauses.append(_clause(it, cid, head, kind="heading", level=1, **common))
            if lines:
                # Абзац между заголовком раздела и его первым подпунктом.
                clauses.append(
                    _clause(
                        it,
                        f"{cid}.0",
                        _join_lines(lines),
                        kind="clause",
                        level=2,
                        parent_id=cid,
                        section_id=section_id,
                        section_title=title,
                    )
                )
            continue

        if top_heading and lines:
            # «7. ФОРС-МАЖОР» и под ним абзацы без номера: условие — абзацы,
            # заголовок уходит в section_title.
            text = _join_lines(lines)
        else:
            text = _join_lines([head, *lines]) if head else _join_lines(lines)

        clauses.append(
            _clause(
                it,
                cid,
                text,
                kind="clause",
                level=len(it.path),
                parent_id=parent if parent in ids else None,
                **common,
            )
        )
    return clauses


def _paragraph_fallback(text: str) -> list[Clause]:
    clauses = []
    offset = 0
    n = 0
    for block in re.split(r"(\n\s*\n)", text):
        if block.strip() and not block.isspace():
            n += 1
            body = " ".join(block.split())
            start = offset + (len(block) - len(block.lstrip()))
            clauses.append(
                Clause(
                    id=f"p{n}",
                    kind="clause",
                    level=1,
                    text=body,
                    start=start,
                    end=offset + len(block.rstrip()),
                    lang=detect_language(body, CLAUSE_THRESHOLD),
                )
            )
        offset += len(block)
    return clauses


def _dedupe_ids(clauses: list[Clause], warnings: list[str]) -> list[Clause]:
    seen: dict[str, int] = {}
    for c in clauses:
        if c.id in seen:
            seen[c.id] += 1
            new_id = f"{c.id}~{seen[c.id]}"
            warnings.append(f"повтор номера пункта {c.id}: переименован в {new_id}")
            c.id = new_id
        else:
            seen[c.id] = 1
    return clauses
