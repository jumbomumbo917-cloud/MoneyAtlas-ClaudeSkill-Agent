import asyncio

from smc.smc_layer_masterpiece import SMCLayerEngine, load_ohlcv_csv
from execution.signal_engine import SignalEngine
from execution.risk_engine import RiskEngine
from execution.execution_engine import ExecutionEngine
from execution.broker_adapter import MockBroker
from execution.trade_logger import TradeLogger


async def run():

    # 1. Load Data
    candles = load_ohlcv_csv("examples/sample_data.csv")

    # 2. Analyze Market
    smc_engine = SMCLayerEngine()
    layer_map = await smc_engine.analyze(
        symbol="BTCUSDT",
        timeframe="4H",
        candles=candles
    )

    print(f"Current layer: L{layer_map.current_layer} @ {layer_map.current_price}")
    for layer in layer_map.layers:
        print(f"  L{layer.layer} {layer.phase:<14} "
              f"{layer.price_low:>10.2f} - {layer.price_high:<10.2f} "
              f"state={layer.state:<13} confidence={layer.confidence}")

    # 3. Generate Signal
    signal_engine = SignalEngine()
    signal = signal_engine.generate_signal(layer_map)

    if not signal:
        print("No Trade Signal")
        return

    print(f"\nSignal: {signal}")

    # 4. Risk Management
    risk_engine = RiskEngine(capital=10000)

    # 5. Execute Trade
    broker = MockBroker()
    execution_engine = ExecutionEngine(broker, risk_engine)

    result = execution_engine.execute(signal)
    print(f"Execution result: {result}")

    # 6. Log
    logger = TradeLogger()
    logger.log(signal, result)


if __name__ == "__main__":
    asyncio.run(run())
