# CRT Scanner — Task Tracker

## Fase 1 — Data Layer ✅
- [x] `config.py` — pydantic-settings, lectura de `.env`, parseo CSV de pares
- [x] `data/twelvedata_client.py` — cliente async aiohttp, `get_candles()`, `poll_candles()` con batch requests
- [x] `data/candle_store.py` — buffer rolling pandas por `(pair, granularity)`, deduplicación por timestamp
- [x] `requirements.txt`, `.env.example`, `.gitignore`
- [x] `check_phase1.py` — smoke test verificado contra Twelve Data

## Fase 2 — CRT Detector ✅
- [x] `core/models.py` — `CRTSignal`, `Direction`, `CRTModel`, tabla de prioridades
- [x] `core/liquidity_sweeper.py` — helpers puros: `swept_high/low`, `closed_back`, `is_inside_bar`
- [x] `core/power_of_3.py` — `classify_candles()` etiqueta ACCUMULATION / MANIPULATION / DISTRIBUTION
- [x] `core/crt_detector.py` — `detect()` con los 4 modelos + deduplicación por prioridad
- [x] `tests/test_crt_detector.py` — 14 tests sintéticos, 14/14 ✓
- [x] `check_phase2.py` — smoke test verificado (1005 señales en 9 pares H4)

## Fase 3 — Key Levels & HTF Confluence ✅
- [x] `core/models.py` — añadidos `KeyLevel`, `KeyLevelType`, `Score`, `ConfluenceResult`
- [x] `core/fvg_detector.py` — Fair Value Gaps bullish y bearish en cualquier TF
- [x] `core/ob_detector.py` — Order Blocks + Swing Highs/Lows
- [x] `core/htf_confluence.py` — `run_confluence()` cruza CRT H4 con Key Levels Diario, score A/B
- [x] `tests/test_fvg_detector.py` — 6/6 ✓
- [x] `tests/test_ob_detector.py` — 7/7 ✓
- [x] `tests/test_htf_confluence.py` — 7/7 ✓
- [x] `check_phase3.py` — smoke test verificado (29 Score A en 9 pares)

## Fase 4 — Entry Models ✅
- [x] `core/entry_models.py` — busca en M15 el trigger dentro de la zona CRT: OB, FVG, Breaker Block, Turtle Soup (TWS/TBS)
- [x] `tests/test_entry_models.py` — 13/13 ✓
- [x] `check_phase4.py` — smoke test verificado (29 entradas en 7 pares)

## Fase 5 — Telegram Alerts ✅
- [x] `output/telegram_bot.py` — `format_alert()` + `TelegramBot` con deduplicación y rate limit
- [x] `tests/test_telegram_bot.py` — 26/26 ✓
- [x] `check_phase5.py` — smoke test verificado (formato OK, --send disponible)

## Fase 7 — Backtesting ✅
- [x] `backtest/evaluator.py` — `TradeResult` + `evaluate_trade()` (WIN/LOSS/OPEN, pip P&L)
- [x] `backtest/runner.py` — walk-forward simulation, pre-filter a M15 window, tail(100) para replicar live scanner
- [x] `backtest/report.py` — tabla de consola por par + totales (Win%, Profit Factor)
- [x] `backtest.py` — CLI con `--rr`, `--pair`, `--min-score`

## Fase 6 — Orquestación ✅
- [x] `main.py` — bootstrap + loop asyncio con `poll_candles`, pipeline completo, shutdown limpio
- [x] `check_phase6.py` — smoke test end-to-end verificado (bootstrap + pipeline, sin Telegram)
