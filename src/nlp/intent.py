from typing import Any
import spacy
from spacy.tokens import Span


class IntentRecognizer:
    def __init__(self) -> None:
        self.nlp = spacy.load("pt_core_news_sm")

    def analyze(self, text: str) -> list[dict[str, Any]]:
        doc = self.nlp(text)
        results = []
        for sent in doc.sents:
            subject = self._get_subject(sent)
            verb = self._get_main_verb(sent)
            complement = self._get_complement(sent, verb)
            results.append(
                {
                    "sentence": sent.text,
                    "subject": subject,
                    "verb": verb,
                    "complement": complement,
                }
            )
        return results

    def _get_subject(self, sent: Span) -> dict[str, str | int] | None:
        subj_tokens = [tok for tok in sent if tok.dep_.startswith("nsubj")]
        if not subj_tokens:
            return None

        subj_full = set(subj_tokens)
        for tok in subj_tokens:
            subj_full.update(tok.subtree)
            subj_full.update(tok.conjuncts)

        indices = sorted(t.i for t in subj_full)
        start, end = indices[0], indices[-1] + 1
        text = sent.doc[start:end].text
        return {"text": text, "start": start, "end": end}

    def _get_main_verb(self, sent: Span) -> dict[str, Any] | None:
        root = next(
            (tok for tok in sent if tok.dep_ == "ROOT" and tok.pos_ in {"VERB", "AUX"}),
            None,
        )
        if not root:
            return None

        tokens = {root}
        for child in root.children:
            if child.dep_ in {"aux", "auxpass", "neg"}:
                tokens.add(child)

        indices = sorted(t.i for t in tokens)
        start, end = indices[0], indices[-1] + 1
        text = sent.doc[start:end].text
        return {
            "text": text,
            "lemma": root.lemma_,
            "start": start,
            "end": end,
            "token": root,
        }

    def _get_complement(
        self, sent: Span, verb_info: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if not verb_info:
            return None

        verb_token = verb_info["token"]
        comp_tokens = []

        for child in verb_token.children:
            if child.dep_ in {"obj", "iobj", "obl", "xcomp", "ccomp", "attr"}:
                comp_tokens.extend(list(child.subtree))

        if not comp_tokens:
            return None

        indices = sorted(t.i for t in comp_tokens)
        start, end = indices[0], indices[-1] + 1
        text = sent.doc[start:end].text
        return {"text": text, "start": start, "end": end}


# ----------------- Exemplo -----------------
if __name__ == "__main__":
    analyzer = IntentRecognizer()
    frases = [
        "João e Maria compraram frutas no mercado.",
        "O gerente da filial e a diretora aprovaram o novo projeto.",
        "Carlos estudou matemática ontem.",
        "A empresa contratou novos funcionários.",
        "O cachorro derrubou o vaso da mesa.",
        "Eu gostaria de extrair todos os dados sobre o SKUs vendidos no último trimestre.",
    ]

    for f in frases:
        print(f"\nFrase: {f}")
        for r in analyzer.analyze(f):
            print(r)
