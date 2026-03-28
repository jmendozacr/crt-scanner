# CRT Scanner — Refactor a modelo Clutifx

## Contexto
El scanner CRT ya está construido y funcionando con Twelve Data.
Este documento guía el refactor para simplificar la lógica de detección
y reemplazar los modelos de entrada genéricos por el modelo Clutifx puro.

---

## Qué se conserva sin tocar

| Módulo | Razón |
|--------|-------|
| `data/twelvedata_client.py` | Conexión con Twelve Data funcionando |
| `data/candle_store.py` | Buffer de velas por par y TF |
| `core/htf_levels.py` | FVG, OB y Swing H/L en Diario/Semanal |
| `core/htf_confluence.py` | Verificación de confluencia HTF |
| `output/telegram_bot.py` | Bot de alertas |
| `config.py` | Settings y .env |

---

## Qué se reemplaza

| Módulo actual | Módulo nuevo | Cambio |
|---------------|--------------|--------|
| `core/crt_detector.py` | `core/crt_detector.py` | Reescribir completo — fuera los 4 modelos, dentro solo barrido H/L |
| `core/entry_models.py` | `core/entry_model.py` | Reemplazar por lógica Clutifx pura |
| `main.py` | `main.py` | Ajustar loop para manejar `expires_at` y estado del setup |

---

## La lógica nueva — paso a paso

### Paso 1 — crt_detector.py (reescribir)

**Lógica anterior:** detectaba 4 modelos (2C, 3C, MultiC, Inside Bar).
**Lógica nueva:** solo detecta si la última vela H4 cerrada barre
el high o low de alguna vela H4 previa dentro de un lookback.

```python
def detect_crt(candles_h4: pd.DataFrame, lookback: int) -> list[CRTSetup]:
    """
    Analiza la última vela H4 cerrada (sweep_candle = candles_h4.iloc[-1]).
    Busca en las últimas `lookback` velas si alguna tiene un High o Low
    que el sweep_candle haya barrido con su wick.

    CRT Bearish válido:
    - sweep_candle.high > ref_candle.high  (wick supera el high)
    - sweep_candle.close < ref_candle.high (cierra por debajo — no breakout)

    CRT Bullish válido:
    - sweep_candle.low < ref_candle.low    (wick supera el low)
    - sweep_candle.close > ref_candle.low  (cierra por encima — no breakout)

    Retorna lista de CRTSetup (puede haber más de uno si barre varios rangos).
    Ordenar por proximidad al precio actual — el más cercano primero.
    """
```

**Campos del CRTSetup resultante:**
```python
@dataclass
class CRTSetup:
    pair: str
    direction: str           # "bearish" | "bullish"
    ref_candle: pd.Series    # Vela H4 cuyo extremo fue barrido
    sweep_candle: pd.Series  # Vela H4 que hizo el barrido
    crt_h: float             # High de ref_candle
    crt_l: float             # Low de ref_candle
    expires_at: pd.Timestamp # = tiempo de cierre de sweep_candle
    htf_level: KeyLevel | None = None
    ob: OBLevel | None = None
    status: str = "pending"
    # status: "pending" → "watching_m15" → "ob_formed" → "triggered"
    #                                                   → "invalidated"
    #                                    → "expired"
```

---

### Paso 2 — entry_model.py (archivo nuevo, reemplaza entry_models.py)

Este módulo implementa el modelo Clutifx completo en M15.
Tres funciones independientes que el loop llama en secuencia:

```python
def find_engulfing_ob(
    candles_m15: pd.DataFrame,
    setup: CRTSetup
) -> OBLevel | None:
    """
    Busca dentro de la ventana temporal del setup
    (desde sweep_candle.open_time hasta setup.expires_at)
    una vela M15 que envuelva la última vela opuesta.

    Para setup bearish:
    - Encontrar la última vela M15 alcista antes del giro.
    - La siguiente vela bajista cuyo high >= bullish.high
      Y cuyo low <= bullish.low es el OB.
    - OB_high = bearish_candle.high (con wick)
    - OB_low  = bearish_candle.low  (con wick)

    Para setup bullish: lógica espejo.
    Retorna OBLevel o None si no se encontró.
    """

def check_ob_invalidation(
    candles_m15: pd.DataFrame,
    ob: OBLevel,
    direction: str
) -> bool:
    """
    Bearish: retorna True si alguna vela M15 posterior al OB
             cierra por ENCIMA de ob.high.
    Bullish: retorna True si alguna vela M15 posterior al OB
             cierra por DEBAJO de ob.low.
    """

def check_ob_touch(
    candles_m15: pd.DataFrame,
    ob: OBLevel,
    direction: str
) -> bool:
    """
    Retorna True si el low de alguna vela M15 entra en la zona del OB
    (para bearish: algún high >= ob.low)
    (para bullish: algún low <= ob.high)
    Solo evalúa velas posteriores a ob.formed_at.
    """
```

**OBLevel:**
```python
@dataclass
class OBLevel:
    high: float
    low: float
    formed_at: pd.Timestamp
    invalidated: bool = False
```

---

### Paso 3 — main.py (ajustar loop)

El cambio principal es el manejo de estado de los setups activos
y la activación condicional del polling M15.

```python
# Estado global
active_setups: dict[str, list[CRTSetup]] = {}  # key = pair

# Loop H4 — corre al cierre de cada vela H4
async def on_h4_close(pair: str):
    candles_h4 = candle_store.get(pair, "4h")

    # 1. Detectar CRTs nuevos
    new_setups = detect_crt(candles_h4, config.CRT_LOOKBACK)

    # 2. Filtrar por confluencia HTF
    htf_daily  = candle_store.get(pair, "1day")
    htf_weekly = candle_store.get(pair, "1week")
    levels = find_all_levels(htf_daily, htf_weekly)

    for setup in new_setups:
        level = check_confluence(setup, levels)
        if level:
            setup.htf_level = level
            setup.status = "watching_m15"
            active_setups.setdefault(pair, []).append(setup)

    # 3. Limpiar setups expirados
    now = pd.Timestamp.utcnow()
    active_setups[pair] = [
        s for s in active_setups.get(pair, [])
        if s.expires_at > now and s.status not in ("triggered", "invalidated")
    ]

# Loop M15 — corre al cierre de cada vela M15
# SOLO si hay setups activos (no gastar recursos si no hay nada esperando)
async def on_m15_close(pair: str):
    if not active_setups.get(pair):
        return

    candles_m15 = candle_store.get(pair, "15min")

    for setup in active_setups[pair]:

        if setup.status == "watching_m15":
            ob = find_engulfing_ob(candles_m15, setup)
            if ob:
                setup.ob = ob
                setup.status = "ob_formed"

        elif setup.status == "ob_formed":
            if check_ob_invalidation(candles_m15, setup.ob, setup.direction):
                setup.status = "invalidated"
            elif check_ob_touch(candles_m15, setup.ob, setup.direction):
                setup.status = "triggered"
                await send_alert(build_alert(setup))
```

---

## Alerta Telegram (sin cambios de formato)

```
🔔 CRT + CLUTIFX SETUP

Par:        EUR/USD
Dirección:  BEARISH 🔻
Key Level:  FVG Diario (1.0842 – 1.0856)
CRT H:      1.0871  ← High barrido (SL)
CRT L:      1.0798  ← Target
OB M15:     1.0858 – 1.0865
Entrada:    Retroceso al OB
Hora UTC:   2025-03-26 14:15
```

---

## Orden de trabajo recomendado en Claude Code

1. Reescribir `core/crt_detector.py` con la nueva lógica de barrido.
   Escribir tests con velas sintéticas para bearish y bullish.

2. Crear `core/entry_model.py` con las 3 funciones.
   Testear `find_engulfing_ob` con secuencias M15 sintéticas.

3. Ajustar `main.py` para el nuevo estado de setups y el loop condicional M15.

4. Eliminar `core/entry_models.py` (el archivo viejo).

5. Smoke test en vivo con un par (EUR_USD) antes de activar todos los pares.

---

## Prompt de arranque para Claude Code

> "Tengo un scanner CRT en Python con Twelve Data que ya funciona.
> Voy a hacer un refactor. Los módulos data/, core/htf_levels.py,
> core/htf_confluence.py, output/telegram_bot.py y config.py
> se conservan sin tocar.
>
> Lo que cambia:
> 1. Reescribir core/crt_detector.py — eliminar los 4 modelos anteriores,
>    reemplazar por detección de barrido simple de High/Low en H4.
> 2. Crear core/entry_model.py con el modelo Clutifx:
>    find_engulfing_ob(), check_ob_invalidation(), check_ob_touch().
> 3. Ajustar main.py para manejar CRTSetup con expires_at y status.
>
> Empecemos por core/crt_detector.py. Aquí está el archivo actual: [pegar código]"
