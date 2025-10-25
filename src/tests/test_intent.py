import pytest
from src.nlp.intent import IntentRecognizer


@pytest.fixture(scope="module")
def analyzer() -> IntentRecognizer:
    return IntentRecognizer()


@pytest.mark.parametrize(
    "sentence,expected_subject,expected_verb,expected_complement",
    [
        (
            "João e Maria compraram frutas no mercado.",
            "João e Maria",
            "compraram",
            "frutas no mercado",
        ),
        (
            "O gerente da filial e a diretora aprovaram o novo projeto.",
            "O gerente da filial e a diretora",
            "aprovaram",
            "o novo projeto",
        ),
        ("Carlos estudou matemática ontem.", "Carlos", "estudou", "matemática"),
        (
            "A empresa contratou novos funcionários.",
            "A empresa",
            "contratou",
            "novos funcionários",
        ),
        (
            "O cachorro derrubou o vaso da mesa.",
            "O cachorro",
            "derrubou",
            "o vaso da mesa",
        ),
    ],
)
def test_analyze_sentence(
    analyzer: IntentRecognizer,
    sentence: str,
    expected_subject: str,
    expected_verb: str,
    expected_complement: str,
) -> None:
    """Testa se a análise retorna sujeito, verbo e complemento corretos."""
    result = analyzer.analyze(sentence)[0]

    assert expected_subject in result["subject"]["text"], (
        f"Sujeito incorreto em: {sentence}"
    )
    assert expected_verb in result["verb"]["text"], f"Verbo incorreto em: {sentence}"
    assert expected_complement in result["complement"]["text"], (
        f"Complemento incorreto em: {sentence}"
    )


def test_no_subject_sentence(analyzer: IntentRecognizer) -> None:
    """Frases sem sujeito explícito devem retornar None para o sujeito."""
    result = analyzer.analyze("Está chovendo.")[0]
    assert result["subject"] is None
    assert result["verb"]["lemma"] == "chover" or "chover" in result["verb"]["lemma"]


def test_invalid_input(analyzer: IntentRecognizer) -> None:
    """Testa se a classe lida com string vazia sem quebrar."""
    result = analyzer.analyze("")
    assert result == []
