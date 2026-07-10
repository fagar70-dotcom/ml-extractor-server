"""
Manejo de OAuth2 de Mercado Libre + persistencia del refresh_token en un
Gist privado de GitHub (porque Render free tier no tiene disco persistente).

Variables de entorno requeridas:
  ML_CLIENT_ID, ML_CLIENT_SECRET  -> de la app en developers.mercadolibre.com.ar
  GITHUB_TOKEN                    -> Personal Access Token con scope 'gist'
  GIST_ID                         -> ID del gist secreto donde se guardan los tokens
  RENDER_EXTERNAL_URL             -> la pone Render automáticamente
"""
import os
import time
import json
import requests

ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GIST_ID = os.environ.get("GIST_ID")

_base_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
REDIRECT_URI = f"{_base_url}/oauth/callback" if _base_url else None

GIST_FILENAME = "ml_tokens.json"
GITHUB_API = "https://api.github.com"
ML_AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

_cache = {}


def _gh_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def load_tokens():
    if "data" in _cache:
        return _cache["data"]
    r = requests.get(f"{GITHUB_API}/gists/{GIST_ID}", headers=_gh_headers(), timeout=15)
    r.raise_for_status()
    files = r.json().get("files", {})
    content = files.get(GIST_FILENAME, {}).get("content", "{}")
    data = json.loads(content or "{}")
    _cache["data"] = data
    return data


def save_tokens(data):
    _cache["data"] = data
    body = {"files": {GIST_FILENAME: {"content": json.dumps(data)}}}
    r = requests.patch(f"{GITHUB_API}/gists/{GIST_ID}", headers=_gh_headers(), json=body, timeout=15)
    r.raise_for_status()


def _store_from_response(data):
    tokens = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + data.get("expires_in", 21600) - 60,
    }
    save_tokens(tokens)
    return tokens


def exchange_code(code):
    r = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": ML_CLIENT_ID,
            "client_secret": ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"accept": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    return _store_from_response(r.json())


def _refresh(refresh_token):
    r = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": ML_CLIENT_ID,
            "client_secret": ML_CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
        headers={"accept": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    return _store_from_response(r.json())


def get_valid_access_token():
    tokens = load_tokens()
    if not tokens.get("refresh_token"):
        raise RuntimeError(
            "No hay tokens guardados todavia. Autorizá la app entrando a /oauth/start"
        )
    if tokens.get("access_token") and time.time() < tokens.get("expires_at", 0):
        return tokens["access_token"]
    tokens = _refresh(tokens["refresh_token"])
    return tokens["access_token"]


def authorization_url():
    return (
        f"{ML_AUTH_URL}?response_type=code"
        f"&client_id={ML_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
