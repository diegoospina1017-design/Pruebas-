---
name: reporte-financiero
description: Genera el reporte financiero de un mes (ingresos, gastos, ahorro, presupuesto vs real, comparación con el mes anterior, top comercios, facturas por vencer y metas de ahorro) a partir de Notion; opcionalmente lo publica como página de Notion o dashboard visual.
---

# Reporte financiero

Referencia de IDs y esquema: `finanzas/NOTION.md`.

## 1. Reunir datos (solo `mode: "view"`)

1. **Movimientos**: vista `view://419ff1f0-d877-814d-a8f9-000cdcb04aa5` (Fecha desc). Pagina con
   `start_cursor` hasta pasar el inicio del **mes anterior** al mes pedido (lo necesitas para comparar).
   Guarda las páginas en `SCRATCH/movs.json` (lista de objetos `{results: [...]}` o una lista plana).
   Para ahorrar espacio, guarda solo las claves que usa el script: `date:Fecha:start`, `Monto`,
   `Moneda`, `Tipo`, `Categoría`, `Comercio`, `url`.
2. **Presupuestos**: vista `view://688a46c1-1681-40b8-a33e-ec54c23e5e26` → `SCRATCH/pres.json`.
3. **Facturas pendientes**: vista `view://36fff1f0-d877-81d6-b71e-000c8375f1c0`.
4. **Metas de ahorro**: vista `view://419ff1f0-d877-8199-aced-000cf88504c6`.

## 2. Calcular

```bash
python3 finanzas/scripts/resumen.py --movimientos SCRATCH/movs.json \
  --presupuestos SCRATCH/pres.json --mes YYYY-MM
```

(`--json` si necesitas las cifras para un gráfico). No recalcules a mano lo que da el script.

## 3. Presentar

Orden del reporte en el chat:
1. **Titular** en una frase: "Noviembre va en $2,1 M de gasto (−12 % vs octubre) y ahorras el 31 %."
2. Totales por moneda (ingresos, gastos, neto, tasa de ahorro, proyección si es el mes en curso).
3. Tabla presupuesto vs real con semáforo.
4. Mayores cambios frente al mes anterior (categorías que suben o bajan >20 %).
5. Top comercios.
6. Facturas pendientes que vencen en ≤ 7 días.
7. Metas de ahorro: progreso y cuánto hay que ahorrar al mes para llegar a la fecha límite.
8. **2–3 recomendaciones accionables**, basadas en los datos (no genéricas).

**Calidad de datos primero.** El script devuelve `calidad` con `posibles_duplicados`,
`posibles_pagos_de_tarjeta` y `gastos_sin_monto`. La automatización de correo suele registrar la
misma compra dos veces (una como "Desconocido", otra con el comercio real) y registra los pagos de
tarjeta como gasto, lo que **cuenta dos veces** el mismo dinero. Antes del titular, si hay hallazgos,
dilo y ofrece corregir: archivar el duplicado "Desconocido" (con permiso) y pasar los pagos de
tarjeta a `Tipo = Transferencia`. Si el usuario no quiere corregir, presenta los totales aclarando
cuánto podría estar inflado.

Si hay muchos gastos en «Otros» o con comercio "Desconocido", ofrece recategorizarlos
(muéstralos en tabla, propone categoría, y actualiza con `notion-update-page` tras confirmación).

## 4. Publicar (opcional, solo si el usuario lo pide)

- **Página en Notion:** crea una subpágina "📊 Reporte YYYY-MM" bajo el Dashboard
  (`page_id 36fff1f0d87781e3ae9af7f63142a244`) con el contenido del reporte.
- **Dashboard visual:** usa la herramienta Artifact (carga antes el skill `dataviz`) con gráficos de
  gasto por categoría, tendencia mensual y presupuesto vs real.
