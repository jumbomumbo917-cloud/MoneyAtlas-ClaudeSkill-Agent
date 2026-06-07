from dataclasses import dataclass
from typing import Optional

@dataclass
class TradeSignal:
    symbol: str
    direction: str   # "long" / "short"
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float

class SignalEngine:

    def generate_signal(self, layer_map) -> Optional[TradeSignal]:

        # Long thesis: accumulate in L1, target the L3 decision zone.
        accumulation = layer_map.layers[0]   # L1 — accumulation
        decision = layer_map.layers[2]       # L3 — decision zone

        if accumulation.state == "accumulating" and accumulation.confidence > 0.6:

            entry = (accumulation.price_low + accumulation.price_high) / 2
            sl = accumulation.price_low * 0.98
            tp = decision.price_high

            return TradeSignal(
                symbol=layer_map.symbol,
                direction="long",
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
                confidence=accumulation.confidence
            )

        return None
