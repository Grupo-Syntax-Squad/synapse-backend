#!/bin/bash
set -e

DB_NAME="synapse"
ESTOQUE_FILE="/mnt/data/estoque 1.csv"
FATURAMENTO_FILE="/mnt/data/faturamento 1.csv"
CLIENTES_FILE="/mnt/clientes.csv"
DUMP_FILE="$(pwd)/${DB_NAME}_backup.dump"

# 1. Remover clientes.csv se já existir
if [ -f "$CLIENTES_FILE" ]; then
    rm -f "$CLIENTES_FILE"
fi

# Criar arquivo clientes.csv com permissões abertas
touch "$CLIENTES_FILE"
chmod 664 "$CLIENTES_FILE"

# 2. Gerar clientes.csv (distinct cod_cliente dos dois arquivos)
echo "cod_cliente" > "$CLIENTES_FILE"
{ cut -d"|" -f2 "$ESTOQUE_FILE" | tail -n +2; cut -d"|" -f2 "$FATURAMENTO_FILE" | tail -n +2; } \
    | sort -u >> "$CLIENTES_FILE"

# 3. Criar o banco se não existir
sudo -u postgres createdb "$DB_NAME" || echo "Banco já existe"

# 4. Executar SQL - recriar tabelas
sudo -u postgres psql -d "$DB_NAME" <<'EOF'
DROP TABLE IF EXISTS faturamento CASCADE;
DROP TABLE IF EXISTS estoque CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;

-- Tabela clientes
CREATE TABLE clientes (
    cod_cliente INT PRIMARY KEY,
    nome VARCHAR(100)
);

-- Tabela estoque
CREATE TABLE estoque (
    data DATE NOT NULL,
    cod_cliente INT NOT NULL,
    es_centro VARCHAR(50),
    tipo_material VARCHAR(100),
    origem VARCHAR(50),
    cod_produto VARCHAR(50),
    lote VARCHAR(50),
    dias_em_estoque INT,
    produto VARCHAR(100),
    grupo_mercadoria VARCHAR(100),
    es_totalestoque NUMERIC,
    SKU VARCHAR(50),
    FOREIGN KEY (cod_cliente) REFERENCES clientes(cod_cliente)
);

-- Tabela faturamento
CREATE TABLE faturamento (
    data DATE NOT NULL,
    cod_cliente INT NOT NULL,
    lote VARCHAR(50),
    origem VARCHAR(50),
    zs_gr_mercad VARCHAR(100),
    produto VARCHAR(100),
    cod_produto VARCHAR(50),
    zs_centro VARCHAR(50),
    zs_cidade VARCHAR(100),
    zs_uf VARCHAR(10),
    zs_peso_liquido NUMERIC,
    giro_sku_cliente NUMERIC,
    SKU VARCHAR(50),
    FOREIGN KEY (cod_cliente) REFERENCES clientes(cod_cliente)
);
EOF

# 5. Carregar clientes, estoque e faturamento
sudo -u postgres psql -d "$DB_NAME" -c "\COPY clientes(cod_cliente) FROM '$CLIENTES_FILE' WITH (FORMAT csv, HEADER true, DELIMITER '|')"
sudo -u postgres psql -d "$DB_NAME" -c "\COPY estoque FROM '$ESTOQUE_FILE' WITH (FORMAT csv, HEADER true, DELIMITER '|')"
sudo -u postgres psql -d "$DB_NAME" -c "\COPY faturamento FROM '$FATURAMENTO_FILE' WITH (FORMAT csv, HEADER true, DELIMITER '|')"

# 6. Atualizar nomes sequenciais dos clientes
sudo -u postgres psql -d "$DB_NAME" -c "
WITH cte AS (
    SELECT cod_cliente, 'Cliente ' || ROW_NUMBER() OVER (ORDER BY cod_cliente) AS nome
    FROM clientes
)
UPDATE clientes c
SET nome = cte.nome
FROM cte
WHERE c.cod_cliente = cte.cod_cliente;
"

# 7. Gerar backup .dump no diretório de execução
sudo -u postgres pg_dump -Fc "$DB_NAME" > "$DUMP_FILE"

echo "Carga concluída com sucesso 🚀"
echo "Backup gerado em: $DUMP_FILE"
