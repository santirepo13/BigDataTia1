import psycopg2


def connect():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="bigdata",
        user="postgres",
        password="postgres"
    )
