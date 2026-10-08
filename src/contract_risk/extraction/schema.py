"""Схема извлечения: что именно мы требуем от модели.

Правило для всех полей: `None` значит «в тексте этого нет». Модель, которая
вместо `None` подставляет правдоподобное значение, галлюцинирует — это
отдельная метрика (`hallucinated` в eval). Исключение — `auto_renewal`:
у него два честных состояния, продлевается или нет.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["landlord", "tenant", "supplier", "buyer", "contractor", "customer"]
PricePeriod = Literal["monthly", "total"]
DisputeForum = Literal[
    "kz_courts",  # суд по законодательству РК, без привязки к месту нахождения стороны
    "counterparty_location_court",  # суд по месту нахождения одной из сторон
    "aifc_court",  # Суд МФЦА
    "foreign_arbitration",  # зарубежный арбитраж (LCIA и т.п.)
]

_DIGITS12 = re.compile(r"^\d{12}$")


class Party(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role = Field(description="Роль стороны в договоре")
    name: str = Field(
        min_length=2, description="Название организации как в тексте, с формой (ТОО, ИП)"
    )
    bin: str | None = Field(
        default=None,
        description="БИН/ИИН/БСН — 12 цифр из реквизитов; null, если у стороны не указан",
    )

    @field_validator("bin")
    @classmethod
    def _bin_is_12_digits(cls, v: str | None) -> str | None:
        if v is not None and not _DIGITS12.match(v):
            raise ValueError("БИН должен состоять ровно из 12 цифр")
        return v


class ContractExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_type: Literal["lease", "supply", "works"] = Field(
        description="lease — аренда, supply — поставка, works — подряд"
    )
    contract_number: str | None = Field(description="Номер договора без знака №")
    contract_date: date | None = Field(description="Дата заключения, YYYY-MM-DD")
    city: str | None = Field(description="Город заключения договора")
    parties: list[Party] = Field(min_length=2, max_length=2, description="Ровно две стороны")
    term_months: int | None = Field(
        ge=1, le=600, description="Срок действия в месяцах, если указан числом"
    )
    auto_renewal: bool = Field(
        description="true, если договор продлевается автоматически при отсутствии возражений"
    )
    price_amount: float | None = Field(
        gt=0, description="Сумма в тенге, если названа в тексте (не в приложении)"
    )
    price_period: PricePeriod | None = Field(
        description="monthly — сумма за месяц, total — общая; null, если суммы нет"
    )
    payment_deadline_days: int | None = Field(
        ge=0, le=365, description="Срок оплаты в днях после события; null, если задан числом месяца"
    )
    payment_penalty_rate_percent_per_day: float | None = Field(
        ge=0, le=100, description="Пеня за просрочку ОПЛАТЫ, % в день; null, если её нет"
    )
    payment_penalty_cap_percent: float | None = Field(
        ge=0,
        le=1000,
        description="Предельный размер пени за просрочку оплаты, %; null, если без потолка",
    )
    dispute_forum: DisputeForum | None = Field(description="Где разрешаются споры")
    termination_notice_days: int | None = Field(
        ge=0,
        le=365,
        description="Дней до расторжения; 0 — без уведомления; null — не сказано",
    )

    @field_validator("contract_date")
    @classmethod
    def _plausible_date(cls, v: date | None) -> date | None:
        if v is not None and not (2000 <= v.year <= 2100):
            raise ValueError("дата договора вне 2000–2100")
        return v

    @field_validator("parties")
    @classmethod
    def _distinct_roles(cls, v: list[Party]) -> list[Party]:
        if v[0].role == v[1].role:
            raise ValueError("у двух сторон не может быть одинаковая роль")
        return v

    @field_validator("price_period")
    @classmethod
    def _period_needs_amount(cls, v, info):  # noqa: ANN001, ANN201
        if v is not None and info.data.get("price_amount") is None:
            raise ValueError("price_period задан, а price_amount — нет")
        return v


EXTRACTION_FIELDS: tuple[str, ...] = tuple(
    name for name in ContractExtraction.model_fields if name != "parties"
)
