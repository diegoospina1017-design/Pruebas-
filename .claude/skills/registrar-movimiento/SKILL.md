---
name: registrar-movimiento
description: Registra uno o varios gastos, ingresos o transferencias dictados en lenguaje natural ("gasté 45.000 en el Éxito", "me pagaron 4,5 millones de nómina") en la base de Movimientos de Notion, con categoría inferida y alerta de presupuesto.
---

# Registrar movimiento

Referencia de IDs y esquema: `finanzas/NOTION.md`.

## 1. Interpretar el mensaje

Extrae por cada movimiento:

| Campo | Cómo deducirlo |
|---|---|
| `Comercio` | Nombre del comercio/fuente, en formato título ("Éxito", "Nómina", "Uber") |
| `Monto` | Número positivo. "45 mil"/"45k" = 45000; "4,5 millones"/"4.5M" = 4500000; "45.000" en COP = 45000 |
| `Moneda` | COP por defecto; USD si dice dólares/US$/USD o la tarjeta es Citi/Amazon (EE. UU.); EUR si dice euros |
| `Tipo` | Gasto por defecto. Ingreso: "me pagaron", "recibí", "nómina", "me consignaron". Transferencia: "pagué la tarjeta", "pasé a ahorros", "retiré del cajero" |
| `Fecha` | Hoy si no se dice. Resuelve "ayer", "el lunes", "15 de octubre" contra la fecha actual |
| `Categoría` | Ver tabla de pistas abajo. Si es ambiguo, elige la más probable y dilo |
| `Tarjeta` | Medio de pago si lo menciona ("con la Visa", "en efectivo", "Nequi") |
| `Origen` | Siempre `Manual` |
| `Notas` | Cualquier detalle extra que el usuario dé |

Pistas de categoría: mercado/supermercado/restaurante/domicilio/Rappi → Alimentación ·
Uber/taxi/gasolina/peaje/parqueadero/TransMilenio → Transporte · arriendo/administración/hipoteca → Vivienda ·
luz/agua/gas/internet/celular → Servicios · Netflix/Spotify/iCloud/ChatGPT → Suscripciones ·
farmacia/médico/EPS/gimnasio → Salud · cursos/colegio/libros → Educación ·
cine/conciertos/bares/juegos → Entretenimiento · tiquetes/hotel/Airbnb → Viajes ·
ropa/Amazon/Mercado Libre/tecnología → Compras · CDT/acciones/fondo/ahorro → Ahorro e inversión.
Ingresos: nómina/sueldo → Salario; resto → Otros ingresos.

Si falta el **monto**, pregunta. Para lo demás, decide.

## 2. Evitar duplicados

Lee la primera página (`page_size: 50`) de la vista de Movimientos. Si hay una fila con el mismo
monto, moneda y fecha ±1 día (p. ej. ya la registró la automatización de correo), muéstrala y
pregunta si es la misma antes de crear otra. Si es la misma, ofrece completar su categoría/comercio
con `notion-update-page` en vez de duplicar.

## 3. Escribir

`notion-create-pages` con `parent: {type: "data_source_id", data_source_id: "3ffee370-e0ed-43fe-8bff-676891744b91"}`
y propiedades, por ejemplo:

```json
{"Comercio": "Éxito", "Monto": 45000, "Moneda": "COP", "Tipo": "Gasto",
 "Categoría": "Alimentación", "date:Fecha:start": "2026-11-15", "date:Fecha:is_datetime": 0,
 "Tarjeta": "Efectivo", "Origen": "Manual"}
```

Varios movimientos en un mensaje → una sola llamada con varias páginas.

## 4. Confirmar y alertar

Responde en una o dos líneas: qué registraste (comercio, monto, categoría, fecha).
Si es un **gasto** y la categoría tiene presupuesto en esa moneda, calcula el uso del mes
(lee la vista de Movimientos del mes y la de Presupuestos, guarda ambos JSON en el scratchpad y
ejecuta `python3 finanzas/scripts/resumen.py --movimientos … --presupuestos … --json`).
Si el estado es `ALERTA`/`EXCEDIDO` o `se_excedera` es `true`, añade una línea de aviso:
"🟡 Alimentación va en 86 % de $350.000 (quedan $50.000, y a este ritmo cerrarías en $600.000)".
