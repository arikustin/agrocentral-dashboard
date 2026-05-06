"""
AGROCENTRAL DASHBOARD v4
Mejoras: links ML, quien está viendo, estado publicación, modal mejorado
"""
import os, json, re
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request, redirect, session
import psycopg2
import psycopg2.extras


def init_db():
    """Inicializa tablas necesarias — una sentencia por vez para mayor robustez."""
    stmts = [
        """CREATE TABLE IF NOT EXISTS ag_items (
            item_id TEXT PRIMARY KEY, sku TEXT, title TEXT, price NUMERIC,
            category_id TEXT, listing_type TEXT, status TEXT,
            pa TEXT, concentracion TEXT, nc TEXT, updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS ag_competidores (
            id SERIAL PRIMARY KEY, my_item_id TEXT, comp_item_id TEXT,
            comp_title TEXT, comp_price NUMERIC, comp_seller_id TEXT,
            comp_cat TEXT, match_type TEXT, claude_verif BOOLEAN DEFAULT FALSE,
            motor_razon TEXT, diff_pct NUMERIC, scraped_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS ag_price_history (
            id SERIAL PRIMARY KEY, item_id TEXT, price NUMERIC,
            min_comp NUMERIC, suggested NUMERIC, semaforo TEXT,
            n_comps INT DEFAULT 0, recorded_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS ag_runs (
            id SERIAL PRIMARY KEY, started_at TIMESTAMP DEFAULT NOW(),
            finished_at TIMESTAMP, items_total INT, items_con_comp INT,
            status TEXT, modo TEXT DEFAULT 'playwright'
        )""",
        "ALTER TABLE ag_competidores ADD COLUMN IF NOT EXISTS motor_razon TEXT",
        "ALTER TABLE ag_price_history ADD COLUMN IF NOT EXISTS n_comps INT DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS ag_presencia (
            usuario TEXT PRIMARY KEY,
            item_id TEXT,
            item_title TEXT,
            visto_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS ag_revisiones (
            id SERIAL PRIMARY KEY,
            item_id TEXT NOT NULL,
            usuario TEXT NOT NULL,
            revisado_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS idx_rev_item ON ag_revisiones(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_comp_item ON ag_competidores(my_item_id)",
        "CREATE INDEX IF NOT EXISTS idx_hist_item ON ag_price_history(item_id)",
    ]
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL",""))
        cur  = conn.cursor()
        for stmt in stmts:
            try:
                cur.execute(stmt)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"init_db stmt warning: {e}")
        conn.close()
    except Exception as e:
        print(f"init_db connection error: {e}")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "agro2026secret")
DATABASE_URL = os.environ.get("DATABASE_URL","")
USERS = {"ariel":"agrocentral2026","jere":"jere2026","ale":"ale2026"}

# Scheduler DESACTIVADO — scraping corre desde PC local con scraper.py

def _ensure_tables():
    """Crea tablas nuevas si no existen — llamado al arrancar."""
    nuevas = [
        """CREATE TABLE IF NOT EXISTS ag_presencia (
            usuario TEXT PRIMARY KEY, item_id TEXT,
            item_title TEXT, visto_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS ag_revisiones (
            id SERIAL PRIMARY KEY, item_id TEXT NOT NULL,
            usuario TEXT NOT NULL, revisado_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS idx_rev_item ON ag_revisiones(item_id)",
        """CREATE TABLE IF NOT EXISTS ag_claude_cache (
            cache_key TEXT PRIMARY KEY, decision BOOLEAN NOT NULL,
            razon TEXT, created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        for stmt in nuevas:
            try:
                cur.execute(stmt)
                conn.commit()
            except:
                conn.rollback()
        cur.close()
        conn.close()
    except:
        pass

_ensure_tables()

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def check_auth():
    return session.get("user") in USERS

# ── Auth ──────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("user","").lower()
        p = request.form.get("pass","")
        if USERS.get(u) == p:
            session["user"] = u
            return redirect("/")
        return render_template_string(LOGIN_HTML, error="Usuario o contraseña incorrectos")
    return render_template_string(LOGIN_HTML, error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ── API ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if not check_auth():
        return redirect("/login")
    return render_template_string(DASHBOARD_HTML, user=session.get("user",""))

@app.route("/api/summary")
def api_summary():
    if not check_auth(): return jsonify({}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT started_at, finished_at, items_total, items_con_comp, status
                    FROM ag_runs ORDER BY id DESC LIMIT 1
                """)
                run = dict(cur.fetchone() or {})
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE ph.semaforo='verde')    as verde,
                        COUNT(*) FILTER (WHERE ph.semaforo='amarillo') as amarillo,
                        COUNT(*) FILTER (WHERE ph.semaforo='rojo')     as rojo,
                        COUNT(*) FILTER (WHERE ph.semaforo='gris')     as gris,
                        COUNT(*) as total
                    FROM ag_items i
                    LEFT JOIN LATERAL (
                        SELECT semaforo FROM ag_price_history
                        WHERE item_id = i.item_id
                        ORDER BY recorded_at DESC LIMIT 1
                    ) ph ON true
                    WHERE i.status = 'active'
                """)
                sem = dict(cur.fetchone() or {})
        for k, v in run.items():
            if hasattr(v, 'isoformat'): run[k] = v.isoformat()
        return jsonify({"run": run, "semaforos": sem})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/items")
def api_items():
    if not check_auth(): return jsonify([]), 401
    filtro = request.args.get("filtro","todos")
    search = request.args.get("q","").lower()
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                v.item_id_principal  AS item_id,
                v.sku,
                v.title,
                v.precio_principal   AS price,
                v.pa,
                NULL                 AS concentracion,
                v.nc,
                'active'             AS status,
                v.semaforo,
                v.mejor_comp_precio  AS min_comp,
                v.suggested,
                v.recorded_at,
                v.total_comps        AS n_comps,
                v.n_publicaciones,
                v.precio_min_propio,
                v.precio_max_propio
            FROM v_items_por_sku v
            ORDER BY
                CASE v.semaforo
                    WHEN 'rojo' THEN 1 WHEN 'amarillo' THEN 2
                    WHEN 'verde' THEN 3 ELSE 4 END,
                (v.precio_principal - COALESCE(v.mejor_comp_precio,0)) DESC
        """)
        cols  = [d[0] for d in cur.description]
        rows  = [dict(zip(cols, r)) for r in cur.fetchall()]

        # Revisiones
        rev_map = {}
        try:
            cur.execute("""
                SELECT DISTINCT ON (item_id) item_id, usuario, revisado_at
                FROM ag_revisiones ORDER BY item_id, revisado_at DESC
            """)
            for r in cur.fetchall():
                rev_map[r[0]] = {'usuario': r[1], 'at': r[2]}
        except: pass

        # Presencia
        pres_map = {}
        try:
            cur.execute("""
                SELECT item_id, usuario FROM ag_presencia
                WHERE visto_at > NOW() - INTERVAL '5 minutes' AND item_id != ''
            """)
            for r in cur.fetchall():
                pres_map[r[0]] = r[1]
        except: pass

        cur.close(); conn.close()

        for r in rows:
            iid = r.get('item_id','')
            rev = rev_map.get(iid, {})
            r['last_revisor']  = rev.get('usuario')
            r['last_revision'] = rev.get('at').isoformat() if rev.get('at') else None
            r['viendo_ahora']  = pres_map.get(iid)
            for k, v in r.items():
                if hasattr(v, 'isoformat'): r[k] = v.isoformat()
                elif v is None: r[k] = None

        if filtro != "todos":
            rows = [r for r in rows if (r.get("semaforo") or "gris") == filtro]
        if search:
            rows = [r for r in rows if
                    search in (r.get("title","") or "").lower() or
                    search in (r.get("sku","") or "").lower() or
                    search in (r.get("pa","") or "").lower()]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/revisiones/<item_id>", methods=["POST"])
def api_revision_set(item_id):
    if not check_auth(): return jsonify({}), 401
    usuario = session.get("user","?")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO ag_revisiones (item_id, usuario, revisado_at)
            VALUES (%s, %s, NOW() AT TIME ZONE 'America/Argentina/Buenos_Aires')
        """, (item_id, usuario))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/presencia", methods=["POST"])
def api_presencia_set():
    if not check_auth(): return jsonify({}), 401
    data       = request.get_json() or {}
    item_id    = data.get("item_id","")
    item_title = data.get("item_title","")
    usuario    = session.get("user","?")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        if item_id:
            cur.execute("""
                INSERT INTO ag_presencia (usuario, item_id, item_title, visto_at)
                VALUES (%s,%s,%s,NOW())
                ON CONFLICT (usuario) DO UPDATE
                SET item_id=EXCLUDED.item_id, item_title=EXCLUDED.item_title, visto_at=NOW()
            """, (usuario, item_id, item_title))
        else:
            cur.execute("DELETE FROM ag_presencia WHERE usuario=%s", (usuario,))
        conn.commit(); cur.close(); conn.close()
    except: pass
    return jsonify({"ok": True})

@app.route("/api/item/<item_id>/competitors")
def api_competitors(item_id):
    if not check_auth(): return jsonify([]), 401
    try:
        conn2 = psycopg2.connect(DATABASE_URL)
        cur2  = conn2.cursor()
        # Filtrar propias publicaciones en SQL — triple seguridad
        MY_SELLER = '339586552'
        # Filtros anti-propio:
        #  1. seller_id distinto al mío (si la BD lo tiene registrado).
        #  2. comp_item_id NO está en ag_items (catálogo propio).
        #  3. NO hay otro item propio con el MISMO SKU y mismo título normalizado
        #     (captura publicaciones duplicadas del mismo SKU que escaparon el
        #     scraping inicial por tener MLA distinto, seller_id vacío, etc.).
        #  4. NO hay otro item propio con el MISMO precio EXACTO y mismo SKU
        #     (backup: muchas publicaciones duplicadas comparten precio exacto).
        cur2.execute("""
            SELECT c.comp_item_id, c.comp_title, c.comp_price,
                   c.match_type, c.claude_verif, c.diff_pct, c.scraped_at,
                   c.comp_seller_id, c.comp_cat, c.motor_razon,
                   i.title as mi_titulo, i.price as mi_price, i.sku as mi_sku
            FROM ag_competidores c
            JOIN ag_items i ON i.item_id = c.my_item_id
            WHERE c.my_item_id = %s
              AND (c.comp_seller_id IS NULL OR c.comp_seller_id != %s)
              AND c.comp_item_id NOT IN (SELECT item_id FROM ag_items)
              AND NOT EXISTS (
                  SELECT 1 FROM ag_items i2
                  WHERE i2.sku = i.sku
                    AND i2.item_id != i.item_id
                    AND (
                        LOWER(TRIM(i2.title)) = LOWER(TRIM(c.comp_title))
                        OR ROUND(i2.price::numeric, 0) = ROUND(c.comp_price::numeric, 0)
                    )
              )
            ORDER BY c.comp_price ASC
        """, (item_id, MY_SELLER))
        cols = [d[0] for d in cur2.description]
        raw  = cur2.fetchall()
        conn2.close()
        rows = []
        for row in raw:
            r = dict(zip(cols, row))
            for k, v in r.items():
                if hasattr(v, 'isoformat'): r[k] = v.isoformat()
                elif k in ('comp_price','diff_pct') and v is not None:
                    try: r[k] = float(v)
                    except: r[k] = None
            # Construir link ML — prioridad: href original > item_id
            comp_href_orig = r.get("comp_cat","")  # comp_cat guarda el href original
            cid = r.get("comp_item_id","") or ""
            if comp_href_orig and comp_href_orig.startswith("http"):
                # Usar el href original capturado por Playwright
                r["comp_url"] = comp_href_orig
            elif cid and "MLA" in cid:
                # Construir desde item_id: MLA1234567 o MLA-1234567 → MLA-1234567
                clean = re.sub(r"[^0-9]", "", cid)  # solo dígitos
                r["comp_url"] = f"https://articulo.mercadolibre.com.ar/MLA-{clean}-_"
            else:
                r["comp_url"] = ""
            # ── Filtrar presentaciones incompatibles ─────────────
            mi_titulo = r.pop("mi_titulo","") or ""
            mi_price  = r.pop("mi_price", None)
            r.pop("mi_sku", None)  # limpiar columna agregada para el filtro
            comp_titulo = r.get("comp_title","") or ""

            # Extraer volúmenes en ml equivalentes
            def get_vol(t):
                import re as _re
                t = t.lower()
                # No convertir gramos de WG/WP (sólidos formulados)
                es_wg = any(f in t for f in [' wg',' wp',' wdg','-wg','-wp'])
                for pat, mult, skip_wg in [
                    (r"(\d+[\.,]?\d*)\s*(?:litros?|lts?|lt)\b", 1000, False),
                    (r"(\d+[\.,]?\d*)\s*(?:kilos?|kgs?|kg)\b",  1000, False),
                    (r"(\d+[\.,]?\d*)\s*(?:cm3|ml|cc)\b",          1, False),
                    (r"(?<!\d)(\d+[\.,]?\d*)\s*c(?=\s|$)",         1, False),
                    (r"(\d+[\.,]?\d*)\s*(?:grs?|gramos?)\b",        1, True),
                    (r"(?<!\d)(\d+[\.,]?\d*)\s*g(?!\w)",           1, True),
                    (r"(?<!\d)(\d+[\.,]?\d*)\s*l(?!\w)",        1000, False),
                ]:
                    if skip_wg and es_wg:
                        continue
                    m = _re.search(pat, t)
                    if m:
                        try:
                            v = float(m.group(1).replace(",","."))
                            if v > 0: return v * mult
                        except: pass
                return None

            v_mi   = get_vol(mi_titulo)
            v_comp = get_vol(comp_titulo)
            if v_mi and v_comp and v_mi > 0 and v_comp > 0:
                ratio = max(v_mi, v_comp) / min(v_mi, v_comp)
                # Umbral: líquidos pequeños (<= 2L) → 3.5x; profesionales → 10x
                max_vol = max(v_mi, v_comp)
                umbral = 3.5 if max_vol <= 2000 else 10
                if ratio > umbral:
                    continue  # presentaciones incompatibles → no mostrar

            rows.append(r)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e), "item_id": item_id}), 500

@app.route("/api/debug/tables")
def api_debug_tables():
    """Verifica estado de tablas y las crea si faltan."""
    if not check_auth(): return jsonify({}), 401
    resultado = {}
    tablas = ["ag_items","ag_competidores","ag_price_history","ag_runs",
              "ag_presencia","ag_revisiones","ag_claude_cache"]
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        for tabla in tablas:
            cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)", (tabla,))
            existe = cur.fetchone()[0]
            if existe:
                cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                n = cur.fetchone()[0]
                resultado[tabla] = f"OK ({n} filas)"
            else:
                resultado[tabla] = "NO EXISTE"
        
        # Crear tablas faltantes
        if resultado.get("ag_revisiones") == "NO EXISTE":
            cur.execute("""CREATE TABLE ag_revisiones (
                id SERIAL PRIMARY KEY, item_id TEXT NOT NULL,
                usuario TEXT NOT NULL, revisado_at TIMESTAMPTZ DEFAULT NOW()
            )""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rev_item2 ON ag_revisiones(item_id)")
            conn.commit()
            resultado["ag_revisiones"] = "CREADA AHORA"
        
        if resultado.get("ag_presencia") == "NO EXISTE":
            cur.execute("""CREATE TABLE ag_presencia (
                usuario TEXT PRIMARY KEY, item_id TEXT,
                item_title TEXT, visto_at TIMESTAMP DEFAULT NOW()
            )""")
            conn.commit()
            resultado["ag_presencia"] = "CREADA AHORA"

        cur.close()
        conn.close()
    except Exception as e:
        resultado["error"] = str(e)
    return jsonify(resultado)


@app.route("/api/last-run")
def api_last_run():
    if not check_auth(): return jsonify({}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, started_at, finished_at, items_total,
                           items_con_comp, status
                    FROM ag_runs ORDER BY id DESC LIMIT 1
                """)
                row = cur.fetchone()
                if not row: return jsonify({})
                r = dict(row)
                for k, v in r.items():
                    if hasattr(v, 'isoformat'): r[k] = v.isoformat()
                return jsonify(r)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Presencia: quién está mirando qué ────────────────────────────────────────
@app.route("/api/presencia")
def api_presencia_get():
    if not check_auth(): return jsonify([]), 401
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            SELECT usuario, item_id, item_title, visto_at
            FROM ag_presencia
            WHERE visto_at > NOW() - INTERVAL '5 minutes'
            ORDER BY visto_at DESC
        """)
        rows = []
        for row in cur.fetchall():
            rows.append({
                "usuario":    row[0],
                "item_id":    row[1],
                "item_title": row[2],
                "visto_at":   row[3].isoformat() if row[3] else None,
            })
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify([])

# ── Revisiones: marcar como revisado ─────────────────────────────────────────
@app.route("/api/revisiones/<item_id>")
def api_revision_get(item_id):
    if not check_auth(): return jsonify([]), 401
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            SELECT usuario, revisado_at
            FROM ag_revisiones
            WHERE item_id = %s
            ORDER BY revisado_at DESC
            LIMIT 10
        """, (item_id,))
        rows = []
        for r in cur.fetchall():
            dt = r[1]
            rows.append({
                "usuario":     r[0],
                "revisado_at": dt.isoformat() if dt else None
            })
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify([])

# ── Agrupación por SKU ────────────────────────────────────────────────────────
@app.route("/api/items/all")
def api_items_all():
    """Todos los items individuales con su último semáforo (para vista SKU)."""
    if not check_auth(): return jsonify([]), 401
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            SELECT i.item_id, i.sku, i.title, i.price, i.pa, i.nc,
                   ph.semaforo, ph.min_comp, ph.suggested, ph.n_comps
            FROM ag_items i
            LEFT JOIN LATERAL (
                SELECT semaforo, min_comp, suggested, n_comps
                FROM ag_price_history WHERE item_id = i.item_id
                ORDER BY recorded_at DESC LIMIT 1
            ) ph ON true
            WHERE i.status = 'active'
              AND i.listing_type = 'gold_special'  -- solo Clásicas, excluir gold_pro (Premium)
            ORDER BY i.price DESC
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close(); conn.close()
        for r in rows:
            for k, v in r.items():
                if v is None: r[k] = None
                elif hasattr(v, 'isoformat'): r[k] = v.isoformat()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/items/sku")
def api_items_sku():
    """Items agrupados por NC para vista SKU."""
    if not check_auth(): return jsonify([]), 401
    try:
        conn = psycopg2.connect(DATABASE_URL)  # cursor estándar, NO RealDictCursor
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                COALESCE(NULLIF(i.sku,''), i.item_id) as grupo,
                MIN(i.title) as titulo_base,
                i.pa,
                COUNT(DISTINCT i.item_id) as n_items,
                MIN(i.price) as precio_min,
                MAX(i.price) as precio_max,
                ROUND(AVG(CASE WHEN ph.semaforo='rojo' THEN 1
                               WHEN ph.semaforo='amarillo' THEN 0
                               ELSE -1 END)::numeric,2) as avg_alerta,
                SUM(CASE WHEN ph.semaforo='rojo'     THEN 1 ELSE 0 END) as n_rojo,
                SUM(CASE WHEN ph.semaforo='amarillo' THEN 1 ELSE 0 END) as n_amarillo,
                SUM(CASE WHEN ph.semaforo='verde'    THEN 1 ELSE 0 END) as n_verde,
                STRING_AGG(i.item_id, ',' ORDER BY i.price ASC) as item_ids,
                STRING_AGG(i.title,   ' | ' ORDER BY i.price ASC) as titulos
            FROM ag_items i
            LEFT JOIN LATERAL (
                SELECT semaforo, min_comp FROM ag_price_history
                WHERE item_id = i.item_id
                ORDER BY recorded_at DESC LIMIT 1
            ) ph ON true
            WHERE i.status = 'active'
              AND i.listing_type = 'gold_special'  -- solo Clásicas, excluir gold_pro (Premium)
            GROUP BY grupo, i.pa
            ORDER BY n_rojo DESC, avg_alerta DESC NULLS LAST
        """)
        cols = [d[0] for d in cur.description]
        rows = []
        for row in cur.fetchall():
            r = {}
            for i, col in enumerate(cols):
                v = row[i]
                if hasattr(v, 'isoformat'): r[col] = v.isoformat()
                elif v is None: r[col] = None
                else: r[col] = v
            rows.append(r)
        cur.close()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── HTML ──────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AGROCENTRAL — Acceso</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
  .card{background:#fff;border-radius:12px;padding:40px;width:360px;box-shadow:0 4px 20px rgba(0,0,0,.12)}
  .logo{color:#1a5c30;font-size:1.6rem;font-weight:800;text-align:center;margin-bottom:8px}
  .sub{color:#888;text-align:center;font-size:.85rem;margin-bottom:28px}
  label{display:block;font-size:.82rem;color:#555;margin-bottom:4px;font-weight:600}
  input{width:100%;padding:10px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:.95rem;margin-bottom:16px}
  input:focus{outline:none;border-color:#1a5c30}
  button{width:100%;padding:12px;background:#1a5c30;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:700;cursor:pointer}
  .err{background:#ffeaea;color:#c62828;padding:10px 14px;border-radius:8px;font-size:.85rem;margin-bottom:16px}
</style></head><body>
<div class="card">
  <div class="logo">🌿 AGROCENTRAL</div>
  <div class="sub">Dashboard de Competencia · MercadoLibre</div>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="POST">
    <label>Usuario</label><input name="user" type="text" required>
    <label>Contraseña</label><input name="pass" type="password" required>
    <button type="submit">Ingresar</button>
  </form>
</div></body></html>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AGROCENTRAL — Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#f5f7f5;color:#222;font-size:14px}
.header{background:#1a5c30;color:#fff;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.header-left{flex:1;min-width:0}
.header-title{font-size:1.1rem;font-weight:800}
.header-sub{font-size:.75rem;opacity:.75;margin-top:2px}
.header-right{display:flex;align-items:center;gap:12px;flex-shrink:0}
.header-user{font-size:.78rem;color:rgba(255,255,255,.85)}
.pres-bar{font-size:.72rem;color:rgba(255,255,255,.8);margin-top:3px;min-height:16px}
.pres-chip{display:inline-block;background:rgba(255,255,255,.18);border-radius:10px;padding:1px 7px;margin:0 2px;font-weight:600}
.btn-salir{color:rgba(255,255,255,.7);font-size:.78rem;text-decoration:none}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:16px 20px 8px}
.stat-card{background:#fff;border-radius:10px;padding:14px 18px;box-shadow:0 2px 6px rgba(0,0,0,.06);cursor:pointer;transition:box-shadow .15s}
.stat-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.12)}
.stat-n{font-size:1.8rem;font-weight:800}
.stat-lb{font-size:.75rem;color:#888;margin-top:2px}
.verde{color:#2e7d32}.amarillo{color:#f57f17}.rojo{color:#c62828}.gris{color:#888}
.toolbar{padding:8px 20px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.toolbar input{flex:1;min-width:180px;padding:8px 12px;border:1.5px solid #ddd;border-radius:8px;font-size:.88rem}
.toolbar input:focus{outline:none;border-color:#1a5c30}
.flt-btn{padding:7px 14px;border:1.5px solid #ddd;background:#fff;border-radius:8px;cursor:pointer;font-size:.82rem;font-weight:600}
.flt-btn.active{background:#1a5c30;color:#fff;border-color:#1a5c30}
.view-toggle{display:flex;gap:3px;padding:3px;background:#e8f5e9;border-radius:8px}
.view-btn{padding:5px 11px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600;background:transparent;color:#666}
.view-btn.active{background:#1a5c30;color:#fff}
/* Tabla */
.table-wrap{padding:0 20px 30px;overflow-x:auto}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,.06)}
th{background:#f8faf8;padding:10px 12px;text-align:left;font-size:.74rem;color:#666;font-weight:700;border-bottom:1.5px solid #eee;white-space:nowrap}
td{padding:8px 12px;font-size:.81rem;border-bottom:1px solid #f0f0f0;vertical-align:middle}
tr:hover td{background:#f9fbf9}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.72rem;font-weight:700}
.badge-verde{background:#e8f5e9;color:#2e7d32}.badge-amarillo{background:#fff9c4;color:#f57f17}
.badge-rojo{background:#ffebee;color:#c62828}.badge-gris{background:#f5f5f5;color:#888}
.btn-det{padding:4px 10px;background:#1a5c30;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.74rem;font-weight:600}
.btn-det:hover{background:#145226}
.link-ml{color:#1a5c30;text-decoration:none;font-size:.74rem;font-weight:600}
.link-ml:hover{text-decoration:underline}
.n-comps{display:inline-block;background:#e8f5e9;color:#1a5c30;border-radius:12px;padding:1px 7px;font-size:.72rem;font-weight:700}
.n-comps-0{background:#f5f5f5;color:#aaa}
.diff-pos{color:#c62828;font-weight:700}.diff-neg{color:#2e7d32;font-weight:700}
/* Info inline en tabla */
.td-rev{font-size:.70rem;color:#888;white-space:nowrap}
.td-rev-ok{color:#2e7d32;font-weight:600}
.td-viendo{font-size:.70rem;color:#1565c0;font-weight:600;white-space:nowrap}
/* Vista SKU */
#sku-view{padding:0 20px 30px;display:none}
.sku-grupo{background:#fff;border-radius:10px;margin-bottom:6px;box-shadow:0 2px 5px rgba(0,0,0,.05);overflow:hidden}
.sku-hdr{display:flex;align-items:center;gap:12px;padding:10px 14px;cursor:pointer;user-select:none}
.sku-hdr:hover{background:#f9fbf9}
.sku-name{font-weight:700;font-size:.88rem;flex:1}
.sku-pa{font-size:.72rem;color:#888}
.sku-pills{display:flex;gap:4px}
.sku-pill{padding:1px 7px;border-radius:10px;font-size:.70rem;font-weight:700}
.sku-items{display:none;border-top:1px solid #f0f0f0}
.sku-items.open{display:block}
.sku-row{display:flex;align-items:center;gap:8px;padding:7px 14px;border-bottom:1px solid #f8f8f8;font-size:.80rem}
.sku-row:last-child{border-bottom:none}
/* Modal */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:#fff;border-radius:14px;width:94%;max-width:860px;max-height:88vh;overflow-y:auto;padding:24px}
.modal-hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
.modal-title{font-size:1rem;font-weight:700;max-width:85%;line-height:1.3}
.modal-close{background:none;border:none;font-size:1.4rem;cursor:pointer;color:#888}
.modal-links{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.modal-link-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:8px;font-size:.80rem;font-weight:700;text-decoration:none;border:1.5px solid}
.ml-btn{background:#fff9e6;color:#b07800;border-color:#f5c518}
.modal-info{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:18px}
.info-box{background:#f8faf8;border-radius:8px;padding:10px 14px}
.info-lb{font-size:.70rem;color:#888;margin-bottom:2px;text-transform:uppercase;letter-spacing:.3px}
.info-val{font-size:.92rem;font-weight:700}
.info-val.rojo{color:#c62828}.info-val.verde{color:#2e7d32}
.comp-table{width:100%;border-collapse:collapse;font-size:.80rem}
.comp-table th{background:#f0f4f0;padding:7px 9px;text-align:left;font-size:.72rem;color:#555;font-weight:700;border-bottom:1.5px solid #e0e8e0}
.comp-table td{padding:8px 9px;border-bottom:1px solid #f0f0f0;vertical-align:middle}
.comp-table tr:hover td{background:#f9fbf9}
.match-dir{color:#1a5c30;font-weight:700}.match-eq{color:#1565c0}
.loading{text-align:center;padding:24px;color:#888}
/* Revisiones en modal */
.rev-section{margin-top:16px;border-top:1.5px solid #eee;padding-top:12px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.rev-titulo{font-size:.83rem;font-weight:700;color:#444;margin-bottom:6px}
.rev-list{font-size:.76rem;color:#888}
.rev-row{display:flex;gap:8px;padding:2px 0}
.rev-user{font-weight:700;color:#1a5c30}
.btn-revisar{padding:6px 14px;background:#1a5c30;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;white-space:nowrap;flex-shrink:0}
.btn-revisar:hover{background:#145226}
.btn-revisar:disabled{opacity:.6;cursor:default}
</style></head><body>

<div class="header">
  <div class="header-left">
    <div class="header-title">🌿 AGROCENTRAL — Dashboard de Competencia</div>
    <div class="header-sub">MercadoLibre Argentina · <span id="last-run-info">Cargando...</span></div>
    <div class="pres-bar" id="pres-bar"></div>
  </div>
  <div class="header-right">
    <div class="header-user">👤 {{ user }}</div>
    <a href="/logout" class="btn-salir">Salir</a>
  </div>
</div>

<div class="stats">
  <div class="stat-card" onclick="setFiltro('todos',null)">
    <div class="stat-n gris" id="s-total">—</div><div class="stat-lb">Total publicaciones</div>
  </div>
  <div class="stat-card" onclick="setFiltro('rojo',null)">
    <div class="stat-n rojo" id="s-rojo">—</div><div class="stat-lb">🔴 Precio alto vs competencia</div>
  </div>
  <div class="stat-card" onclick="setFiltro('amarillo',null)">
    <div class="stat-n amarillo" id="s-amarillo">—</div><div class="stat-lb">🟡 Precio similar</div>
  </div>
  <div class="stat-card" onclick="setFiltro('verde',null)">
    <div class="stat-n verde" id="s-verde">—</div><div class="stat-lb">🟢 Precio competitivo</div>
  </div>
</div>

<div class="toolbar">
  <input type="text" id="search" placeholder="🔍 Buscar por título, SKU, principio activo..." oninput="filtrar()">
  <button class="flt-btn active" id="btn-todos" onclick="setFiltro('todos',this)">Todos</button>
  <button class="flt-btn" onclick="setFiltro('rojo',this)">🔴 Rojos</button>
  <button class="flt-btn" onclick="setFiltro('amarillo',this)">🟡 Similares</button>
  <button class="flt-btn" onclick="setFiltro('verde',this)">🟢 Verdes</button>
  <button class="flt-btn" onclick="setFiltro('gris',this)">⚪ Sin datos</button>
  <div class="view-toggle">
    <button class="view-btn active" id="vbtn-item" onclick="setVista('item',this)">📋 Items</button>
    <button class="view-btn" id="vbtn-sku" onclick="setVista('sku',this)">📦 SKU</button>
  </div>
</div>

<div class="table-wrap" id="table-wrap" style="display:block">
  <table>
    <thead><tr>
      <th>Estado</th><th>SKU</th><th>Producto</th><th>PA</th>
      <th style="text-align:right">Mi precio</th>
      <th style="text-align:right">Mín. comp.</th>
      <th style="text-align:right">Diferencia</th>
      <th style="text-align:right">Sugerido</th>
      <th style="text-align:center">Comps</th>
      <th>Revisado</th>
      <th>Viendo</th>
      <th>Acciones</th>
    </tr></thead>
    <tbody id="tbody"><tr><td colspan="12" class="loading">Cargando...</td></tr></tbody>
  </table>
</div>

<div id="sku-view" style="display:none">
  <div id="sku-body"><div class="loading">Cargando...</div></div>
</div>

<!-- Modal -->
<div class="modal-bg" id="modal-bg" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-hdr">
      <div>
        <div class="modal-title" id="modal-title">—</div>
        <div style="font-size:.72rem;color:#888;margin-top:3px" id="modal-sub">—</div>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-links" id="modal-links"></div>
    <div class="modal-info" id="modal-info"></div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <h3 style="font-size:.92rem;color:#333">Competidores encontrados</h3>
      <span id="modal-n-comps" style="font-size:.78rem;color:#888"></span>
    </div>
    <div id="modal-comps"><div class="loading">Cargando...</div></div>
    <div class="rev-section">
      <div style="flex:1">
        <div class="rev-titulo">✅ Revisiones</div>
        <div class="rev-list" id="rev-list"><span style="color:#aaa">Aún no revisado</span></div>
      </div>
      <button class="btn-revisar" id="btn-marcar" onclick="marcarRevisado()">Marcar como revisado</button>
    </div>
  </div>
</div>

<script>
const USER = "{{ user }}";
let allItems = [];
let filtroActivo = 'todos';
let vistaActiva  = 'item';
let modalItemId  = null;

const fpp = v => v != null ? '$'+Number(v).toLocaleString('es-AR',{minimumFractionDigits:0,maximumFractionDigits:0}) : '—';

function semBadge(s) {
  const lb = {verde:'🟢 Competitivo',amarillo:'🟡 Similar',rojo:'🔴 Caro',gris:'⚪ Sin datos'};
  return `<span class="badge badge-${s||'gris'}">${lb[s]||'⚪ Sin datos'}</span>`;
}
function semIcono(s) {
  return {verde:'🟢',amarillo:'🟡',rojo:'🔴',gris:'⚪'}[s]||'⚪';
}
function mlUrl(id) {
  if (!id) return '#';
  return 'https://articulo.mercadolibre.com.ar/MLA-'+id.replace(/[^0-9]/g,'')+'-_';
}
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('es-AR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:'America/Argentina/Buenos_Aires'});
}

// ── Tabla de items ───────────────────────────────────────────────────
function renderTable(items) {
  const tb = document.getElementById('tbody');
  if (!items.length) { tb.innerHTML = '<tr><td colspan="12" class="loading">Sin resultados</td></tr>'; return; }
  tb.innerHTML = items.map(it => {
    const sem  = it.semaforo || 'gris';
    const diff = it.min_comp && it.price ? ((it.price - it.min_comp)/it.min_comp*100) : null;
    const diffStr = diff != null ? `<span class="${diff>5?'diff-pos':'diff-neg'}">${diff>0?'+':''}${diff.toFixed(1)}%</span>` : '—';
    const nc = it.n_comps || 0;
    const ncBadge = nc > 0 ? `<span class="n-comps">${nc}</span>` : `<span class="n-comps n-comps-0">0</span>`;

    // Columna "Revisado"
    let revTd = '<span style="color:#ccc;font-size:.70rem">—</span>';
    if (it.last_revisor) {
      revTd = `<span class="td-rev"><span class="td-rev-ok">${it.last_revisor}</span><br>${fmtDate(it.last_revision)}</span>`;
    }

    // Columna "Viendo"
    let viendoTd = '';
    if (it.viendo_ahora && it.viendo_ahora !== USER) {
      viendoTd = `<span class="td-viendo">👁 ${it.viendo_ahora}</span>`;
    }

    return `<tr>
      <td>${semBadge(sem)}</td>
      <td style="font-family:monospace;font-size:.75rem;color:#555">${it.sku||'—'}</td>
      <td style="max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${it.title}">${it.title}</td>
      <td style="font-size:.75rem;color:#666;max-width:110px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${it.pa||'—'}</td>
      <td style="text-align:right;font-weight:700">${fpp(it.price)}</td>
      <td style="text-align:right;color:${sem==='rojo'?'#c62828':'#333'}">${fpp(it.min_comp)}</td>
      <td style="text-align:right">${diffStr}</td>
      <td style="text-align:right;color:#1a5c30;font-weight:700">${fpp(it.suggested)}</td>
      <td style="text-align:center">${ncBadge}</td>
      <td>${revTd}</td>
      <td>${viendoTd}</td>
      <td style="white-space:nowrap;display:flex;gap:6px;align-items:center">
        <button class="btn-det" onclick="openModal('${it.item_id}')">Ver</button>
        <a href="${mlUrl(it.item_id)}" target="_blank" class="link-ml">↗ ML</a>
      </td>
    </tr>`;
  }).join('');
}

// ── Vista SKU ────────────────────────────────────────────────────────
function setVista(v, btn) {
  vistaActiva = v;
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.getElementById('table-wrap').style.display = v==='item' ? 'block' : 'none';
  document.getElementById('sku-view').style.display   = v==='sku'  ? 'block' : 'none';
  if (v==='sku') loadSKU();
}

async function loadSKU() {
  const d = await fetch('/api/items/sku').then(r=>r.json()).catch(()=>[]);
  const body = document.getElementById('sku-body');
  if (!d || d.error || !d.length) {
    body.innerHTML = '<p style="color:#888;padding:20px">Sin datos de SKU</p>';
    return;
  }
  // Traer todos los items individuales para lookup (no la vista agrupada)
  const allIndiv = await fetch('/api/items/all').then(r=>r.json()).catch(()=>[]);
  const itemMap = {};
  (Array.isArray(allIndiv) ? allIndiv : allItems).forEach(x => { itemMap[x.item_id] = x; });

  body.innerHTML = d.map((g,gi) => {
    const rojo = parseInt(g.n_rojo)||0, amar = parseInt(g.n_amarillo)||0, verde = parseInt(g.n_verde)||0;
    const total = parseInt(g.n_items)||1;
    const pills = [
      rojo  > 0 ? `<span class="sku-pill" style="background:#ffebee;color:#c62828">🔴 ${rojo}</span>` : '',
      amar  > 0 ? `<span class="sku-pill" style="background:#fff9c4;color:#f57f17">🟡 ${amar}</span>` : '',
      verde > 0 ? `<span class="sku-pill" style="background:#e8f5e9;color:#2e7d32">🟢 ${verde}</span>` : '',
    ].filter(Boolean).join('');
    const ids  = (g.item_ids||'').split(',').filter(Boolean);
    const tits = (g.titulos||'').split(' | ');
    const grupo = g.grupo || '—';
    const titulo_base = g.titulo_base || grupo;
    const pa    = g.pa    || '';

    // Semáforo dominante del grupo
    const semDom = rojo > 0 ? 'rojo' : amar > 0 ? 'amarillo' : verde > 0 ? 'verde' : 'gris';

    const itemRows = ids.map((id,i) => {
      const item = itemMap[id];
      const s    = item ? (item.semaforo||'gris') : semDom;
      const precio = item ? item.price : null;
      const minComp = item ? item.min_comp : null;
      const d2 = precio && minComp ? ((precio-minComp)/minComp*100).toFixed(1) : null;
      return `<div class="sku-row">
        <span style="width:22px">${semIcono(s)}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tits[i]||id}">${tits[i]||id}</span>
        <span style="width:85px;text-align:right;font-weight:700">${precio ? fpp(precio) : '—'}</span>
        <span style="width:65px;text-align:right;color:${d2&&parseFloat(d2)>5?'#c62828':'#2e7d32'}">${d2 != null ? (parseFloat(d2)>0?'+':'')+d2+'%' : '—'}</span>
        <span style="width:100px;text-align:right">
          <button class="btn-det" onclick="openModal('${id}')" style="font-size:.70rem;padding:3px 7px">Ver</button>
          <a href="${mlUrl(id)}" target="_blank" class="link-ml" style="margin-left:4px">↗</a>
        </span>
      </div>`;
    }).join('');

    return `<div class="sku-grupo">
      <div class="sku-hdr" onclick="document.getElementById('sku-items-${gi}').classList.toggle('open')">
        <div style="flex:1;min-width:0">
          <div class="sku-name">${semIcono(semDom)} ${titulo_base}</div>
          <div style="font-size:.70rem;color:#888;font-family:monospace">${grupo}</div>
          <div class="sku-pa">${pa} · ${total} presentación${total>1?'es':''}</div>
        </div>
        <div class="sku-pills">${pills}</div>
        <span style="color:#aaa;font-size:.80rem;margin-left:8px">▾</span>
      </div>
      <div class="sku-items" id="sku-items-${gi}">${itemRows}</div>
    </div>`;
  }).join('');
}

// ── Carga y filtrado ──────────────────────────────────────────────────
async function loadItems() {
  const q   = document.getElementById('search').value;
  const url = `/api/items?filtro=${filtroActivo}&q=${encodeURIComponent(q)}`;
  const items = await fetch(url).then(r=>r.json()).catch(()=>[]);
  allItems = Array.isArray(items) ? items : [];
  renderTable(allItems);
}

async function loadSummary() {
  const d = await fetch('/api/summary').then(r=>r.json()).catch(()=>({}));
  const s = d.semaforos || {};
  const r = d.run       || {};
  document.getElementById('s-total').textContent    = s.total    || '—';
  document.getElementById('s-rojo').textContent     = s.rojo     || '0';
  document.getElementById('s-amarillo').textContent = s.amarillo || '0';
  document.getElementById('s-verde').textContent    = s.verde    || '0';
  if (r.finished_at) {
    const dt = new Date(r.finished_at);
    document.getElementById('last-run-info').textContent = 'Último análisis: ' +
      dt.toLocaleString('es-AR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  }
}

function setFiltro(f, btn) {
  filtroActivo = f;
  document.querySelectorAll('.flt-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  else document.getElementById('btn-todos').classList.add('active');
  loadItems();
}
function filtrar() { loadItems(); }

// ── Presencia ─────────────────────────────────────────────────────────
async function reportarPresencia(itemId, itemTitle) {
  await fetch('/api/presencia',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({item_id: itemId||'', item_title: itemTitle||''})
  }).catch(()=>{});
}

async function actualizarPresencia() {
  const data = await fetch('/api/presencia').then(r=>r.json()).catch(()=>[]);
  const bar  = document.getElementById('pres-bar');
  const activos = (data||[]).filter(d => d.item_id && d.item_id !== '');
  if (!activos.length) { bar.innerHTML = ''; return; }
  bar.innerHTML = '👀 ' + activos.map(d =>
    `<span class="pres-chip">${d.usuario} → ${(d.item_title||d.item_id).slice(0,30)}…</span>`
  ).join('');
  // Actualizar columna "viendo" en tabla sin recargar todo
  document.querySelectorAll('[data-item-viendo]').forEach(el => {
    const id = el.dataset.itemViendo;
    const quien = activos.find(a => a.item_id === id);
    el.textContent = quien && quien.usuario !== USER ? '👁 '+quien.usuario : '';
  });
}

// ── Modal ─────────────────────────────────────────────────────────────
async function openModal(itemId) {
  // Buscar en allItems primero, si no buscar en allIndivMap (vista SKU)
  let item = allItems.find(i => i.item_id === itemId);
  if (!item) {
    // Intentar traer el item directamente de la API de todos los items
    const allIndiv = await fetch('/api/items/all').then(r=>r.json()).catch(()=>[]);
    item = allIndiv.find(i => i.item_id === itemId);
  }
  if (!item) {
    // Crear item mínimo para abrir el modal igual
    item = { item_id: itemId, title: itemId, sku: '—', pa: '—', nc: '—',
             price: null, min_comp: null, suggested: null, status: 'active', recorded_at: null };
  }
  modalItemId = itemId;
  reportarPresencia(itemId, item.title);

  document.getElementById('modal-title').textContent = item.title;
  document.getElementById('modal-sub').textContent =
    `SKU: ${item.sku||'—'} · PA: ${item.pa||'—'}${item.concentracion?' '+item.concentracion+'%':''} ${item.nc?'· NC: '+item.nc:''}`;
  document.getElementById('modal-links').innerHTML =
    `<a class="modal-link-btn ml-btn" href="${mlUrl(item.item_id)}" target="_blank">🛒 Ver mi publicación en ML</a>`;

  const diff = item.min_comp && item.price ? ((item.price - item.min_comp)/item.min_comp*100).toFixed(1) : null;
  const diffColor = diff == null ? '' : parseFloat(diff) > 5 ? 'rojo' : 'verde';
  document.getElementById('modal-info').innerHTML = `
    <div class="info-box"><div class="info-lb">Mi precio actual</div><div class="info-val">${fpp(item.price)}</div></div>
    <div class="info-box"><div class="info-lb">Mínimo competidor</div><div class="info-val ${diffColor}">${fpp(item.min_comp)}</div></div>
    <div class="info-box"><div class="info-lb">Precio sugerido (+3%)</div><div class="info-val verde">${fpp(item.suggested)}</div></div>
    <div class="info-box"><div class="info-lb">Diferencia vs competencia</div><div class="info-val ${diffColor}">${diff != null ? (parseFloat(diff)>0?'+':'')+diff+'%' : '—'}</div></div>
    <div class="info-box"><div class="info-lb">Estado</div><div class="info-val">${item.status==='active'?'✅ Activa':item.status||'—'}</div></div>
    <div class="info-box"><div class="info-lb">Último análisis</div><div class="info-val" style="font-size:.78rem">${fmtDate(item.recorded_at)}</div></div>`;

  document.getElementById('modal-comps').innerHTML = '<div class="loading">Cargando...</div>';
  document.getElementById('rev-list').innerHTML = '<span style="color:#aaa">Cargando...</span>';
  document.getElementById('modal-bg').classList.add('open');

  const [compResp] = await Promise.all([
    fetch(`/api/item/${itemId}/competitors`),
    cargarRevisiones(itemId)
  ]);
  const comps = await compResp.json().catch(()=>[]);
  document.getElementById('modal-n-comps').textContent = `${(comps||[]).length} competidores`;

  if (!comps || !comps.length) {
    document.getElementById('modal-comps').innerHTML = '<p style="color:#888;padding:16px 0">No se encontraron competidores.</p>';
    return;
  }
  document.getElementById('modal-comps').innerHTML = `
    <table class="comp-table"><thead><tr>
      <th>Producto competidor</th><th style="text-align:right">Precio</th>
      <th style="text-align:right">Diferencia</th><th>Tipo</th><th>Verif.</th><th>Link</th>
    </tr></thead><tbody>
    ${comps.map(c => {
      const d = c.diff_pct;
      const dStr = d != null ? `<span class="${d>0?'diff-pos':'diff-neg'}">${d>0?'+':''}${d.toFixed(1)}%</span>` : '—';
      const cid = c.comp_item_id||'';
      const url = c.comp_url || (cid ? mlUrl(cid) : '');
      return `<tr>
        <td style="max-width:260px" title="${c.comp_title}">${c.comp_title}</td>
        <td style="text-align:right;font-weight:700">${fpp(c.comp_price)}</td>
        <td style="text-align:right">${dStr}</td>
        <td><span class="${c.match_type==='directo'?'match-dir':'match-eq'}">${c.match_type==='directo'?'✅ Directo':'≈ Equiv.'}</span></td>
        <td style="font-size:.72rem;color:#888">${c.claude_verif?'🤖 Claude':'🔧 Motor'}</td>
        <td>${url?`<a href="${url}" target="_blank" class="link-ml">↗ Ver</a>`:'—'}</td>
      </tr>`;
    }).join('')}
    </tbody></table>`;
}

function closeModal(e) {
  if (!e || e.target === document.getElementById('modal-bg')) {
    document.getElementById('modal-bg').classList.remove('open');
    modalItemId = null;
    reportarPresencia('','');
  }
}

// ── Revisiones ────────────────────────────────────────────────────────
async function marcarRevisado() {
  if (!modalItemId) return;
  const btn = document.getElementById('btn-marcar');
  btn.textContent = 'Guardando...'; btn.disabled = true;
  try {
    const r = await fetch('/api/revisiones/'+modalItemId, {method:'POST'});
    const j = await r.json();
    if (j.error) throw new Error(j.error);
    await cargarRevisiones(modalItemId);
    await loadItems(); // refrescar tabla para mostrar revisión
  } catch(e) {
    alert('Error al guardar revisión: ' + e.message);
  }
  btn.textContent = 'Marcar como revisado'; btn.disabled = false;
}

async function cargarRevisiones(itemId) {
  const data = await fetch('/api/revisiones/'+itemId).then(r=>r.json()).catch(()=>[]);
  const el = document.getElementById('rev-list');
  if (!data || !data.length) { el.innerHTML = '<span style="color:#aaa">Aún no revisado</span>'; return; }
  el.innerHTML = data.map(r => `
    <div class="rev-row">
      <span class="rev-user">${r.usuario}</span>
      <span style="color:#aaa;margin:0 4px">·</span>
      <span>${fmtDate(r.revisado_at)} hs</span>
    </div>`).join('');
}

// ── Init y auto-refresh ───────────────────────────────────────────────
loadSummary();
loadItems();
setInterval(loadSummary, 60000);
setInterval(actualizarPresencia, 10000);  // presencia cada 10s
setInterval(() => {
  loadItems();  // auto-refresh tabla cada 30s
  if (vistaActiva === 'sku') loadSKU();
}, 30000);
actualizarPresencia();
window.addEventListener('beforeunload', () => reportarPresencia('',''));
</script>
</body></html>"""




@app.route("/upload", methods=["POST"])
def upload_data():
    """
    Endpoint para que el scraper (PC local) suba los datos frescos al dashboard.
    El scraper llama a este endpoint al final de cada corrida con todos los items
    y sus competidores actuales — así el dashboard siempre muestra datos frescos.
    Autenticación: header X-Upload-Key debe coincidir con UPLOAD_KEY en env.
    """
    auth       = request.headers.get("X-Upload-Key", "")
    upload_key = os.environ.get("UPLOAD_KEY", "agrocentral_upload_2026")
    if auth != upload_key:
        return jsonify({"ok": False, "msg": "No autorizado"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    items   = payload.get("items", [])
    if not items:
        return jsonify({"ok": False, "msg": "Sin items en payload"}), 400

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()

        uploaded = 0
        for item in items:
            item_id = item.get("id") or item.get("item_id", "")
            if not item_id:
                continue

            # 1. Upsert en ag_items
            cur.execute("""
                INSERT INTO ag_items
                    (item_id, sku, title, price, category_id, listing_type,
                     status, pa, concentracion, nc, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                ON CONFLICT (item_id) DO UPDATE SET
                    price        = EXCLUDED.price,
                    title        = EXCLUDED.title,
                    listing_type = EXCLUDED.listing_type,
                    status       = EXCLUDED.status,
                    pa           = EXCLUDED.pa,
                    nc           = EXCLUDED.nc,
                    updated_at   = NOW()
            """, (
                item_id,
                item.get("sku",""),
                item.get("title",""),
                item.get("price", 0),
                item.get("category_id",""),
                item.get("listing_type_id", "gold_special"),
                item.get("status","active"),
                item.get("pa",""),
                item.get("concentracion",""),
                item.get("nc",""),
            ))

            # 2. Reemplazar competidores: borrar viejos e insertar nuevos
            cur.execute("DELETE FROM ag_competidores WHERE my_item_id = %s", (item_id,))
            for comp in item.get("competidores", []):
                cur.execute("""
                    INSERT INTO ag_competidores
                        (my_item_id, comp_item_id, comp_title, comp_price,
                         comp_seller_id, match_type, claude_verif,
                         motor_razon, diff_pct, scraped_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                """, (
                    item_id,
                    comp.get("id",""),
                    comp.get("title",""),
                    comp.get("price", 0),
                    comp.get("seller_id",""),
                    comp.get("match_type","directo"),
                    bool(comp.get("claude_verif", False)),
                    comp.get("motor_razon",""),
                    comp.get("diff_pct"),
                ))

            # 3. Guardar semáforo y precio sugerido en ag_price_history
            semaforo = item.get("semaforo","gris")
            min_comp = item.get("min_comp")
            sugerido = item.get("precio_sugerido")
            n_comps  = len(item.get("competidores", []))
            if semaforo != "gris":
                cur.execute("""
                    INSERT INTO ag_price_history
                        (item_id, price, min_comp, suggested, semaforo, n_comps, recorded_at)
                    VALUES (%s,%s,%s,%s,%s,%s, NOW())
                """, (item_id, item.get("price",0), min_comp, sugerido, semaforo, n_comps))

            uploaded += 1

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "uploaded": uploaded})

    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
