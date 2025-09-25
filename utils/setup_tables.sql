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