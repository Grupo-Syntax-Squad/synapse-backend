import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.models import Clients, Estoque, Faturamento
from src.logger_instance import logger
from src.settings import settings


class DataLoader:
    def __init__(self, session: Session):
        self._session = session
        base_path = settings.CLIENT_DATABASE_FILES_FOLDER_PATH.rstrip("/")
        self.ESTOQUE_FILE = f"{base_path}/estoque 1.csv"
        self.FATURAMENTO_FILE = f"{base_path}/faturamento 1.csv"
        self.CLIENTES_FILE = f"{base_path}/clientes.csv"
        self._log = logger

    def generate_clients_csv(self) -> None:
        self._log.info("Gerando clientes.csv...")
        esto_df = pd.read_csv(self.ESTOQUE_FILE, sep="|")
        fat_df = pd.read_csv(self.FATURAMENTO_FILE, sep="|")
        cods = (
            pd.concat([esto_df.iloc[:, 1], fat_df.iloc[:, 1]])
            .dropna()
            .astype(int)
            .drop_duplicates()
            .sort_values()
        )
        pd.DataFrame({"cod_cliente": cods}).to_csv(self.CLIENTES_FILE, index=False)
        self._log.info("clientes.csv gerado!")

    def load_clients(self) -> None:
        self._log.info("Carregando tabela clientes...")
        df = pd.read_csv(self.CLIENTES_FILE)
        self._session.query(Clients).delete()
        self._session.bulk_insert_mappings(Clients, df.to_dict(orient="records"))  # type: ignore[arg-type]
        self._session.commit()

    def update_client_names(self) -> None:
        self._log.info("Atualizando nome dos clientes...")
        stmt = text("""
            WITH cte AS (
                SELECT cod_cliente,
                       'Cliente ' || ROW_NUMBER() OVER (ORDER BY cod_cliente) AS nome
                FROM clientes
            )
            UPDATE clientes c
            SET nome = cte.nome
            FROM cte
            WHERE c.cod_cliente = cte.cod_cliente;
        """)
        self._session.execute(stmt)
        self._session.commit()

    def load_estoque(self) -> None:
        self._log.info("Carregando tabela estoque...")
        df = pd.read_csv(self.ESTOQUE_FILE, sep="|")
        df.columns = df.columns.str.lower()
        missing_sku = df[df["sku"].isna()]
        if not missing_sku.empty:
            self._log.warning(
                f"{len(missing_sku)} linhas com SKU nulo serão ignoradas:\n{missing_sku}"
            )
        df_valid = df.dropna(subset=["sku"])
        self._session.query(Estoque).delete()
        self._session.bulk_insert_mappings(Estoque, df_valid.to_dict(orient="records"))  # type: ignore[arg-type]
        self._session.commit()
        self._log.info(f"{len(df_valid)} linhas de estoque carregadas com sucesso!")

    def load_faturamento(self) -> None:
        self._log.info("Carregando tabela faturamento...")
        df = pd.read_csv(self.FATURAMENTO_FILE, sep="|")
        df.columns = df.columns.str.lower()
        missing_sku = df[df["sku"].isna()]
        if not missing_sku.empty:
            self._log.warning(
                f"{len(missing_sku)} linhas com SKU nulo serão ignoradas:\n{missing_sku}"
            )
        df_valid = df.dropna(subset=["sku"])
        self._session.query(Faturamento).delete()
        self._session.bulk_insert_mappings(
            Faturamento,  # type: ignore[arg-type]
            df_valid.to_dict(orient="records"),
        )
        self._session.commit()
        self._log.info(f"{len(df_valid)} linhas de faturamento carregadas com sucesso!")

    def execute(self) -> None:
        self._log.info("Iniciando rotina de carga (DataLoader)...")
        self.generate_clients_csv()
        self.load_clients()
        self.update_client_names()
        self.load_estoque()
        self.load_faturamento()
        self._log.info("Carga concluída com sucesso 🚀")
