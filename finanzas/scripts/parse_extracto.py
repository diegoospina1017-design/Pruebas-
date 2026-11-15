#!/usr/bin/env python3
"""Normaliza un extracto bancario (CSV o XLSX) a una lista JSON de movimientos.

Uso:
    python3 finanzas/scripts/parse_extracto.py EXTRACTO.csv --moneda COP
    python3 finanzas/scripts/parse_extracto.py EXTRACTO.xlsx --moneda USD \
        --existentes movimientos_notion.json

Salida (stdout): JSON con
    {"movimientos": [{fecha, descripcion, monto, tipo, moneda, duplicado_de?}], "avisos": [...]}

- `monto` siempre es positivo; `tipo` es "Gasto" o "Ingreso".
- Con --existentes (filas leídas de la vista de Notion) marca los posibles duplicados:
  misma moneda, mismo monto y fecha a ±1 día.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

FECHA_KEYS = ("fecha", "date", "posted", "transaction date", "fecha transaccion", "fecha movimiento")
DESC_KEYS = ("descripcion", "description", "concepto", "detalle", "merchant", "comercio",
             "referencia", "payee", "establecimiento", "transaccion")
MONTO_KEYS = ("monto", "amount", "valor", "importe", "total")
DEBITO_KEYS = ("debito", "debit", "cargo", "retiro", "withdrawal", "egreso")
CREDITO_KEYS = ("credito", "credit", "abono", "deposito", "deposit", "ingreso")


def _norm(texto: object) -> str:
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _match(header: str, keys: tuple[str, ...]) -> bool:
    return any(k == header or k in header.split() or header.startswith(k) for k in keys)


# ---------------------------------------------------------------- lectura de archivos

def leer_filas(ruta: Path) -> list[list[object]]:
    if ruta.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    if ruta.suffix.lower() == ".xls":
        sys.exit("Formato .xls antiguo no soportado: ábrelo y guárdalo como .xlsx o .csv")
    raw = ruta.read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    # csv.Sniffer falla con la coma decimal colombiana ("125.400,00"): elegimos el
    # delimitador presente en más líneas y, si empatan, el más frecuente.
    lineas = [ln for ln in texto.splitlines()[:60] if ln.strip()]
    delim = max(",;\t|", key=lambda d: (sum(d in ln for ln in lineas), sum(ln.count(d) for ln in lineas)))
    return [r for r in csv.reader(io.StringIO(texto), delimiter=delim)]


def encontrar_encabezado(filas: list[list[object]]) -> tuple[int, dict[str, int]]:
    """Busca en las primeras 40 filas la que tenga columna de fecha y de monto."""
    for i, fila in enumerate(filas[:40]):
        headers = [_norm(c) for c in fila]
        cols: dict[str, int] = {}
        for j, h in enumerate(headers):
            if not h:
                continue
            if "fecha" not in cols and _match(h, FECHA_KEYS):
                cols["fecha"] = j
            elif "desc" not in cols and _match(h, DESC_KEYS):
                cols["desc"] = j
            elif "debito" not in cols and _match(h, DEBITO_KEYS):
                cols["debito"] = j
            elif "credito" not in cols and _match(h, CREDITO_KEYS):
                cols["credito"] = j
            elif "monto" not in cols and _match(h, MONTO_KEYS):
                cols["monto"] = j
        if "fecha" in cols and ("monto" in cols or "debito" in cols or "credito" in cols):
            return i, cols
    sys.exit("No encontré encabezados de fecha y monto en el extracto. "
             "Revisa el archivo o indica las columnas manualmente.")


# ---------------------------------------------------------------- números y fechas

def parse_numero(valor: object) -> float | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    negativo = s.startswith("-") or s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    if re.search(r"\b(cr|db)\b", s, re.I):
        negativo = negativo or bool(re.search(r"\bdb\b", s, re.I))
    s = re.sub(r"[^\d,.]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        # El separador que aparece al final es el decimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        partes = s.split(",")
        s = s.replace(",", ".") if len(partes) == 2 and len(partes[1]) in (1, 2) else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        s = s.replace(".", "")  # 1.234.567 o 45.000 (miles estilo COP)
    n = float(s)
    return -n if negativo else n


def detectar_orden_fecha(valores: list[str], moneda: str) -> str:
    for v in valores:
        m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", v.strip())
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > 12:
                return "DMY"
            if b > 12:
                return "MDY"
    return "MDY" if moneda == "USD" else "DMY"


def parse_fecha(valor: object, orden: str) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        d, mth = (a, b) if orden == "DMY" else (b, a)
        return date(y, mth, d)
    for fmt in ("%d %b %Y", "%b %d, %Y", "%d-%b-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- normalización

def normalizar(filas, moneda: str, signo: str) -> tuple[list[dict], list[str]]:
    idx, cols = encontrar_encabezado(filas)
    datos = [f for f in filas[idx + 1:] if any(c not in (None, "") for c in f)]
    avisos: list[str] = []

    def celda(f, key):
        j = cols.get(key)
        return f[j] if j is not None and j < len(f) else None

    orden = detectar_orden_fecha([str(celda(f, "fecha") or "") for f in datos], moneda)

    crudos = []
    for n, f in enumerate(datos, start=idx + 2):
        fecha = parse_fecha(celda(f, "fecha"), orden)
        if fecha is None:
            continue  # filas de totales, saldos, pies de página
        if "monto" in cols:
            valor = parse_numero(celda(f, "monto"))
        else:
            deb = parse_numero(celda(f, "debito")) or 0.0
            cre = parse_numero(celda(f, "credito")) or 0.0
            valor = abs(cre) - abs(deb)  # convención: negativo = salida de dinero
        if valor is None or valor == 0:
            continue
        desc = str(celda(f, "desc") or "").strip() or "(sin descripción)"
        crudos.append((fecha, desc, valor, n))

    if "monto" in cols and signo == "auto":
        negativos = sum(1 for c in crudos if c[2] < 0)
        signo = "gasto-negativo" if negativos >= len(crudos) / 2 else "gasto-positivo"
        avisos.append(f"Convención de signo detectada: {signo} "
                      f"({negativos} de {len(crudos)} valores negativos). Confírmala con el usuario.")
    elif "monto" not in cols:
        signo = "gasto-negativo"
    avisos.append(f"Orden de fecha usado: {orden}.")

    movimientos = []
    for fecha, desc, valor, n in crudos:
        es_gasto = valor < 0 if signo == "gasto-negativo" else valor > 0
        movimientos.append({
            "fecha": fecha.isoformat(),
            "descripcion": re.sub(r"\s+", " ", desc),
            "monto": round(abs(valor), 2),
            "tipo": "Gasto" if es_gasto else "Ingreso",
            "moneda": moneda,
            "fila": n,
        })
    return movimientos, avisos


def marcar_duplicados(movs: list[dict], existentes: list[dict]) -> int:
    indice = []
    for e in existentes:
        f = e.get("date:Fecha:start") or e.get("fecha")
        if not f or e.get("Monto") is None and e.get("monto") is None:
            continue
        indice.append((date.fromisoformat(f[:10]),
                       round(float(e.get("Monto", e.get("monto"))), 2),
                       e.get("Moneda", e.get("moneda")),
                       e.get("url") or e.get("Comercio") or ""))
    usados: set[int] = set()
    total = 0
    for m in movs:
        f = date.fromisoformat(m["fecha"])
        for k, (fe, monto, mon, ref) in enumerate(indice):
            if k in usados or mon != m["moneda"] or monto != m["monto"]:
                continue
            if abs((fe - f).days) <= 1:
                m["duplicado_de"] = ref
                usados.add(k)
                total += 1
                break
    return total


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("archivo", type=Path)
    p.add_argument("--moneda", default="COP", choices=["COP", "USD", "EUR"])
    p.add_argument("--signo", default="auto", choices=["auto", "gasto-negativo", "gasto-positivo"],
                   help="Cómo representa el banco los gastos cuando hay una sola columna de monto")
    p.add_argument("--existentes", type=Path,
                   help="JSON con filas de Notion (lista, o {'results': [...]}) para detectar duplicados")
    a = p.parse_args(argv)

    movs, avisos = normalizar(leer_filas(a.archivo), a.moneda, a.signo)
    if a.existentes:
        ex = json.loads(a.existentes.read_text())
        ex = ex.get("results", ex) if isinstance(ex, dict) else ex
        n = marcar_duplicados(movs, ex)
        avisos.append(f"{n} posibles duplicados frente a Notion.")
    json.dump({"movimientos": movs, "avisos": avisos}, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
