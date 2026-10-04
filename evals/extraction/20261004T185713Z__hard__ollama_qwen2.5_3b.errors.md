# Ошибки: ollama:qwen2.5:3b на hard (20261004T185713Z__hard__ollama_qwen2.5_3b)

## Документы без валидного ответа

- `hw_lease_kk_01` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `hw_supply_01` failed: - auto_renewal: Input should be a valid boolean
- `hw_works_02_clean` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `st_supply_01` failed: - price_amount: Input should be greater than 0
- price_period: Value error, price_period задан, а price_amount — нет
- `st_supply_02` failed: - price_amount: Input should be greater than 0
- price_period: Value error, price_period задан, а price_amount — нет

## payment_deadline_days (9)

- `hw_lease_01` hallucinated: эталон `None` → модель `5`
- `hw_lease_kk_01` failed: эталон `None` → модель `—`
- `hw_supply_01` failed: эталон `None` → модель `—`
- `hw_works_02_clean` failed: эталон `15` → модель `—`
- `st_lease_01` hallucinated: эталон `None` → модель `5`
- `st_lease_02_clean` hallucinated: эталон `None` → модель `10`
- `st_lease_kk_01` hallucinated: эталон `None` → модель `30`
- `st_supply_01` failed: эталон `None` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## term_months (8)

- `hw_lease_01` hallucinated: эталон `None` → модель `12`
- `hw_lease_kk_01` failed: эталон `11` → модель `—`
- `hw_supply_01` failed: эталон `None` → модель `—`
- `hw_supply_02` hallucinated: эталон `None` → модель `12`
- `hw_works_02_clean` failed: эталон `None` → модель `—`
- `st_lease_kk_01` hallucinated: эталон `None` → модель `12`
- `st_supply_01` failed: эталон `None` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## payment_penalty_rate_percent_per_day (8)

- `hw_lease_kk_01` failed: эталон `1.0` → модель `—`
- `hw_supply_01` failed: эталон `0.3` → модель `—`
- `hw_supply_02` hallucinated: эталон `None` → модель `0.2`
- `hw_works_02_clean` failed: эталон `0.1` → модель `—`
- `st_lease_01` hallucinated: эталон `None` → модель `0.33`
- `st_lease_kk_01` missed: эталон `0.5` → модель `None`
- `st_supply_01` failed: эталон `0.5` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## termination_notice_days (7)

- `hw_lease_01` hallucinated: эталон `None` → модель `7`
- `hw_lease_kk_01` failed: эталон `None` → модель `—`
- `hw_supply_01` failed: эталон `None` → модель `—`
- `hw_works_02_clean` failed: эталон `30` → модель `—`
- `st_lease_kk_01` hallucinated: эталон `None` → модель `0`
- `st_supply_01` failed: эталон `None` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## auto_renewal (6)

- `hw_lease_01` wrong: эталон `True` → модель `False`
- `hw_lease_kk_01` failed: эталон `True` → модель `—`
- `hw_supply_01` failed: эталон `False` → модель `—`
- `hw_works_02_clean` failed: эталон `False` → модель `—`
- `st_supply_01` failed: эталон `False` → модель `—`
- `st_supply_02` failed: эталон `False` → модель `—`

## price_amount (6)

- `hw_lease_01` hallucinated: эталон `None` → модель `240000.0`
- `hw_lease_kk_01` failed: эталон `280000.0` → модель `—`
- `hw_supply_01` failed: эталон `None` → модель `—`
- `hw_works_02_clean` failed: эталон `6400000.0` → модель `—`
- `st_supply_01` failed: эталон `None` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## price_period (6)

- `hw_lease_01` hallucinated: эталон `None` → модель `monthly`
- `hw_lease_kk_01` failed: эталон `monthly` → модель `—`
- `hw_supply_01` failed: эталон `None` → модель `—`
- `hw_works_02_clean` failed: эталон `total` → модель `—`
- `st_supply_01` failed: эталон `None` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## contract_number (6)

- `hw_lease_kk_01` failed: эталон `8` → модель `—`
- `hw_supply_01` failed: эталон `45-П` → модель `—`
- `hw_works_02_clean` failed: эталон `31` → модель `—`
- `st_lease_kk_01` wrong: эталон `3` → модель `ЖАЛҒА АЛУ ШАРТЫ № 3`
- `st_supply_01` failed: эталон `77/С` → модель `—`
- `st_supply_02` failed: эталон `9/К` → модель `—`

## contract_date (6)

- `hw_lease_kk_01` failed: эталон `2026-04-20` → модель `—`
- `hw_supply_01` failed: эталон `2026-03-03` → модель `—`
- `hw_works_02_clean` failed: эталон `2026-06-02` → модель `—`
- `st_lease_kk_01` wrong: эталон `2026-10-05` → модель `2026-05-02`
- `st_supply_01` failed: эталон `2026-10-12` → модель `—`
- `st_supply_02` failed: эталон `2026-10-25` → модель `—`

## payment_penalty_cap_percent (6)

- `hw_lease_kk_01` failed: эталон `None` → модель `—`
- `hw_supply_01` failed: эталон `None` → модель `—`
- `hw_works_02_clean` failed: эталон `10.0` → модель `—`
- `st_lease_02_clean` missed: эталон `10.0` → модель `None`
- `st_supply_01` failed: эталон `None` → модель `—`
- `st_supply_02` failed: эталон `None` → модель `—`

## contract_type (5)

- `hw_lease_kk_01` failed: эталон `lease` → модель `—`
- `hw_supply_01` failed: эталон `supply` → модель `—`
- `hw_works_02_clean` failed: эталон `works` → модель `—`
- `st_supply_01` failed: эталон `supply` → модель `—`
- `st_supply_02` failed: эталон `supply` → модель `—`

## city (5)

- `hw_lease_kk_01` failed: эталон `Шымкент` → модель `—`
- `hw_supply_01` failed: эталон `Караганда` → модель `—`
- `hw_works_02_clean` failed: эталон `Актобе` → модель `—`
- `st_supply_01` failed: эталон `Шымкент` → модель `—`
- `st_supply_02` failed: эталон `Караганда` → модель `—`

## dispute_forum (5)

- `hw_lease_kk_01` failed: эталон `kz_courts` → модель `—`
- `hw_supply_01` failed: эталон `kz_courts` → модель `—`
- `hw_works_02_clean` failed: эталон `kz_courts` → модель `—`
- `st_supply_01` failed: эталон `counterparty_location_court` → модель `—`
- `st_supply_02` failed: эталон `kz_courts` → модель `—`

## parties.role_bin (5)

- `hw_lease_kk_01` failed: эталон [{'role': 'landlord', 'name': '«Оңтүстік Сауда Үйі» ЖШС', 'bin': '000000000071'}, {'role': 'tenant', 'name': '«Әлем Тігін» ЖК', 'bin': '000000000080'}] → модель None
- `hw_supply_01` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Сары-Арка Продукт»', 'bin': '000000000035'}, {'role': 'buyer', 'name': 'ИП «Мадина»', 'bin': '000000000044'}] → модель None
- `hw_works_02_clean` failed: эталон [{'role': 'customer', 'name': 'ТОО «Ақтөбе Логистика»', 'bin': '000000000117'}, {'role': 'contractor', 'name': 'ТОО «Батыс Құрылыс»', 'bin': '000000000126'}] → модель None
- `st_supply_01` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Юг Опт Трейд»', 'bin': '000000000153'}, {'role': 'buyer', 'name': 'ТОО «Магазин у дома»', 'bin': '000000000162'}] → модель None
- `st_supply_02` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Сарыарка Молоко»', 'bin': '000000000217'}, {'role': 'buyer', 'name': 'ТОО «Сеть Минимаркетов Береке»', 'bin': '000000000226'}] → модель None

## parties.name (5)

- `hw_lease_kk_01` failed: эталон [{'role': 'landlord', 'name': '«Оңтүстік Сауда Үйі» ЖШС', 'bin': '000000000071'}, {'role': 'tenant', 'name': '«Әлем Тігін» ЖК', 'bin': '000000000080'}] → модель None
- `hw_supply_01` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Сары-Арка Продукт»', 'bin': '000000000035'}, {'role': 'buyer', 'name': 'ИП «Мадина»', 'bin': '000000000044'}] → модель None
- `hw_works_02_clean` failed: эталон [{'role': 'customer', 'name': 'ТОО «Ақтөбе Логистика»', 'bin': '000000000117'}, {'role': 'contractor', 'name': 'ТОО «Батыс Құрылыс»', 'bin': '000000000126'}] → модель None
- `st_supply_01` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Юг Опт Трейд»', 'bin': '000000000153'}, {'role': 'buyer', 'name': 'ТОО «Магазин у дома»', 'bin': '000000000162'}] → модель None
- `st_supply_02` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Сарыарка Молоко»', 'bin': '000000000217'}, {'role': 'buyer', 'name': 'ТОО «Сеть Минимаркетов Береке»', 'bin': '000000000226'}] → модель None
