#!/usr/bin/env python3
"""Calcula el resumen financiero de un mes a partir de filas exportadas de Notion.

Uso:
    python3 finanzas/scripts/resumen.py --movimientos movs.json \
        [--presupuestos presupuestos.json] [--mes 2026-11] [--hoy 2026-11-15] [--json]

`movs.json` / `presupuestos.json` son los `results` de `notion-query-data-sources`
en modo view (una lista, o un objeto con clave "results"; también vale una lista de páginas
concatenadas).

Reglas:
- Tipo vacío = Gasto. Tipo "Transferencia" no cuenta ni como gasto ni como ingreso.
- Nunca mezcla monedas: todos los totales van por moneda.
- Estado del presupuesto: OK (<80 %), ALERTA (80–99 %), EXCEDIDO (>=100 %).
- Si el mes es el mes en curso, proyecta el gasto a fin de mes al ritmo actual.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ALERTA, EXCEDIDO = 0.80, 1.00


def cargar(ruta: Path | None) -> list[dict]:
    if not ruta:
        return []
    data = json.loads(ruta.read_text())
    if isinstance(data, dict):
        data = data.get("results", [])
    filas: list[dict] = []
    for item in data:  # admite lista de páginas [{results: [...]}, ...]
        if isinstance(item, dict) and "results" in item and "Monto" not in item:
            filas.extend(item["results"])
        else:
            filas.append(item)
    return filas


def mes_de(fila: dict) -> str | None:
    f = fila.get("date:Fecha:start") or ""
    return f[:7] or None


def mes_anterior(mes: str) -> str:
    y, m = map(int, mes.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def tipo(fila: dict) -> str:
    return fila.get("Tipo") or "Gasto"


def agregar(filas: list[dict], mes: str):
    gastos = defaultdict(lambda: defaultdict(float))   # moneda -> categoría -> total
    ingresos = defaultdict(float)                       # moneda -> total
    comercios = defaultdict(lambda: defaultdict(float))
    sin_categoria = 0
    for f in filas:
        if mes_de(f) != mes or f.get("Monto") is None:
            continue
        mon = f.get("Moneda") or "¿?"
        monto = abs(float(f["Monto"]))
        t = tipo(f)
        if t == "Ingreso":
            ingresos[mon] += monto
        elif t == "Gasto":
            cat = f.get("Categoría") or "Otros"
            if cat == "Otros":
                sin_categoria += 1
            gastos[mon][cat] += monto
            comercios[mon][f.get("Comercio") or "(sin nombre)"] += monto
    return gastos, ingresos, comercios, sin_categoria


PAGO_TARJETA = re.compile(
    r"card (online )?payment|pymt|payment thank|pago (de )?tarjeta|pago (online|en l[ií]nea)|"
    r"applecard|apple card|syf pay|pago syf|autopay|abono a tarjeta", re.I)


def revisar_calidad(filas: list[dict], mes: str) -> dict:
    """Señala filas del mes que probablemente distorsionan el reporte."""
    del_mes = [f for f in filas if mes_de(f) == mes and tipo(f) == "Gasto"]
    sin_monto = [f.get("url") for f in del_mes if f.get("Monto") in (None, "")]
    pagos = [{"comercio": f.get("Comercio"), "monto": f.get("Monto"), "url": f.get("url")}
             for f in del_mes if PAGO_TARJETA.search(str(f.get("Comercio") or ""))]
    con_monto = sorted((f for f in del_mes if f.get("Monto")), key=lambda f: f["date:Fecha:start"])
    duplicados, usados = [], set()
    for i, a in enumerate(con_monto):
        if i in usados:
            continue
        fa = date.fromisoformat(a["date:Fecha:start"][:10])
        for j in range(i + 1, len(con_monto)):
            b = con_monto[j]
            if (date.fromisoformat(b["date:Fecha:start"][:10]) - fa).days > 1:
                break
            if j not in usados and b.get("Moneda") == a.get("Moneda") and float(b["Monto"]) == float(a["Monto"]):
                usados.update((i, j))
                duplicados.append({"monto": a["Monto"], "moneda": a.get("Moneda"),
                                   "filas": [{"comercio": x.get("Comercio"), "fecha": x["date:Fecha:start"],
                                              "url": x.get("url")} for x in (a, b)]})
                break
    return {"posibles_duplicados": duplicados, "posibles_pagos_de_tarjeta": pagos,
            "gastos_sin_monto": sin_monto}


def resumen(movs: list[dict], presupuestos: list[dict], mes: str, hoy: date) -> dict:
    gastos, ingresos, comercios, sin_cat = agregar(movs, mes)
    g_prev, _, _, _ = agregar(movs, mes_anterior(mes))

    y, m = map(int, mes.split("-"))
    dias_mes = calendar.monthrange(y, m)[1]
    en_curso = (hoy.year, hoy.month) == (y, m)
    factor = dias_mes / hoy.day if en_curso else 1.0

    pres = {}
    for p in presupuestos:
        lim = p.get("Presupuesto mensual")
        if lim:
            pres[(p.get("Moneda") or "COP", p.get("Categoría"))] = float(lim)

    monedas = sorted(set(gastos) | set(ingresos) | {k[0] for k in pres})
    out = {"mes": mes, "en_curso": en_curso, "dia": hoy.day if en_curso else dias_mes,
           "dias_mes": dias_mes, "movimientos_en_otros": sin_cat,
           "calidad": revisar_calidad(movs, mes), "monedas": {}}
    for mon in monedas:
        total_g = sum(gastos[mon].values())
        total_i = ingresos.get(mon, 0.0)
        cats = []
        for cat in sorted(set(gastos[mon]) | {c for (mm, c) in pres if mm == mon},
                          key=lambda c: -gastos[mon].get(c, 0)):
            gastado = gastos[mon].get(cat, 0.0)
            lim = pres.get((mon, cat))
            fila = {"categoria": cat, "gastado": round(gastado, 2),
                    "mes_anterior": round(g_prev[mon].get(cat, 0.0), 2)}
            if lim:
                uso = gastado / lim
                fila.update(presupuesto=lim, uso=round(uso, 3), restante=round(lim - gastado, 2),
                            estado="EXCEDIDO" if uso >= EXCEDIDO else "ALERTA" if uso >= ALERTA else "OK")
                if en_curso:
                    proy = gastado * factor
                    fila["proyeccion"] = round(proy, 2)
                    fila["se_excedera"] = proy > lim
            cats.append(fila)
        out["monedas"][mon] = {
            "ingresos": round(total_i, 2),
            "gastos": round(total_g, 2),
            "neto": round(total_i - total_g, 2),
            "tasa_ahorro": round((total_i - total_g) / total_i, 3) if total_i else None,
            "gastos_mes_anterior": round(sum(g_prev[mon].values()), 2),
            "proyeccion_gastos": round(total_g * factor, 2) if en_curso else None,
            "categorias": cats,
            "top_comercios": [{"comercio": c, "total": round(v, 2)} for c, v in
                              sorted(comercios[mon].items(), key=lambda kv: -kv[1])[:5]],
        }
    return out


def fmt(n: float | None, mon: str) -> str:
    if n is None:
        return "—"
    signo, n = ("-" if n < 0 else ""), abs(n)
    if mon == "COP":
        return signo + "$" + f"{n:,.0f}".replace(",", ".")
    return f"{signo}{'€' if mon == 'EUR' else 'US$'}{n:,.2f}"


def a_markdown(r: dict) -> str:
    icon = {"OK": "🟢", "ALERTA": "🟡", "EXCEDIDO": "🔴"}
    lineas = [f"## Resumen {r['mes']}" + (f" (día {r['dia']} de {r['dias_mes']})" if r["en_curso"] else "")]
    if not r["monedas"]:
        lineas.append("\nSin movimientos en este mes.")
    for mon, d in r["monedas"].items():
        lineas += ["", f"### {mon}",
                   f"- Ingresos: **{fmt(d['ingresos'], mon)}**",
                   f"- Gastos: **{fmt(d['gastos'], mon)}** (mes anterior: {fmt(d['gastos_mes_anterior'], mon)})",
                   f"- Neto: **{fmt(d['neto'], mon)}**"
                   + (f" · tasa de ahorro {d['tasa_ahorro']:.0%}" if d["tasa_ahorro"] is not None else "")]
        if d["proyeccion_gastos"] is not None:
            lineas.append(f"- Proyección de gasto a fin de mes: {fmt(d['proyeccion_gastos'], mon)}")
        lineas += ["", "| Categoría | Gastado | Presupuesto | Uso | Mes anterior |", "|---|---:|---:|---:|---:|"]
        for c in d["categorias"]:
            uso = f"{icon[c['estado']]} {c['uso']:.0%}" if "estado" in c else "—"
            if c.get("se_excedera") and c.get("estado") != "EXCEDIDO":
                uso += " ⚠️ proyección"
            lineas.append(f"| {c['categoria']} | {fmt(c['gastado'], mon)} | {fmt(c.get('presupuesto'), mon)} "
                          f"| {uso} | {fmt(c['mes_anterior'], mon)} |")
        if d["top_comercios"]:
            lineas += ["", "Top comercios: " + ", ".join(f"{t['comercio']} ({fmt(t['total'], mon)})"
                                                          for t in d["top_comercios"])]
    q = r["calidad"]
    if q["posibles_duplicados"] or q["posibles_pagos_de_tarjeta"] or q["gastos_sin_monto"]:
        lineas += ["", "### ⚠️ Revisar antes de confiar en los totales"]
        for d in q["posibles_duplicados"]:
            a, b = d["filas"]
            lineas.append(f"- Posible duplicado {fmt(d['monto'], d['moneda'] or 'USD')}: "
                          f"«{a['comercio']}» ({a['fecha']}) y «{b['comercio']}» ({b['fecha']})")
        for p_ in q["posibles_pagos_de_tarjeta"]:
            lineas.append(f"- «{p_['comercio']}» ({p_['monto']}) parece pago de tarjeta: debería ser Transferencia")
        if q["gastos_sin_monto"]:
            lineas.append(f"- {len(q['gastos_sin_monto'])} gastos sin monto")
    if r["movimientos_en_otros"]:
        lineas += ["", f"ℹ️ {r['movimientos_en_otros']} gastos están en la categoría «Otros»; "
                       "recategorizarlos mejora el reporte."]
    return "\n".join(lineas)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--movimientos", type=Path, required=True)
    p.add_argument("--presupuestos", type=Path)
    p.add_argument("--mes", help="YYYY-MM (por defecto, el mes de --hoy)")
    p.add_argument("--hoy", type=date.fromisoformat, default=date.today())
    p.add_argument("--json", action="store_true", help="Salida JSON en lugar de Markdown")
    a = p.parse_args(argv)
    mes = a.mes or a.hoy.strftime("%Y-%m")
    r = resumen(cargar(a.movimientos), cargar(a.presupuestos), mes, a.hoy)
    if a.json:
        json.dump(r, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(a_markdown(r))


if __name__ == "__main__":
    main()
