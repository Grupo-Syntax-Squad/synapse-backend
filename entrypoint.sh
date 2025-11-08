echo "Aguardando o PostgreSQL iniciar..."

while ! nc -z postgres 5432; do
  sleep 1
done

echo "Banco pronto! Executando migrações..."
alembic upgrade head

echo "Iniciando servidor Uvicorn..."
exec uvicorn src.main:app --host 0.0.0.0 --port 80
