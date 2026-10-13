# Ошибки: ollama:qwen2.5:3b на test (20261004T182426Z__test__ollama_qwen2.5_3b)

## Документы без валидного ответа

- `lease_kk_test_003` failed: - auto_renewal: Input should be a valid boolean
- `lease_kk_test_006` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `lease_kk_test_007` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `lease_kk_test_011` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `lease_ru_test_014` failed: - auto_renewal: Input should be a valid boolean
- `lease_ru_test_033` failed: - auto_renewal: Input should be a valid boolean
- `supply_ru_test_004` failed: - price_amount: Input should be greater than 0
- `supply_ru_test_005` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `supply_ru_test_006` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `supply_ru_test_008` failed: - price_amount: Input should be greater than 0
- `supply_ru_test_016` failed: - price_amount: Input should be greater than 0
- `supply_ru_test_027` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `supply_ru_test_028` failed: - auto_renewal: Input should be a valid boolean
- price_period: Value error, price_period задан, а price_amount — нет
- `supply_ru_test_040` failed: - auto_renewal: Input should be a valid boolean
- price_period: Value error, price_period задан, а price_amount — нет
- `works_ru_test_003` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `works_ru_test_004` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `works_ru_test_015` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `works_ru_test_026` failed: - auto_renewal: Input should be a valid boolean
- `works_ru_test_037` failed: - contract_type: Field required
- contract_number: Field required
- contract_date: Field required
- city: Field required
- parties: Field required
- term_months: Field required
- auto_renewal: Field r
- `works_ru_test_038` failed: - auto_renewal: Input should be a valid boolean
- `works_ru_test_039` failed: - auto_renewal: Input should be a valid boolean

## payment_deadline_days (29)

- `lease_kk_test_001` hallucinated: эталон `None` → модель `30`
- `lease_kk_test_002` hallucinated: эталон `None` → модель `30`
- `lease_kk_test_003` failed: эталон `None` → модель `—`
- `lease_kk_test_006` failed: эталон `None` → модель `—`
- `lease_kk_test_007` failed: эталон `None` → модель `—`
- `lease_kk_test_011` failed: эталон `None` → модель `—`
- `lease_ru_test_003` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_004` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_006` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_007` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_014` failed: эталон `None` → модель `—`
- `lease_ru_test_024` hallucinated: эталон `None` → модель `5`
- `lease_ru_test_033` failed: эталон `None` → модель `—`
- `lease_ru_test_035` hallucinated: эталон `None` → модель `5`
- `supply_ru_test_004` failed: эталон `20` → модель `—`
- `supply_ru_test_005` failed: эталон `None` → модель `—`
- `supply_ru_test_006` failed: эталон `75` → модель `—`
- `supply_ru_test_008` failed: эталон `20` → модель `—`
- `supply_ru_test_016` failed: эталон `20` → модель `—`
- `supply_ru_test_027` failed: эталон `20` → модель `—`
- `supply_ru_test_028` failed: эталон `120` → модель `—`
- `supply_ru_test_040` failed: эталон `20` → модель `—`
- `works_ru_test_003` failed: эталон `150` → модель `—`
- `works_ru_test_004` failed: эталон `20` → модель `—`
- `works_ru_test_015` failed: эталон `20` → модель `—`
- `works_ru_test_026` failed: эталон `20` → модель `—`
- `works_ru_test_037` failed: эталон `20` → модель `—`
- `works_ru_test_038` failed: эталон `20` → модель `—`
- `works_ru_test_039` failed: эталон `20` → модель `—`

## contract_number (25)

- `lease_kk_test_001` wrong: эталон `234` → модель `ДД-234`
- `lease_kk_test_003` failed: эталон `226` → модель `—`
- `lease_kk_test_006` failed: эталон `101` → модель `—`
- `lease_kk_test_007` failed: эталон `129` → модель `—`
- `lease_kk_test_011` failed: эталон `37` → модель `—`
- `lease_ru_test_003` wrong: эталон `207` → модель `ДОГОВОР АРЕНДЫ НЕЖИЛОГО ПОМЕЩЕНИЯ № 207`
- `lease_ru_test_004` wrong: эталон `23` → модель `ДОГОВОР АРЕНДЫ НЕЖИЛОГО ПОМЕЩЕНИЯ № 23`
- `lease_ru_test_014` failed: эталон `176` → модель `—`
- `lease_ru_test_033` failed: эталон `88` → модель `—`
- `supply_ru_test_004` failed: эталон `129` → модель `—`
- `supply_ru_test_005` failed: эталон `164` → модель `—`
- `supply_ru_test_006` failed: эталон `1` → модель `—`
- `supply_ru_test_008` failed: эталон `175` → модель `—`
- `supply_ru_test_016` failed: эталон `25` → модель `—`
- `supply_ru_test_027` failed: эталон `227` → модель `—`
- `supply_ru_test_028` failed: эталон `5` → модель `—`
- `supply_ru_test_040` failed: эталон `129` → модель `—`
- `works_ru_test_003` failed: эталон `144` → модель `—`
- `works_ru_test_004` failed: эталон `146` → модель `—`
- `works_ru_test_015` failed: эталон `131` → модель `—`
- `works_ru_test_026` failed: эталон `181` → модель `—`
- `works_ru_test_037` failed: эталон `29` → модель `—`
- `works_ru_test_038` failed: эталон `224` → модель `—`
- `works_ru_test_039` failed: эталон `245` → модель `—`
- `works_ru_test_040` wrong: эталон `100` → модель `ДОГОВОР ПОДРЯДА № 100`

## payment_penalty_cap_percent (24)

- `lease_kk_test_001` missed: эталон `10.0` → модель `None`
- `lease_kk_test_002` missed: эталон `10.0` → модель `None`
- `lease_kk_test_003` failed: эталон `None` → модель `—`
- `lease_kk_test_006` failed: эталон `10.0` → модель `—`
- `lease_kk_test_007` failed: эталон `10.0` → модель `—`
- `lease_kk_test_011` failed: эталон `10.0` → модель `—`
- `lease_ru_test_014` failed: эталон `10.0` → модель `—`
- `lease_ru_test_033` failed: эталон `10.0` → модель `—`
- `supply_ru_test_004` failed: эталон `10.0` → модель `—`
- `supply_ru_test_005` failed: эталон `10.0` → модель `—`
- `supply_ru_test_006` failed: эталон `None` → модель `—`
- `supply_ru_test_008` failed: эталон `None` → модель `—`
- `supply_ru_test_016` failed: эталон `None` → модель `—`
- `supply_ru_test_027` failed: эталон `None` → модель `—`
- `supply_ru_test_028` failed: эталон `10.0` → модель `—`
- `supply_ru_test_040` failed: эталон `10.0` → модель `—`
- `works_ru_test_003` failed: эталон `None` → модель `—`
- `works_ru_test_004` failed: эталон `None` → модель `—`
- `works_ru_test_015` failed: эталон `10.0` → модель `—`
- `works_ru_test_026` failed: эталон `None` → модель `—`
- `works_ru_test_037` failed: эталон `None` → модель `—`
- `works_ru_test_038` failed: эталон `10.0` → модель `—`
- `works_ru_test_039` failed: эталон `None` → модель `—`
- `works_ru_test_040` missed: эталон `10.0` → модель `None`

## contract_date (23)

- `lease_kk_test_001` wrong: эталон `2026-09-03` → модель `2026-03-24`
- `lease_kk_test_002` wrong: эталон `2026-05-15` → модель `2026-01-15`
- `lease_kk_test_003` failed: эталон `2026-03-01` → модель `—`
- `lease_kk_test_006` failed: эталон `2026-03-01` → модель `—`
- `lease_kk_test_007` failed: эталон `2026-03-01` → модель `—`
- `lease_kk_test_011` failed: эталон `2026-03-01` → модель `—`
- `lease_ru_test_014` failed: эталон `2026-09-20` → модель `—`
- `lease_ru_test_033` failed: эталон `2026-11-12` → модель `—`
- `supply_ru_test_004` failed: эталон `2026-10-21` → модель `—`
- `supply_ru_test_005` failed: эталон `2026-08-21` → модель `—`
- `supply_ru_test_006` failed: эталон `2026-08-21` → модель `—`
- `supply_ru_test_008` failed: эталон `2026-12-30` → модель `—`
- `supply_ru_test_016` failed: эталон `2026-10-30` → модель `—`
- `supply_ru_test_027` failed: эталон `2026-08-14` → модель `—`
- `supply_ru_test_028` failed: эталон `2026-12-30` → модель `—`
- `supply_ru_test_040` failed: эталон `2026-10-30` → модель `—`
- `works_ru_test_003` failed: эталон `2026-09-16` → модель `—`
- `works_ru_test_004` failed: эталон `2026-01-16` → модель `—`
- `works_ru_test_015` failed: эталон `2026-11-16` → модель `—`
- `works_ru_test_026` failed: эталон `2026-03-03` → модель `—`
- `works_ru_test_037` failed: эталон `2026-07-16` → модель `—`
- `works_ru_test_038` failed: эталон `2026-05-24` → модель `—`
- `works_ru_test_039` failed: эталон `2026-09-11` → модель `—`

## payment_penalty_rate_percent_per_day (23)

- `lease_kk_test_001` missed: эталон `0.05` → модель `None`
- `lease_kk_test_002` missed: эталон `0.05` → модель `None`
- `lease_kk_test_003` failed: эталон `1.0` → модель `—`
- `lease_kk_test_006` failed: эталон `0.05` → модель `—`
- `lease_kk_test_007` failed: эталон `0.05` → модель `—`
- `lease_kk_test_011` failed: эталон `0.05` → модель `—`
- `lease_ru_test_014` failed: эталон `0.05` → модель `—`
- `lease_ru_test_033` failed: эталон `0.05` → модель `—`
- `supply_ru_test_004` failed: эталон `0.05` → модель `—`
- `supply_ru_test_005` failed: эталон `0.05` → модель `—`
- `supply_ru_test_006` failed: эталон `None` → модель `—`
- `supply_ru_test_008` failed: эталон `None` → модель `—`
- `supply_ru_test_016` failed: эталон `None` → модель `—`
- `supply_ru_test_027` failed: эталон `None` → модель `—`
- `supply_ru_test_028` failed: эталон `0.05` → модель `—`
- `supply_ru_test_040` failed: эталон `0.05` → модель `—`
- `works_ru_test_003` failed: эталон `0.1` → модель `—`
- `works_ru_test_004` failed: эталон `None` → модель `—`
- `works_ru_test_015` failed: эталон `0.05` → модель `—`
- `works_ru_test_026` failed: эталон `0.1` → модель `—`
- `works_ru_test_037` failed: эталон `None` → модель `—`
- `works_ru_test_038` failed: эталон `0.05` → модель `—`
- `works_ru_test_039` failed: эталон `None` → модель `—`

## dispute_forum (22)

- `lease_kk_test_001` wrong: эталон `foreign_arbitration` → модель `kz_courts`
- `lease_kk_test_003` failed: эталон `kz_courts` → модель `—`
- `lease_kk_test_006` failed: эталон `kz_courts` → модель `—`
- `lease_kk_test_007` failed: эталон `kz_courts` → модель `—`
- `lease_kk_test_011` failed: эталон `kz_courts` → модель `—`
- `lease_ru_test_014` failed: эталон `kz_courts` → модель `—`
- `lease_ru_test_033` failed: эталон `kz_courts` → модель `—`
- `supply_ru_test_004` failed: эталон `kz_courts` → модель `—`
- `supply_ru_test_005` failed: эталон `kz_courts` → модель `—`
- `supply_ru_test_006` failed: эталон `kz_courts` → модель `—`
- `supply_ru_test_008` failed: эталон `kz_courts` → модель `—`
- `supply_ru_test_016` failed: эталон `foreign_arbitration` → модель `—`
- `supply_ru_test_027` failed: эталон `counterparty_location_court` → модель `—`
- `supply_ru_test_028` failed: эталон `kz_courts` → модель `—`
- `supply_ru_test_040` failed: эталон `counterparty_location_court` → модель `—`
- `works_ru_test_003` failed: эталон `kz_courts` → модель `—`
- `works_ru_test_004` failed: эталон `counterparty_location_court` → модель `—`
- `works_ru_test_015` failed: эталон `kz_courts` → модель `—`
- `works_ru_test_026` failed: эталон `kz_courts` → модель `—`
- `works_ru_test_037` failed: эталон `kz_courts` → модель `—`
- `works_ru_test_038` failed: эталон `kz_courts` → модель `—`
- `works_ru_test_039` failed: эталон `kz_courts` → модель `—`

## termination_notice_days (22)

- `lease_kk_test_001` hallucinated: эталон `None` → модель `30`
- `lease_kk_test_003` failed: эталон `30` → модель `—`
- `lease_kk_test_006` failed: эталон `None` → модель `—`
- `lease_kk_test_007` failed: эталон `None` → модель `—`
- `lease_kk_test_011` failed: эталон `30` → модель `—`
- `lease_ru_test_014` failed: эталон `30` → модель `—`
- `lease_ru_test_033` failed: эталон `30` → модель `—`
- `supply_ru_test_004` failed: эталон `30` → модель `—`
- `supply_ru_test_005` failed: эталон `30` → модель `—`
- `supply_ru_test_006` failed: эталон `30` → модель `—`
- `supply_ru_test_008` failed: эталон `5` → модель `—`
- `supply_ru_test_016` failed: эталон `30` → модель `—`
- `supply_ru_test_027` failed: эталон `5` → модель `—`
- `supply_ru_test_028` failed: эталон `30` → модель `—`
- `supply_ru_test_040` failed: эталон `30` → модель `—`
- `works_ru_test_003` failed: эталон `7` → модель `—`
- `works_ru_test_004` failed: эталон `30` → модель `—`
- `works_ru_test_015` failed: эталон `30` → модель `—`
- `works_ru_test_026` failed: эталон `7` → модель `—`
- `works_ru_test_037` failed: эталон `30` → модель `—`
- `works_ru_test_038` failed: эталон `30` → модель `—`
- `works_ru_test_039` failed: эталон `30` → модель `—`

## parties.name (22)

- `lease_kk_test_002` wrong: эталон [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': '144454351711'}, {'role': 'tenant', 'name': '«Кофе Нүкте» ЖШС', 'bin': '622262689272'}] → модель [{'role': 'landlord', 'name': 'Жалға беруші «Алтын Сарай» ЖШС', 'bin': '144454351711'}, {'role': 'tenant', 'name': 'Жалға алушы «Кофе Нүкте» ЖШС', 'bin': '622262689272'}]
- `lease_kk_test_003` failed: эталон [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': '510539978883'}, {'role': 'tenant', 'name': '«Сейтқали» ЖК', 'bin': '093002501523'}] → модель None
- `lease_kk_test_006` failed: эталон [{'role': 'landlord', 'name': '«Бизнес Орталық» ЖШС', 'bin': '943914780876'}, {'role': 'tenant', 'name': '«Кофе Нүкте» ЖШС', 'bin': '845966435725'}] → модель None
- `lease_kk_test_007` failed: эталон [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': '191671761389'}, {'role': 'tenant', 'name': '«Дәріхана Денсаулық» ЖШС', 'bin': '597065763576'}] → модель None
- `lease_kk_test_011` failed: эталон [{'role': 'landlord', 'name': '«Бизнес Орталық» ЖШС', 'bin': '237255824807'}, {'role': 'tenant', 'name': '«Кофе Нүкте» ЖШС', 'bin': '994304499412'}] → модель None
- `lease_ru_test_014` failed: эталон [{'role': 'landlord', 'name': 'ТОО «Алтын Сарай»', 'bin': '912402403566'}, {'role': 'tenant', 'name': 'ТОО «Аптека Здоровье»', 'bin': '404240560475'}] → модель None
- `lease_ru_test_033` failed: эталон [{'role': 'landlord', 'name': 'ТОО «Алтын Сарай»', 'bin': '453167591985'}, {'role': 'tenant', 'name': 'ИП «Сейткали»', 'bin': '322637954236'}] → модель None
- `supply_ru_test_004` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '294127178435'}, {'role': 'buyer', 'name': 'ИП «Оразбекова»', 'bin': '097678657102'}] → модель None
- `supply_ru_test_005` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '377617678296'}, {'role': 'buyer', 'name': 'ИП «Жумабаев»', 'bin': '678378201685'}] → модель None
- `supply_ru_test_006` failed: эталон [{'role': 'supplier', 'name': 'ТОО «ТехноПоставка KZ»', 'bin': '670394999437'}, {'role': 'buyer', 'name': 'ТОО «Строй Сервис Юг»', 'bin': '606894143290'}] → модель None
- `supply_ru_test_008` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Евразия Трейд»', 'bin': '235940581287'}, {'role': 'buyer', 'name': 'ТОО «Строй Сервис Юг»', 'bin': '092406447514'}] → модель None
- `supply_ru_test_016` failed: эталон [{'role': 'supplier', 'name': 'ТОО «ТехноПоставка KZ»', 'bin': '111742554416'}, {'role': 'buyer', 'name': 'ТОО «Мини-маркет Береке»', 'bin': '540186466089'}] → модель None
- `supply_ru_test_027` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '479675693181'}, {'role': 'buyer', 'name': 'ИП «Оразбекова»', 'bin': '348287637587'}] → модель None
- `supply_ru_test_028` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '655288550881'}, {'role': 'buyer', 'name': 'ТОО «Мини-маркет Береке»', 'bin': '238404402957'}] → модель None
- `supply_ru_test_040` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '128624437921'}, {'role': 'buyer', 'name': 'ТОО «Строй Сервис Юг»', 'bin': '122527036784'}] → модель None
- `works_ru_test_003` failed: эталон [{'role': 'customer', 'name': 'ТОО «Кафе Тулпар»', 'bin': '515825097224'}, {'role': 'contractor', 'name': 'ТОО «Ремонт Групп»', 'bin': '490474063462'}] → модель None
- `works_ru_test_004` failed: эталон [{'role': 'customer', 'name': 'ТОО «Логистик Центр»', 'bin': '626626534311'}, {'role': 'contractor', 'name': 'ТОО «Ремонт Групп»', 'bin': '980492365257'}] → модель None
- `works_ru_test_015` failed: эталон [{'role': 'customer', 'name': 'ИП «Абилова»', 'bin': '969582680819'}, {'role': 'contractor', 'name': 'ТОО «Ремонт Групп»', 'bin': '026779194369'}] → модель None
- `works_ru_test_026` failed: эталон [{'role': 'customer', 'name': 'ИП «Абилова»', 'bin': '127954650438'}, {'role': 'contractor', 'name': 'ИП «Токтаров»', 'bin': '345934347154'}] → модель None
- `works_ru_test_037` failed: эталон [{'role': 'customer', 'name': 'ТОО «Логистик Центр»', 'bin': '798759968238'}, {'role': 'contractor', 'name': 'ТОО «Инжиниринг Сервис»', 'bin': '879517411626'}] → модель None
- `works_ru_test_038` failed: эталон [{'role': 'customer', 'name': 'ТОО «Медицина Плюс»', 'bin': '530769602873'}, {'role': 'contractor', 'name': 'ТОО «Мастер Строй»', 'bin': '959482434184'}] → модель None
- `works_ru_test_039` failed: эталон [{'role': 'customer', 'name': 'ТОО «Логистик Центр»', 'bin': '255186519635'}, {'role': 'contractor', 'name': 'ИП «Токтаров»', 'bin': '779404441852'}] → модель None

## term_months (22)

- `lease_kk_test_003` failed: эталон `11` → модель `—`
- `lease_kk_test_006` failed: эталон `11` → модель `—`
- `lease_kk_test_007` failed: эталон `11` → модель `—`
- `lease_kk_test_011` failed: эталон `11` → модель `—`
- `lease_ru_test_014` failed: эталон `11` → модель `—`
- `lease_ru_test_033` failed: эталон `11` → модель `—`
- `supply_ru_test_004` failed: эталон `None` → модель `—`
- `supply_ru_test_005` failed: эталон `None` → модель `—`
- `supply_ru_test_006` failed: эталон `None` → модель `—`
- `supply_ru_test_008` failed: эталон `None` → модель `—`
- `supply_ru_test_016` failed: эталон `None` → модель `—`
- `supply_ru_test_027` failed: эталон `None` → модель `—`
- `supply_ru_test_028` failed: эталон `None` → модель `—`
- `supply_ru_test_040` failed: эталон `None` → модель `—`
- `works_ru_test_003` failed: эталон `None` → модель `—`
- `works_ru_test_004` failed: эталон `None` → модель `—`
- `works_ru_test_015` failed: эталон `None` → модель `—`
- `works_ru_test_026` failed: эталон `None` → модель `—`
- `works_ru_test_037` failed: эталон `None` → модель `—`
- `works_ru_test_038` failed: эталон `None` → модель `—`
- `works_ru_test_039` failed: эталон `None` → модель `—`
- `works_ru_test_040` hallucinated: эталон `None` → модель `24`

## price_period (22)

- `lease_kk_test_003` failed: эталон `monthly` → модель `—`
- `lease_kk_test_006` failed: эталон `monthly` → модель `—`
- `lease_kk_test_007` failed: эталон `monthly` → модель `—`
- `lease_kk_test_011` failed: эталон `monthly` → модель `—`
- `lease_ru_test_014` failed: эталон `monthly` → модель `—`
- `lease_ru_test_033` failed: эталон `monthly` → модель `—`
- `supply_ru_test_004` failed: эталон `None` → модель `—`
- `supply_ru_test_005` failed: эталон `None` → модель `—`
- `supply_ru_test_006` failed: эталон `None` → модель `—`
- `supply_ru_test_008` failed: эталон `None` → модель `—`
- `supply_ru_test_016` failed: эталон `None` → модель `—`
- `supply_ru_test_027` failed: эталон `None` → модель `—`
- `supply_ru_test_028` failed: эталон `None` → модель `—`
- `supply_ru_test_040` failed: эталон `None` → модель `—`
- `works_ru_test_003` failed: эталон `total` → модель `—`
- `works_ru_test_004` failed: эталон `total` → модель `—`
- `works_ru_test_015` failed: эталон `total` → модель `—`
- `works_ru_test_026` failed: эталон `total` → модель `—`
- `works_ru_test_037` failed: эталон `total` → модель `—`
- `works_ru_test_038` failed: эталон `total` → модель `—`
- `works_ru_test_039` failed: эталон `total` → модель `—`
- `works_ru_test_040` wrong: эталон `total` → модель `monthly`

## contract_type (21)

- `lease_kk_test_003` failed: эталон `lease` → модель `—`
- `lease_kk_test_006` failed: эталон `lease` → модель `—`
- `lease_kk_test_007` failed: эталон `lease` → модель `—`
- `lease_kk_test_011` failed: эталон `lease` → модель `—`
- `lease_ru_test_014` failed: эталон `lease` → модель `—`
- `lease_ru_test_033` failed: эталон `lease` → модель `—`
- `supply_ru_test_004` failed: эталон `supply` → модель `—`
- `supply_ru_test_005` failed: эталон `supply` → модель `—`
- `supply_ru_test_006` failed: эталон `supply` → модель `—`
- `supply_ru_test_008` failed: эталон `supply` → модель `—`
- `supply_ru_test_016` failed: эталон `supply` → модель `—`
- `supply_ru_test_027` failed: эталон `supply` → модель `—`
- `supply_ru_test_028` failed: эталон `supply` → модель `—`
- `supply_ru_test_040` failed: эталон `supply` → модель `—`
- `works_ru_test_003` failed: эталон `works` → модель `—`
- `works_ru_test_004` failed: эталон `works` → модель `—`
- `works_ru_test_015` failed: эталон `works` → модель `—`
- `works_ru_test_026` failed: эталон `works` → модель `—`
- `works_ru_test_037` failed: эталон `works` → модель `—`
- `works_ru_test_038` failed: эталон `works` → модель `—`
- `works_ru_test_039` failed: эталон `works` → модель `—`

## city (21)

- `lease_kk_test_003` failed: эталон `Ақтөбе` → модель `—`
- `lease_kk_test_006` failed: эталон `Ақтөбе` → модель `—`
- `lease_kk_test_007` failed: эталон `Қарағанды` → модель `—`
- `lease_kk_test_011` failed: эталон `Алматы` → модель `—`
- `lease_ru_test_014` failed: эталон `Астана` → модель `—`
- `lease_ru_test_033` failed: эталон `Астана` → модель `—`
- `supply_ru_test_004` failed: эталон `Усть-Каменогорск` → модель `—`
- `supply_ru_test_005` failed: эталон `Костанай` → модель `—`
- `supply_ru_test_006` failed: эталон `Алматы` → модель `—`
- `supply_ru_test_008` failed: эталон `Павлодар` → модель `—`
- `supply_ru_test_016` failed: эталон `Павлодар` → модель `—`
- `supply_ru_test_027` failed: эталон `Павлодар` → модель `—`
- `supply_ru_test_028` failed: эталон `Астана` → модель `—`
- `supply_ru_test_040` failed: эталон `Павлодар` → модель `—`
- `works_ru_test_003` failed: эталон `Тараз` → модель `—`
- `works_ru_test_004` failed: эталон `Алматы` → модель `—`
- `works_ru_test_015` failed: эталон `Алматы` → модель `—`
- `works_ru_test_026` failed: эталон `Атырау` → модель `—`
- `works_ru_test_037` failed: эталон `Атырау` → модель `—`
- `works_ru_test_038` failed: эталон `Кокшетау` → модель `—`
- `works_ru_test_039` failed: эталон `Астана` → модель `—`

## auto_renewal (21)

- `lease_kk_test_003` failed: эталон `False` → модель `—`
- `lease_kk_test_006` failed: эталон `False` → модель `—`
- `lease_kk_test_007` failed: эталон `False` → модель `—`
- `lease_kk_test_011` failed: эталон `False` → модель `—`
- `lease_ru_test_014` failed: эталон `False` → модель `—`
- `lease_ru_test_033` failed: эталон `False` → модель `—`
- `supply_ru_test_004` failed: эталон `False` → модель `—`
- `supply_ru_test_005` failed: эталон `False` → модель `—`
- `supply_ru_test_006` failed: эталон `False` → модель `—`
- `supply_ru_test_008` failed: эталон `True` → модель `—`
- `supply_ru_test_016` failed: эталон `False` → модель `—`
- `supply_ru_test_027` failed: эталон `False` → модель `—`
- `supply_ru_test_028` failed: эталон `False` → модель `—`
- `supply_ru_test_040` failed: эталон `False` → модель `—`
- `works_ru_test_003` failed: эталон `False` → модель `—`
- `works_ru_test_004` failed: эталон `False` → модель `—`
- `works_ru_test_015` failed: эталон `False` → модель `—`
- `works_ru_test_026` failed: эталон `False` → модель `—`
- `works_ru_test_037` failed: эталон `False` → модель `—`
- `works_ru_test_038` failed: эталон `False` → модель `—`
- `works_ru_test_039` failed: эталон `False` → модель `—`

## price_amount (21)

- `lease_kk_test_003` failed: эталон `350000.0` → модель `—`
- `lease_kk_test_006` failed: эталон `450000.0` → модель `—`
- `lease_kk_test_007` failed: эталон `600000.0` → модель `—`
- `lease_kk_test_011` failed: эталон `450000.0` → модель `—`
- `lease_ru_test_014` failed: эталон `820000.0` → модель `—`
- `lease_ru_test_033` failed: эталон `350000.0` → модель `—`
- `supply_ru_test_004` failed: эталон `None` → модель `—`
- `supply_ru_test_005` failed: эталон `None` → модель `—`
- `supply_ru_test_006` failed: эталон `None` → модель `—`
- `supply_ru_test_008` failed: эталон `None` → модель `—`
- `supply_ru_test_016` failed: эталон `None` → модель `—`
- `supply_ru_test_027` failed: эталон `None` → модель `—`
- `supply_ru_test_028` failed: эталон `None` → модель `—`
- `supply_ru_test_040` failed: эталон `None` → модель `—`
- `works_ru_test_003` failed: эталон `8900000.0` → модель `—`
- `works_ru_test_004` failed: эталон `8900000.0` → модель `—`
- `works_ru_test_015` failed: эталон `8900000.0` → модель `—`
- `works_ru_test_026` failed: эталон `8900000.0` → модель `—`
- `works_ru_test_037` failed: эталон `8900000.0` → модель `—`
- `works_ru_test_038` failed: эталон `8900000.0` → модель `—`
- `works_ru_test_039` failed: эталон `8900000.0` → модель `—`

## parties.role_bin (21)

- `lease_kk_test_003` failed: эталон [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': '510539978883'}, {'role': 'tenant', 'name': '«Сейтқали» ЖК', 'bin': '093002501523'}] → модель None
- `lease_kk_test_006` failed: эталон [{'role': 'landlord', 'name': '«Бизнес Орталық» ЖШС', 'bin': '943914780876'}, {'role': 'tenant', 'name': '«Кофе Нүкте» ЖШС', 'bin': '845966435725'}] → модель None
- `lease_kk_test_007` failed: эталон [{'role': 'landlord', 'name': '«Алтын Сарай» ЖШС', 'bin': '191671761389'}, {'role': 'tenant', 'name': '«Дәріхана Денсаулық» ЖШС', 'bin': '597065763576'}] → модель None
- `lease_kk_test_011` failed: эталон [{'role': 'landlord', 'name': '«Бизнес Орталық» ЖШС', 'bin': '237255824807'}, {'role': 'tenant', 'name': '«Кофе Нүкте» ЖШС', 'bin': '994304499412'}] → модель None
- `lease_ru_test_014` failed: эталон [{'role': 'landlord', 'name': 'ТОО «Алтын Сарай»', 'bin': '912402403566'}, {'role': 'tenant', 'name': 'ТОО «Аптека Здоровье»', 'bin': '404240560475'}] → модель None
- `lease_ru_test_033` failed: эталон [{'role': 'landlord', 'name': 'ТОО «Алтын Сарай»', 'bin': '453167591985'}, {'role': 'tenant', 'name': 'ИП «Сейткали»', 'bin': '322637954236'}] → модель None
- `supply_ru_test_004` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '294127178435'}, {'role': 'buyer', 'name': 'ИП «Оразбекова»', 'bin': '097678657102'}] → модель None
- `supply_ru_test_005` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '377617678296'}, {'role': 'buyer', 'name': 'ИП «Жумабаев»', 'bin': '678378201685'}] → модель None
- `supply_ru_test_006` failed: эталон [{'role': 'supplier', 'name': 'ТОО «ТехноПоставка KZ»', 'bin': '670394999437'}, {'role': 'buyer', 'name': 'ТОО «Строй Сервис Юг»', 'bin': '606894143290'}] → модель None
- `supply_ru_test_008` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Евразия Трейд»', 'bin': '235940581287'}, {'role': 'buyer', 'name': 'ТОО «Строй Сервис Юг»', 'bin': '092406447514'}] → модель None
- `supply_ru_test_016` failed: эталон [{'role': 'supplier', 'name': 'ТОО «ТехноПоставка KZ»', 'bin': '111742554416'}, {'role': 'buyer', 'name': 'ТОО «Мини-маркет Береке»', 'bin': '540186466089'}] → модель None
- `supply_ru_test_027` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '479675693181'}, {'role': 'buyer', 'name': 'ИП «Оразбекова»', 'bin': '348287637587'}] → модель None
- `supply_ru_test_028` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '655288550881'}, {'role': 'buyer', 'name': 'ТОО «Мини-маркет Береке»', 'bin': '238404402957'}] → модель None
- `supply_ru_test_040` failed: эталон [{'role': 'supplier', 'name': 'ТОО «Каспий Снаб»', 'bin': '128624437921'}, {'role': 'buyer', 'name': 'ТОО «Строй Сервис Юг»', 'bin': '122527036784'}] → модель None
- `works_ru_test_003` failed: эталон [{'role': 'customer', 'name': 'ТОО «Кафе Тулпар»', 'bin': '515825097224'}, {'role': 'contractor', 'name': 'ТОО «Ремонт Групп»', 'bin': '490474063462'}] → модель None
- `works_ru_test_004` failed: эталон [{'role': 'customer', 'name': 'ТОО «Логистик Центр»', 'bin': '626626534311'}, {'role': 'contractor', 'name': 'ТОО «Ремонт Групп»', 'bin': '980492365257'}] → модель None
- `works_ru_test_015` failed: эталон [{'role': 'customer', 'name': 'ИП «Абилова»', 'bin': '969582680819'}, {'role': 'contractor', 'name': 'ТОО «Ремонт Групп»', 'bin': '026779194369'}] → модель None
- `works_ru_test_026` failed: эталон [{'role': 'customer', 'name': 'ИП «Абилова»', 'bin': '127954650438'}, {'role': 'contractor', 'name': 'ИП «Токтаров»', 'bin': '345934347154'}] → модель None
- `works_ru_test_037` failed: эталон [{'role': 'customer', 'name': 'ТОО «Логистик Центр»', 'bin': '798759968238'}, {'role': 'contractor', 'name': 'ТОО «Инжиниринг Сервис»', 'bin': '879517411626'}] → модель None
- `works_ru_test_038` failed: эталон [{'role': 'customer', 'name': 'ТОО «Медицина Плюс»', 'bin': '530769602873'}, {'role': 'contractor', 'name': 'ТОО «Мастер Строй»', 'bin': '959482434184'}] → модель None
- `works_ru_test_039` failed: эталон [{'role': 'customer', 'name': 'ТОО «Логистик Центр»', 'bin': '255186519635'}, {'role': 'contractor', 'name': 'ИП «Токтаров»', 'bin': '779404441852'}] → модель None
