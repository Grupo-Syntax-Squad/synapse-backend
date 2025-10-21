import spacy
from sqlalchemy import Engine, create_engine, inspect
from src.settings import settings
import requests
import json
from typing import Optional


class IntentEntityRecognizer:
    def __init__(self) -> None:
        self._nlp = spacy.load("pt_core_news_sm")

    def recognize(self, text: str) -> Optional[str]:
        doc = self._nlp(text)
        for ent in doc.ents:
            return ent.text
        return None


class SchemaExtractor:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.inspector = inspect(engine)

    def get_schema(self) -> dict[str, list[str]]:
        schema: dict[str, list[str]] = {}
        for table_name in self.inspector.get_table_names():
            columns = [col["name"] for col in self.inspector.get_columns(table_name)]
            schema[table_name] = columns
        return schema

    def schema_to_text(self) -> str:
        schema = self.get_schema()
        lines = [f"- {table}({', '.join(cols)})" for table, cols in schema.items()]
        return "\n".join(lines)


class QueryGeneratorOpenRouter:
    def __init__(self) -> None:
        self._api_key: str = settings.OPEN_ROUTER_API_KEY
        self._model: str = settings.OPEN_ROUTER_MODEL
        self._endpoint: str = "https://openrouter.ai/v1/chat/completions"

    def generate_query(
        self, entity: str, schema_text: str, extra_context: Optional[str] = ""
    ) -> str:
        prompt = f"""
Você é um assistente que gera apenas queries SELECT válidas para um banco SQL.

Schema do banco:
{schema_text}

Entidade ou filtro solicitado pelo usuário: {entity}

Contexto adicional: {extra_context}

Retorne apenas a query SQL, sem explicações.
"""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        response = requests.post(
            self._endpoint, headers=headers, data=json.dumps(payload)
        )
        print("Status code:", response.status_code)
        print("Resposta crua:", response.text)
        try:
            result = response.json()
        except json.JSONDecodeError:
            raise ValueError(
                f"Não foi possível decodificar JSON. Resposta do servidor: {response.text}"
            )

        return str(result["choices"][0]["message"]["content"].strip())


if __name__ == "__main__":
    user_text = "Quero consultar todos os clientes ativos"
    recognizer = IntentEntityRecognizer()
    entity = recognizer.recognize(user_text)

    if entity is None:
        raise ValueError("Nenhuma entidade identificada no texto do usuário")

    print(f"Entidade identificada: {entity}")

    engine = create_engine(settings.DATABASE_URL)
    extractor = SchemaExtractor(engine)
    schema_text = extractor.schema_to_text()
    print(f"Schema do banco:\n{schema_text}")

    generator = QueryGeneratorOpenRouter()
    query = generator.generate_query(entity, schema_text)
    print(f"Query gerada:\n{query}")
