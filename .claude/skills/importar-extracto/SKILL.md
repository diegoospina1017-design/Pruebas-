---
name: importar-extracto
description: Importa un extracto bancario o de tarjeta (CSV, XLSX o PDF) a la base de Movimientos de Notion — normaliza fechas y montos, categoriza en lote, detecta duplicados con lo ya registrado y pide confirmación antes de escribir.
---

# Importar extracto bancario

Referencia de IDs y esquema: `finanzas/NOTION.md`. Trabaja los archivos intermedios en el
**scratchpad**, nunca dentro de `finanzas/` (son datos privados).

## 1. Obtener y normalizar el archivo

- **CSV / XLSX:** pregunta la moneda si no es obvia (Bancolombia/Davivienda/Nequi → COP; Citi/Chase/Amex US → USD) y ejecuta:
  ```bash
  python3 -I finanzas/scripts/parse_extracto.py RUTA --moneda COP > SCRATCH/extracto.json
  ```
  El script detecta encabezados (aunque haya filas de preámbulo), formato de número colombiano o
  estadounidense, orden de fecha y columnas Débito/Crédito. Lee los `avisos`.
- **Convención de signo:** si el aviso dice "Convención de signo detectada", verifica con un
  ejemplo evidente (un pago de nómina debe ser Ingreso; una compra, Gasto). Si sale al revés,
  vuelve a correr con `--signo gasto-negativo` o `--signo gasto-positivo`.
- **PDF:** léelo con Read (por páginas), transcribe las transacciones a un CSV en el scratchpad
  (`Fecha,Descripción,Monto`) y córrelo por el script. Revisa que el total coincida con el del extracto.
- `.xls` antiguo: pide al usuario guardarlo como `.xlsx` o `.csv`.

## 2. Detectar duplicados

Lee la vista de Movimientos (`mode: "view"`, paginando con `start_cursor`) hasta cubrir el rango
de fechas del extracto. Concatena los `results` en `SCRATCH/notion.json` y vuelve a correr el
script con `--existentes SCRATCH/notion.json`. Las filas con `duplicado_de` **no se importan**
(normalmente ya las trajo la automatización de correo); pero si esa fila de Notion está en
«Otros» o con comercio "Desconocido", ofrece actualizarla con la descripción y categoría del extracto.

## 3. Categorizar y limpiar

Para cada movimiento nuevo:
- `Comercio`: limpia la descripción ("COMPRA POS EXITO CALLE 80 BOG" → "Éxito").
- `Categoría`: usa las pistas de `registrar-movimiento`.
- `Tipo`: pagos de tarjeta, traslados entre cuentas propias, retiros de cajero → `Transferencia`.
- `Tarjeta`: nombre de la cuenta/tarjeta del extracto. `Origen`: `Extracto`.

## 4. Vista previa y confirmación

Muestra una tabla compacta: nº de filas nuevas, duplicadas omitidas y transferencias; totales de
gastos e ingresos; y la lista (fecha, comercio, monto, categoría). Señala las de categoría dudosa.
**Espera confirmación** y aplica las correcciones que pida el usuario.

## 5. Escribir

`notion-create-pages` en lotes de hasta 50 páginas, `parent.data_source_id = 3ffee370-e0ed-43fe-8bff-676891744b91`.
Al final, informa cuántas filas se crearon/actualizaron y ofrece el reporte del mes
(skill `reporte-financiero`).
