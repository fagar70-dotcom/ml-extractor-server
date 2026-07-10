"""
Lógica de extracción de datos públicos de Mercado Libre.
Usada por app.py (servidor Flask).
"""
import re
import time
import requests
import ml_auth

API = "https://api.mercadolibre.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (ML-extractor)"}


def auth_headers():
    token = ml_auth.get_valid_access_token()
    return {**HEADERS, "Authorization": f"Bearer {token}"}

ID_RE = re.compile(r"(MLA|MLM|MLB|MLC|MCO|MLU|MPE|MEC|MLV)-?(\d+)")

DIM_ATTR_IDS = {
    "length": ["PACKAGE_LENGTH", "LENGTH"],
    "width": ["PACKAGE_WIDTH", "WIDTH"],
    "height": ["PACKAGE_HEIGHT", "HEIGHT"],
    "weight": ["PACKAGE_WEIGHT", "WEIGHT"],
}
DIM_NAME_HINTS = {
    "length": ["largo", "profundidad", "length"],
    "width": ["ancho", "width"],
    "height": ["alto", "height"],
    "weight": ["peso", "weight"],
}


def extract_id(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    m = ID_RE.search(raw.replace("%20", ""))
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return None


def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def search_ids(query, site, limit):
    ids, offset = [], 0
    while len(ids) < limit:
        page_limit = min(50, limit - len(ids))
        r = requests.get(
            f"{API}/sites/{site}/search",
            params={"q": query, "limit": page_limit, "offset": offset},
            headers=auth_headers(),
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        ids.extend([it["id"] for it in results])
        offset += len(results)
        if offset >= data.get("paging", {}).get("total", 0):
            break
        time.sleep(0.15)
    return ids[:limit]


def fetch_items(ids):
    items = []
    errors = []
    for batch in chunked(ids, 20):
        r = requests.get(
            f"{API}/items", params={"ids": ",".join(batch)}, headers=auth_headers(), timeout=20
        )
        r.raise_for_status()
        for entry in r.json():
            if entry.get("code") == 200:
                items.append(entry["body"])
            else:
                body = entry.get("body", {})
                errors.append(f"{body.get('id', '?')}: {body.get('message') or body}")
        time.sleep(0.15)
    return items, errors


def fetch_description(item_id):
    try:
        r = requests.get(f"{API}/items/{item_id}/description", headers=auth_headers(), timeout=15)
        if r.status_code == 200:
            data = r.json()
            return (data.get("plain_text") or data.get("text") or "").strip()
    except requests.RequestException:
        pass
    return ""


def get_dim(attributes, key):
    ids_wanted = DIM_ATTR_IDS[key]
    hints = DIM_NAME_HINTS[key]
    for attr in attributes:
        if attr.get("id") in ids_wanted:
            val = attr.get("value_name") or attr.get("value_struct")
            if val:
                return str(val)
    for attr in attributes:
        name = (attr.get("name") or "").lower()
        if any(h in name for h in hints):
            val = attr.get("value_name")
            if val:
                return str(val)
    return ""


def parse_shipping_dimensions(item):
    dims = (item.get("shipping") or {}).get("dimensions")
    if not dims:
        return None
    try:
        size_part, weight_part = dims.split(",")
        length, width, height = size_part.split("x")
        return {
            "largo": f"{length} cm",
            "ancho": f"{width} cm",
            "alto": f"{height} cm",
            "peso": f"{weight_part} g",
        }
    except Exception:
        return None


def build_row(item):
    item_id = item["id"]
    attributes = item.get("attributes", [])
    shipping_dims = parse_shipping_dimensions(item)

    if shipping_dims:
        largo, ancho, alto, peso = (
            shipping_dims["largo"],
            shipping_dims["ancho"],
            shipping_dims["alto"],
            shipping_dims["peso"],
        )
    else:
        largo = get_dim(attributes, "length")
        ancho = get_dim(attributes, "width")
        alto = get_dim(attributes, "height")
        peso = get_dim(attributes, "weight")

    short_desc = ""
    for attr in attributes:
        if attr.get("id") == "SHORT_DESCRIPTION" and attr.get("value_name"):
            short_desc = attr["value_name"]
            break
    if not short_desc:
        short_desc = item.get("title", "")

    long_desc = fetch_description(item_id)

    pictures = [p.get("secure_url") or p.get("url") for p in item.get("pictures", [])]
    pictures = [p for p in pictures if p]

    return {
        "id": item_id,
        "titulo_desc_corta": short_desc,
        "descripcion_larga": long_desc,
        "precio": item.get("price"),
        "moneda": item.get("currency_id"),
        "largo": largo,
        "ancho": ancho,
        "alto": alto,
        "peso": peso,
        "cantidad_fotos": len(pictures),
        "fotos": pictures,
        "link": item.get("permalink", ""),
    }


def extract(ids=None, refs=None, search=None, site="MLA", limit=20):
    """
    ids: lista de IDs de ML ya normalizados (MLA123...)
    refs: lista de links o strings sueltos de donde extraer el ID con regex
    search: palabra clave para buscar publicaciones
    Devuelve: (rows, warnings)
    """
    all_ids = list(ids or [])
    warnings = []

    for ref in refs or []:
        item_id = extract_id(ref)
        if item_id:
            all_ids.append(item_id)
        else:
            warnings.append(f"No se pudo reconocer un ID en: {ref}")

    if search:
        all_ids += search_ids(search, site, limit)

    seen = set()
    all_ids = [i for i in all_ids if not (i in seen or seen.add(i))]

    if not all_ids:
        return [], warnings + ["No se encontraron IDs para procesar."]

    items, item_errors = fetch_items(all_ids)
    warnings = warnings + item_errors
    rows = [build_row(item) for item in items]
    return rows, warnings
