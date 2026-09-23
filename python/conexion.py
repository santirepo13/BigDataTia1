"""Conexión local, configurable sin guardar contraseñas en el repositorio."""
import os
import psycopg2

def conectar():
    return psycopg2.connect(host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'), dbname=os.getenv('PGDATABASE', 'bigdata'),
        user=os.getenv('PGUSER', 'postgres'), password=os.getenv('PGPASSWORD', 'postgres'),
        sslmode=os.getenv('PGSSLMODE', 'prefer'))
