import sys
import os
import difflib
from sqlalchemy.orm import Session
from sqlalchemy import inspect, and_, or_
from typing import List, Dict, Any

# Adiciona o diretório atual ao path do Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importa o reconhecedor de intenções
try:
    from .intent import IntentRecognizer
except ImportError:
    try:
        from intent import IntentRecognizer
    except ImportError:
        # Fallback para desenvolvimento
        class IntentRecognizer:
            def analyze(self, text):
                return [{
                    "sentence": text,
                    "subject": {"text": ""},
                    "verb": {"lemma": "", "text": ""},
                    "complement": {"text": ""}
                }]

class IntentQueryProcessor:
    def __init__(self, engine, base):
        self.engine = engine
        self.base = base
        self.recognizer = IntentRecognizer()
        self.models = self._load_models()
        
        # Mapeamento de sinônimos melhorado
        self.table_synonyms = {
            'clientes': ['cliente', 'pessoa', 'comprador'],
            'user': ['usuário', 'user', 'utilizador', 'admin', 'administrador'],
            'report': ['relatório', 'report', 'laudo', 'informe'],
            'estoque': ['estoque', 'inventário', 'stock', 'mercadoria'],
            'faturamento': ['faturamento', 'venda', 'fatura', 'receita'],
        }
        
        self.time_filters = {
            'última semana': '7 days',
            'último mês': '30 days', 
            'último ano': '365 days',
            'hoje': '1 day',
            'ontem': '1 day'
        }

    def _load_models(self):
        """Carrega dinamicamente todos os modelos declarados"""
        models = {}
        for cls in self.base.registry.mappers:
            model = cls.class_
            models[model.__tablename__] = model
        return models

    def process(self, text: str) -> Dict[str, Any]:
        """Processa o texto natural e retorna resultados da consulta"""
        try:
            intents = self.recognizer.analyze(text)
            if not intents:
                return {"erro": "Não foi possível entender a intenção"}

            intent = intents[0]
            verb = intent.get("verb", {}).get("lemma", "").lower() if intent.get("verb") else ""
            subject = intent.get("subject", {}).get("text", "").lower() if intent.get("subject") else ""
            complement = intent.get("complement", {}).get("text", "").lower() if intent.get("complement") else ""

            print(f"Debug - Verb: {verb}, Subject: {subject}, Complement: {complement}")

            # Identifica tabela e condições
            table_info = self._detect_table(text, subject, complement)
            if not table_info:
                return {"erro": f"Tabela não identificada para: {text}"}

            table_model, search_terms, conditions = table_info
            
            # Corrige o verbo "mostrir" para "mostrar"
            if verb == "mostrir":
                verb = "mostrar"
            
            # Executa consulta - apenas leitura
            results = self._execute_readonly_query(table_model, search_terms, conditions)

            return {
                "intenção": verb,
                "tabela": table_model.__tablename__,
                "termos_busca": search_terms,
                "condições": conditions,
                "resultados": len(results),
                "dados": [self._serialize_result(r) for r in results]
            }
        except Exception as e:
            return {"erro": f"Erro ao processar consulta: {str(e)}"}

    def _detect_table(self, full_text: str, subject: str, complement: str):
        """Identifica a tabela e extrai condições de busca"""
        all_text = full_text.lower()
        search_terms = []
        conditions = {}
        
        print(f"Debug - Detectando tabela para: {all_text}")
        
        # Identifica tabela principal - usa o texto completo para melhor precisão
        table_model = self._find_best_table_match(all_text)
        if not table_model:
            print(f"Debug - Nenhuma tabela encontrada para: {all_text}")
            return None

        print(f"Debug - Tabela encontrada: {table_model.__tablename__}")

        # Extrai termos de busca do texto completo
        search_terms.extend(self._extract_search_terms(all_text))

        # Identifica condições
        time_condition = self._extract_time_condition(all_text)
        if time_condition:
            conditions.update(time_condition)

        status_condition = self._extract_status_condition(all_text)
        if status_condition:
            conditions.update(status_condition)

        print(f"Debug - Termos: {search_terms}, Condições: {conditions}")
        return table_model, search_terms, conditions

    def _find_best_table_match(self, text: str):
        """Encontra a melhor correspondência de tabela com lógica melhorada"""
        words = text.split()
        table_names = list(self.models.keys())
        
        print(f"Debug - Tabelas disponíveis: {table_names}")
        print(f"Debug - Palavras para busca: {words}")
        
        # Primeiro: busca por palavras específicas com alta prioridade
        priority_words = {
            'usuário': 'user',
            'usuarios': 'user',
            'admin': 'user', 
            'administrador': 'user',
            'relatório': 'report',
            'relatorios': 'report',
            'estoque': 'estoque',
            'faturamento': 'faturamento',
            'cliente': 'clientes',
            'clientes': 'clientes'
        }
        
        for word, table_name in priority_words.items():
            if word in text and table_name in self.models:
                print(f"Debug - Match por palavra prioritária: '{word}' -> '{table_name}'")
                return self.models[table_name]
        
        # Segundo: busca em sinônimos
        for table_name, synonyms in self.table_synonyms.items():
            if table_name not in self.models:
                continue
                
            for synonym in synonyms:
                if synonym in text:
                    print(f"Debug - Match por sinônimo: '{synonym}' -> '{table_name}'")
                    return self.models[table_name]
        
        # Terceiro: busca por similaridade
        for word in words:
            if len(word) < 4:  # Ignora palavras muito curtas
                continue
                
            matches = difflib.get_close_matches(word, table_names, n=1, cutoff=0.7)
            if matches:
                print(f"Debug - Match por similaridade: '{word}' -> '{matches[0]}'")
                return self.models[matches[0]]
                
        return None

    def _extract_search_terms(self, text: str) -> List[str]:
        """Extrai termos relevantes para busca"""
        stop_words = {
            "os", "as", "o", "a", "um", "uma", "de", "da", "do", "em", "no", "na", 
            "por", "para", "são", "quais", "me", "todos", "todas", "liste", "mostre",
            "quero", "ver", "encontrar", "buscar", "procurar"
        }
        words = [word.strip('.,!?;:') for word in text.split() if word.strip('.,!?;:') not in stop_words and len(word.strip('.,!?;:')) > 2]
        return words

    def _extract_time_condition(self, text: str) -> Dict[str, Any]:
        """Extrai condições temporais do texto"""
        for time_phrase, delta in self.time_filters.items():
            if time_phrase in text:
                return {"time_filter": delta}
        return {}

    def _extract_status_condition(self, text: str) -> Dict[str, Any]:
        """Extrai condições de status"""
        status_map = {
            'ativos': 'ativo',
            'ativo': 'ativo', 
            'inativos': 'inativo',
            'inativo': 'inativo',
            'administradores': 'admin',
            'administrador': 'admin',
            'admin': 'admin'
        }
        
        for status_word, status_value in status_map.items():
            if status_word in text:
                return {"status": status_value}
        return {}

    def _execute_readonly_query(self, model, search_terms: List[str], conditions: Dict[str, Any]):
        """Executa consulta de apenas leitura de forma mais segura"""
        session = Session(self.engine)
        
        try:
            query = session.query(model)
            
            # Aplica condições de status apenas se a tabela for 'user'
            if 'status' in conditions and model.__tablename__ == 'user':
                query = self._apply_user_status_condition(query, model, conditions['status'])
                print(f"Debug - Aplicando filtro de status: {conditions['status']}")
            
            # Aplica busca por termos em colunas textuais
            if search_terms:
                query = self._apply_text_search(query, model, search_terms)
                print(f"Debug - Aplicando filtros de texto: {search_terms}")
            
            # Limita resultados para evitar sobrecarga
            results = query.limit(20).all()
            print(f"Debug - Consulta retornou {len(results)} resultados")
            return results
            
        except Exception as e:
            print(f"Erro na consulta: {e}")
            # Tenta uma consulta mais simples como fallback
            try:
                results = session.query(model).limit(10).all()
                return results
            except Exception as fallback_error:
                print(f"Erro no fallback: {fallback_error}")
                return []
        finally:
            session.close()

    def _apply_user_status_condition(self, query, model, status_value):
        """Aplica condição de status para tabela user"""
        status_mapping = {
            'ativo': (model.is_active, True),
            'inativo': (model.is_active, False),
            'admin': (model.is_admin, True)
        }
        
        if status_value in status_mapping:
            column, value = status_mapping[status_value]
            return query.filter(column == value)
        
        return query

    def _apply_text_search(self, query, model, search_terms: List[str]):
        """Aplica busca por texto nas colunas string"""
        text_conditions = []
        inspector = inspect(model)
        
        for column in inspector.columns:
            col_type = str(column.type).upper()
            if any(tipo in col_type for tipo in ['VARCHAR', 'TEXT', 'CHAR']):
                for term in search_terms:
                    # Remove pontuação do termo
                    clean_term = term.strip('.,!?;:')
                    if len(clean_term) > 2:  # Só busca termos com mais de 2 caracteres
                        text_conditions.append(column.ilike(f"%{clean_term}%"))
        
        if text_conditions:
            return query.filter(or_(*text_conditions))
        
        return query

    def _serialize_result(self, result):
        """Serializa resultado para JSON"""
        if hasattr(result, '_asdict'):
            return result._asdict()
        elif hasattr(result, '__dict__'):
            return {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
        else:
            return str(result)

# Para teste direto - corrigindo a importação
if __name__ == "__main__":
    import sys
    import os
    from sqlalchemy import create_engine
    
    # Adiciona o diretório pai ao path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # src
    project_root = os.path.dirname(parent_dir)  # raiz do projeto
    sys.path.append(project_root)
    
    try:
        from src.database.models import Base
        
        # Tenta importar settings do caminho correto
        try:
            from src.settings import settings
            DATABASE_URL = settings.DATABASE_URL
            print(f"Usando DATABASE_URL do settings: {DATABASE_URL[:20]}...")  # Log parcial por segurança
        except ImportError as e:
            print(f"Erro ao importar settings: {e}")
            # Fallback direto para PostgreSQL - ALTERE COM SUAS CREDENCIAIS
            DATABASE_URL = "postgresql://usuario:senha@localhost:5432/seu_banco"
            print(f"Usando DATABASE_URL fallback: {DATABASE_URL}")
            
    except ImportError as e:
        print(f"Erro ao importar Base: {e}")
        sys.exit(1)

    # Configuração do banco - SEM fallback para SQLite
    engine = create_engine(DATABASE_URL)
    
    # Testa a conexão com o banco
    try:
        with engine.connect() as conn:
            print("✅ Conexão com o banco estabelecida com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao conectar com o banco: {e}")
        print("Verifique se:")
        print("1. O PostgreSQL está rodando")
        print("2. A DATABASE_URL está correta no arquivo .env")
        print("3. As tabelas existem no banco")
        sys.exit(1)

    processor = IntentQueryProcessor(engine, Base)

    consultas = [
        "Quais são os clientes ativos?",
        "Me mostre os usuários administradores",
        "Liste todos os clientes",
        "Mostre os relatórios",
        "Mostre o estoque",
        "Liste o faturamento",
        "Quero ver os usuários ativos"
    ]

    for consulta in consultas:
        print(f"\n{'='*50}")
        print(f"Consulta: {consulta}")
        resultado = processor.process(consulta)
        print(f"Resultado: {resultado}")