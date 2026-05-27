# Inventory Tracker - Guía de uso

## Cómo usarlo

Tienes 2 opciones:

### Opción A: Google Sheets (recomendado)
1. Ve a https://sheets.google.com → New → Blank spreadsheet
2. File → Import → Upload → selecciona `inventory_tracker.csv`
3. Cuando pregunte "Import location" elige "Replace spreadsheet"
4. Listo. Las 2 filas de ejemplo (EX001, EX002) te enseñan cómo llenar cada columna

### Opción B: Excel
Abre directo `inventory_tracker.csv` con Excel. Save As → `.xlsx` para que no se pierdan los datos.

## Qué significa cada columna

| Columna | Qué pones |
|---|---|
| `sku` | Tu código interno (EX001, EX002...). Pégaselo a las cajas con sharpie |
| `asin` | El ASIN de Amazon del producto (B07XXXXX) — está en la URL del listing |
| `product_name` | Nombre corto descriptivo |
| `category` | Categoría Amazon (kitchen, toys_games, etc.) — usa la lista de fees.py |
| `source_store` | Dónde lo compraste (Walmart Christiansburg, Target online, AliExpress, etc.) |
| `purchase_date` | Fecha compra (YYYY-MM-DD) |
| `units_purchased` | Cuántas unidades compraste |
| `cost_per_unit` | Precio por unidad antes de tax |
| `sales_tax_pct` | % impuesto que pagaste (VA = 5.3%) |
| `total_cost` | `units_purchased × cost_per_unit × (1 + sales_tax_pct/100)` |
| `inbound_ship_cost` | Lo que pagaste a UPS/Amazon Partnered Carrier para mandar TODO el lote |
| `prep_supplies_cost` | Cajas, polybags, labels, tape, prep service si aplica |
| `total_landed_cost_per_unit` | `(total_cost + inbound + supplies) / units_purchased` |
| `target_sale_price` | Precio al que esperas vender en Amazon |
| `amazon_referral_fee` | Del calculator (sale_price × % categoría) |
| `fba_fulfillment_fee` | Del calculator (depende de peso/tamaño) |
| `storage_fee_est` | Estimado mensual × meses esperados |
| `total_amazon_fees` | Suma de los 3 fees de Amazon |
| `expected_profit_per_unit` | `target_sale_price - total_landed_cost_per_unit - total_amazon_fees` |
| `expected_roi_pct` | `expected_profit / total_landed_cost × 100` |
| `actual_units_sold` | Actualiza cada semana desde Seller Central |
| `actual_avg_sale_price` | Si tuviste que bajar precio, aquí va el promedio real |
| `actual_revenue` | Lo que Amazon te depositó (después de fees) |
| `returns_count` | Cuántas devoluciones |
| `return_cost` | Costo de las devoluciones (producto + return shipping) |
| `actual_profit` | `actual_revenue - total_landed_cost × units_sold - return_cost` |
| `actual_roi_pct` | ROI real cuando ya se vendió todo |
| `days_in_inventory` | Cuánto llevaba en FBA antes de venderse (afecta storage fees) |
| `bsr_at_purchase` | Best Seller Rank cuando compraste (Keepa lo muestra) |
| `bsr_current` | BSR actual — si subió mucho la demanda cayó |
| `status` | active / shipped_to_fba / selling / sold_out / liquidating / returned |
| `notes` | Cualquier cosa importante (proveedor, código de descuento, etc.) |

## Métricas que debes vigilar cada lunes

1. **Velocidad de venta**: `actual_units_sold / days_in_inventory` — si <0.3 unidades/día está lento
2. **ROI promedio del portafolio**: filtra `status=sold_out`, promedio de `actual_roi_pct` — objetivo >40%
3. **Cash flow**: total invertido (suma `total_cost + inbound + supplies` de items activos) vs total recuperado
4. **Productos en zombie**: `days_in_inventory > 90` y `actual_units_sold = 0` → liquida o devuelve
5. **Tasa de devoluciones por SKU**: si `returns_count / actual_units_sold > 5%` algo anda mal con el producto

## Fórmulas listas para pegar en Google Sheets

Asumiendo encabezados en fila 1, datos desde fila 2. Para fila 2 (`I2 = total_cost`):

```
J2  (total_cost):                   =G2*H2*(1+I2/100)
M2  (total_landed_cost_per_unit):   =(J2+K2+L2)/G2
R2  (total_amazon_fees):            =O2+P2+Q2
S2  (expected_profit_per_unit):     =N2-M2-R2
T2  (expected_roi_pct):             =S2/M2*100
Y2  (actual_profit):                =W2-(M2*U2)-X2
Z2  (actual_roi_pct):               =Y2/(M2*U2)*100
```

Selecciona las celdas con fórmula → arrastra hacia abajo para que aplique a todas las filas nuevas.
