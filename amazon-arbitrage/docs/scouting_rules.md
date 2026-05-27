# Manual de Scouting - Reglas para evaluar productos

## El proceso completo en 30 segundos

1. Encuentras un producto con descuento (físico o online)
2. Lo escaneas con **Amazon Seller App** (código de barras)
3. La app te muestra: precio en Amazon, fees, BSR, restricciones
4. Aplicas las **5 reglas de oro** (abajo)
5. Si pasa las 5 → compras
6. Si falla alguna → siguiente producto

---

## Las 5 reglas de oro (todas deben cumplirse)

### Regla 1: Ganancia neta mínima $3 / ROI mínimo 30%
- Usa la calculadora del proyecto (`amazon-arbitrage/calculator/profit.py`)
- Por debajo de $3 de ganancia neta, una sola devolución te come 2 ventas
- ROI <30% no compensa el capital amarrado

### Regla 2: BSR < 100,000 en categoría principal
- BSR = Best Seller Rank. Lo ves en la página del producto en Amazon, o en Keepa
- Más bajo = vende más rápido
- Guía rápida por categoría (rangos donde vende ~1-3 unidades/día):
  - Toys & Games: BSR < 50,000
  - Home & Kitchen: BSR < 100,000
  - Beauty: BSR < 80,000
  - Sports & Outdoors: BSR < 80,000
  - Electronics: BSR < 30,000 (categoría muy competida)
- **Usa Keepa**: te muestra el BSR promedio de los últimos 90 días, no el actual (puede estar engañado por una venta reciente)

### Regla 3: No estar restringido para tu cuenta
- La Amazon Seller App te dice si la marca/producto está "restricted" o "gated"
- Cuentas nuevas tienen ~30% de marcas bloqueadas hasta que construyan historial
- **Marcas comúnmente gated** que debes evitar al inicio: Nike, Disney, Apple, LEGO, Funko, Adidas, Sony, Samsung
- **Categorías gated** al inicio: Beauty (algunas marcas), Grocery, Health, Automotive

### Regla 4: Competencia razonable
- En la página del producto baja a "Other sellers on Amazon"
- **<10 vendedores FBA** = buen escenario (te rotará el BuyBox)
- **>20 vendedores FBA** = guerra de precios, te van a undercutting hasta perder margen
- **Si Amazon mismo vende** (Sold by Amazon): SKIP, no compites contra ellos
- **Si solo 1-2 vendedores**: cuidado, puede haber restricción de marca escondida

### Regla 5: Estabilidad de precio (Keepa)
- En el gráfico de Keepa, el precio de los últimos 90 días debe ser **estable o creciente**
- Patrones que indican SKIP:
  - Precio que cae constantemente
  - Picos altos con valles bajos (volatilidad)
  - BSR que se ha disparado en últimos 30 días (demanda muriendo)
- Patrón que indica BUY:
  - Precio horizontal o ligero crecimiento
  - BSR estable o mejorando

---

## Filtros adicionales para principiantes

### Tamaño y peso
- **Sweet spot inicial**: < 1 lb y < 12 x 9 x 4 pulgadas (Small Standard size)
- Por qué: FBA fees más bajos ($3.06-$4.75) y storage barato
- Evita oversize hasta que tengas experiencia (fees pueden ser $9-50)

### Precio de venta
- **Inicio**: $15 - $40 en Amazon
- < $15: márgenes muy delgados, no compensan fees fijos
- > $40: capital amarrado por unidad, más riesgo de devolución cara

### Frágil / líquido / batería
- **SKIP al inicio**: cristal, cerámica, perfumes, productos con baterías de litio
- Razón: requieren prep especial, mayor tasa de devoluciones, restricciones de envío

### Fecha de expiración
- Solo aplica grocery/beauty/health/supplements
- **Regla Amazon**: debe tener >90 días de vida útil cuando llega a FBA
- Más fácil ignorar estas categorías al inicio

---

## Dónde buscar (Christiansburg, VA y alrededores)

### Físico (retail arbitrage)
| Tienda | Cuándo ir | Qué buscar |
|---|---|---|
| **Walmart (460 N Franklin St)** | Martes/jueves AM | Pasillos de clearance (etiquetas amarillas), end caps con descuentos rojos |
| **Target (Christiansburg)** | Lunes (markdowns nuevos) | Clearance con etiquetas terminadas en .X8 o .X4 = 70% off coming soon |
| **TJ Maxx / Marshalls / HomeGoods** | Cualquier día | Marcas de calidad a precios bajos, pero verifica restricciones |
| **Ross** | Miércoles | Hogar y juguetes a precios muy bajos |
| **Big Lots** | Fines de semana | Clearance al final de la tienda |
| **Dollar Tree / Dollar General** | Cualquier día | Multi-pack arbitrage (compras pack y vendes individual) |
| **CVS / Walgreens** | Después de Halloween/Navidad/Pascua | Liquidación seasonal 75-90% off |

### Online (online arbitrage)
| Sitio | Para qué |
|---|---|
| **Walmart.com** | Clearance section + envío gratis $35+ |
| **Target.com** | RedCard te da 5% off extra |
| **Kohls.com** | Combos de cupones + Kohls Cash = descuentos brutales |
| **Slickdeals.net** | Comunidad que postea las mejores ofertas en tiempo real |
| **BrickSeek.com** | Te muestra inventario y precios clearance en Walmart/Target locales |
| **Camelcamelcamel.com** | Historial precios Amazon (gratis, alternativa a Keepa) |

---

## Banderas rojas - SKIP inmediato

- Producto con review promedio < 4.0 estrellas → tasa de devolución alta
- Reviews recientes negativos mencionando "broken", "fake", "not as described"
- Producto con menos de 50 reviews totales → demanda no validada
- Marca privada de Amazon (AmazonBasics, Solimo, Pinzon, etc.) → no compites
- Tiene "Climate Pledge Friendly" o badge especial que tú no puedes obtener
- Listing mal hecho (sin imágenes buenas, sin bullets) → probablemente vendedor único protegiendo monopolio
- El producto tiene un knockoff/falsificación común en mercado → Amazon te puede suspender por queja de marca

---

## Plantilla mental antes de comprar

```
[ ] Escaneé con Amazon Seller App
[ ] Ganancia neta > $3 (calculator)
[ ] ROI > 30% (calculator)
[ ] BSR < 100,000 (Keepa 90-day avg)
[ ] No restricted en mi cuenta
[ ] < 20 vendedores FBA
[ ] Amazon no es vendedor
[ ] Precio Keepa estable últimos 90 días
[ ] Tamaño Small/Standard
[ ] Sin batería / frágil / vencimiento
[ ] Reviews > 4.0 estrellas
[ ] No es marca AmazonBasics
```

**Si los 12 checkmarks están: COMPRA.**
**Si falta uno: SKIP. Habrá otro producto.**

---

## Errores típicos del primer mes

1. **Comprar emocionalmente**: ves una "ganga" y compras sin calcular. Siempre pasa por la calculadora.
2. **Ignorar storage fees Q4**: en Oct-Dec las storage fees se triplican. Productos lentos te queman dinero.
3. **No verificar restricciones antes de comprar**: te quedas con inventario que no puedes vender.
4. **Comprar producto único en vez de multipack**: el inbound shipping cost por unidad mata el margen. Compra siempre en cantidad (mínimo 12-24 unidades del mismo SKU).
5. **No documentar en el tracker**: a los 2 meses no sabes qué se vendió bien ni por qué.
6. **Confiar en BSR actual sin Keepa**: el BSR salta segundo a segundo. Solo el promedio 90 días te dice si hay demanda real.

---

## Próximo paso después de 20-50 ventas

Cuando hayas vendido 20-50 SKUs con datos reales en el tracker, regresa al asistente para construir el **agente cazador automatizado** con tus reglas refinadas. La diferencia entre las reglas genéricas de este manual y tus reglas reales basadas en datos es donde está el margen competitivo.
