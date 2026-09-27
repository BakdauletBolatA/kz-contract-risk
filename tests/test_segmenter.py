"""Сегментатор: нумерация, иерархия, заголовки, перенесённые строки."""

import pytest

from contract_risk.ingestion import parse_text
from contract_risk.ingestion.contract_type import detect_contract_type
from contract_risk.ingestion.language import detect_language
from contract_risk.ingestion.normalize import normalize_text, strip_repeated_lines
from contract_risk.ingestion.segmenter import is_successor, segment
from contract_risk.schemas import ContractType, Language

LEASE = """ДОГОВОР АРЕНДЫ НЕЖИЛОГО ПОМЕЩЕНИЯ
№ 15/2026
г. Алматы «1» сентября 2026 г.
ТОО «Бизнес Центр», именуемое в дальнейшем «Арендодатель», и ИП «Асан», именуемый в дальнейшем «Арендатор», заключили настоящий договор:

1. ПРЕДМЕТ ДОГОВОРА
1.1. Арендодатель передает, а Арендатор принимает во временное пользование помещение.
1.2. Помещение используется под офис.
2. АРЕНДНАЯ ПЛАТА
2.1. Арендная плата составляет 450 000 тенге в месяц и вносится не позднее
10 числа текущего месяца.
2.2. Арендодатель вправе изменить размер арендной платы, уведомив Арендатора за
15 (пятнадцать) дней.
2.2.1. Изменение оформляется письмом.
2.3. Арендатор обязан:
а) своевременно вносить плату;
б) содержать помещение в порядке.
3. Ответственность сторон
3.1. За просрочку платежа Арендатор уплачивает пеню 1% за каждый день.
4. ФОРС-МАЖОР
Стороны освобождаются от ответственности при обстоятельствах непреодолимой силы.
5. АДРЕСА И РЕКВИЗИТЫ СТОРОН
Арендодатель: ТОО «Бизнес Центр», БИН 123456789012
Арендатор: ИП Асан, ИИН 900101300123
"""


@pytest.fixture(scope="module")
def lease():
    return parse_text(LEASE, "lease")


def ids(doc, kind="clause"):
    return [c.id for c in doc.clauses if c.kind == kind]


def test_title_and_preamble(lease):
    assert lease.title == "ДОГОВОР АРЕНДЫ НЕЖИЛОГО ПОМЕЩЕНИЯ № 15/2026"
    preamble = lease.clause("preamble")
    assert preamble.kind == "preamble"
    assert preamble.text.startswith("г. Алматы")
    assert "именуемое в дальнейшем «Арендодатель»" in preamble.text


def test_numbered_clauses_and_hierarchy(lease):
    assert ids(lease) == ["1.1", "1.2", "2.1", "2.2", "2.2.1", "2.3", "3.1", "4"]
    assert ids(lease, "heading") == ["1", "2", "3"]
    sub = lease.clause("2.2.1")
    assert (sub.level, sub.parent_id, sub.section_id) == (3, "2.2", "2")
    assert lease.clause("2.1").parent_id == "2"
    assert lease.clause("3.1").section_title == "Ответственность сторон"


def test_wrapped_line_starting_with_number_is_continuation(lease):
    # «10 числа…» и «15 (пятнадцать) дней» — продолжение, а не пункты 10 и 15.
    assert lease.clause("2.1").text.endswith("не позднее 10 числа текущего месяца.")
    assert "за 15 (пятнадцать) дней" in lease.clause("2.2").text


def test_enumeration_stays_inside_clause(lease):
    assert lease.clause("2.3").text == (
        "Арендатор обязан:\nа) своевременно вносить плату;\nб) содержать помещение в порядке."
    )


def test_heading_with_unnumbered_body_becomes_clause(lease):
    fm = lease.clause("4")
    assert fm.kind == "clause"
    assert fm.section_title == "ФОРС-МАЖОР"
    assert fm.text.startswith("Стороны освобождаются")


def test_requisites_are_not_analysable(lease):
    req = lease.clause("5")
    assert req.kind == "requisites"
    assert "ИИН" in req.text
    assert all("ИИН" not in c.text for c in lease.analysable_clauses)


def test_offsets_point_into_document_text(lease):
    c = lease.clause("3.1")
    assert lease.text[c.start : c.end].startswith("3.1. За просрочку")


def test_is_successor_rules():
    assert is_successor(None, (1,))
    assert is_successor(None, (1, 1))
    assert not is_successor(None, (15,))
    assert is_successor((4, 2), (4, 3))
    assert is_successor((4, 2), (4, 2, 1))
    assert is_successor((4, 2, 1), (4, 3))
    assert is_successor((4, 3), (5,))
    assert is_successor((4, 3), (5, 1))
    assert is_successor((4, 3), (4, 5))  # один пропущенный номер допустим
    assert not is_successor((4, 3), (4, 9))
    assert not is_successor((4, 3), (4, 3))
    assert not is_successor((4, 3), (15,))


def test_article_form_restarts_numbering_inside_article():
    doc = parse_text(
        "ДОГОВОР ПОСТАВКИ\n"
        "Статья 1. Предмет\n"
        "1. Поставщик поставляет товар.\n"
        "2. Покупатель принимает и оплачивает товар.\n"
        "Статья 2. Цена\n"
        "1. Цена указана в спецификации.\n",
        "s",
    )
    assert ids(doc) == ["1.1", "1.2", "2.1"]
    assert doc.clause("2.1").section_title == "Цена"


def test_kazakh_contract_segments_and_is_detected_as_kk():
    doc = parse_text(
        "ҮЙ-ЖАЙДЫ ЖАЛҒА АЛУ ШАРТЫ\n"
        "1. ШАРТТЫҢ МӘНІ\n"
        "1.1. Жалға беруші Жалға алушыға үй-жайды уақытша пайдалануға береді.\n"
        "2. ТАРАПТАРДЫҢ ЖАУАПКЕРШІЛІГІ\n"
        "2.1. Жалға алушы төлемді кешіктіргені үшін әрбір күнге 1% өсімпұл төлейді.\n",
        "kk",
    )
    assert doc.language == Language.KK
    assert ids(doc) == ["1.1", "2.1"]
    assert doc.clause("2.1").lang == Language.KK
    assert doc.contract_type == ContractType.LEASE


def test_kazakh_section_form():
    doc = parse_text(
        "ШАРТ\n1-бап. Жалпы ережелер\n1. Тараптар келісті.\n2-бап. Төлем\n1. Төлем жүргізіледі.\n",
        "kk2",
    )
    assert ids(doc) == ["1.1", "2.1"]


def test_appendix_restarts_numbering_with_prefix():
    doc = parse_text(
        "ДОГОВОР\n1. Предмет\n1.1. Текст.\n1.2. Текст.\nПриложение № 2\n1. Спецификация товара.\n",
        "a",
    )
    assert "прил2.1" in ids(doc)


def test_unnumbered_contract_falls_back_to_paragraphs():
    doc = parse_text("Первый абзац договора.\n\nВторой абзац договора.\n", "p")
    assert ids(doc) == ["p1", "p2"]
    assert any("нумерация" in w for w in doc.warnings)


def test_unnumbered_uppercase_headings_set_section_title():
    doc = parse_text(
        "ДОГОВОР ПОДРЯДА\nПреамбула.\n1.1. Подрядчик выполняет работы.\n"
        "ОТВЕТСТВЕННОСТЬ СТОРОН\n1.2. Заказчик уплачивает неустойку.\n",
        "w",
    )
    assert doc.clause("1.2").section_title == "ОТВЕТСТВЕННОСТЬ СТОРОН"


def test_number_without_space_before_capital():
    result = segment("ДОГОВОР\n1.1.Арендатор обязан платить.\n1.2.Арендодатель обязан.\n")
    assert [c.id for c in result.clauses if c.kind == "clause"] == ["1.1", "1.2"]


def test_normalize_hyphenation_page_markers_and_spaces():
    raw = "Стороны несут ответ-\nственность  по​ договору.\nСтраница 2 из 5\n- 3 -\n"
    assert normalize_text(raw) == "Стороны несут ответственность по договору.\n"


def test_strip_repeated_lines_removes_headers_only_with_enough_pages():
    pages = [f"ТОО «Колонтитул»\nтекст страницы {i}" for i in range(4)]
    assert all("Колонтитул" not in p for p in strip_repeated_lines(pages))
    assert strip_repeated_lines(pages[:2]) == pages[:2]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Арендатор уплачивает пеню за каждый день просрочки.", Language.RU),
        ("Жалға алушы өсімпұл төлейді.", Language.KK),
        # казахский топоним в русском тексте не делает документ казахским
        (
            "Помещение расположено по адресу: г. Алматы, ул. Құрманғазы, 12. "
            "Арендатор обязуется использовать помещение по назначению и своевременно "
            "вносить арендную плату в размере, установленном настоящим договором.",
            Language.RU,
        ),
    ],
)
def test_language_detection(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("ДОГОВОР АРЕНДЫ", ContractType.LEASE),
        ("ДОГОВОР ПОСТАВКИ № 7", ContractType.SUPPLY),
        ("ДОГОВОР ПОДРЯДА", ContractType.WORKS),
        ("ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ УСЛУГ", ContractType.WORKS),
        ("ТАУАР ЖЕТКІЗУ ШАРТЫ", ContractType.SUPPLY),
        ("СОГЛАШЕНИЕ", None),
    ],
)
def test_contract_type(title, expected):
    assert detect_contract_type("", title) == expected


def test_reference_to_clause_after_line_break_is_not_a_new_clause():
    doc = parse_text(
        "ДОГОВОР\n1. Общие положения\n1.1. Субаренда допускается в порядке, предусмотренном п.\n"
        "1.2 настоящего Договора, с согласия Арендодателя.\n1.2. Согласие дается письменно.\n",
        "r",
    )
    assert ids(doc) == ["1.1", "1.2"]
    assert doc.clause("1.1").text.endswith("с согласия Арендодателя.")
