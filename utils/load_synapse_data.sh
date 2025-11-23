#!/bin/bash
set -e

export PGPASSWORD='admin'

DB_NAME="synapse"
ESTOQUE_FILE="./estoque 1.csv"
FATURAMENTO_FILE="./faturamento 1.csv"
CLIENTES_FILE="./clientes.csv"
DUMP_FILE="$(pwd)/${DB_NAME}_backup.dump"

if [ -f "$CLIENTES_FILE" ]; then
    rm -f "$CLIENTES_FILE"
fi

touch "$CLIENTES_FILE"
chmod 664 "$CLIENTES_FILE"

echo "cod_cliente" > "$CLIENTES_FILE"

{
    cut -d"|" -f2 "$ESTOQUE_FILE" | tail -n +2
    cut -d"|" -f2 "$FATURAMENTO_FILE" | tail -n +2
} | sort -u >> "$CLIENTES_FILE"

psql -U postgres -d "$DB_NAME" -c "\COPY clientes(cod_cliente) FROM '$CLIENTES_FILE' WITH (FORMAT csv, HEADER true, DELIMITER '|')"

psql -U postgres -d "$DB_NAME" -c "
WITH cte AS (
    SELECT cod_cliente, 'Cliente ' || ROW_NUMBER() OVER (ORDER BY cod_cliente) AS nome
    FROM clientes
)
UPDATE clientes c
SET nome = cte.nome
FROM cte
WHERE c.cod_cliente = cte.cod_cliente;
"

psql -U postgres -d "$DB_NAME" -c "\COPY estoque(data, cod_cliente, es_centro, tipo_material, origem, cod_produto, lote, dias_em_estoque, produto, grupo_mercadoria, es_totalestoque, sku) FROM '$ESTOQUE_FILE' WITH (FORMAT csv, HEADER true, DELIMITER '|')"

psql -U postgres -d "$DB_NAME" -c "\COPY faturamento(data, cod_cliente, lote, origem, zs_gr_mercad, produto, cod_produto, zs_centro, zs_cidade, zs_uf, zs_peso_liquido, giro_sku_cliente, sku) FROM '$FATURAMENTO_FILE' WITH (FORMAT csv, HEADER true, DELIMITER '|')"

pg_dump -U postgres -d "$DB_NAME" > "$DUMP_FILE"

echo "Carga concluída com sucesso 🚀"
echo "Backup gerado em: $DUMP_FILE"