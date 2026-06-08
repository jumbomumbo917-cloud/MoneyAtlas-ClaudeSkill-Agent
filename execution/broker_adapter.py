class BrokerAdapter:

    def place_order(self, symbol, direction, size, entry, sl, tp):
        raise NotImplementedError


class MockBroker(BrokerAdapter):
    """Paper-trading broker — records the order instead of routing it to a venue."""

    def place_order(self, symbol, direction, size, entry, sl, tp):
        return {
            "status": "filled",
            "symbol": symbol,
            "direction": direction,
            "size": round(size, 6),
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
        }
