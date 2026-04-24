# 📊 Will Street & Clutifx Scanner — Plan Maestro

> Documento de referencia para iniciar el proyecto en Claude Code.
> Basado en la estrategia completa del PDF de @LIAMCTD.

---

## 🎯 Objetivo

Construir un scanner en Python que detecte setups de trading basados en la estrategia Will Street & Clutifx (OB y FVG como modelos de entrada), con alertas en tiempo real vía Telegram.

---

## ⚙️ Stack Técnico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.10+ |
| API de datos | Twelve Data API (plan gratuito) |
| Alertas | Telegram Bot API |
| Ejecución | Local (máquina del usuario) |
| Cache | JSON local (para conservar requests) |

---

## 💱 Pares Monitoreados

- EUR/USD
- GBP/USD
- USD/CAD

### Correlaciones (para SMT informativo)
- EUR/USD ↔ GBP/USD → correlación **positiva**
- USD/CAD ↔ EUR/USD y GBP/USD → correlación **negativa**

---

## 🧠 Lógica de Detección (Flujo Completo)

### PASO 1 — Bias HTF via CRT (1D / 2D / 3D)

- Buscar un CRT (Candle Range Theory) completamente cerrado en 1D, 2D o 3D.
- El CRT puede ser de **2 o 3 velas**:
  - **3 velas:** Acumulación → Manipulación → Distribución
  - **2 velas:** La vela de manipulación también hace la distribución (cierra en dirección contraria al sweep)
- **Bias = dirección de la vela de distribución**
- Basta con que **uno** de los tres timeframes (1D, 2D o 3D) confirme el CRT.
- Si no hay CRT confirmado → el par se omite en ese ciclo.
- El **High o Low del CRT** que definió el bias se usa como **TP objetivo**.

```
Ejemplo Bias Alcista (CRT 1D):
  Vela 1 (acumulación): rango lateral
  Vela 2 (manipulación): barre el Low previo con mecha
  Vela 3 / misma vela 2 (distribución): cierra por encima del Open
  → Bias = COMPRA
  → TP = High del CRT
```

---

### PASO 2 — Turtle Soup en H4

- Buscar en la vela H4 cerrada más reciente:
  - ¿Barrió (con mecha o cierre) un **High o Low previo** de H4?
  - ¿El **cierre** de esa vela H4 es en **dirección contraria** al sweep?
- Si sí → **TS confirmado**
- Registrar la **ventana temporal**: desde el open de esa vela H4 hasta +4 horas.
- Solo procesar la búsqueda de OB/FVG **dentro de esa ventana**.
- El TS debe estar **alineado con el Bias HTF**:
  - Bias alcista → TS debe barrer un Low (sweep de mínimos)
  - Bias bajista → TS debe barrer un High (sweep de máximos)

```
Ejemplo TS Alcista:
  Vela H4 de las 08:00:
    - Barre el Low de las últimas N velas H4
    - Cierra por encima del Low barrido
  → TS confirmado, ventana: 08:00 – 12:00 UTC
```

---

### PASO 3 — OB y FVG en M15 (dentro de ventana H4)

Solo se buscan setups M15 si hay un TS activo en H4.

#### Order Block (OB)
- Identificar la **última vela M15 de color contrario al bias** antes del impulso.
- Esa vela es el OB.
- Confirmar con una **vela envolvente M15 en dirección del bias** que siga al OB.
- El precio debe **retroceder al OB** para considerar entrada.

```
Ejemplo OB Alcista:
  Dentro de ventana H4:
    Vela M15 roja (bajista) → es el OB
    Siguiente vela M15 verde envuelve la roja → confirmación
    El precio retrocede al rango de la vela roja → zona de entrada
```

#### Fair Value Gap (FVG)
- Buscar entre **3 velas M15 consecutivas** un gap no cubierto:
  - Low de vela 1 > High de vela 3 (FVG bajista)
  - High de vela 1 < Low de vela 3 (FVG alcista)
- No se requiere tamaño mínimo en pips — basta con que el gap exista.
- La **zona de entrada es el rango del FVG** (o su mitad).

---

### PASO 4 — Parámetros de la Operación

| Parámetro | Valor |
|---|---|
| Entrada (OB) | Precio del Order Block (open/close de la vela OB) |
| Entrada (FVG) | Mitad del gap (50% del FVG) |
| Stop Loss | 12 pips desde la zona de entrada |
| Take Profit | High o Low del CRT que definió el Bias |
| R:R estimado | Calculado dinámicamente según distancia entrada–TP |

---

### PASO 5 — SMT Check (informativo, no filtra)

- Al momento de generar la alerta, revisar el par correlacionado:
  - EUR/USD: comparar con GBP/USD
  - GBP/USD: comparar con EUR/USD
  - USD/CAD: correlación inversa con EUR/USD
- Si hay **divergencia** (uno hace nuevo extremo y el otro no) → agregar nota en la alerta.
- No bloquea la alerta, solo informa.

---

### PASO 6 — Alerta Telegram

- Se dispara **una sola vez por setup**.
- No se repite hasta que se forme un nuevo TS en H4.
- El tracker de estado evita duplicados.

---

## 📱 Formato de Alerta Telegram

```
🔔 SETUP DETECTADO

Par: EUR/USD
Dirección: 🟢 COMPRA
Modelo: Order Block (OB)
TF Entrada: M15
Bias HTF: Alcista (CRT 1D confirmado)

Entrada: 1.08450
SL: 1.08330 (-12 pips)
TP: 1.09120 (High CRT 1D)
R:R estimado: 1:5.6

TS origen: H4 08:00 UTC
Ventana M15: 08:00 – 12:00 UTC

SMT: ⚠️ GBP/USD no confirmó nuevo Low
(divergencia informativa)

🕐 2024-01-15 09:30 UTC
```

---

## 📁 Arquitectura de Archivos

```
scanner/
├── config/
│   ├── settings.py       # API keys, Telegram token/chat_id, parámetros globales
│   └── pairs.py          # Lista de pares y sus correlaciones SMT
│
├── data/
│   ├── fetcher.py        # Requests a Twelve Data (M15, H4, 1D, 2D, 3D)
│   └── cache.py          # Cache JSON local para conservar requests diarios
│
├── detectors/
│   ├── crt_bias.py       # Detecta CRT en 1D/2D/3D → retorna bias + nivel TP
│   ├── turtle_soup.py    # Detecta TS en H4 → retorna ventana temporal
│   ├── ob_detector.py    # Busca OB en M15 dentro de ventana H4
│   ├── fvg_detector.py   # Busca FVG en M15 dentro de ventana H4
│   └── smt_checker.py    # Verifica divergencia SMT entre pares correlacionados
│
├── alerts/
│   ├── formatter.py      # Construye el mensaje de texto de la alerta
│   └── telegram.py       # Envía el mensaje al bot de Telegram
│
├── state/
│   └── tracker.py        # Registra setups ya alertados, evita duplicados
│
└── main.py               # Loop principal: orquesta todo el flujo cada 15 minutos
```

---

## 🔄 Gestión de Requests (Twelve Data Gratuito)

| Límite | Valor |
|---|---|
| Requests por minuto | 8 |
| Requests por día | 800 |

### Estrategia por ciclo (cada 15 minutos al cierre de vela M15)

```
Si NO hay TS activo:
  - 3 pares × 1D  = 3 requests  (bias CRT)
  - 3 pares × H4  = 3 requests  (TS check)
  Total: 6 requests por ciclo

Si HAY TS activo en algún par:
  - + 1 par × M15 = 1 request   (OB/FVG check)
  Total: 7 requests por ciclo

Ciclos por día: 96 (cada 15 min × 24h)
Requests máximos/día: 96 × 7 = 672 ✅ dentro del límite

Cache aplicado:
  - 1D: se refresca 1 vez cada 24h
  - 2D/3D: se refresca 1 vez cada 48h/72h
  - H4: se refresca cada 4h
  - M15: se refresca cada 15min (solo si hay TS activo)
```

---

## 🚀 Orden de Desarrollo en Claude Code

### Fase 1 — Infraestructura base
- `config/settings.py`
- `config/pairs.py`
- `data/fetcher.py`
- `data/cache.py`

### Fase 2 — Detectores (orden de prioridad)
1. `detectors/crt_bias.py` ← el más crítico, define todo lo demás
2. `detectors/turtle_soup.py`
3. `detectors/ob_detector.py`
4. `detectors/fvg_detector.py`
5. `detectors/smt_checker.py`

### Fase 3 — Alertas
- `alerts/formatter.py`
- `alerts/telegram.py`

### Fase 4 — Integración y estado
- `state/tracker.py`
- `main.py`

### Fase 5 — Pruebas con datos históricos
- Validar cada detector con datos reales antes de ir en vivo.
- Confirmar que los setups detectados corresponden a setups válidos de la estrategia.

---

## 📝 Checklist antes de iniciar en Claude Code

- [ ] Twelve Data API Key lista
- [ ] Telegram Bot creado con @BotFather
- [ ] Telegram Bot Token disponible
- [ ] Telegram Chat ID conocido
- [ ] Python 3.10+ instalado
- [ ] Entorno virtual preparado (`python -m venv venv`)

---

## 📚 Referencia de la Estrategia

### Definición CRT (Candle Range Theory)
- **Acumulación:** Vela de rango lateral o consolidación
- **Manipulación:** Vela que barre High o Low previo con mecha
- **Distribución:** Vela (o la misma de manipulación) que cierra en dirección contraria al sweep
- El CRT de 2 velas ocurre cuando la vela de manipulación también cierra como distribución

### Definición Turtle Soup (TS)
- El precio rompe un High/Low previo de H4 de forma engañosa
- La vela H4 cierra en dirección contraria a la ruptura
- Señal de reversión institucional (manipulación de liquidez)

### Definición Order Block (OB)
- Última vela de color contrario al bias antes del impulso que crea el TS
- Confirmada por una vela envolvente en dirección del bias en M15
- Zona de entrada: rango completo de la vela OB

### Definición Fair Value Gap (FVG)
- Gap entre High de vela 3 y Low de vela 1 (o viceversa) en 3 velas M15 consecutivas
- La vela 2 no cubre completamente ese espacio
- Zona de entrada: mitad del gap (50%)

### Stop Loss
- OB: 12 pips desde el extremo de la zona OB
- FVG: 12 pips desde el extremo del gap

### Take Profit
- High o Low del CRT que confirmó el Bias en HTF (1D/2D/3D)

### SMT (Smart Money Technique)
- Divergencia entre pares correlacionados
- Informativo: no filtra la alerta, se incluye como nota
