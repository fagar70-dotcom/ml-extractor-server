"""
Server HTTP simple para extraer datos públicos de Mercado Libre.
Pensado para deployar gratis en Render (mismo patrón que dashboard-ls).

Endpoints:
  GET  /health
  POST /extraer   body JSON: {"ids": [...], "refs": [...], "search": "...", "site": "MLA", "limit": 20}
"""
from flask import Flask, request, jsonify, redirect
import ml_core
import ml_auth

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/oauth/start")
def oauth_start():
    if not ml_auth.REDIRECT_URI:
        return jsonify({"error": "Falta RENDER_EXTERNAL_URL / configuración"}), 500
    return redirect(ml_auth.authorization_url())


@app.get("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return f"Error de autorización: {error}", 400
    if not code:
        return "Falta el parámetro 'code'.", 400
    try:
        ml_auth.exchange_code(code)
    except Exception as e:
        return f"Error al intercambiar el código: {e}", 500
    return "Autorización completada con éxito. Ya podés cerrar esta pestaña y volver al chat."


@app.route("/extraer", methods=["GET", "POST"])
def extraer():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        ids = data.get("ids") or []
        refs = data.get("refs") or []
        search = data.get("search")
        site = data.get("site", "MLA")
        limit = int(data.get("limit", 20))
    else:
        args = request.args
        ids = [i for i in args.get("ids", "").split(",") if i]
        refs = [r for r in args.get("refs", "").split(",") if r]
        search = args.get("search")
        site = args.get("site", "MLA")
        limit = int(args.get("limit", 20))

    if not ids and not refs and not search:
        return jsonify({"error": "Mandá 'ids', 'refs' y/o 'search'."}), 400

    try:
        rows, warnings = ml_core.extract(
            ids=ids, refs=refs, search=search, site=site, limit=limit
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"rows": rows, "warnings": warnings, "count": len(rows)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
