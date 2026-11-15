# 💰 Agente de finanzas personales

Agente de Claude Code que registra, categoriza y reporta tus finanzas usando como base de datos
el **💰 Control de Gastos — Dashboard** en Notion (Personal › Resumen de correos).

## Cómo usarlo

Abre Claude Code en este repo y habla normal; Claude delega en el subagente `finanzas`:

```
> gasté 45 dólares en Walmart con la Citi
> me pagaron la nómina, 5.200 dólares
> importa este extracto  (adjunta CSV/XLSX/PDF)
> pon 600 dólares de presupuesto para Alimentación
> ¿cómo voy este mes?
> quiero ahorrar 3.000 dólares para un viaje antes de junio
```

También puedes invocarlo explícitamente: *"usa el agente finanzas para…"*.

## Piezas

| Archivo | Qué hace |
|---|---|
| `.claude/agents/finanzas.md` | Subagente: personalidad, reglas y a qué skill delegar |
| `.claude/skills/registrar-movimiento/` | Gastos/ingresos en lenguaje natural + alerta de presupuesto |
| `.claude/skills/importar-extracto/` | Extractos CSV/XLSX/PDF → Notion, con deduplicación y vista previa |
| `.claude/skills/presupuesto/` | Definir límites y revisar uso con semáforo 🟢🟡🔴 y proyección |
| `.claude/skills/reporte-financiero/` | Reporte mensual, calidad de datos, metas, facturas por vencer |
| `finanzas/NOTION.md` | IDs, esquemas y vistas de las bases de Notion |
| `finanzas/scripts/parse_extracto.py` | Normaliza extractos (formatos COP/US, débito/crédito, preámbulos) |
| `finanzas/scripts/resumen.py` | Totales por moneda, presupuesto vs real, proyección, duplicados y pagos de tarjeta |

Pruebas: `python3 -m unittest discover finanzas/tests`

## Bases de Notion

- **🧾 Gastos tarjeta de crédito**: movimientos. Se añadieron `Tipo` (Gasto/Ingreso/Transferencia),
  `Origen` (Correo/Manual/Extracto), `Notas` y categorías nuevas. La automatización diaria de
  correo sigue escribiendo aquí igual que antes.
- **🎯 Presupuestos mensuales**: una fila por categoría (falta llenar los montos).
- **💳 Facturas pendientes por pago**: sin cambios.
- **🏦 Metas de ahorro**: nueva.

## Limitación conocida

El workspace de Notion no tiene plan Business, así que el agente no puede usar consultas SQL; lee
por vistas, paginando de a 100 filas. Funciona bien para uso personal, pero los reportes de varios
meses tardan un poco más.
