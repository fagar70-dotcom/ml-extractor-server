# ML Extractor Server

Server HTTP chico para extraer datos públicos de Mercado Libre (título,
descripción, medidas, peso, fotos) sin depender del sandbox de Claude ni de
Emmanuel.

## Deploy en Render (gratis)

1. Crear un repo nuevo en GitHub (ej. `ml-extractor-server`) y subir estos
   4 archivos: `app.py`, `ml_core.py`, `requirements.txt`, `Procfile`.
2. En Render (render.com) → **New +** → **Web Service** → conectar el repo.
3. Configuración:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free
4. Deploy. Te queda una URL tipo `https://ml-extractor-server.onrender.com`.

⚠️ Free tier: el server se duerme después de un rato sin uso. La primera
llamada después de estar dormido tarda ~30-50 seg (cold start), después
responde normal.

## Uso

```bash
curl -X POST https://TU-URL.onrender.com/extraer \
  -H "Content-Type: application/json" \
  -d '{"refs": ["https://articulo.mercadolibre.com.ar/MLA-123456789-..."], "search": "valija samsonite", "site": "MLA", "limit": 20}'
```

Body:
- `ids`: lista de IDs ya normalizados (`"MLA123456789"`)
- `refs`: lista de links o strings de los que extraer el ID (regex)
- `search`: palabra clave para buscar publicaciones
- `site`: sitio ML (default `MLA` = Argentina)
- `limit`: máximo de resultados para `search` (default 20)

Devuelve JSON: `{"rows": [...], "warnings": [...], "count": N}`, con cada
row conteniendo `id, titulo_desc_corta, descripcion_larga, precio, moneda,
largo, ancho, alto, peso, cantidad_fotos, fotos (lista de URLs), link`.

## Uso desde Claude

Una vez deployado, avisarle a Claude la URL una sola vez (o pedirle que la
guarde en memoria). Claude hace un `web_fetch`/POST a `/extraer` y arma el
Excel localmente con esos datos (columnas: Título/Descripción corta,
Descripción larga, Precio, Largo, Ancho, Alto, Peso, Fotos URLs, Link).
