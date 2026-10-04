# Ошибки: ollama:qwen2.5:7b на hard (20261004T185337Z__hard__ollama_qwen2.5_7b)

## city (7)

- `hw_lease_01` wrong: эталон `Астана` → модель `г. Астана`
- `hw_supply_01` wrong: эталон `Караганда` → модель `город Караганда`
- `hw_supply_02` wrong: эталон `Усть-Каменогорск` → модель `г. Усть-Каменогорск`
- `hw_works_02_clean` wrong: эталон `Актобе` → модель `г. Актобе`
- `st_lease_01` wrong: эталон `Алматы` → модель `г. Алматы`
- `st_lease_02_clean` wrong: эталон `Павлодар` → модель `г. Павлодар`
- `st_supply_02` wrong: эталон `Караганда` → модель `г. Караганда`

## parties.role_bin (5)

- `hw_lease_01` wrong: эталон [{'role': 'landlord', 'name': 'ТОО «Есиль Бизнес Центр»', 'bin': '000000000017'}, {'role': 'tenant', 'name': 'ИП Калиев Д.С.', 'bin': '000000000026'}] → модель [{'role': 'landlord', 'name': 'ТОО «Есиль Бизнес Центр»', 'bin': '000000000017'}, {'role': 'tenant', 'name': 'ИП Калиев Д.С.', 'bin': None}]
- `hw_lease_kk_01` wrong: эталон [{'role': 'landlord', 'name': '«Оңтүстік Сауда Үйі» ЖШС', 'bin': '000000000071'}, {'role': 'tenant', 'name': '«Әлем Тігін» ЖК', 'bin': '000000000080'}] → модель [{'role': 'landlord', 'name': '«Оңтүстік Сауда Үйі» ЖШС', 'bin': None}, {'role': 'tenant', 'name': '«Әлем Тігін» ЖК', 'bin': None}]
- `hw_supply_01` wrong: эталон [{'role': 'supplier', 'name': 'ТОО «Сары-Арка Продукт»', 'bin': '000000000035'}, {'role': 'buyer', 'name': 'ИП «Мадина»', 'bin': '000000000044'}] → модель [{'role': 'supplier', 'name': 'ТОО «Сары-Арка Продукт»', 'bin': '000000000035'}, {'role': 'buyer', 'name': 'ИП «Мадина»', 'bin': None}]
- `st_lease_01` wrong: эталон [{'role': 'landlord', 'name': 'ТОО «Мега Плаза»', 'bin': '000000000135'}, {'role': 'tenant', 'name': 'ИП Жаксылыкова А.Н.', 'bin': '000000000144'}] → модель [{'role': 'landlord', 'name': 'ТОО «Мега Плаза»', 'bin': '000000000135'}, {'role': 'tenant', 'name': 'ИП Жаксылыкова А.Н.', 'bin': None}]
- `st_lease_kk_01` wrong: эталон [{'role': 'landlord', 'name': '«Ақтөбе Сауда» ЖШС', 'bin': '000000000199'}, {'role': 'tenant', 'name': '«Нұр Сұлу» ЖК', 'bin': '000000000208'}] → модель [{'role': 'landlord', 'name': '«Ақтөбе Сауда» ЖШС', 'bin': None}, {'role': 'tenant', 'name': '«Нұр Сұлу» ЖК', 'bin': None}]

## payment_deadline_days (4)

- `hw_lease_01` hallucinated: эталон `None` → модель `5`
- `hw_works_02_clean` missed: эталон `15` → модель `None`
- `st_lease_01` hallucinated: эталон `None` → модель `5`
- `st_lease_02_clean` hallucinated: эталон `None` → модель `10`

## dispute_forum (4)

- `hw_lease_01` wrong: эталон `counterparty_location_court` → модель `kz_courts`
- `hw_lease_kk_01` missed: эталон `kz_courts` → модель `None`
- `st_lease_01` wrong: эталон `kz_courts` → модель `aifc_court`
- `st_lease_kk_01` missed: эталон `kz_courts` → модель `None`

## auto_renewal (3)

- `hw_lease_01` wrong: эталон `True` → модель `False`
- `hw_lease_kk_01` wrong: эталон `True` → модель `False`
- `st_lease_01` wrong: эталон `True` → модель `False`

## termination_notice_days (3)

- `hw_lease_01` hallucinated: эталон `None` → модель `7`
- `hw_lease_kk_01` hallucinated: эталон `None` → модель `15`
- `hw_supply_02` wrong: эталон `0` → модель `1`

## term_months (2)

- `hw_lease_01` hallucinated: эталон `None` → модель `10`
- `st_lease_kk_01` hallucinated: эталон `None` → модель `12`

## payment_penalty_cap_percent (2)

- `hw_lease_01` hallucinated: эталон `None` → модель `10.0`
- `st_supply_01` hallucinated: эталон `None` → модель `10.0`

## payment_penalty_rate_percent_per_day (2)

- `hw_supply_02` hallucinated: эталон `None` → модель `0.2`
- `st_lease_01` hallucinated: эталон `None` → модель `0.0033333333333333335`

## price_amount (1)

- `hw_lease_01` hallucinated: эталон `None` → модель `243000.0`

## price_period (1)

- `hw_lease_01` hallucinated: эталон `None` → модель `monthly`

## contract_date (1)

- `st_lease_kk_01` wrong: эталон `2026-10-05` → модель `2026-05-01`
