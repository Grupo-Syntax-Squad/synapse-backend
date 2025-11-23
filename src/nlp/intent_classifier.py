import re
import unidecode
from typing import Any, Dict, Tuple, Optional

import spacy
from src.logger_instance import logger

try:
    from sentence_transformers import SentenceTransformer, util

    EMBEDDING_AVAILABLE = True
except Exception:
    EMBEDDING_AVAILABLE = False

MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

PHRASE_WEIGHT = 3
WORD_WEIGHT = 1

# quando usar semântica: similaridade mínima para aceitar fallback
SEMANTIC_THRESHOLD = 0.45
# diferença mínima de score entre top intents para aceitar semântica
MIN_SCORE_DELTA = 0.15


class RuleIntentClassifier:
    SKU_RE = re.compile(r"\b[Ss][Kk][Uu][ _-]?(\d+)\b")
    YEAR_RE = re.compile(r"\b(20\d{2})\b")
    NUMBER_RE = re.compile(
        r"\btop\s*(\d+)\b|\b(\d+)\s*(top|maiores|principais)\b", re.I
    )
    MONTH_WITH_YEAR_RE = re.compile(
        r"(janeiro|fevereiro|mar[cç]o|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*(?:de\s*)?(20\d{2})",
        re.I,
    )

    VOCABULARY = {
        "greeting": ["tudo bem", "bom dia", "boa tarde", "boa noite", "como vai", "oi", "olá", "ola", "eae", "hey", "fala", "salve", "iai"],
        "farewell": ["até logo", "até mais", "tchau", "valeu", "obrigado", "obrigada", "flw", "bye", "adeus"],
        "predict_stockout": ["sem estoque", "estoque zero", "ficar sem", "vai esgotar", "vai acabar", "zerar estoque"],
        "predict_top_sales": [
            "serão as melhores vendas", "serao as melhores vendas",
            "serão os mais vendidos", "serao os mais vendidos",
            "vai vender mais", "vão vender mais", "vao vender mais",
            "previsão de top vendas", "prever top vendas",
            "projeção de mais vendidos", "projeção de vendas",
            "melhores vendas para", "maiores vendas para"
        ],
        "predict_sku_sales": [
            "previsão de vendas do sku", "previsao de vendas do sku",
            "previsão do sku", "previsao do sku",
            "projeção de vendas do sku", "projecao de vendas do sku",
            "vai vender quanto", "quanto vai vender"
        ],
        "active_clients_count": ["quantos clientes", "clientes ativos", "quantidade de clientes"],
        "distinct_products_count": [
            "quantos produtos", "produtos distintos", "skus distintos", "produtos únicos", "skus únicos",
            "quantidade de produtos", "produtos diferentes", "skus diferentes",
        ],
        "sales_between_dates": ["vendas entre", "vendeu entre", "faturamento entre", "entre"],
        "sku_best_month": ["melhor mes", "melhor mês", "mes quem mais vendeu", "mês que mais vendeu"],
        "stock_by_client": ["estoque por cliente", "estoque do cliente", "estoque cliente"],
        "sku_sales_compare": [
            "comparar vendas", "comparação de vendas", "comparar o sku", "comparar os skus",
            "qual vendeu mais", "quem vendeu mais", "qual teve maior venda", "qual teve mais vendas",
            "comparativo de vendas", "diferença de vendas entre",
        ],
        "total_stock": ["estoque total", "total de estoque"],
        "top_n_skus": [
            "top vendas", "top produtos", "top skus", "top mais vendidos", "ranking de vendas",
            "ranking dos produtos", "produtos mais vendidos", "skus mais vendidos", "lista dos mais vendidos",
        ],
        "sales_time_series": [
            "série temporal de vendas", "série temporal de faturamento", "gráfico de vendas por mês",
            "histórico de vendas", "evolução das vendas", "linha do tempo de vendas", "vendas por mês",
            "faturamento por mês", "histórico mensal de vendas"
        ],
        "sales_time_series_sku": [
            "série temporal do sku", "histórico de vendas do sku", "evolução de vendas do sku",
            "vendas por mês do sku", "faturamento por mês do sku", "histórico mensal do sku",
            "série temporal do produto", "histórico de vendas do produto"
        ],
    }

    VOCAB_KEY_TO_INTENT = {
        "sales_time_series_sku": "sales_time_series",
    }

    INTENT_EXAMPLES = {
        "greeting": [
            "oi", "olá", "eae", "tudo bem?", "bom dia", "boa tarde", "boa noite", "hey", "fala", "salve", "iai", "como vai", "tudo certo?", "oi, tudo bem?"
        ],
        "farewell": [
            "tchau", "até mais", "até logo", "valeu", "flw", "adeus", "bye", "obrigado", "obrigada", "até a próxima"
        ],
        "predict_stockout": [
            "o produto vai acabar?", "tem estoque desse item?", "vai zerar o estoque?", "ficaremos sem esse produto?", 
            "previsão de ruptura de estoque", "produto esgotando", "o estoque está baixo", "quando vai acabar o estoque?"
        ],
        "predict_top_sales": [
            "quais produtos vão vender mais no próximo mês?", "previsão dos produtos mais vendidos", 
            "top vendas no próximo mês", "quais serão os mais vendidos?", "produtos com maior venda prevista", 
            "ranking de vendas esperado", "quais itens terão maior faturamento?", "quais produtos terão maior demanda?"
        ],
        "predict_sku_sales": [
            "quanto o sku vai vender no próximo mês?", "previsão de vendas do sku_10", 
            "projeção de vendas do sku 123", "quanto vai faturar o produto sku_345?", 
            "previsão de faturamento do sku_999", "projeção do sku_777", "quanto venderá o sku_ABC?", 
            "quantas unidades do sku_456 serão vendidas?", "previsão de vendas do produto X"
        ],
        "sales_between_dates": [
            "quanto vendemos entre junho e agosto?", "vendas entre 01/01/2024 e 31/03/2024", 
            "faturamento do período de março a maio", "total de vendas entre datas específicas", 
            "quanto faturamos entre essas datas?", "vendas no trimestre passado", "quanto foi vendido no mês passado?"
        ],
        "top_n_skus": [
            "top 5 produtos", "quais os 10 mais vendidos?", "me mostre o top 3", "ranking dos principais produtos", 
            "produtos mais vendidos do mês", "lista dos top skus", "quais skus tiveram maior venda?"
        ],
        "sales_time_series": [
            "mostrar histórico de vendas por mês", "série temporal de faturamento", "evolução de vendas mensal", 
            "histórico mensal de faturamento", "linha do tempo das vendas", "gráfico de vendas por mês", 
            "como as vendas evoluíram ao longo do tempo?", "histórico de faturamento ao longo do ano"
        ],
        "sales_time_series_sku": [
            "série temporal do sku_10", "histórico de vendas do sku 123", "evolução de vendas do produto X", 
            "vendas por mês do sku_456", "faturamento por mês do sku_789", "histórico mensal do produto Y", 
            "como as vendas do sku_ABC mudaram ao longo do tempo?"
        ],
        "sku_sales_compare": [
            "comparar vendas do sku_10 com sku_20", "qual sku vendeu mais em março?", 
            "diferença de vendas entre sku_123 e sku_456", "comparativo de vendas entre produtos", 
            "quais skus tiveram maior venda no período?", "quem vendeu mais, sku_10 ou sku_20?", 
            "comparar faturamento do sku_ABC com sku_DEF"
        ],
        "sku_best_month": [
            "qual foi o melhor mês do sku_123?", "em que mês o produto X vendeu mais?", 
            "melhor mês para vendas do sku_456", "histórico do mês com maior venda do produto Y", 
            "quando o sku_789 teve maior faturamento?", "mes que mais vendeu o sku_ABC"
        ],
        "active_clients_count": [
            "quantos clientes ativos temos?", "quantos clientes temos no total?", 
            "quantidade de clientes ativos?", "número de clientes cadastrados", 
            "clientes ativos no sistema", "total de clientes"
        ],
        "distinct_products_count": [
            "quantos produtos distintos temos?", "skus distintos no sistema", "produtos únicos cadastrados", 
            "quantidade de produtos diferentes", "total de skus únicos", "quantos skus diferentes existem?"
        ],
        "stock_by_client": [
            "estoque por cliente", "estoque do cliente X", "quanto cada cliente tem em estoque?", 
            "quantidade de produtos por cliente", "estoque disponível por cliente", "relatório de estoque do cliente"
        ],
        "total_stock": [
            "estoque total", "quantidade total em estoque", "total de produtos disponíveis", 
            "relatório do estoque geral", "quantos itens temos no estoque?"
        ]
    }

    def __init__(self, use_embeddings: bool = True) -> None:
        self._nlp = spacy.load("pt_core_news_sm")
        self.use_embeddings = use_embeddings and EMBEDDING_AVAILABLE

        self.embedding_model = None
        if self.use_embeddings:
            try:
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                self._examples_emb = {
                    intent: self.embedding_model.encode(exs, convert_to_tensor=True)
                    for intent, exs in self.INTENT_EXAMPLES.items()
                }
            except Exception as e:
                logger.warning(f"Embedding model not available, semantic fallback disabled: {e}")
                self.use_embeddings = False

    def _normalize(self, text: str) -> str:
        return unidecode.unidecode(text.lower())

    def _bow_score(self, text: str) -> Dict[str, float]:
        text_norm = self._normalize(text)
        scores: Dict[str, float] = {k: 0.0 for k in self.VOCABULARY.keys()}

        for key, patterns in self.VOCABULARY.items():
            for p in patterns:
                p_norm = self._normalize(p)
                if " " in p_norm:
                    tokens = [t for t in p_norm.split() if t]
                    if all(t in text_norm for t in tokens):
                        scores[key] += PHRASE_WEIGHT
                else:
                    if p_norm in text_norm:
                        scores[key] += WORD_WEIGHT

        return scores

    def _semantic_fallback(self, text: str) -> Tuple[Optional[str], float]:
        if not self.use_embeddings or not self.embedding_model:
            return None, 0.0

        text_emb = self.embedding_model.encode(text, convert_to_tensor=True)
        best_intent = None
        best_score = 0.0

        for intent, ex_emb in self._examples_emb.items():
            sim = util.cos_sim(text_emb, ex_emb).max().item()
            if sim > best_score:
                best_score = sim
                best_intent = intent

        if best_score >= SEMANTIC_THRESHOLD:
            return best_intent, best_score
        return None, best_score

    def detect_intent(self, text: str) -> str:
        text_norm = self._normalize(text)
        for intent, patterns in self.VOCABULARY.items():
            for p in patterns:
                if " " in self._normalize(p) and self._normalize(p) in text_norm:
                    return self.VOCAB_KEY_TO_INTENT.get(intent, intent)

        scores = self._bow_score(text)

        intent_scores: Dict[str, float] = {}
        for key, score in scores.items():
            final_intent = self.VOCAB_KEY_TO_INTENT.get(key, key)
            intent_scores[final_intent] = intent_scores.get(final_intent, 0.0) + score

        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        if not sorted_intents:
            return "unknown"

        top_intent, top_score = sorted_intents[0]
        second_score = sorted_intents[1][1] if len(sorted_intents) > 1 else 0.0

        if (top_score == 0 or (top_score - second_score) < MIN_SCORE_DELTA) and self.use_embeddings:
            sem_intent, sem_score = self._semantic_fallback(text)
            if sem_intent and sem_score is not None:
                # se semântica sugere forte intenção e difere do top atual, usar
                if sem_score - top_score >= -0.05:  # tolerância pequena
                    return sem_intent

        # senao, retorno do bow
        return top_intent if top_score > 0 else "unknown"

    def extract_entities(self, text: str) -> Dict[str, Any]:
        text_norm = unidecode.unidecode(text)
        sku_match = self.SKU_RE.search(text_norm)
        sku = f"SKU_{sku_match.group(1)}".upper() if sku_match else None

        years = [int(y) for y in self.YEAR_RE.findall(text_norm)]
        month_year = self.MONTH_WITH_YEAR_RE.findall(text_norm)
        months = [
            {"month": MONTHS_PT.get(m.lower().replace("ç", "c")), "year": int(y)}
            for m, y in month_year
            if MONTHS_PT.get(m.lower().replace("ç", "c"))
        ]

        mnum = self.NUMBER_RE.search(text_norm)
        n = int(mnum.group(1) or mnum.group(2)) if mnum else None

        client: int | str | None = None
        client_match = re.search(r"(?:cliente|client)\s*[:#]?\s*([A-Za-z0-9\-_ &]+)", text_norm, re.I)
        if client_match:
            client_raw = client_match.group(1).strip()
            if re.fullmatch(r"\d{2,6}", client_raw):
                client = int(client_raw)
            else:
                client = client_raw

        return {"sku": sku, "months": months, "years": years, "n": n, "client": client}

    def execute(self, text: str) -> Tuple[str, Dict[str, Any]]:
        logger.debug(f"Classifying text: {text}")
        best_intent = self.detect_intent(text)
        logger.debug(f"Detected intent (hybrid): {best_intent}")

        entities = self.extract_entities(text)
 
        try:
            doc = self._nlp(text)
            for ent in doc.ents:
                if ent.label_.lower() in {"product", "produto", "sku"}:
                    entities["sku"] = ent.text
        except Exception:
            logger.error("spaCy NER failed, continuing without NER override")

        params: Dict[str, Any] = {}
        if best_intent in {
            "predict_stockout",
            "predict_sku_sales",
            "predict_top_sales",
            "sku_sales_compare",
            "sku_best_month",
            "sales_between_dates",
            "top_n_skus",
            "stock_by_client",
            "sales_time_series",
        }:
            if entities.get("sku"):
                params["sku"] = entities["sku"]
            if entities.get("months"):
                params["months"] = entities["months"]
            if entities.get("years"):
                params["years"] = entities["years"]
            if best_intent == "top_n_skus" and entities.get("n"):
                params["n"] = entities["n"]
            if best_intent == "stock_by_client" and entities.get("client"):
                params["client"] = entities["client"]
            if best_intent == "sales_between_dates":
                if len(entities.get("months", [])) >= 2:
                    params.update({"start": entities["months"][0], "end": entities["months"][1]})
                elif len(entities.get("years", [])) >= 2:
                    params.update({"start": {"year": entities['years'][0]}, "end": {"year": entities['years'][1]}})
            if best_intent == "predict_top_sales":
                if entities.get("months"):
                    params["period"] = {"type": "month", "month": entities["months"][0]["month"], "year": entities["months"][0]["year"]}
                elif entities.get("years"):
                    params["period"] = {"type": "year", "year": entities["years"][0]}
                else:
                    params["period"] = {"type": "next_month"}

        return best_intent, params
