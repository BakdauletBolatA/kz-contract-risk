# Ошибки: grok:grok-4-fast-non-reasoning на hard (20261004T180640Z__hard__grok_grok-4-fast-non-reasoning)

## termination_notice_days (3)

- `hw_lease_kk_01` hallucinated: эталон `None` → модель `15`
- `st_lease_01` missed: эталон `5` → модель `None`
- `st_lease_02_clean` missed: эталон `30` → модель `None`

## term_months (1)

- `hw_lease_01` hallucinated: эталон `None` → модель `11`

## price_amount (1)

- `hw_lease_01` hallucinated: эталон `None` → модель `247500.0`

## price_period (1)

- `hw_lease_01` hallucinated: эталон `None` → модель `monthly`

## parties.name (1)

- `hw_lease_01` wrong: эталон [{'role': 'landlord', 'name': 'ТОО «Есиль Бизнес Центр»', 'bin': '000000000017'}, {'role': 'tenant', 'name': 'ИП Калиев Д.С.', 'bin': '000000000026'}] → модель [{'role': 'landlord', 'name': 'Товарищество с ограниченной ответственностью «Есиль Бизнес Центр»', 'bin': '000000000017'}, {'role': 'tenant', 'name': 'индивидуальный предприниматель Калиев Д.С.', 'bin': '000000000026'}]

## payment_deadline_days (1)

- `hw_works_02_clean` missed: эталон `15` → модель `None`
