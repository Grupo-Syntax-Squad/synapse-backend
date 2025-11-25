# encoding: utf-8
import redis
from contextlib import contextmanager
from typing import Generator

from src.settings import settings
from src.logger_instance import logger

redis_pool: redis.ConnectionPool | None = None
redis_client_instance: redis.Redis | None = None

try:
    redis_pool = redis.ConnectionPool.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    redis_client_instance = redis.Redis(connection_pool=redis_pool)
    redis_client_instance.ping()
    logger.debug("Conectado ao pool do Redis com sucesso.")
except Exception as e:
    logger.error(f"Não foi possível conectar ao Redis: {e}")
    redis_pool = None
    redis_client_instance = None


@contextmanager
def get_redis_client() -> Generator[redis.Redis, None, None]:
    if redis_client_instance is None:
        logger.error("Pool de conexão do Redis não foi inicializado.")
        raise ConnectionError("Pool de conexão do Redis não foi inicializado.")
    client = redis_client_instance
    try:
        yield client
    except redis.RedisError as e:
        logger.error(f"Erro de conexão com o Redis: {e}")
        raise


def get_redis_dependency() -> Generator[redis.Redis, None, None]:
    with get_redis_client() as client:
        yield client
