# Deal Hunter v1

Cazador de ofertas para arbitraje en Amazon. Lee deals de fuentes públicas, los filtra contra tus reglas, y los pasa por la calculadora de rentabilidad.

## Pipeline

```
  Slickdeals RSS ─┐
                  ├─→ filter (config.json) ─→ analyze (asin_map.json) ─→ report.md
  sample_deals ───┘                                     │
                                                        ↓
                                              calculator/profit.py
```

## Estructura

```
deal_hunter/
├── hunter.py              # entrypoint - corre todo el pipeline
├── config.json            # tus reglas de filtrado (edítalo)
├── asin_map.json          # tu cache de mappings deal→Amazon (edítalo manualmente)
├── sources/
│   ├── slickdeals.py      # fetcher de RSS pública (sin auth)
│   └── sample_deals.json  # 10 deals de ejemplo para probar offline
├── filters.py             # motor de reglas
├── analyzer.py            # bridge a la calculadora
├── report.py              # generador de reporte markdown
├── report.md              # output (regenerated each run)
└── candidates.json        # output JSON crudo (para que otro script lo consuma)
```

## Quick start

### Offline (sin internet) - para probar la lógica
```bash
cd amazon-arbitrage/deal_hunter
python3 hunter.py --offline
cat report.md
```

### Live (desde tu máquina en VA, con internet)
```bash
python3 hunter.py
```

## Workflow real (cómo lo vas a usar día a día)

### Día 1: setup
1. Edita `config.json` con tus criterios (precio min/max, descuento mínimo, retailers preferidos)
2. Corre `python3 hunter.py` por la mañana
3. Revisa `report.md` → sección "Pending Amazon lookup"
4. Para los top 5-10 candidatos, abre Amazon y busca el producto:
   - Copia el **ASIN** (lo ves en la URL: amazon.com/dp/**B07XYZ**)
   - Toma nota del **precio actual**, **peso**, **dimensiones del paquete**, **BSR**, **# vendedores FBA**
5. Pega esos datos en `asin_map.json` usando la URL del deal como key
6. Re-corre `python3 hunter.py --offline` (usa la última fetch cacheada en `candidates.json`)
7. El reporte ahora tendrá esos deals en "Fully analyzed" con buy/skip claro

### Día 2 en adelante
- Solo necesitas mapear los deals **nuevos**. El `asin_map.json` se va llenando con tu propia base de datos de productos.
- A los 30 días tendrás 100+ entradas → el hunter va a ser muy preciso porque ya conoces los productos.

## Editar `config.json` - reglas que importan

| Sección | Para qué sirve |
|---|---|
| `price.min/max_deal_price` | Filtra rango de inversión por unidad. Default $5-$60 |
| `discount.min_discount_pct` | Mínimo % off. Default 40% (sin descuento real no hay arbitraje) |
| `retailers.include_only` | Solo deals de estas tiendas. Vacío = todas |
| `retailers.exclude` | Bloquea tiendas que no usas |
| `keywords.exclude_in_title` | Palabras que matan el deal (subscription, warranty, etc.) |
| `keywords.exclude_gated_brands` | Marcas que Amazon te bloquea hasta tener historial |
| `keywords.exclude_categories` | Categorías problemáticas (batería, perfume, vitaminas, alcohol) |
| `size_hints.exclude_in_title` | Detecta items grandes (TV, treadmill) con fees terribles |

## Editar `asin_map.json` - tu memoria del agente

Para cada deal que pase los filtros, agrega una entrada con el formato:

```json
"https://slickdeals.net/f/12345-some-deal-url": {
  "asin": "B07GFKJM5N",
  "amazon_sale_price": 29.99,
  "weight_lb": 4.5,
  "length_in": 14, "width_in": 10, "height_in": 6,
  "category": "kitchen",
  "size_tier": "standard",
  "units_per_box": 24,
  "bsr": 18500,
  "fba_sellers": 12
}
```

Categorías válidas: ver `calculator/fees.py` (kitchen, beauty, toys_games, home_garden, etc.)
Size tiers: `small_standard`, `standard`, `large_bulky`

## Lección importante de la primera corrida

Al correr offline con los 10 deals de muestra, **TODOS los 4 candidatos analizados salieron SKIP**:

| Deal | Descuento aparente | Resultado real |
|---|---|---|
| OXO Kitchen Tools | 58% off | $2.38 profit, 8% ROI → skip |
| Pyrex containers | 57% off | -$1.91 profit → skip (pesado) |
| Mainstays towels | 55% off | -$0.36 profit → skip |
| Mr. Coffee maker | 56% off | -$4.87 profit → skip (pesado y grande) |

**Esto es realista**. La mayoría de "gangas" no son arbitraje rentable porque:
- Items pesados o grandes → FBA fee de $5-8 + inbound $3-8
- Categorías saturadas → no puedes subir precio
- Descuento aparente vs precio real en Amazon es menor de lo que parece

El agente te ahorra perder dinero en deals que se ven buenos pero no son. Cuando uno SÍ pase los filtros y salga "STRONG BUY", esa es la señal.

## Limitaciones de v1 (transparencia)

1. **Una sola fuente**: solo Slickdeals. Más fuentes (BrickSeek, DealNews) requieren scraping/APIs adicionales.
2. **Sin auto-lookup de Amazon**: el step de mappear deal→ASIN es manual. Para automatizarlo necesitas Keepa API ($19/mes) o Amazon SP-API (requiere cuenta seller activa).
3. **Sin Keepa BSR histórico**: el `bsr` que pones es el actual, no el promedio 90 días. Para datos serios → integra Keepa.
4. **Sin restrictions check automático**: Amazon Seller App es la fuente de verdad. El agente solo hace heurísticas por keywords de marca.

## Roadmap v2 (cuando tengas cuenta seller)

- [ ] Integración Keepa API → auto-fetch de precio Amazon, BSR 90-day avg, sales velocity
- [ ] Integración SP-API → check de restrictions por tu cuenta específica
- [ ] Más fuentes: DealNews RSS, BrickSeek API, Walmart clearance API
- [ ] Notificaciones: Telegram bot o email diario
- [ ] Cron/GitHub Action para correrlo automático cada mañana
- [ ] LLM-powered: usar Claude API para extraer estructura de descripciones de deals (cuando el regex falla)

## Troubleshooting

**`Cannot reach Slickdeals: ... 403`**
Slickdeals está rate-limiting o cambió user-agent. Espera 5 min y reintenta, o usa `--offline`.

**`no asin_map at ...`**
Crea el archivo con `{}` vacío, o copia el formato de `asin_map.json` que viene en el repo.

**Todos los deals salen "pending Amazon lookup"**
Es esperado en la primera corrida — tu asin_map está vacío. Empieza mapeando los top 5 del reporte.
