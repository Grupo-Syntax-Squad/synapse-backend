import pytest


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("oi", "greeting"),
        ("olá", "greeting"),
        ("ola", "greeting"),
        ("eae", "greeting"),
        ("hey", "greeting"),
        ("iai", "greeting"),
        ("salve", "greeting"),
        ("oi!", "greeting"),
        ("olá!", "greeting"),
        ("eae!", "greeting"),
        ("OI", "greeting"),
        ("OLÁ", "greeting"),
        ("OLÁ!", "greeting"),
        ("  oi  ", "greeting"),
        ("  olá  ", "greeting"),
        ("bom dia", "greeting"),
        ("boa tarde", "greeting"),
        ("boa noite", "greeting"),
        ("tudo bem?", "greeting"),
        ("tudo bem", "greeting"),
        ("oi, tudo bem?", "greeting"),
        ("bom dia, tudo bem?", "greeting"),
    ],
)
def test_greetings(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent
    assert params == {}


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("tchau", "farewell"),
        ("obrigado", "farewell"),
        ("obrigada", "farewell"),
        ("até logo", "farewell"),
        ("até mais", "farewell"),
        ("flw", "farewell"),
        ("falou", "farewell"),
        ("bye", "farewell"),
        ("adeus", "farewell"),
        ("tchau!", "farewell"),
        ("obrigado!", "farewell"),
        ("TCHAU", "farewell"),
        ("OBRIGADO", "farewell"),
        ("ATÉ LOGO", "farewell"),
        ("  tchau  ", "farewell"),
        ("  obrigado  ", "farewell"),
        ("encerrar", "farewell"),
        ("finalizar", "farewell"),
        ("fim", "farewell"),
        ("obrigado, tchau", "farewell"),
        ("falou, valeu", "farewell"),
    ],
)
def test_farewells(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent
    assert params == {}


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("mostre o total de estoque", "total_stock"),
        ("previsão de vendas", "predict_top_sales"),
        ("top 10 produtos", "top_n_skus"),
        ("vendas do sku_123", "sales_time_series"),
    ],
)
def test_dont_confuse_greeting_with_other_intents(  # type:ignore[no-untyped-def]
    classifier, text, expected_intent
) -> None:
    intent, params = classifier.execute(text)
    assert intent != "greeting"
    assert intent != "farewell"


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("OI", "greeting"),
        ("OlÁ", "greeting"),
        ("TCHAU", "farewell"),
        ("OBRIGADO", "farewell"),
        ("ObRiGaDo", "farewell"),
    ],
)
def test_case_insensitive(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_entities",
    [
        (
            "SKU_123",
            {"sku": "SKU_123", "months": [], "years": [], "n": None, "client": None},
        ),
        (
            "sku-456",
            {"sku": "SKU_456", "months": [], "years": [], "n": None, "client": None},
        ),
        (
            "SKU 789",
            {"sku": "SKU_789", "months": [], "years": [], "n": None, "client": None},
        ),
        (
            "vendas em 2023",
            {"sku": None, "months": [], "years": [2023], "n": None, "client": None},
        ),
        (
            "previsão para 2024 e 2025",
            {
                "sku": None,
                "months": [],
                "years": [2024, 2025],
                "n": None,
                "client": None,
            },
        ),
        (
            "janeiro de 2023",
            {
                "sku": None,
                "months": [{"month": 1, "year": 2023}],
                "years": [2023],
                "n": None,
                "client": None,
            },
        ),
        (
            "março 2024",
            {
                "sku": None,
                "months": [{"month": 3, "year": 2024}],
                "years": [2024],
                "n": None,
                "client": None,
            },
        ),
        ("top 5", {"sku": None, "months": [], "years": [], "n": 5, "client": None}),
        (
            "10 principais",
            {"sku": None, "months": [], "years": [], "n": 10, "client": None},
        ),
    ],
)
def test_entity_extraction(classifier, text, expected_entities) -> None:  # type:ignore[no-untyped-def]
    entities = classifier.extract_entities(text)
    assert entities == expected_entities


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("o produto vai acabar?", "predict_stockout"),
        ("vai zerar o estoque?", "predict_stockout"),
        ("ficaremos sem esse produto?", "predict_stockout"),
        ("quantos clientes ativos temos?", "active_clients_count"),
        ("quantidade de clientes?", "active_clients_count"),
        ("quantos produtos distintos?", "distinct_products_count"),
        ("skus únicos no sistema", "distinct_products_count"),
        ("estoque total", "total_stock"),
        ("total de estoque", "total_stock"),
    ],
)
def test_specific_intents(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_params",
    [
        ("comparar sku_123 com sku_456", {"sku": "SKU_123"}),
        (
            "vendas de janeiro 2023 a março 2024",
            {"start": {"month": 1, "year": 2023}, "end": {"month": 3, "year": 2024}},
        ),
        ("estoque cliente 12345", {"client": 12345}),
        ("estoque do cliente ABC-XYZ", {"client": "ABC-XYZ"}),
    ],
)
def test_complex_entities(classifier, text, expected_params) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    for key, value in expected_params.items():
        assert params[key] == value


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("oi, qual o total de estoque?", "total_stock"),
        ("olá, quantos clientes ativos?", "active_clients_count"),
        ("previsão de vendas do sku_123 e estoque total", "predict_sku_sales"),
    ],
)
def test_intent_priority(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_sku",
    [
        (
            "previsão do produto XYZ-123",
            "XYZ-123",
        ),
    ],
)
def test_spacy_ner_integration(classifier, text, expected_sku) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    if "sku" in params:
        assert params["sku"] == expected_sku


@pytest.mark.parametrize(
    "text,expected_intent,expected_entities",
    [
        (
            "top 10 produtos em janeiro de 2023",
            "top_n_skus",
            {"n": 10, "months": [{"month": 1, "year": 2023}]},
        ),
        (
            "comparar sku_123 e sku_456 em março 2024",
            "sku_sales_compare",
            {"sku": "SKU_123", "months": [{"month": 3, "year": 2024}]},
        ),
    ],
)
def test_multiple_entities(  # type:ignore[no-untyped-def]
    classifier, text, expected_intent, expected_entities
) -> None:
    intent, params = classifier.execute(text)
    assert intent == expected_intent
    for key, value in expected_entities.items():
        assert params[key] == value


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("serao as melhores vendas", "predict_top_sales"),
        ("obrigada pela ajuda", "farewell"),
    ],
)
def test_spelling_variations(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


def test_long_text_processing(classifier) -> None:  # type:ignore[no-untyped-def]
    long_text = """
    Bom dia, gostaria de saber a previsão de vendas do SKU_123 para o mês de março de 2024.
    Também preciso comparar com as vendas do SKU_456 e ver o estoque total disponível.
    Além disso, qual será o top 5 produtos em abril? Obrigado!
    """
    intent, params = classifier.execute(long_text)
    assert intent != "unknown"
    assert "sku" in params or "months" in params or "n" in params


@pytest.mark.parametrize(
    "text",
    [
        "quais produtos vão vender mais no próximo mês?",
        "previsão dos produtos mais vendidos",
        "serão as melhores vendas",
        "quais vão vender mais?",
    ],
)
def test_predict_top_sales_next_month(classifier, text) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "predict_top_sales"
    assert params.get("period", {}).get("type") == "next_month"


@pytest.mark.parametrize(
    "text,expected_sku,expected_months",
    [
        (
            "quanto o sku_123 vai vender em março de 2024?",
            "SKU_123",
            [{"month": 3, "year": 2024}],
        ),
        (
            "previsão de vendas do sku 456 em dezembro 2025",
            "SKU_456",
            [{"month": 12, "year": 2025}],
        ),
        (
            "projeção do sku-789 para janeiro 2024",
            "SKU_789",
            [{"month": 1, "year": 2024}],
        ),
        (
            "quanto vai faturar o sku_999 em abril 2024?",
            "SKU_999",
            [{"month": 4, "year": 2024}],
        ),
    ],
)
def test_predict_sku_sales_with_date(  # type:ignore[no-untyped-def]
    classifier, text, expected_sku, expected_months
) -> None:
    intent, params = classifier.execute(text)
    assert intent == "predict_sku_sales"
    assert params.get("sku") == expected_sku
    assert params.get("months") == expected_months


@pytest.mark.parametrize(
    "text,expected_sku",
    [
        ("quanto o sku_123 vai vender?", "SKU_123"),
        ("previsão de vendas do sku 456", "SKU_456"),
        ("projeção do sku-789", "SKU_789"),
        ("quanto vai vender o sku_999?", "SKU_999"),
    ],
)
def test_predict_sku_sales_without_date(classifier, text, expected_sku) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "predict_sku_sales"
    assert params.get("sku") == expected_sku


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("série temporal de vendas", "sales_time_series"),
        ("histórico de vendas por mês", "sales_time_series"),
        ("evolução das vendas", "sales_time_series"),
        ("gráfico de vendas por mês", "sales_time_series"),
        ("linha do tempo de vendas", "sales_time_series"),
        ("faturamento por mês", "sales_time_series"),
        ("histórico mensal de vendas", "sales_time_series"),
    ],
)
def test_sales_time_series_general(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_sku",
    [
        ("série temporal do sku_123", "SKU_123"),
        ("histórico de vendas do sku 456", "SKU_456"),
        ("evolução de vendas do sku-789", "SKU_789"),
        ("vendas por mês do sku_999", "SKU_999"),
        ("faturamento por mês do sku 111", "SKU_111"),
        ("histórico mensal do sku-222", "SKU_222"),
    ],
)
def test_sales_time_series_with_sku(classifier, text, expected_sku) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "sales_time_series"
    assert params.get("sku") == expected_sku


@pytest.mark.parametrize(
    "text,expected_sku,expected_years",
    [
        ("série temporal do sku_123 em 2024", "SKU_123", [2024]),
        ("histórico de vendas do sku 456 em 2023 e 2024", "SKU_456", [2023, 2024]),
        ("evolução do sku-789 de 2022 a 2024", "SKU_789", [2022, 2024]),
    ],
)
def test_sales_time_series_with_sku_and_years(  # type:ignore[no-untyped-def]
    classifier, text, expected_sku, expected_years
) -> None:
    intent, params = classifier.execute(text)
    assert intent == "sales_time_series"
    assert params.get("sku") == expected_sku
    assert params.get("years") == expected_years


@pytest.mark.parametrize(
    "text,expected_sku",
    [
        ("comparar vendas do sku_123 com sku_456", "SKU_123"),
        ("qual sku vendeu mais: sku 789 ou sku 999?", "SKU_789"),
        ("diferença de vendas entre sku_111 e sku_222", "SKU_111"),
        ("sku-333 ou sku-444, quem vendeu mais?", "SKU_333"),
        ("comparativo entre sku_555 e sku_666", "SKU_555"),
    ],
)
def test_sku_sales_compare_basic(classifier, text, expected_sku) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "sku_sales_compare"
    assert params.get("sku") == expected_sku


@pytest.mark.parametrize(
    "text,expected_sku,expected_months",
    [
        (
            "comparar sku_123 e sku_456 em março 2024",
            "SKU_123",
            [{"month": 3, "year": 2024}],
        ),
        (
            "qual vendeu mais em dezembro 2025: sku 789 ou sku 999?",
            "SKU_789",
            [{"month": 12, "year": 2025}],
        ),
        (
            "diferença entre sku_111 e sku_222 em janeiro de 2024",
            "SKU_111",
            [{"month": 1, "year": 2024}],
        ),
    ],
)
def test_sku_sales_compare_with_date(  # type:ignore[no-untyped-def]
    classifier, text, expected_sku, expected_months
) -> None:
    intent, params = classifier.execute(text)
    assert intent == "sku_sales_compare"
    assert params.get("sku") == expected_sku
    assert params.get("months") == expected_months


@pytest.mark.parametrize(
    "text,expected_n",
    [
        ("top 5 produtos", 5),
        ("top 10 skus", 10),
        ("top 3 mais vendidos", 3),
        ("me mostre o top 20", 20),
    ],
)
def test_top_n_skus_basic(classifier, text, expected_n) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "top_n_skus"
    assert params.get("n") == expected_n


@pytest.mark.parametrize(
    "text,expected_n,expected_months",
    [
        ("top 5 produtos em março de 2024", 5, [{"month": 3, "year": 2024}]),
        ("top 10 em dezembro 2025", 10, [{"month": 12, "year": 2025}]),
    ],
)
def test_top_n_skus_with_date(classifier, text, expected_n, expected_months) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "top_n_skus"
    assert params.get("n") == expected_n
    assert params.get("months") == expected_months


@pytest.mark.parametrize(
    "text,expected_start,expected_end",
    [
        (
            "vendas entre janeiro 2024 e março 2024",
            {"month": 1, "year": 2024},
            {"month": 3, "year": 2024},
        ),
        (
            "faturamento entre junho 2023 e dezembro 2023",
            {"month": 6, "year": 2023},
            {"month": 12, "year": 2023},
        ),
        (
            "vendeu entre abril 2024 e agosto 2024",
            {"month": 4, "year": 2024},
            {"month": 8, "year": 2024},
        ),
    ],
)
def test_sales_between_dates_months(  # type:ignore[no-untyped-def]
    classifier, text, expected_start, expected_end
) -> None:
    intent, params = classifier.execute(text)
    assert intent == "sales_between_dates"
    assert params.get("start") == expected_start
    assert params.get("end") == expected_end


@pytest.mark.parametrize(
    "text,expected_start_year,expected_end_year",
    [
        ("vendas entre 2022 e 2024", 2022, 2024),
        ("faturamento entre 2020 e 2023", 2020, 2023),
        ("quanto vendemos entre 2021 e 2025", 2021, 2025),
    ],
)
def test_sales_between_dates_years(  # type:ignore[no-untyped-def]
    classifier, text, expected_start_year, expected_end_year
) -> None:
    intent, params = classifier.execute(text)
    assert intent == "sales_between_dates"
    assert params.get("start", {}).get("year") == expected_start_year
    assert params.get("end", {}).get("year") == expected_end_year


@pytest.mark.parametrize(
    "text,expected_client",
    [
        ("estoque do cliente 12345", 12345),
        ("estoque por cliente 9876", 9876),
        ("estoque cliente 555", 555),
    ],
)
def test_stock_by_client_numeric(classifier, text, expected_client) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "stock_by_client"
    assert params.get("client") == expected_client


@pytest.mark.parametrize(
    "text,expected_sku",
    [
        ("qual foi o melhor mês do sku_123?", "SKU_123"),
        ("melhor mês para o sku 456", "SKU_456"),
        ("em que mês o sku-789 vendeu mais?", "SKU_789"),
        ("mês que mais vendeu o sku_999", "SKU_999"),
    ],
)
def test_sku_best_month(classifier, text, expected_sku) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "sku_best_month"
    assert params.get("sku") == expected_sku


@pytest.mark.parametrize(
    "text,expected_intent,expected_sku,expected_months",
    [
        (
            "oi, preciso da previsão de vendas do sku_123 para março de 2024",
            "predict_sku_sales",
            "SKU_123",
            [{"month": 3, "year": 2024}],
        ),
        (
            "olá! qual será o top 5 produtos em dezembro 2025?",
            "top_n_skus",
            None,
            [{"month": 12, "year": 2025}],
        ),
        (
            "bom dia, comparar sku_111 e sku_222 em janeiro 2024",
            "sku_sales_compare",
            "SKU_111",
            [{"month": 1, "year": 2024}],
        ),
    ],
)
def test_complex_greeting_with_intent(  # type:ignore[no-untyped-def]
    classifier, text, expected_intent, expected_sku, expected_months
) -> None:
    intent, params = classifier.execute(text)
    assert intent == expected_intent
    if expected_sku:
        assert params.get("sku") == expected_sku
    if expected_months:
        assert params.get("months") == expected_months


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("série temporal do sku_123 em março 2024, obrigado", "sales_time_series"),
        ("top 10 produtos de 2024, valeu!", "top_n_skus"),
        ("previsão do sku_456 para janeiro 2025, até mais", "predict_sku_sales"),
    ],
)
def test_complex_intent_with_farewell(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text",
    [
        "comparar sku_123, sku_456 e sku_789 em março 2024",
        "qual vendeu mais: sku 111, sku 222 ou sku 333?",
        "diferença entre sku_444, sku_555 e sku_666",
    ],
)
def test_multiple_skus_extracts_first(classifier, text) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == "sku_sales_compare"
    assert params.get("sku") is not None
    assert params["sku"].startswith("SKU_")


@pytest.mark.parametrize(
    "text,expected_years_count",
    [
        ("vendas de 2020, 2021, 2022 e 2023", 4),
        ("histórico de 2022 até 2025", 2),
        ("evolução em 2023", 1),
    ],
)
def test_multiple_years_extraction(classifier, text, expected_years_count) -> None:  # type:ignore[no-untyped-def]
    entities = classifier.extract_entities(text)
    assert len(entities["years"]) == expected_years_count


@pytest.mark.parametrize(
    "text,expected_sku",
    [
        ("vendas do SKU_123", "SKU_123"),
        ("vendas do sku-456", "SKU_456"),
        ("vendas do sku 789", "SKU_789"),
        ("vendas do SKU123", "SKU_123"),
        ("vendas do skU_999", "SKU_999"),
    ],
)
def test_sku_format_variations(classifier, text, expected_sku) -> None:  # type:ignore[no-untyped-def]
    entities = classifier.extract_entities(text)
    assert entities["sku"] == expected_sku


@pytest.mark.parametrize(
    "text,expected_month",
    [
        ("vendas em marco de 2024", 3),
        ("março de 2024", 3),
        ("MARÇO de 2024", 3),
        ("Marco 2024", 3),
    ],
)
def test_month_accent_variations(classifier, text, expected_month) -> None:  # type:ignore[no-untyped-def]
    entities = classifier.extract_entities(text)
    assert len(entities["months"]) == 1
    assert entities["months"][0]["month"] == expected_month


@pytest.mark.parametrize(
    "text",
    [
        "a" * 500,
        "previsão " * 100,
    ],
)
def test_very_long_text(classifier, text) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent is not None


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("previsão... de... vendas... do... sku_123", "predict_sku_sales"),
        ("top!!! 5!!! produtos!!!", "top_n_skus"),
    ],
)
def test_excessive_punctuation(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, _ = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text",
    [
        "PreViSãO dE vEnDaS dO sKu_123",
        "TOP 5 pRoDuToS",
        "HiStÓrIcO dE vEnDaS",
    ],
)
def test_mixed_case(classifier, text) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent != "unknown"


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("quantos clientes temos?", "active_clients_count"),
        ("quantidade de clientes", "active_clients_count"),
        ("número de clientes ativos", "active_clients_count"),
        ("total de clientes", "active_clients_count"),
    ],
)
def test_active_clients_count_variations(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("quantos produtos distintos?", "distinct_products_count"),
        ("skus únicos no sistema", "distinct_products_count"),
        ("produtos diferentes", "distinct_products_count"),
        ("quantidade de skus distintos", "distinct_products_count"),
    ],
)
def test_distinct_products_count_variations(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("estoque total", "total_stock"),
        ("total de estoque", "total_stock"),
        ("quanto temos em estoque?", "total_stock"),
        ("quantidade total em estoque", "total_stock"),
    ],
)
def test_total_stock_variations(classifier, text, expected_intent) -> None:  # type:ignore[no-untyped-def]
    intent, params = classifier.execute(text)
    assert intent == expected_intent
