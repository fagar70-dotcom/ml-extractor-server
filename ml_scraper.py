"""
Scraper de datos públicos desde el HTML de publicaciones de Mercado Libre.
Uso: cuando la API oficial no da acceso (publicaciones que no son tuyas).

No usa la API — lee directamente la página pública, igual que lo vería
cualquier visitante o Google. Puede romperse si ML cambia el diseño del HTML.
"""
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.mercadolibre.com.ar/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Ch-Ua": '"Chromium";v="125", "Not.A/Brand";v="24", "Google Chrome";v="125"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

_session = None


def _get_session():
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            s.get("https://www.mercadolibre.com.ar/", timeout=15)
        except requests.RequestException:
            pass
        _session = s
    return _session


def fetch_html(url):
    session = _get_session()
    r = session.get(url, timeout=20, allow_redirects=True)
    r.raise_for_status()
    if "Verificación de seguridad" in r.text or "/security-check" in r.url:
        raise RuntimeError(
            "Mercado Libre mostró una pantalla de verificación de seguridad "
            "en vez de la publicación (bloqueo anti-bot)."
        )
    return r.text


def _json_ld_product(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for c in candidates:
            if isinstance(c, dict) and c.get("@type") == "Product":
                return c
    return {}


def _meta(soup, prop):
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return tag.get("content", "").strip() if tag else ""


def _long_description(soup):
    for sel in [
        "p.ui-pdp-description__content",
        "div.ui-pdp-description__content",
        "div#description",
    ]:
        node = soup.select_one(sel)
        if node:
            text = node.get_text("\n", strip=True)
            if text:
                return text
    return ""


def _spec_value(soup, keywords):
    for row in soup.select("tr, div.andes-table__row"):
        label_node = row.select_one("th, .andes-table__header__container, td:first-child")
        if not label_node:
            continue
        label = label_node.get_text(strip=True).lower()
        if any(k in label for k in keywords):
            value_node = row.select_one("td:last-child, .andes-table__column")
            if value_node:
                val = value_node.get_text(strip=True)
                if val:
                    return val
    return ""


def _gallery_images(soup):
    urls = []
    for img in soup.select("figure.ui-pdp-gallery__figure img, img.ui-pdp-image"):
        src = img.get("data-zoom") or img.get("data-src") or img.get("src")
        if src and src.startswith("http"):
            urls.append(src.split("#")[0])
    seen = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def parse_item(html, url):
    soup = BeautifulSoup(html, "html.parser")
    product = _json_ld_product(soup)

    title = (
        product.get("name")
        or _meta(soup, "og:title")
        or (soup.title.string.strip() if soup.title and soup.title.string else "")
    )

    long_desc = _long_description(soup)
    if not long_desc:
        long_desc = product.get("description") or _meta(soup, "og:description")

    price, currency = "", ""
    offers = product.get("offers")
    if isinstance(offers, dict):
        price = offers.get("price", "")
        currency = offers.get("priceCurrency", "")
    elif isinstance(offers, list) and offers:
        price = offers[0].get("price", "")
        currency = offers[0].get("priceCurrency", "")

    images = product.get("image")
    if isinstance(images, str):
        images = [images]
    if not images:
        images = _gallery_images(soup)
    if not images:
        og_img = _meta(soup, "og:image")
        images = [og_img] if og_img else []

    return {
        "titulo_desc_corta": title,
        "descripcion_larga": long_desc,
        "precio": price,
        "moneda": currency,
        "largo": _spec_value(soup, ["largo", "profundidad"]),
        "ancho": _spec_value(soup, ["ancho"]),
        "alto": _spec_value(soup, ["alto"]),
        "peso": _spec_value(soup, ["peso"]),
        "cantidad_fotos": len(images),
        "fotos": images,
        "link": url,
    }


def scrape(urls):
    rows, warnings = [], []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            html = fetch_html(url)
            rows.append(parse_item(html, url))
        except Exception as e:
            warnings.append(f"{url}: {e}")
    return rows, warnings
