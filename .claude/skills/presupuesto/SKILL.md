---
name: presupuesto
description: Define, ajusta o revisa los presupuestos mensuales por categoría en Notion y reporta el uso del mes con semáforo (OK / alerta al 80 % / excedido) y proyección a fin de mes.
---

# Presupuestos

Referencia de IDs y esquema: `finanzas/NOTION.md` (sección 🎯 Presupuestos mensuales).

## Definir o cambiar un límite

1. Lee la vista de Presupuestos. Hay **una fila por categoría** (el título es el nombre de la categoría).
2. Si la categoría existe, actualízala con `notion-update-page`
   (`Presupuesto mensual`, `Moneda`, y `Notas` si da contexto). Si no existe, créala con
   `notion-create-pages` en `data_source_id = e54cd51d-ae7d-4996-a185-6998fac4e242`.
   Usa exactamente los nombres de categoría de Movimientos.
3. La moneda del presupuesto debe ser la moneda en que realmente se gasta esa categoría. Si el
   usuario gasta en COP y en USD en la misma categoría, pregunta cuál presupuestar o crea la fila en
   la moneda principal y dilo.

## Ayudar a armar el presupuesto

Si el usuario no sabe cuánto poner, lee los movimientos de los últimos 3 meses, corre
`resumen.py --json` para cada mes y propón por categoría el promedio redondeado (hacia arriba, a
$50.000 en COP o US$25 en USD), marcando dónde podría recortar. Escribe solo tras su "sí".
Recordatorio útil: una regla de partida es 50 % necesidades / 30 % gustos / 20 % ahorro.

## Revisar cómo va

Lee Movimientos (del mes, paginando) y Presupuestos, guarda los JSON en el scratchpad y ejecuta:

```bash
python3 finanzas/scripts/resumen.py --movimientos SCRATCH/movs.json --presupuestos SCRATCH/pres.json
```

Muestra la tabla y destaca primero lo 🔴 excedido, luego lo 🟡 en alerta y lo que se proyecta a
exceder. Cierra con una recomendación concreta (p. ej. "te quedan $120.000 para Alimentación en 15
días: unos $8.000 diarios").
