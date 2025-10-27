from typing import Any
from unittest.mock import Mock

from src.nlp.extract_data_nl import (
    ResponseGenerator,
    RuleIntentClassifier,
    SQLQueryBuilder,
)


class TestGreetingsFarewells:
    def setup_method(self) -> None:
        self.classifier = RuleIntentClassifier()
        self.response_generator = ResponseGenerator()

    def test_varied_greetings(self) -> None:
        test_cases = [
            ("oi", "greeting"),
            ("olá", "greeting"),
            ("ola", "greeting"),
            ("eae", "greeting"),
            ("hey", "greeting"),
            ("iai", "greeting"),
            ("fala", "greeting"),
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
            ("como vai?", "greeting"),
            ("como vai", "greeting"),
            ("oi, tudo bem?", "greeting"),
            ("olá, como vai?", "greeting"),
            ("bom dia, tudo bem?", "greeting"),
        ]

        for text, expected_intent in test_cases:
            intent, params = self.classifier.execute(text)
            assert intent == expected_intent, (
                f"Texto: '{text}' - Esperado: {expected_intent}, Obtido: {intent}"
            )
            assert params == {}, (
                f"Params deveria ser vazio para saudação, mas foi: {params}"
            )

    def test_varied_farewells(self) -> None:
        test_cases = [
            ("tchau", "farewell"),
            ("obrigado", "farewell"),
            ("obrigada", "farewell"),
            ("valeu", "farewell"),
            ("até logo", "farewell"),
            ("até mais", "farewell"),
            ("flw", "farewell"),
            ("falou", "farewell"),
            ("bye", "farewell"),
            ("adeus", "farewell"),
            ("tchau!", "farewell"),
            ("obrigado!", "farewell"),
            ("valeu!", "farewell"),
            ("TCHAU", "farewell"),
            ("OBRIGADO", "farewell"),
            ("ATÉ LOGO", "farewell"),
            ("  tchau  ", "farewell"),
            ("  obrigado  ", "farewell"),
            ("encerrar", "farewell"),
            ("finalizar", "farewell"),
            ("fim", "farewell"),
            ("valeu, até mais", "farewell"),
            ("obrigado, tchau", "farewell"),
            ("falou, valeu", "farewell"),
        ]

        for text, expected_intent in test_cases:
            intent, params = self.classifier.execute(text)
            assert intent == expected_intent, (
                f"Texto: '{text}' - Esperado: {expected_intent}, Obtido: {intent}"
            )
            assert params == {}, (
                f"Params deveria ser vazio para despedida, mas foi: {params}"
            )

    def test_greeting_responses(self) -> None:
        params: dict[str, Any] = {}
        result = {"message": "greeting"}

        response = self.response_generator.execute("greeting", params, result)

        expected_responses = [
            "Olá! Como posso ajudar você com informações sobre vendas e estoque?",
            "Oi! Estou aqui para ajudar com dados de vendas, estoque e previsões.",
            "Olá! Pronto para analisar alguns dados de negócio?",
            "Oi! Em que posso ser útil hoje?",
        ]

        assert response in expected_responses, f"Resposta inesperada: {response}"
        assert len(response) > 0, "Resposta não pode ser vazia"

    def test_farewell_responses(self) -> None:
        params: dict[str, Any] = {}
        result = {"message": "farewell"}

        response = self.response_generator.execute("farewell", params, result)

        expected_responses = [
            "Até logo! Fico à disposição para mais análises.",
            "Obrigado! Volte sempre que precisar de informações.",
            "Tchau! Foi um prazer ajudar.",
            "Até mais! Estarei aqui quando precisar.",
        ]

        assert response in expected_responses, f"Resposta inesperada: {response}"
        assert len(response) > 0, "Resposta não pode ser vazia"

    def test_greeting_precedence(self) -> None:
        test_cases = [
            ("oi, qual o total de estoque?", "greeting"),
            ("olá, preciso das vendas", "greeting"),
            ("bom dia, tem previsão de vendas?", "greeting"),
            ("tudo bem? quero saber sobre estoque", "greeting"),
        ]

        for text, expected_intent in test_cases:
            intent, params = self.classifier.execute(text)
            assert intent == expected_intent, (
                f"Texto: '{text}' deveria ser {expected_intent}, mas foi {intent}"
            )

    def test_unknown_intent(self) -> None:
        test_cases = [
            "xyzabc",
            "qual o significado da vida?",
            "como fazer um bolo?",
            "previsão do tempo",
            "notícias de hoje",
        ]

        for text in test_cases:
            intent, params = self.classifier.execute(text)
            assert intent == "unknown_intent", (
                f"Texto: '{text}' deveria ser unknown_intent, mas foi {intent}"
            )
            assert "original_text" in params, (
                f"Params deveria conter original_text: {params}"
            )

    def test_unknown_intent_response(self) -> None:
        params = {"original_text": "texto desconhecido"}
        result = {
            "error": "Não entendi sua pergunta",
            "original_text": "texto desconhecido",
        }

        response = self.response_generator.execute("unknown_intent", params, result)

        assert "texto desconhecido" in response
        assert "desculpe" in response.lower() or "não entendi" in response.lower()
        assert len(response) > 0, "Resposta não pode ser vazia"

    def test_dont_confuse_greeting_with_other_intents(self) -> None:
        test_cases = [
            ("mostre o total de estoque", "total_stock"),
            ("previsão de vendas", "predict_top_sales"),
            ("top 10 produtos", "top_n_skus"),
            ("vendas do sku_123", "sales_time_series"),
        ]

        for text, expected_intent in test_cases:
            intent, params = self.classifier.execute(text)
            assert intent != "greeting", (
                f"Texto: '{text}' não deveria ser classificado como greeting, mas foi"
            )
            assert intent != "farewell", (
                f"Texto: '{text}' não deveria ser classificado como farewell, mas foi"
            )

    def test_case_insensitive(self) -> None:
        test_cases = [
            ("OI", "greeting"),
            ("OlÁ", "greeting"),
            ("TCHAU", "farewell"),
            ("OBRIGADO", "farewell"),
            ("ObRiGaDo", "farewell"),
        ]

        for text, expected_intent in test_cases:
            intent, params = self.classifier.execute(text)
            assert intent == expected_intent, (
                f"Texto: '{text}' - Esperado: {expected_intent}, Obtido: {intent}"
            )


class TestCompleteIntegration:
    def test_complete_greeting_flow(self) -> None:
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = []

        query_builder = SQLQueryBuilder(mock_engine)
        query_builder.inspector = mock_inspector

        classifier = RuleIntentClassifier()
        intent, params = classifier.execute("oi")

        assert intent == "greeting"
        assert params == {}

        result = query_builder.execute(intent, params)

        assert result == {"message": "greeting"}

        response_generator = ResponseGenerator()
        response = response_generator.execute(intent, params, result)

        assert response in [
            "Olá! Como posso ajudar você com informações sobre vendas e estoque?",
            "Oi! Estou aqui para ajudar com dados de vendas, estoque e previsões.",
            "Olá! Pronto para analisar alguns dados de negócio?",
            "Oi! Em que posso ser útil hoje?",
        ]

    def test_complete_farewell_flow(self) -> None:
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = []

        query_builder = SQLQueryBuilder(mock_engine)
        query_builder.inspector = mock_inspector

        classifier = RuleIntentClassifier()
        intent, params = classifier.execute("obrigado, tchau")

        assert intent == "farewell"
        assert params == {}

        result = query_builder.execute(intent, params)

        assert result == {"message": "farewell"}

        response_generator = ResponseGenerator()
        response = response_generator.execute(intent, params, result)

        assert response in [
            "Até logo! Fico à disposição para mais análises.",
            "Obrigado! Volte sempre que precisar de informações.",
            "Tchau! Foi um prazer ajudar.",
            "Até mais! Estarei aqui quando precisar.",
        ]
