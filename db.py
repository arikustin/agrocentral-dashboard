"""
db.py — Módulo de base de datos PostgreSQL para AGROCENTRAL Dashboard
Usado tanto por el script local (uploader) como por el dashboard en Railway.
"""
import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime

# DATABASE_URL viene de variable de entorno (Railway la setea automáticamente)
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    """Obtiene conexión a PostgreSQL."""
    url = DATABASE_URL
    # Railway a veces usa postgres:// en vez de postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, sslmode="require")


def init_db():
    """Crea las tablas si no existen."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id          TEXT PRIMARY KEY,
                    sku         TEXT,
                    title       TEXT,
                    data        JSONB,
                    updated_at  TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS sync_meta (
                    key         TEXT PRIMARY KEY,
                    value       TEXT,
                    updated_at  TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    item_id     TEXT PRIMARY KEY,
                    username    TEXT,
                    fecha       TEXT,
                    timestamp   TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_items_sku ON items(sku);
            """)
        conn.commit()
    print("  DB: tablas verificadas/creadas OK")


def upsert_items(items):
    """
    Inserta o actualiza una lista de items en la BD.
    Cada item es un dict con todos los campos del dashboard_cache.
    """
    if not items:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO items (id, sku, title, data)
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    sku        = EXCLUDED.sku,
                    title      = EXCLUDED.title,
                    data       = EXCLUDED.data,
                    updated_at = NOW()
                """,
                [(
                    it.get("id", ""),
                    it.get("sku", ""),
                    it.get("title", ""),
                    json.dumps(it, ensure_ascii=False),
                ) for it in items],
                template="(%s, %s, %s, %s::jsonb)"
            )
        conn.commit()


def get_all_items():
    """Devuelve todos los items de la BD como lista de dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT data FROM items ORDER BY updated_at DESC")
            rows = cur.fetchall()
    result = []
    for row in rows:
        d = row["data"]
        # JSONB ya viene deserializado por psycopg2
        if isinstance(d, str):
            d = json.loads(d)
        result.append(d)
    return result


def get_item(item_id):
    """Devuelve un item específico por ID."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT data FROM items WHERE id = %s", (item_id,))
            row = cur.fetchone()
    if not row:
        return None
    d = row["data"]
    if isinstance(d, str):
        d = json.loads(d)
    return d


def get_sync_meta():
    """Devuelve metadatos de la última sincronización."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT key, value FROM sync_meta")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_sync_meta(key, value):
    """Guarda un metadato de sincronización."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sync_meta (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = NOW()
            """, (key, str(value)))
        conn.commit()


def save_review(item_id, username):
    """Registra que un usuario revisó una publicación."""
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reviews (item_id, username, fecha, timestamp)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (item_id) DO UPDATE SET
                    username  = EXCLUDED.username,
                    fecha     = EXCLUDED.fecha,
                    timestamp = NOW()
            """, (item_id, username, fecha))
        conn.commit()
    return {"usuario": username, "fecha": fecha}


def get_all_reviews():
    """Devuelve todas las revisiones como dict {item_id: {usuario, fecha}}."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT item_id, username, fecha FROM reviews")
            rows = cur.fetchall()
    return {
        r["item_id"]: {"usuario": r["username"], "fecha": r["fecha"]}
        for r in rows
    }
