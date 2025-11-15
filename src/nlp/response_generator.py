from typing import Any, Callable
import random

from src.logger_instance import logger


class ResponseGenerator:
    def __init__(self) -> None:
        self._response_handlers: dict[str, Callable[[dict[str, Any], Any], str]] = {
            "total_stock": self._format_total_stock,
            "distinct_products_count": self._format_distinct_products_count,
            "active_clients_count": self._format_active_clients_count,
            "sku_sales_compare": self._format_sku_sales_compare,
            "sku_best_month": self._format_sku_best_month,
            "sales_time_series": self._format_sales_time_series,
            "sales_between_dates": self._format_sales_between_dates,
            "top_n_skus": self._format_top_n_skus,
            "stock_by_client": self._format_stock_by_client,
            "predict_stockout": self._format_predict_stockout,
            "predict_top_sales": self._format_predict_top_sales,
            "predict_sku_sales": self._format_predict_sku_sales,
            "greeting": self._format_greeting,
            "farewell": self._format_farewell,
            "unknown_intent": self._format_unknown_intent,
        }

    def _format_greeting(self, params: dict[str, Any], result: Any) -> str:
        greetings = [
            "Olá! Como posso ajudar você com informações sobre vendas e estoque?",
            "Oi! Estou aqui para ajudar com dados de vendas, estoque e previsões.",
            "Olá! Pronto para analisar alguns dados de negócio?",
            "Oi! Em que posso ser útil hoje?",
        ]
        return random.choice(greetings)

    def _format_farewell(self, params: dict[str, Any], result: Any) -> str:
        farewells = [
            "Até logo! Fico à disposição para mais análises.",
            "Obrigado! Volte sempre que precisar de informações.",
            "Tchau! Foi um prazer ajudar.",
            "Até mais! Estarei aqui quando precisar.",
        ]
        return random.choice(farewells)

    def _format_unknown_intent(self, params: dict[str, Any], result: Any) -> str:
        original_text = params.get("original_text", "")
        responses = [
            f"Desculpe, não entendi '{original_text}'. Posso ajudar com informações sobre vendas, estoque, previsões e análises de SKU.",
            f"Não consegui compreender '{original_text}'. Tente perguntar sobre vendas, estoque, produtos mais vendidos ou previsões.",
            f"Minha especialidade é análise de dados comerciais. Não entendi '{original_text}'. Que tal perguntar sobre vendas ou estoque?",
        ]
        return random.choice(responses)

    def _format_total_stock(self, params: dict[str, Any], result: Any) -> str:
        if isinstance(result, dict) and "total_stock" in result:
            total = result["total_stock"]
            return f"O total de itens em estoque é {total}."

        return "Nenhum dado disponível sobre estoque."

    def _format_distinct_products_count(
        self, params: dict[str, Any], result: Any
    ) -> str:
        c = result.get("distinct_products") if isinstance(result, dict) else None
        return (
            f"Encontramos {c} produtos diferentes no estoque."
            if c is not None
            else "Não foi possível contar os produtos."
        )

    def _format_active_clients_count(self, params: dict[str, Any], result: Any) -> str:
        ac = result.get("active_clients") if isinstance(result, dict) else None
        note = result.get("note") if isinstance(result, dict) else None
        base = (
            f"Existem {ac} clientes ativos."
            if ac is not None
            else "Não foi possível contar clientes ativos."
        )
        if note:
            base += f" (Observação: {note})"
        return base

    def _format_sku_sales_compare(self, params: dict[str, Any], result: Any) -> str:
        sku = params.get("sku", "o SKU solicitado")

        intro = (
            f"Analisando as vendas do {sku}, "
            if random.random() > 0.5
            else f"Comparando o desempenho do {sku}, "
        )

        if "period1" in result and "period2" in result:
            p1_val = result["period1"]
            p2_val = result["period2"]

            if p1_val > p2_val:
                return (
                    f"{intro}o primeiro período teve vendas maiores "
                    f"({p1_val} vs {p2_val})."
                )
            elif p2_val > p1_val:
                return (
                    f"{intro}o segundo período teve vendas maiores "
                    f"({p2_val} vs {p1_val})."
                )
            else:
                return f"{intro}as vendas foram iguais nos dois períodos ({p1_val})."

        if "year1" in result and "year2" in result:
            y1_val = result["year1"]
            y2_val = result["year2"]

            if y1_val > y2_val:
                return (
                    f"{intro}o primeiro ano teve vendas maiores ({y1_val} vs {y2_val})."
                )
            elif y2_val > y1_val:
                return (
                    f"{intro}o segundo ano teve vendas maiores ({y2_val} vs {y1_val})."
                )
            else:
                return f"{intro}as vendas foram iguais nos dois anos ({y1_val})."

        return f"Não foi possível obter dados comparativos para {sku}."

    def _format_sku_best_month(self, params: dict[str, Any], result: Any) -> str:
        sku = result.get("sku", params.get("sku", "o SKU solicitado"))
        bm = result.get("best_month") if isinstance(result, dict) else None
        if bm:
            return f"O melhor mês de vendas para o SKU {sku} foi {bm['month']:02d}/{bm['year']}, com um total de {bm['total']} unidades."
        return f"Não encontrei registros de vendas para o SKU {sku} para determinar o melhor mês."

    def _format_sales_time_series(self, params: dict[str, Any], result: Any) -> str:
        sku_info = f" para o SKU {params['sku']}" if params.get("sku") else ""
        if isinstance(result, list) and result:
            first = result[0]
            last = result[-1]
            return f"Encontrei {len(result)} registros de vendas mensais{sku_info}, indo de {first['month']:02d}/{first['year']} (Total: {first['total']}) até {last['month']:02d}/{last['year']} (Total: {last['total']})."
        return f"Não há dados de série temporal de vendas disponíveis{sku_info}."

    def _format_sales_between_dates(self, params: dict[str, Any], result: Any) -> str:
        total = result.get("total") if isinstance(result, dict) else None
        filters = result.get("filters", {}) if isinstance(result, dict) else {}
        sku_info = f" para o SKU {filters['sku']}" if filters.get("sku") else ""
        period_info = ""

        if "start_ym" in filters and "end_ym" in filters:
            start_y, start_m = filters["start_ym"].split("-")
            end_y, end_m = filters["end_ym"].split("-")
            period_info = (
                f"entre {int(start_m):02d}/{start_y} e {int(end_m):02d}/{end_y}"
            )
        elif "y1" in filters and "y2" in filters:
            period_info = f"entre os anos {filters['y1']} e {filters['y2']}"

        if total is not None:
            return f"O total de vendas{sku_info} no período {period_info} foi de {total} unidades."
        return f"Não encontrei vendas{sku_info} no período {period_info}."

    def _format_top_n_skus(self, params: dict[str, Any], result: Any) -> str:
        if not result:
            return "Desculpe, não consegui encontrar os SKUs mais vendidos."

        intro = "Os SKUs com melhor desempenho são:"

        sku_lines = []
        for i, r in enumerate(result, 1):
            sku_lines.append(f"{i}. {r['sku']}: {r['total']} vendas")

        formatted_skus = "\n".join(sku_lines)
        return f"{intro}\n{formatted_skus}"

    def _format_stock_by_client(self, params: dict[str, Any], result: Any) -> str:
        total = result.get("total_stock_client") if isinstance(result, dict) else None
        filters = result.get("filters", {}) if isinstance(result, dict) else {}
        if total is not None:
            if filters.get("client"):
                return f"O estoque total associado ao cliente {filters['client']} é de {total} unidades."
            return f"O estoque total (considerando todos os clientes/registros) é de {total} unidades."
        client_info = (
            f" para o cliente {params['client']}" if params.get("client") else ""
        )
        return f"Não foi possível calcular o estoque{client_info}."

    def _format_predict_stockout(self, params: dict[str, Any], result: Any) -> str:
        if "error" in result:
            return result["error"]  # type: ignore[no-any-return]

        predictions = result.get("predictions", [])
        if not predictions:
            return "Não foi identificado risco de estoque zero para nenhum SKU no próximo mês."

        response = "SKUs com risco de estoque zero:\n\n"
        for p in predictions:
            stockout_date = p["predicted_stockout"].strftime("%d/%m/%Y")
            current_avg = int(p["current_avg"])
            predicted_avg = int(p["predicted_avg"])
            percent_drop = (
                ((current_avg - predicted_avg) / current_avg * 100)
                if current_avg > 0
                else 0
            )

            response += (
                f"SKU: {p['sku']}\n"
                f"- Data prevista: {stockout_date}\n"
                f"- Média atual: {current_avg} unidades\n"
                f"- Média prevista: {predicted_avg} unidades\n"
                f"- Queda prevista: {percent_drop:.1f}%\n\n"
            )
        return response

    def _format_predict_top_sales(self, params: dict[str, Any], result: Any) -> str:
        if "error" in result:
            return result["error"]  # type: ignore[no-any-return]

        predictions = result.get("predictions", [])
        if not predictions:
            return "Não foi possível fazer previsões de vendas no momento."

        period = (
            "próximo mês" if params.get("period") == "next_month" else "próximo ano"
        )
        response = f"Previsão dos SKUs mais vendidos para o {period}:\n\n"

        for i, p in enumerate(predictions, 1):
            predicted = int(p["predicted_sales"])
            current = int(p["current_avg"])
            growth = p["growth_rate"]

            growth_text = (
                f"crescimento de {growth:.1f}%"
                if growth > 0
                else f"queda de {abs(growth):.1f}%"
                if growth < 0
                else "estável"
            )

            response += (
                f"{i}. SKU: {p['sku']}\n"
                f"   - Previsão: {predicted} unidades\n"
                f"   - Média atual: {current} unidades\n"
                f"   - Tendência: {growth_text}\n\n"
            )
        return response

    def _format_predict_sku_sales(self, params: dict[str, Any], result: Any) -> str:
        if "error" in result:
            return result["error"]  # type: ignore[no-any-return]

        sku = result["sku"]
        predicted = int(result["predicted_sales"])
        current = int(result["current_avg"])
        growth = result["growth_rate"]
        period = (
            "próximo mês" if params.get("period") == "next_month" else "próximo ano"
        )

        growth_text = (
            f"crescimento de {growth:.1f}%"
            if growth > 0
            else f"queda de {abs(growth):.1f}%"
            if growth < 0
            else "estável"
        )

        ci = result.get("confidence_interval", {})
        confidence_text = (
            f"\nIntervalo de confiança: entre {int(ci['lower'])} e {int(ci['upper'])} unidades"
            if ci
            else ""
        )

        return (
            f"Análise de vendas para o SKU {sku}:\n\n"
            f"- Período: {period}\n"
            f"- Média atual: {current} unidades\n"
            f"- Previsão: {predicted} unidades\n"
            f"- Tendência: {growth_text}{confidence_text}"
        )

    def execute(self, intent: str, params: dict[str, Any], result: Any) -> str:
        handler = self._response_handlers.get(intent)
        if not handler:
            logger.warning(
                f"Aviso: Handler de resposta não encontrado para a intenção '{intent}'"
            )
            return f"Não tenho um formato de resposta específico para '{intent}', mas o resultado foi: {result}"

        try:
            return handler(params, result)
        except Exception as e:
            logger.error(f"Erro ao gerar resposta para intent '{intent}': {e}")
            return "Desculpe — não consegui formular uma resposta amigável a partir dos dados retornados."