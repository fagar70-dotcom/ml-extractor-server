"""
Server HTTP simple para extraer datos públicos de Mercado Libre.
Pensado para deployar gratis en Render (mismo patrón que dashboard-ls).

Endpoints:
  GET  /health
  POST /extraer   body JSON: {"ids": [...], "refs": [...], "search": "...", "site": "MLA", "limit": 20}
"""
from flask import Flask, request, jsonify
import ml_core

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/extraer")
def extraer():
    data = request.get_json(force=True, silent=True) or {}
    ids = data.get("ids") or []
    refs = data.get("refs") or []
    search = data.get("search")
    site = data.get("site", "MLA")
    limit = int(data.get("limit", 20))

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
