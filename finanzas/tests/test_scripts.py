"""Pruebas de los scripts de finanzas. Ejecutar: python3 -m unittest discover finanzas/tests"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import parse_extracto as pe  # noqa: E402
import resumen as rs  # noqa: E402


class ParseNumero(unittest.TestCase):
    def test_formatos(self):
        casos = {
            "$1.234.567,89": 1234567.89, "1,234.56": 1234.56, "45.000": 45000.0,
            "12,5": 12.5, "(45.00)": -45.0, "-45.00": -45.0, "1,234": 1234.0,
            "45.00 DB": -45.0, "45.00 CR": 45.0, 30: 30.0, "": None,
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(pe.parse_numero(entrada), esperado)


class ParseFecha(unittest.TestCase):
    def test_orden(self):
        self.assertEqual(pe.detectar_orden_fecha(["25/10/2026"], "USD"), "DMY")
        self.assertEqual(pe.detectar_orden_fecha(["10/25/2026"], "COP"), "MDY")
        self.assertEqual(pe.detectar_orden_fecha(["01/02/2026"], "COP"), "DMY")
        self.assertEqual(pe.parse_fecha("01/02/26", "DMY"), date(2026, 2, 1))
        self.assertEqual(pe.parse_fecha("2026-11-03", "DMY"), date(2026, 11, 3))


class Normalizar(unittest.TestCase):
    def _csv(self, texto):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(texto)
        f.close()
        return pe.leer_filas(Path(f.name))

    def test_banco_colombiano_debito_credito_con_preambulo(self):
        filas = self._csv(
            "Bancolombia;Extracto\nCuenta;1234\n\n"
            "Fecha;Descripción;Valor Débito;Valor Crédito;Saldo\n"
            "03/11/2026;ÉXITO CALLE 80;125.400,00;;1.000.000\n"
            "15/11/2026;NOMINA EMPRESA;;4.500.000,00;5.000.000\n"
            "Total;;125.400,00;4.500.000,00;\n")
        movs, _ = pe.normalizar(filas, "COP", "auto")
        self.assertEqual(len(movs), 2)
        self.assertEqual(movs[0], {"fecha": "2026-11-03", "descripcion": "ÉXITO CALLE 80",
                                   "monto": 125400.0, "tipo": "Gasto", "moneda": "COP", "fila": 5})
        self.assertEqual(movs[1]["tipo"], "Ingreso")
        self.assertEqual(movs[1]["monto"], 4500000.0)

    def test_tarjeta_usa_gastos_positivos(self):
        filas = self._csv("Date,Description,Amount\n11/10/2026,AMAZON,47.39\n"
                          "11/12/2026,UBER,21.04\n11/13/2026,PAYMENT THANK YOU,-500.00\n")
        movs, avisos = pe.normalizar(filas, "USD", "auto")
        self.assertEqual([m["tipo"] for m in movs], ["Gasto", "Gasto", "Ingreso"])
        self.assertEqual(movs[0]["fecha"], "2026-11-10")
        self.assertTrue(any("gasto-positivo" in a for a in avisos))

    def test_duplicados(self):
        movs = [{"fecha": "2026-11-10", "monto": 47.39, "moneda": "USD"},
                {"fecha": "2026-11-10", "monto": 47.39, "moneda": "USD"},
                {"fecha": "2026-11-20", "monto": 47.39, "moneda": "USD"}]
        existentes = [{"date:Fecha:start": "2026-11-11", "Monto": 47.39, "Moneda": "USD", "url": "u1"}]
        self.assertEqual(pe.marcar_duplicados(movs, existentes), 1)
        self.assertEqual(movs[0]["duplicado_de"], "u1")
        self.assertNotIn("duplicado_de", movs[1])  # cada fila existente se usa una vez


class Resumen(unittest.TestCase):
    MOVS = [
        {"Comercio": "Éxito", "Monto": 300000, "Moneda": "COP", "Categoría": "Alimentación",
         "date:Fecha:start": "2026-11-05"},
        {"Comercio": "Nómina", "Monto": 4000000, "Moneda": "COP", "Tipo": "Ingreso",
         "Categoría": "Salario", "date:Fecha:start": "2026-11-01"},
        {"Comercio": "Pago tarjeta", "Monto": 999999, "Moneda": "COP", "Tipo": "Transferencia",
         "date:Fecha:start": "2026-11-02"},
        {"Comercio": "Amazon", "Monto": 47.39, "Moneda": "USD", "Categoría": "Compras",
         "Tipo": "Gasto", "date:Fecha:start": "2026-11-14"},
        {"Comercio": "Éxito", "Monto": 200000, "Moneda": "COP", "Categoría": "Alimentación",
         "date:Fecha:start": "2026-10-20"},
    ]
    PRES = [{"Categoría": "Alimentación", "Moneda": "COP", "Presupuesto mensual": 350000},
            {"Categoría": "Transporte", "Moneda": "COP", "Presupuesto mensual": 200000}]

    def test_totales_por_moneda_y_estados(self):
        r = rs.resumen(self.MOVS, self.PRES, "2026-11", date(2026, 11, 15))
        cop, usd = r["monedas"]["COP"], r["monedas"]["USD"]
        self.assertEqual(cop["ingresos"], 4000000)
        self.assertEqual(cop["gastos"], 300000)  # transferencia excluida
        self.assertEqual(usd["gastos"], 47.39)    # sin mezclar monedas
        ali = next(c for c in cop["categorias"] if c["categoria"] == "Alimentación")
        self.assertEqual(ali["estado"], "ALERTA")  # 300k / 350k = 86 %
        self.assertEqual(ali["mes_anterior"], 200000)
        self.assertEqual(ali["proyeccion"], 600000)  # 30 días / día 15
        self.assertTrue(ali["se_excedera"])
        tra = next(c for c in cop["categorias"] if c["categoria"] == "Transporte")
        self.assertEqual((tra["gastado"], tra["estado"]), (0.0, "OK"))

    def test_markdown_y_carga_paginada(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            p.write_text(json.dumps([{"results": self.MOVS[:2]}, {"results": self.MOVS[2:]}]))
            self.assertEqual(len(rs.cargar(p)), 5)
        md = rs.a_markdown(rs.resumen(self.MOVS, self.PRES, "2026-11", date(2026, 11, 15)))
        self.assertIn("$300.000", md)
        self.assertIn("US$47.39", md)

    def test_calidad_duplicados_y_pagos_de_tarjeta(self):
        movs = [
            {"Comercio": "WALMART", "Monto": 156.45, "Moneda": "USD", "date:Fecha:start": "2026-10-05", "url": "a"},
            {"Comercio": "Desconocido Citi", "Monto": 156.45, "Moneda": "USD", "date:Fecha:start": "2026-10-05", "url": "b"},
            {"Comercio": "ATM 10/13", "Monto": 1000, "Moneda": "USD", "date:Fecha:start": "2026-10-13"},
            {"Comercio": "ATM 10/15", "Monto": 1000, "Moneda": "USD", "date:Fecha:start": "2026-10-15"},
            {"Comercio": "CITI CARD ONLINE PAYMENT", "Monto": 876.02, "Moneda": "USD", "date:Fecha:start": "2026-10-20"},
            {"Comercio": "Pago SYF", "Monto": 1, "Moneda": "USD", "Tipo": "Transferencia", "date:Fecha:start": "2026-10-20"},
            {"Comercio": "Amazon", "Moneda": "USD", "date:Fecha:start": "2026-10-18", "url": "c"},
        ]
        q = rs.revisar_calidad(movs, "2026-10")
        self.assertEqual(len(q["posibles_duplicados"]), 1)  # ATM a 2 días no cuenta
        self.assertEqual([x["url"] for x in q["posibles_duplicados"][0]["filas"]], ["a", "b"])
        self.assertEqual([p["comercio"] for p in q["posibles_pagos_de_tarjeta"]], ["CITI CARD ONLINE PAYMENT"])
        self.assertEqual(q["gastos_sin_monto"], ["c"])
        self.assertEqual(rs.fmt(-13233.19, "USD"), "-US$13,233.19")
        self.assertEqual(rs.fmt(-50000, "COP"), "-$50.000")


if __name__ == "__main__":
    unittest.main()
