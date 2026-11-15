# Referencia Notion — Agente de finanzas

Fuente única de verdad para IDs, esquemas y reglas. Todos los skills de finanzas leen este archivo.

Ubicación en Notion: **Personal › Resumen de correos › 💰 Control de Gastos — Dashboard**
(`https://app.notion.com/p/36fff1f0d87781e3ae9af7f63142a244`)

> ⚠️ El workspace de Notion **no tiene plan Business**: el modo `sql` y el modo `rows` de
> `notion-query-data-sources` fallan con `entitlement_required`. **Lee siempre con
> `mode: "view"`** usando las vistas de abajo, y pagina con `start_cursor` mientras `has_more` sea `true`.
> No reintentes SQL.

## 1. 🧾 Movimientos (`Gastos tarjeta de crédito`)

- Database: `79be9c3c3f1c49d39d0301df8d0bdf5b`
- Data source: `collection://3ffee370-e0ed-43fe-8bff-676891744b91`
- Vista para leer (ordenada por Fecha desc): `view://419ff1f0-d877-814d-a8f9-000cdcb04aa5`

| Propiedad | Tipo | Notas |
|---|---|---|
| `Comercio` | title | Nombre del comercio o del ingreso ("Nómina Tekni-Plex", "Éxito") |
| `Fecha` | date | Escribir como `date:Fecha:start` = `YYYY-MM-DD`, `date:Fecha:is_datetime` = 0 |
| `Monto` | number | **Siempre positivo.** El signo lo da `Tipo` |
| `Moneda` | select | `COP`, `USD`, `EUR` |
| `Tipo` | select | `Gasto`, `Ingreso`, `Transferencia`. **Vacío = Gasto** (filas antiguas del correo) |
| `Categoría` | select | ver lista abajo |
| `Tarjeta` | text | Medio de pago / cuenta ("Citi AAdvantage 7394", "Efectivo", "Bancolombia") |
| `Origen` | select | `Correo` (automatización diaria), `Manual` (chat), `Extracto` (importación) |
| `Notas` | text | libre |
| `Correo` | url | link al correo de origen (solo automatización) |
| `Mes`, `Detectado` | formula / created_time | solo lectura, no escribir |

**Categorías de gasto:** Alimentación, Transporte, Vivienda, Servicios, Suscripciones, Compras,
Salud, Educación, Entretenimiento, Viajes, Ahorro e inversión, Otros.
**Categorías de ingreso:** Salario, Otros ingresos.
`Transferencia` (pago de tarjeta, movimiento entre cuentas propias) **no cuenta** ni como gasto ni como ingreso.

## 2. 🎯 Presupuestos mensuales

- Database: `80db7302ee50468593fa604b2fde897f`
- Data source: `collection://e54cd51d-ae7d-4996-a185-6998fac4e242`
- Vista: `view://688a46c1-1681-40b8-a33e-ec54c23e5e26`
- Propiedades: `Categoría` (title, igual al nombre de la categoría de movimientos),
  `Presupuesto mensual` (number), `Moneda` (select COP/USD/EUR), `Notas` (text).
- Una fila por categoría. Para cambiar un límite, actualiza la fila existente (no crees duplicados).

## 3. 💳 Facturas pendientes por pago

- Database: `6295b4b6614c4fbf84c664afb4b1d7b9`
- Data source: `collection://29dcd429-91d4-4acf-b42a-80e88bf8de87`
- Vista pendientes (ordenada por vencimiento): `view://36fff1f0-d877-81d6-b71e-000c8375f1c0`
- Propiedades: `Proveedor` (title), `Monto`, `Moneda`, `Estado` (Pendiente/Pagada/Vencida),
  `Fecha de emisión`, `Fecha límite de pago`, `Categoría`, `Correo`, `Días para vencer` (fórmula).

## 4. 🏦 Metas de ahorro

- Database: `419ff1f0d87781f089e9e76ce787a3f7`
- Data source: `collection://419ff1f0-d877-8144-9847-000bf79fa801`
- Vista: `view://419ff1f0-d877-8199-aced-000cf88504c6`
- Propiedades: `Meta` (title), `Objetivo`, `Ahorrado`, `Moneda`, `Fecha límite` (date),
  `Estado` (Activa/Lograda/Pausada), `Progreso` (fórmula 0–1, solo lectura), `Notas`.

## Reglas comunes

1. **Escribir** filas: `notion-create-pages` con `parent: {type: "data_source_id", data_source_id: "<uuid sin collection://>"}`.
   **Actualizar**: `notion-update-page` con el id de la fila.
2. **No borrar** filas sin confirmación explícita del usuario. Para corregir, actualiza.
3. **Duplicados:** antes de insertar, compara contra los movimientos existentes del mismo periodo
   (misma fecha ±1 día, mismo monto, misma moneda). La automatización de correo ya registra
   las compras de tarjeta, así que un extracto de tarjeta casi siempre se solapa con ella.
4. **Monedas:** nunca sumes COP con USD. Reporta cada moneda por separado, salvo que el usuario
   dé una tasa de cambio explícita.
5. Las fechas relativas ("ayer", "el viernes") se resuelven contra la fecha actual del sistema.
