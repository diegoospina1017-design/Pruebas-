# Amazon Arbitrage Toolkit

Herramientas para arrancar tu negocio de retail/online arbitrage en Amazon FBA desde Christiansburg, VA.

## Estructura

```
amazon-arbitrage/
├── calculator/          Calculadora de rentabilidad en Python
│   ├── fees.py          Tarifas FBA y referral fees por categoría (2024-2025)
│   ├── shipping.py      Estimador de envío desde ZIP 24073 a hubs FBA
│   └── profit.py        Calculadora principal (corre este archivo)
├── tracker/             Plantilla de inventario
│   ├── inventory_tracker.csv    Importar a Google Sheets o Excel
│   └── README_TRACKER.md        Guía de uso de cada columna
└── docs/
    └── scouting_rules.md        Manual de qué buscar y qué evitar
```

## Quick start

### 1. Probar la calculadora
```bash
cd amazon-arbitrage/calculator
python3 profit.py
```
Verás 3 ejemplos (uno SKIP, dos BUY). Al final pregunta si quieres entrar en modo interactivo para calcular tu propio producto.

### 2. Usar el tracker
- Sube `tracker/inventory_tracker.csv` a Google Sheets
- File → Import → Replace spreadsheet
- Lee `tracker/README_TRACKER.md` para entender cada columna

### 3. Leer las reglas de scouting
Abre `docs/scouting_rules.md` antes de ir a Walmart/Target. Llévalo en el celular.

## Próximos pasos

1. **Esta semana**: abre cuenta Amazon Seller Professional, instala Amazon Seller App
2. **Semanas 2-4**: scouting físico + primeras compras (usa la calculadora antes de pagar)
3. **Mes 2**: envía a FBA, llena el tracker con datos reales
4. **Mes 3**: cuando tengas 20-50 SKUs vendidos, construimos el agente automatizado

## Notas importantes

- Las tarifas FBA cambian cada enero. Actualiza `fees.py` con las nuevas rates del año.
- Sales tax de Virginia: 5.3% base + 0.7% local en Montgomery County = 6.0% (verifica el actual cuando compres)
- Amazon NO permite usar Walmart+ como cuenta de revendedor en algunos casos - lee los ToS de Walmart
