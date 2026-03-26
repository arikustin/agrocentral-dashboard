"""
agrocentral_cloud_dashboard.py — Railway
Lee HTML desde dashboard_template.html (archivo separado).
"""
import os, json
from flask import (Flask, jsonify, make_response, redirect,
                   render_template_string, request)
import db

USERS = {
    "ariel":    os.environ.get("DASHBOARD_PASSWORD_ARIEL",  "agrocentral2026"),
    "usuario2": os.environ.get("DASHBOARD_PASSWORD_USER2",  "agro2026"),
    "usuario3": os.environ.get("DASHBOARD_PASSWORD_USER3",  "agro2026b"),
}

app = Flask(__name__)

def make_token(u):
    return f"{u}:{str(abs(hash(USERS[u]+u)))[:12]}"

def get_session_user(req):
    t = req.cookies.get("agro_session","")
    if not t or ":" not in t: return None
    u, s = t.split(":",1)
    if u in USERS and s == str(abs(hash(USERS[u]+u)))[:12]: return u
    return None

def check_auth(req): return get_session_user(req) is not None

def load_dashboard_html():
    path = os.path.join(os.path.dirname(__file__), "dashboard_template.html")
    with open(path, encoding="utf-8") as f:
        return f.read()

LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>AGROCENTRAL</title>
<style>*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f0f4f0;display:flex;
  align-items:center;justify-content:center;min-height:100vh}
.box{background:#fff;border-radius:12px;padding:40px 48px;
  box-shadow:0 4px 24px rgba(0,0,0,.12);text-align:center;width:340px}
.logo{font-size:2.5rem;margin-bottom:8px}h2{color:#1a5c30;margin-bottom:6px}
p{color:#888;font-size:.85rem;margin-bottom:24px}
input{width:100%;padding:10px 14px;border:1px solid #ccc;border-radius:6px;
  font-size:.95rem;margin-bottom:12px;outline:none}
input:focus{border-color:#2e7d32}
button{width:100%;padding:11px;background:#1a5c30;color:#fff;border:none;
  border-radius:6px;font-size:.95rem;font-weight:bold;cursor:pointer}
button:hover{background:#2e7d32}.err{color:#c62828;font-size:.82rem;margin-top:10px}
</style></head><body><div class="box">
<div class="logo">🌿</div><h2>AGROCENTRAL</h2>
<p>Dashboard de Competencia</p>
<form method="POST" action="/login">
  <input type="text" name="username" placeholder="Usuario" autofocus>
  <input type="password" name="password" placeholder="Contrasena">
  <button type="submit">Ingresar</button>
  {%if error%}<div class="err">Usuario o contrasena incorrectos</div>{%endif%}
</form></div></body></html>"""

@app.route("/login", methods=["GET","POST"])
def login():
    error = False
    if request.method == "POST":
        u = request.form.get("username","").strip().lower()
        p = request.form.get("password","").strip()
        if u in USERS and USERS[u] == p:
            resp = make_response(redirect("/"))
            resp.set_cookie("agro_session", make_token(u),
                            max_age=60*60*24*30, httponly=True)
            return resp
        error = True
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie("agro_session")
    return resp

@app.route("/")
def index():
    if not check_auth(request): return redirect("/login")
    return load_dashboard_html()

@app.route("/api/me")
def api_me():
    return jsonify({"username": get_session_user(request) or ""})

@app.route("/api/data")
def api_data():
    if not check_auth(request): return jsonify({}), 401
    try:
        items = db.get_all_items()
        meta  = db.get_sync_meta()
        return jsonify({"items": items, "last_update": meta.get("last_update","")})
    except Exception as e:
        return jsonify({"error": str(e), "items": []}), 500

@app.route("/api/item/<item_id>")
def api_item(item_id):
    if not check_auth(request): return jsonify({}), 401
    try: return jsonify(db.get_item(item_id) or {})
    except: return jsonify({})

@app.route("/api/reviews")
def api_reviews():
    if not check_auth(request): return jsonify({}), 401
    try: return jsonify(db.get_all_reviews())
    except: return jsonify({})

@app.route("/api/review/<item_id>", methods=["POST"])
def api_review(item_id):
    u = get_session_user(request)
    if not u: return jsonify({"ok":False}), 401
    try:
        rev = db.save_review(item_id, u)
        return jsonify({"ok":True,"review":rev})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

@app.route("/api/status")
def api_status():
    if not check_auth(request): return jsonify({}), 401
    try:
        meta = db.get_sync_meta()
        return jsonify({"status":"done","progress":100,"cloud_mode":True,
            "message":"Datos actualizados",
            "last_update":meta.get("last_update",""),"has_data":True})
    except: return jsonify({"status":"idle","cloud_mode":True})

@app.route("/api/update", methods=["POST"])
def api_update():
    return jsonify({"ok":False,"msg":"Actualizar desde la PC de Ariel."})

@app.route("/api/pause", methods=["POST"])
def api_pause():
    return jsonify({"ok":False,"msg":"No disponible en modo cloud."})

if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
