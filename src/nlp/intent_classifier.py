import re
import unidecode
from typing import Any, Dict, Tuple, Optional, cast
from huggingface_hub import hf_hub_download

import spacy
from src.logger_instance import logger

# default to keep static analyzers happy if import fails
EMBEDDING_AVAILABLE = False

# Shared, cached models to avoid reloading on every class instantiation
# Use explicit annotations so static checkers know the expected types.
_NL_PARSER: Optional[Any] = None
_EMBEDDING_MODEL: Optional[Any] = None
_EXAMPLES_EMB: Dict[str, Any] = {}

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

# quando usar semântica: similaridade mínima para aceitar fallback
# reduced threshold slightly to avoid many unknowns in borderline cases
SEMANTIC_THRESHOLD = 0.35
# diferença mínima de score entre top intents para aceitar semântica
MIN_SCORE_DELTA = 0.05


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

    # aliases for intents (legacy names -> canonical intent names)
    VOCAB_KEY_TO_INTENT = {
        "sales_time_series_sku": "sales_time_series",
    }

    INTENT_EXAMPLES = {
        "greeting": [
            "oi",
            "olá",
            "eae",
            "tudo bem?",
            "bom dia",
            "boa tarde",
            "boa noite",
            "hey",
            "fala",
            "salve",
            "iai",
            "como vai",
            "tudo certo?",
            "oi, tudo bem?",
        ],
        "farewell": [
            "tchau",
            "até mais",
            "até logo",
            "valeu",
            "flw",
            "adeus",
            "bye",
            "obrigado",
            "obrigada",
            "até a próxima",
            "falou",
            "encerrar",
            "finalizar",
            "fim",
        ],
        "predict_stockout": [
            "o produto vai acabar?",
            "tem estoque desse item?",
            "vai zerar o estoque?",
            "ficaremos sem esse produto?",
            "previsão de ruptura de estoque",
            "produto esgotando",
            "o estoque está baixo",
            "quando vai acabar o estoque?",
        ],
        "predict_top_sales": [
            "quais produtos vão vender mais no próximo mês?",
            "previsão dos produtos mais vendidos",
            "top vendas no próximo mês",
            "quais serão os mais vendidos?",
            "produtos com maior venda prevista",
            "ranking de vendas esperado",
            "quais itens terão maior faturamento?",
            "quais produtos terão maior demanda?",
        ],
        "predict_sku_sales": [
            "quanto o sku vai vender no próximo mês?",
            "previsão de vendas do sku_10",
            "projeção de vendas do sku 123",
            "quanto vai faturar o produto sku_345?",
            "previsão de faturamento do sku_999",
            "projeção do sku_777",
            "quanto venderá o sku_ABC?",
            "quantas unidades do sku_456 serão vendidas?",
            "previsão de vendas do produto X",
        ],
        "sales_between_dates": [
            "quanto vendemos entre junho e agosto?",
            "vendas entre 01/01/2024 e 31/03/2024",
            "faturamento do período de março a maio",
            "total de vendas entre datas específicas",
            "quanto faturamos entre essas datas?",
            "vendas no trimestre passado",
            "quanto foi vendido no mês passado?",
        ],
        "top_n_skus": [
            "top 5 produtos",
            "quais os 10 mais vendidos?",
            "me mostre o top 3",
            "ranking dos principais produtos",
            "produtos mais vendidos do mês",
            "lista dos top skus",
            "quais skus tiveram maior venda?",
        ],
        "sales_time_series": [
            "mostrar histórico de vendas por mês",
            "série temporal de faturamento",
            "evolução de vendas mensal",
            "histórico mensal de faturamento",
            "linha do tempo das vendas",
            "gráfico de vendas por mês",
            "como as vendas evoluíram ao longo do tempo?",
            "histórico de faturamento ao longo do ano",
        ],
        "sales_time_series_sku": [
            "série temporal do sku_10",
            "histórico de vendas do sku 123",
            "evolução de vendas do produto X",
            "vendas por mês do sku_456",
            "faturamento por mês do sku_789",
            "histórico mensal do produto Y",
            "como as vendas do sku_ABC mudaram ao longo do tempo?",
        ],
        "sku_sales_compare": [
            "comparar vendas do sku_10 com sku_20",
            "qual sku vendeu mais em março?",
            "diferença de vendas entre sku_123 e sku_456",
            "comparativo de vendas entre produtos",
            "quais skus tiveram maior venda no período?",
            "quem vendeu mais, sku_10 ou sku_20?",
            "comparar faturamento do sku_ABC com sku_DEF",
        ],
        "sku_best_month": [
            "qual foi o melhor mês do sku_123?",
            "em que mês o produto X vendeu mais?",
            "melhor mês para vendas do sku_456",
            "histórico do mês com maior venda do produto Y",
            "quando o sku_789 teve maior faturamento?",
            "mes que mais vendeu o sku_ABC",
        ],
        "active_clients_count": [
            "quantos clientes ativos temos?",
            "quantos clientes temos no total?",
            "quantidade de clientes ativos?",
            "número de clientes cadastrados",
            "clientes ativos no sistema",
            "total de clientes",
        ],
        "distinct_products_count": [
            "quantos produtos distintos temos?",
            "skus distintos no sistema",
            "produtos únicos cadastrados",
            "quantidade de produtos diferentes",
            "total de skus únicos",
            "quantos skus diferentes existem?",
        ],
        "stock_by_client": [
            "estoque por cliente",
            "estoque do cliente X",
            "quanto cada cliente tem em estoque?",
            "quantidade de produtos por cliente",
            "estoque disponível por cliente",
            "relatório de estoque do cliente",
        ],
        "total_stock": [
            "estoque total",
            "quantidade total em estoque",
            "total de produtos disponíveis",
            "relatório do estoque geral",
            "quantos itens temos no estoque?",
        ],
    }

    def __init__(
        self, use_embeddings: bool = True, allow_model_download: bool = True
    ) -> None:
        global _NL_PARSER, _EMBEDDING_MODEL, _EXAMPLES_EMB, EMBEDDING_AVAILABLE
        if _NL_PARSER is None:
            try:
                _NL_PARSER = spacy.load("pt_core_news_sm")
            except Exception:
                # Best-effort load; if it fails, set to None and continue
                _NL_PARSER = None
        self._nlp = _NL_PARSER
        self.use_embeddings = use_embeddings

        self.embedding_model = None
        self._examples_emb = {}
        self._util = None
        # No rule-based prefixes: we use semantic-only matching
        if self.use_embeddings:
            try:
                # Import and cache the embedding model and embeddings to avoid re-loading
                from sentence_transformers import SentenceTransformer, util as s_util

                # If downloads are not allowed, check model exists in HF cache
                model_name = "sentence-transformers/all-MiniLM-L6-v2"
                model_cached = True
                if not allow_model_download:
                    try:
                        # Try to fetch a small file from the local cache only
                        hf_hub_download(
                            repo_id=model_name,
                            filename="config.json",
                            repo_type="model",
                            local_files_only=True,
                        )
                        model_cached = True
                    except Exception:
                        model_cached = False

                if not model_cached and not allow_model_download:
                    logger.warning(
                        "Embedding model not in local cache and model download is disabled. Semantic detection is disabled."
                    )
                    self.use_embeddings = False
                else:
                    if _EMBEDDING_MODEL is None:
                        logger.info(
                            "Loading embedding model (may download from HF). This can take a few seconds on first run."
                        )
                        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
                self.embedding_model = _EMBEDDING_MODEL
                self._util = s_util
                # compute per-intent mean embedding vector for faster and more stable similarity
                if not _EXAMPLES_EMB:
                    temp = {
                        intent: cast(Any, _EMBEDDING_MODEL).encode(
                            exs, convert_to_tensor=True
                        )
                        for intent, exs in self.INTENT_EXAMPLES.items()
                    }
                    # store mean vector per intent
                    _EXAMPLES_EMB = {}
                    for intent, v in temp.items():
                        # if torch tensor, use mean(0), if numpy array, use mean(axis=0)
                        # In practice, v is a torch tensor; cast to Any so static type
                        # checkers don't complain about mean signature.
                        mean_vec = cast(Any, v).mean(0)
                        _EXAMPLES_EMB[intent] = mean_vec
                self._examples_emb = _EXAMPLES_EMB
                EMBEDDING_AVAILABLE = True
                logger.info(
                    f"Embedding model loaded: {type(self.embedding_model).__name__}; {len(self._examples_emb)} intents cached"
                )
            except Exception as e:
                logger.warning(
                    f"Embedding model not available, semantic detection disabled: {e}"
                )
                self.use_embeddings = False

    def _normalize(self, text: str) -> str:
        return unidecode.unidecode(text.lower())

    def _semantic_detect(self, text: str) -> Tuple[Optional[str], float, float]:
        """
        Compute semantic similarity against example embeddings and return
        the best intent and a confidence score along with the second best score.
        """
        if not self.use_embeddings or not self.embedding_model or not self._util:
            return None, 0.0, 0.0

        text_emb = self.embedding_model.encode(text, convert_to_tensor=True)
        best_intent = None
        best_score = float("-inf")
        second_score = float("-inf")

        for intent, ex_emb in self._examples_emb.items():
            sim_t = self._util.cos_sim(text_emb, ex_emb)
            # returns a 1x1 tensor (since ex_emb is a single vector); get scalar
            sim = sim_t.item() if hasattr(sim_t, "item") else float(sim_t)
            if sim > best_score:
                second_score = best_score
                best_score = sim
                best_intent = intent
            elif sim > second_score:
                second_score = sim

        # if second_score remained -inf, set to 0.0
        if second_score == float("-inf"):
            second_score = 0.0
        if best_score == float("-inf"):
            best_score = 0.0
        return best_intent, float(best_score), float(second_score)

    def intent_candidates(self, text: str) -> list[tuple[str, float]]:
        """
        Return a ranked list of intents and similarity scores for a given text.
        Helpful for debugging and logging.
        """
        if not self.use_embeddings or not self.embedding_model or not self._util:
            return []
        text_emb = self.embedding_model.encode(text, convert_to_tensor=True)
        results: list[tuple[str, float]] = []
        for intent, ex_emb in self._examples_emb.items():
            sim_t = self._util.cos_sim(text_emb, ex_emb)
            sim = sim_t.item() if hasattr(sim_t, "item") else float(sim_t)
            results.append((intent, float(sim)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _semantic_fallback(self, text: str) -> Tuple[Optional[str], float]:
        # keep for backwards compatibility: delegate to _semantic_detect
        best_intent, best_score, _ = self._semantic_detect(text)
        if best_score >= SEMANTIC_THRESHOLD:
            return best_intent, best_score
        return None, best_score

    def detect_intent(self, text: str) -> str:
        # Only semantic transformer-based intent detection is used now.
        if not self.use_embeddings or not self.embedding_model:
            logger.warning(
                "Embedding model not available, returning 'unknown_intent' intent"
            )
            return "unknown_intent"

        best_intent, best_score, second_score = self._semantic_detect(text)
        logger.debug(
            f"Semantic decision: best={best_intent} score={best_score:.3f} second={second_score:.3f}"
        )
        if self.use_embeddings:
            candidates = self.intent_candidates(text)
            logger.debug(f"Intent candidates (top 5): {candidates[:5]}")
        if best_intent:
            canonical = self.VOCAB_KEY_TO_INTENT.get(best_intent)
            return canonical if canonical is not None else best_intent

        return "unknown_intent"

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
        client_match = re.search(
            r"(?:cliente|client)\s*[:#]?\s*([A-Za-z0-9\-_ &]+)", text_norm, re.I
        )
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
        logger.debug(f"Detected intent (semantic): {best_intent}")

        entities = self.extract_entities(text)

        try:
            if self._nlp:
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
                    params.update(
                        {"start": entities["months"][0], "end": entities["months"][1]}
                    )
                elif len(entities.get("years", [])) >= 2:
                    params.update(
                        {
                            "start": {"year": entities["years"][0]},
                            "end": {"year": entities["years"][1]},
                        }
                    )
            if best_intent == "predict_top_sales":
                if entities.get("months"):
                    params["period"] = {
                        "type": "month",
                        "month": entities["months"][0]["month"],
                        "year": entities["months"][0]["year"],
                    }
                elif entities.get("years"):
                    params["period"] = {"type": "year", "year": entities["years"][0]}
                else:
                    params["period"] = {"type": "next_month"}

        # If unknown intent, keep original text in params for better UX in responses
        if best_intent == "unknown_intent":
            params.setdefault("original_text", text)

        return best_intent, params
