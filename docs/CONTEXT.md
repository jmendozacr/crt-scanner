# CRT Scanner — Contexto del Proyecto

## Qué es esto
Scanner automático de la estrategia **CRT (Candle Range Theory)** para Forex.
Detecta patrones CRT válidos en H4, los filtra con Key Levels del Diario,
espera confirmación de entrada en M15 y dispara una alerta a Telegram.

Fuente de datos: **OANDA API** (gratis, streaming real-time).
Stack: **Python 3.11+ · asyncio · aiohttp · pandas · python-telegram-bot**.

---

## La estrategia (lógica de negocio — leer antes de codificar)

### Qué es un CRT
Cada vela representa un rango con un High (CRT H) y un Low (CRT L).
Cuando el precio barre el High o el Low de una vela previa y la vela que
hace el barrido CIERRA (no solo toca), se forma un CRT válido.
La expectativa es que el precio viaje hacia el extremo opuesto.

**Regla crítica**: la vela que barre la liquidez debe estar CERRADA.
Un barrido en progreso (vela aún abierta) NO es CRT válido.

### Los 4 modelos CRT (todos deben detectarse)
| Modelo | Descripción |
|--------|-------------|
| 2 Candle CRT | Vela 1 = rango de referencia. Vela 2 barre y cierra dentro. |
| 3 Candle CRT | Vela 1 = rango. Vela 2 = manipulación (barre). Vela 3 = distribución. |
| Multiple Candle CRT | Varias velas barren antes de cerrar el rango. |
| Inside Bar CRT | La vela barrida está completamente dentro del rango previo. |

### Power of 3 (contexto de la vela)
- Vela 1: Acumulación
- Vela 2: Manipulación (el barrido ocurre aquí)
- Vela 3: Distribución (el movimiento real)

### Dirección del CRT
- **Bearish CRT**: barre el HIGH de la vela de referencia → esperar caída al LOW
- **Bullish CRT**: barre el LOW de la vela de referencia → esperar subida al HIGH

---

## Flujo de señal — 3 temporalidades

```
[DIARIO]  Key Level activo (FVG / OB / Swing High-Low)
     |
     v  ¿el precio de H4 está tocando o cerca del Key Level diario?
     |
[H4]     CRT válido formado (vela cerrada, barrido confirmado)
     |
     v  ¿el modelo H4 coincide en dirección con el Key Level diario?
     |
[M15]    Modelo de entrada confirmado (OB, FVG, Breaker Block, Turtle Soup)
     |
     v
[ALERTA] Telegram con: par, dirección, score, tipo de CRT, entry zone
```

### Score de calidad
- **Score A**: los 3 TF alineados (Diario + H4 + M15 confirmado)
- **Score B**: Diario + H4 alineados, M15 aún no confirma (pre-alerta)

---

## Key Levels (lo que el scanner debe detectar en Diario)

### Fair Value Gap (FVG)
Desequilibrio entre 3 velas consecutivas:
- `FVG_high = vela[i-2].high`
- `FVG_low  = vela[i].low`
- Condición: `vela[i-2].high < vela[i].low` (bullish FVG)
- O: `vela[i-2].low > vela[i].high` (bearish FVG)

### Order Block (OB)
Última vela bearish antes de un movimiento alcista impulsivo (bullish OB),
o última vela bullish antes de un movimiento bajista impulsivo (bearish OB).
Zona definida por el high y low del cuerpo de esa vela.

### Swing Highs / Lows de alta temporalidad
Máximos y mínimos de las últimas N velas diarias que aún no han sido barridos.

---

## Modelos de entrada M15 (triggers de alerta final)

| Modelo | Lógica |
|--------|--------|
| Order Block M15 | Última vela opuesta antes del impulso en M15 |
| FVG M15 | Desequilibrio en M15 dentro de la zona del CRT H4 |
| Breaker Block | OB previo que fue roto y ahora actúa como soporte/resistencia |
| Turtle Soup (TWS) | Barrido del wick de un swing reciente en M15 |
| Turtle Soup (TBS) | Barrido del body de un swing reciente en M15 |

---

## Estructura de carpetas

```
crt-scanner/
├── core/
│   ├── crt_detector.py       # Detecta los 4 modelos CRT (usa velas cerradas)
│   ├── liquidity_sweeper.py  # Identifica barridos de High/Low
│   ├── power_of_3.py         # Clasifica fase de la vela (acum/manip/dist)
│   ├── fvg_detector.py       # Fair Value Gaps en cualquier TF
│   ├── ob_detector.py        # Order Blocks bullish y bearish
│   ├── htf_confluence.py     # Cruza CRT H4 con Key Level Diario
│   └── entry_models.py       # Modelos de entrada M15 (OB, FVG, TS, Breaker)
├── data/
│   ├── oanda_client.py       # Cliente async OANDA REST + streaming
│   └── candle_store.py       # Buffer de velas por par y TF (pandas)
├── output/
│   └── telegram_bot.py       # Envío de alertas formateadas
├── main.py                   # Entry point, asyncio loop, orquestación
├── config.py                 # Settings con pydantic-settings + .env
├── .env                      # OANDA_API_KEY, OANDA_ACCOUNT_ID, TELEGRAM_TOKEN, etc.
└── requirements.txt
```

---

## Pares Forex a escanear (configurable en .env)

```
PAIRS = EUR_USD, GBP_USD, USD_JPY, USD_CHF, AUD_USD, NZD_USD, USD_CAD, GBP_JPY, EUR_JPY
```

---

## Temporalidades y polling

| TF | Uso | Intervalo de polling |
|----|-----|----------------------|
| D (diario) | Key Levels de referencia | Cada cierre de vela diaria (00:00 UTC) |
| H4 | Detección CRT principal | Cada cierre de vela H4 (cada 4h) |
| M15 | Confirmación de entrada | Cada cierre de vela M15 (cada 15min) |

La lógica corre en un loop asyncio. No es necesario WebSocket para M15;
polling REST al cierre de cada vela es suficiente y más simple de mantener.

---

## Formato de alerta Telegram

```
🔔 CRT SIGNAL — Score A

Par:       EUR/USD
Dirección: BEARISH 🔻
TF CRT:    H4
Modelo:    3 Candle CRT
Key Level: FVG Diario (1.0842 – 1.0856)
Entrada M15: OB @ 1.0851
CRT H:     1.0871
CRT L:     1.0823 ← objetivo
Score:     A (3 TF alineados)
Hora UTC:  2025-03-26 16:15
```

---

## Dependencias (requirements.txt)

```
aiohttp>=3.9
pandas>=2.2
python-telegram-bot>=21.0
pydantic-settings>=2.0
python-dotenv>=1.0
numpy>=1.26
```

---

## Variables de entorno (.env)

```env
OANDA_API_KEY=your_oanda_api_key
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENV=practice          # o 'live'
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
PAIRS=EUR_USD,GBP_USD,USD_JPY,USD_CHF,AUD_USD
MIN_SCORE=A                 # A = solo alertas perfectas, B = incluye pre-alertas
CANDLE_BUFFER_SIZE=100      # Velas a mantener en memoria por par/TF
```

---

## Notas para Claude Code

1. **Empezar por Fase 1**: `config.py` + `oanda_client.py` + `candle_store.py`.
   Verificar que se obtienen velas históricas para D, H4, M15 de EUR_USD.

2. **Fase 2**: `crt_detector.py`. La función principal recibe un DataFrame de
   velas y retorna una lista de CRTSignal (dataclass) con: modelo, dirección,
   crt_high, crt_low, timestamp.

3. **Fase 3**: `fvg_detector.py` + `ob_detector.py` + `htf_confluence.py`.
   El confluencer recibe CRTSignal (H4) + key_levels (Diario) y retorna
   si hay confluencia y a qué nivel.

4. **Fase 4**: `entry_models.py` busca en M15 el trigger dentro de la zona CRT.

5. **Fase 5**: `telegram_bot.py` con el formato de alerta especificado arriba.

6. **main.py**: loop asyncio que cada 15 min llama al pipeline completo
   para cada par de PAIRS.

7. Usar `dataclasses` para todos los modelos internos (CRTSignal, KeyLevel,
   EntrySignal, Alert). Tipado estricto con type hints en todas las funciones.

8. Tests: pytest con velas sintéticas para cada módulo del core.
