import psycopg2
import psycopg2.extras
import os
from flask import Flask, jsonify, make_response, redirect, request, Response
import db

app = Flask(__name__)

USERS = {
    "ariel":    os.environ.get("PASS_ARIEL",  "agrocentral2026"),
    "jere":     os.environ.get("PASS_JERE",   "jere2026"),
    "ale":      os.environ.get("PASS_ALE",    "ale2026"),
}

with open(os.path.join(os.path.dirname(__file__), "dashboard_template.html"), encoding="utf-8") as _f:
    DASH_HTML = _f.read()

LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>AGROCENTRAL</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh}.box{background:#fff;border-radius:12px;padding:40px 48px;box-shadow:0 4px 24px rgba(0,0,0,.12);text-align:center;width:340px}.logo{font-size:2.5rem;margin-bottom:8px}h2{color:#1a5c30;margin-bottom:6px}p{color:#888;font-size:.85rem;margin-bottom:24px}input{width:100%;padding:10px 14px;border:1px solid #ccc;border-radius:6px;font-size:.95rem;margin-bottom:12px;outline:none}input:focus{border-color:#2e7d32}button{width:100%;padding:11px;background:#1a5c30;color:#fff;border:none;border-radius:6px;font-size:.95rem;font-weight:bold;cursor:pointer}button:hover{background:#2e7d32}.err{color:#c62828;font-size:.82rem;margin-top:10px}</style></head><body><div class="box"><div class="logo">&#127807;</div><h2>AGROCENTRAL</h2><p>Dashboard de Competencia</p><form method="POST" action="/login"><input type="text" name="username" placeholder="Usuario" autofocus><input type="password" name="password" placeholder="Contrasena"><button type="submit">Ingresar</button>{error}</form></div></body></html>"""

def make_token(u):
    return u + ":" + str(abs(hash(USERS[u] + u)))[:12]

def get_user(req):
    t = req.cookies.get("agro_session", "")
    if ":" not in t: return None
    u, s = t.split(":", 1)
    if u in USERS and s == str(abs(hash(USERS[u] + u)))[:12]: return u
    return None

def auth(req): return get_user(req) is not None

@app.route("/login", methods=["GET","POST"])
def login():
    err = ""
    if request.method == "POST":
        u = request.form.get("username","").strip().lower()
        p = request.form.get("password","").strip()
        if u in USERS and USERS[u] == p:
            resp = make_response(redirect("/"))
            resp.set_cookie("agro_session", make_token(u), max_age=86400*30, httponly=True)
            return resp
        err = '<div class="err">Usuario o contrasena incorrectos</div>'
    return LOGIN_HTML.replace("{error}", err)

@app.route("/logout")
def logout():
    r = make_response(redirect("/login"))
    r.delete_cookie("agro_session")
    return r

@app.route("/")
def index():
    if not auth(request): return redirect("/login")
    return Response(DASH_HTML, mimetype="text/html")

@app.route("/api/me")
def api_me(): return jsonify({"username": get_user(request) or ""})

@app.route("/api/data")
def api_data():
    if not auth(request): return jsonify({}), 401
    try:
        # get_all_items con manejo robusto de JSONB
        items = []
        meta  = {}
        import psycopg2.extras as _extras
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor(cursor_factory=_extras.RealDictCursor) as cur:
                cur.execute("SELECT data FROM items ORDER BY updated_at DESC")
                for row in cur.fetchall():
                    d = row["data"]
                    if isinstance(d, str):
                        import json as _json
                        d = _json.loads(d)
                    items.append(d)
                cur.execute("SELECT key, value FROM sync_meta")
                meta = {r["key"]: r["value"] for r in cur.fetchall()}
        return jsonify({"items": items, "last_update": meta.get("last_update",""), "total": len(items)})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(), "items": []}), 500

@app.route("/api/item/<iid>")
def api_item(iid):
    if not auth(request): return jsonify({}), 401
    try:
        import psycopg2.extras as _extras
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor(cursor_factory=_extras.RealDictCursor) as cur:
                cur.execute("SELECT data FROM items WHERE id=%s",(iid,))
                row = cur.fetchone()
        if not row: return jsonify({})
        d = row["data"]
        if isinstance(d,str): import json as _j; d=_j.loads(d)
        return jsonify(d)
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/reviews")
def api_reviews():
    if not auth(request): return jsonify({}), 401
    try:
        import psycopg2.extras as _extras
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor(cursor_factory=_extras.RealDictCursor) as cur:
                cur.execute("SELECT item_id, username, fecha FROM reviews")
                rows = cur.fetchall()
        return jsonify({r["item_id"]:{"usuario":r["username"],"fecha":r["fecha"]} for r in rows})
    except: return jsonify({})

@app.route("/api/review/<iid>", methods=["POST"])
def api_review(iid):
    u = get_user(request)
    if not u: return jsonify({"ok":False}), 401
    try:
        from datetime import datetime as _dt
        fecha = _dt.now().strftime("%d/%m/%Y %H:%M")
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO reviews (item_id,username,fecha,timestamp)
                    VALUES (%s,%s,%s,NOW())
                    ON CONFLICT (item_id) DO UPDATE SET
                    username=EXCLUDED.username,fecha=EXCLUDED.fecha,timestamp=NOW()
                """,(iid,u,fecha))
            conn.commit()
        return jsonify({"ok":True,"review":{"usuario":u,"fecha":fecha}})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}), 500

@app.route("/api/status")
def api_status():
    if not auth(request): return jsonify({}), 401
    try:
        meta = db.get_sync_meta()
        return jsonify({"status":"done","progress":100,"cloud_mode":True,"has_data":True,"last_update":meta.get("last_update",""),"message":"Datos disponibles"})
    except: return jsonify({"status":"idle","cloud_mode":True})

@app.route("/api/update", methods=["POST"])
def api_update(): return jsonify({"ok":False,"msg":"Actualizar desde la PC de Ariel."})

@app.route("/api/pause", methods=["POST"])
def api_pause(): return jsonify({"ok":False})

if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
