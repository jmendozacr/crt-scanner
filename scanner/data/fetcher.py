import time
from collections import deque

import requests.exceptions
from twelvedata import TDClient
from twelvedata.exceptions import BadRequestError, InvalidApiKeyError, TwelveDataError

from scanner.data.candle import Candle


class FetcherError(Exception):
    pass


class FetcherAuthError(FetcherError):
    pass


class FetcherRateLimitError(FetcherError):
    pass


class FetcherNetworkError(FetcherError):
    pass


class FetcherServerError(FetcherError):
    pass


class FetcherBadRequestError(FetcherError):
    pass


class FetcherEmptyResponseError(FetcherError):
    pass


_WINDOW_SECONDS = 60
_MAX_CALLS_PER_WINDOW = 8

_OUTPUTSIZE_DEFAULTS: dict[str, int] = {
    "1day": 30,
    "2day": 30,
    "3day": 30,
    "4h": 25,
    "15min": 55,
}


class RateLimiter:
    def __init__(self) -> None:
        self._timestamps: deque[float] = deque(maxlen=_MAX_CALLS_PER_WINDOW)

    def acquire(self) -> None:
        while True:
            now = time.monotonic()
            if len(self._timestamps) < _MAX_CALLS_PER_WINDOW:
                break
            oldest = self._timestamps[0]
            elapsed = now - oldest
            if elapsed >= _WINDOW_SECONDS:
                break
            time.sleep(_WINDOW_SECONDS - elapsed + 0.01)
        self._timestamps.append(time.monotonic())


def _is_synthetic_timeframe(tf: str) -> bool:
    return tf in ("2day", "3day")


def _synthetic_factor(tf: str) -> int:
    return {"2day": 2, "3day": 3}[tf]


def _aggregate_daily(candles: list[Candle], factor: int) -> list[Candle]:
    result: list[Candle] = []
    complete_groups = len(candles) // factor
    for i in range(complete_groups):
        group = candles[i * factor : (i + 1) * factor]
        result.append(
            Candle(
                datetime=group[0].datetime,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )
    return result


class TwelveDataFetcher:
    def __init__(self, api_key: str) -> None:
        self._client = TDClient(apikey=api_key)
        self._rate_limiter = RateLimiter()

    def _outputsize_for(self, timeframe: str, requested: int) -> int:
        if _is_synthetic_timeframe(timeframe):
            return requested * _synthetic_factor(timeframe)
        return requested

    def fetch(self, symbol: str, timeframe: str, outputsize: int | None = None) -> list[Candle]:
        effective = outputsize if outputsize is not None else _OUTPUTSIZE_DEFAULTS.get(timeframe, 30)
        self._rate_limiter.acquire()

        try:
            if _is_synthetic_timeframe(timeframe):
                raw = (
                    self._client.time_series(
                        symbol=symbol,
                        interval="1day",
                        outputsize=self._outputsize_for(timeframe, effective),
                        order="asc",
                    )
                    .as_json()
                )
                candles = [Candle.from_api({"datetime": dt, **vals}) for dt, vals in raw.items()]
                if not candles:
                    raise FetcherEmptyResponseError(f"Empty response for {symbol} 1day")
                return _aggregate_daily(candles, _synthetic_factor(timeframe))
            else:
                raw = (
                    self._client.time_series(
                        symbol=symbol,
                        interval=timeframe,
                        outputsize=effective,
                        order="asc",
                    )
                    .as_json()
                )
                candles = [Candle.from_api({"datetime": dt, **vals}) for dt, vals in raw.items()]
                if not candles:
                    raise FetcherEmptyResponseError(f"Empty response for {symbol} {timeframe}")
                return candles

        except FetcherError:
            raise
        except InvalidApiKeyError as e:
            raise FetcherAuthError(str(e)) from e
        except BadRequestError as e:
            raise FetcherBadRequestError(str(e)) from e
        except TwelveDataError as e:
            raise FetcherRateLimitError(str(e)) from e
        except requests.exceptions.Timeout as e:
            raise FetcherNetworkError(str(e)) from e
        except requests.exceptions.ConnectionError as e:
            raise FetcherNetworkError(str(e)) from e
