# Ошибки: ollama:qwen2.5:7b на test (20261004T185045Z__test__ollama_qwen2.5_7b)

## payment_deadline_days (19)

- `lease_kk_test_002` hallucinated: эталон `None` → модель `5`
- `lease_kk_test_003` hallucinated: эталон `None` → модель `5`
- `lease_kk_test_006` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_003` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_004` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_006` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_007` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_014` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_024` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_033` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_035` hallucinated: эталон `None` → модель `5`
- `supply_ru_test_028` missed: эталон `120` → модель `None`
- `works_ru_test_004` missed: эталон `20` → модель `None`
- `works_ru_test_015` missed: эталон `20` → модель `None`
- `works_ru_test_026` missed: эталон `20` → модель `None`
- `works_ru_test_037` missed: эталон `20` → модель `None`
- `works_ru_test_038` missed: эталон `20` → модель `None`
- `works_ru_test_039` missed: эталон `20` → модель `None`
- `works_ru_test_040` missed: эталон `20` → модель `None`

## city (16)

- `lease_kk_test_003` wrong: эталон `Ақтөбе` → модель `Актобе`
- `lease_kk_test_006` wrong: эталон `Ақтөбе` → модель `Актобе`
- `lease_ru_test_003` wrong: эталон `Астана` → модель `г. Астана`
- `lease_ru_test_007` wrong: эталон `Шымкент` → модель `г. Шымкент`
- `lease_ru_test_014` wrong: эталон `Астана` → модель `г. Астана`
- `lease_ru_test_033` wrong: эталон `Астана` → модель `г. Астана`
- `lease_ru_test_035` wrong: эталон `Алматы` → модель `г. Алматы`
- `supply_ru_test_004` wrong: эталон `Усть-Каменогорск` → модель `г. Усть-Каменогорск`
- `supply_ru_test_005` wrong: эталон `Костанай` → модель `г. Костанай`
- `supply_ru_test_006` wrong: эталон `Алматы` → модель `г. Алматы`
- `supply_ru_test_028` wrong: эталон `Астана` → модель `г. Астана`
- `works_ru_test_004` wrong: эталон `Алматы` → модель `г. Алматы`
- `works_ru_test_015` wrong: эталон `Алматы` → модель `г. Алматы`
- `works_ru_test_026` wrong: эталон `Атырау` → модель `г. Атырау`
- `works_ru_test_039` wrong: эталон `Астана` → модель `г. Астана`
- `works_ru_test_040` wrong: эталон `Астана` → модель `г. Астана`

## payment_penalty_rate_percent_per_day (8)

- `lease_kk_test_001` missed: эталон `0.05` → модель `None`
- `lease_kk_test_003` missed: эталон `1.0` → модель `None`
- `lease_kk_test_007` missed: эталон `0.05` → модель `None`
- `lease_kk_test_011` missed: эталон `0.05` → модель `None`
- `supply_ru_test_016` hallucinated: эталон `None` → модель `0.05`
- `supply_ru_test_027` hallucinated: эталон `None` → модель `0.05`
- `works_ru_test_037` hallucinated: эталон `None` → модель `0.05`
- `works_ru_test_039` hallucinated: эталон `None` → модель `0.5`

## payment_penalty_cap_percent (7)

- `lease_kk_test_001` missed: эталон `10.0` → модель `None`
- `lease_kk_test_007` missed: эталон `10.0` → модель `None`
- `lease_kk_test_011` missed: эталон `10.0` → модель `None`
- `supply_ru_test_016` hallucinated: эталон `None` → модель `10.0`
- `supply_ru_test_027` hallucinated: эталон `None` → модель `10.0`
- `works_ru_test_003` hallucinated: эталон `None` → модель `10.0`
- `works_ru_test_037` hallucinated: эталон `None` → модель `10.0`

## contract_date (6)

- `lease_kk_test_001` wrong: эталон `2026-09-03` → модель `2026-04-15`
- `lease_kk_test_002` wrong: эталон `2026-05-15` → модель `2026-04-15`
- `lease_kk_test_003` wrong: эталон `2026-03-01` → модель `2026-01-01`
- `lease_kk_test_006` wrong: эталон `2026-03-01` → модель `2026-01-01`
- `lease_kk_test_007` wrong: эталон `2026-03-01` → модель `2026-01-01`
- `lease_kk_test_011` wrong: эталон `2026-03-01` → модель `2026-01-01`

## dispute_forum (5)

- `lease_kk_test_001` missed: эталон `foreign_arbitration` → модель `None`
- `lease_kk_test_003` missed: эталон `kz_courts` → модель `None`
- `lease_kk_test_006` missed: эталон `kz_courts` → модель `None`
- `lease_kk_test_011` missed: эталон `kz_courts` → модель `None`
- `supply_ru_test_040` wrong: эталон `counterparty_location_court` → модель `kz_courts`

## termination_notice_days (2)

- `lease_kk_test_003` missed: эталон `30` → модель `None`
- `lease_kk_test_011` missed: эталон `30` → модель `None`

## price_period (2)

- `works_ru_test_038` missed: эталон `total` → модель `None`
- `works_ru_test_039` missed: эталон `total` → модель `None`

## parties.role_bin (1)

- `lease_kk_test_003` wrong: эталон [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': '510539978883'}, {'role': 'tenant', 'name': '«Сейтқали» ЖК', 'bin': '093002501523'}] → модель [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': None}, {'role': 'tenant', 'name': '«Сейтқали» ЖК', 'bin': None}]
