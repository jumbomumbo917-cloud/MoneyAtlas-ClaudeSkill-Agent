# smc/smc_layer_masterpiece.py
#
# Smart Money Cycle (SMC) Layer Engine
# Maps OHLCV price action onto the 5-layer institutional cycle:
#   L1 Accumulation -> L2 Expansion -> L3 Decision Zone
#   -> L4 Distribution -> L5 Exit Liquidity
#
# The price range observed in the candle set is split into 5 horizontal
# zones (lowest price -> highest price = L1 -> L5). Each zone is then
# scored against the behaviour expected of its phase (participation,
# volatility, directional bias) using the candles whose closes fall
# inside it, producing a confidence grounded in the actual data.

import csv
from dataclasses import dataclass
from typing import List


LAYER_COUNT = 5

# layer number -> (phase identifier, state label)
LAYER_PHASES = {
    1: ("accumulation", "accumulating"),
    2: ("expansion", "expanding"),
    3: ("decision_zone", "deciding"),
    4: ("distribution", "distributing"),
    5: ("exit_liquidity", "exit_liquidity"),
}


@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SMCLayer:
    layer: int
    phase: str
    price_low: float
    price_high: float
    state: str
    confidence: float
    candle_count: int


@dataclass
class SMCAnalysisResult:
    symbol: str
    timeframe: str
    layers: List[SMCLayer]
    current_layer: int
    current_price: float


def load_ohlcv_csv(path: str) -> List[Candle]:
    """Load OHLCV candles from a CSV with columns: timestamp,open,high,low,close,volume"""
    candles = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            candles.append(Candle(
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            ))
    return candles


class SMCLayerEngine:
    """Derives the 5-layer Smart Money Cycle structure from OHLCV candles."""

    async def analyze(self, symbol: str, timeframe: str, candles: List[Candle]) -> SMCAnalysisResult:
        if not candles:
            return SMCAnalysisResult(symbol=symbol, timeframe=timeframe, layers=[], current_layer=0, current_price=0.0)

        lowest = min(c.low for c in candles)
        highest = max(c.high for c in candles)
        zone_height = (highest - lowest) / LAYER_COUNT

        avg_volume = sum(c.volume for c in candles) / len(candles)
        avg_range = sum(c.high - c.low for c in candles) / len(candles)

        layers = []
        for i in range(LAYER_COUNT):
            layer_no = i + 1
            price_low = lowest + i * zone_height
            price_high = highest if layer_no == LAYER_COUNT else lowest + (i + 1) * zone_height

            zone_candles = [c for c in candles if price_low <= c.close <= price_high]
            phase, state = LAYER_PHASES[layer_no]
            confidence = self._score_zone(layer_no, zone_candles, avg_volume, avg_range)

            layers.append(SMCLayer(
                layer=layer_no,
                phase=phase,
                price_low=round(price_low, 2),
                price_high=round(price_high, 2),
                state=state if zone_candles else "untested",
                confidence=round(confidence, 2),
                candle_count=len(zone_candles),
            ))

        current_price = candles[-1].close
        current_layer = self._locate_layer(current_price, layers)

        return SMCAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            layers=layers,
            current_layer=current_layer,
            current_price=current_price,
        )

    def _score_zone(self, layer_no: int, zone_candles: List[Candle], avg_volume: float, avg_range: float) -> float:
        """Score how strongly a price zone exhibits the behaviour expected of its SMC phase."""
        if not zone_candles:
            return 0.0

        zone_volume = sum(c.volume for c in zone_candles) / len(zone_candles)
        zone_range = sum(c.high - c.low for c in zone_candles) / len(zone_candles)
        net_move = zone_candles[-1].close - zone_candles[0].close

        volume_ratio = zone_volume / avg_volume if avg_volume else 1.0
        volatility_ratio = zone_range / avg_range if avg_range else 1.0
        rising = net_move > 0
        falling = net_move < 0

        if layer_no == 1:    # Accumulation: heavy participation, tight ranges, basing-to-up
            fit = (volume_ratio - 1) - (volatility_ratio - 1) + (0.3 if not falling else -0.3)
        elif layer_no == 2:  # Expansion: directional breakout, expanding ranges
            fit = (volatility_ratio - 1) + (0.4 if rising else -0.2) + (volume_ratio - 1) * 0.5
        elif layer_no == 3:  # Decision zone: contested, highest volatility
            fit = (volatility_ratio - 1) * 1.5
        elif layer_no == 4:  # Distribution: heavy participation, tight ranges, topping-to-down
            fit = (volume_ratio - 1) - (volatility_ratio - 1) + (0.3 if not rising else -0.3)
        else:                # Exit liquidity: sharp reversal off highs on volume
            fit = (volume_ratio - 1) + (0.4 if falling else -0.2)

        # More candles tested in the zone -> more evidence behind the read
        sample_strength = min(len(zone_candles) / 10.0, 1.0)
        confidence = (0.5 + fit * 0.25) * (0.5 + 0.5 * sample_strength)

        return max(0.0, min(1.0, confidence))

    def _locate_layer(self, price: float, layers: List[SMCLayer]) -> int:
        for layer in layers:
            if layer.price_low <= price <= layer.price_high:
                return layer.layer
        return layers[-1].layer if price > layers[-1].price_high else layers[0].layer
