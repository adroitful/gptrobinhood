import time
import pandas as pd
import numpy as np
from tradingview_ta import TA_Handler, Interval
import robin_stocks.robinhood as r
import logging
import os

# Configuration variables
USERNAME = 'your_username'
PASSWORD = 'your_password'
CANDLE_INTERVAL = Interval.INTERVAL_1_MINUTE  # Change candle interval here

# Candle interval parameters mapping
interval_params = {
    Interval.INTERVAL_1_MINUTE: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    Interval.INTERVAL_5_MINUTES: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    Interval.INTERVAL_15_MINUTES: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    Interval.INTERVAL_30_MINUTES: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    Interval.INTERVAL_1_HOUR: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    Interval.INTERVAL_4_HOURS: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    Interval.INTERVAL_1_DAY: {
        'bb_period': 20,
        'bb_std_dev': 2,
        'rsi_period': 14
    },
    # Add more intervals and corresponding parameters as needed
}

# Extract parameters based on selected interval
bb_period = interval_params[CANDLE_INTERVAL]['bb_period']
bb_std_dev = interval_params[CANDLE_INTERVAL]['bb_std_dev']
rsi_period = interval_params[CANDLE_INTERVAL]['rsi_period']

# Profit parameters
PROFIT_TARGET_PERCENT = 0.01  # 1% profit target
PARTIAL_SELL_PERCENT = 0.5    # Sell half of holdings when profit target is reached
KEEP_CRYPTO_PERCENT = 0.1      # Keep 10% of the crypto after selling for profit

# RSI thresholds for buy and sell signals (adjustable)
RSI_OVERSOLD_THRESHOLD = 30
RSI_OVERBOUGHT_THRESHOLD = 70

# Setup logging
logging.basicConfig(filename='trade_log.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Connect to Robinhood
r.login(USERNAME, PASSWORD)

# CSV file setup
trade_log_file = 'trades.csv'
if not os.path.isfile(trade_log_file):
    with open(trade_log_file, 'w') as f:
        f.write('timestamp,symbol,action,price,quantity\n')

# Function to get TradingView data
def get_tv_data(symbol, interval=CANDLE_INTERVAL):
    handler = TA_Handler(
        symbol=symbol,
        screener="crypto",
        exchange="BINANCE",
        interval=interval
    )
    analysis = handler.get_analysis()
    data = {
        'timestamp': [bar['timestamp'] for bar in analysis.indicators['chart_data']],
        'close': [bar['close'] for bar in analysis.indicators['chart_data']]
    }
    return pd.DataFrame(data)

# Function to calculate Bollinger Bands and RSI
def calculate_bbands_rsi(data):
    data['mean'] = data['close'].rolling(window=bb_period).mean()
    data['std'] = data['close'].rolling(window=bb_period).std()
    data['upperband'] = data['mean'] + (bb_std_dev * data['std'])
    data['lowerband'] = data['mean'] - (bb_std_dev * data['std'])
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    data['rsi'] = 100 - (100 / (1 + rs))
    data.dropna(inplace=True)
    return data

# Function to check Bollinger Bands and RSI signals
def check_signal(data):
    current_price = data['close'].iloc[-1]
    current_rsi = data['rsi'].iloc[-1]
    bb_info = f"BB: {data['lowerband'].iloc[-1]:.2f} - {current_price:.2f} - {data['upperband'].iloc[-1]:.2f}"
    
    print(f"Current RSI: {current_rsi:.2f}")
    print(f"Bollinger Bands: {bb_info}")
    
    if current_price < data['lowerband'].iloc[-1] and current_rsi < RSI_OVERSOLD_THRESHOLD:
        print(f'Signal: Buy')
        return 'buy'
    elif current_price > data['upperband'].iloc[-1] and current_rsi > RSI_OVERBOUGHT_THRESHOLD:
        print(f'Signal: Sell')
        return 'sell'
    else:
        print(f'Signal: Hold')
        return 'hold'

# Function to log trade to CSV file
def log_trade(timestamp, symbol, action, price, quantity):
    with open(trade_log_file, 'a') as f:
        f.write(f'{timestamp},{symbol},{action},{price},{quantity}\n')

# Function to execute trade on Robinhood and log the trade
def execute_trade(symbol, action, quantity=1):
    if action == 'buy':
        order = r.orders.order_buy_market(symbol, quantity)
    elif action == 'sell':
        order = r.orders.order_sell_market(symbol, quantity)

    # Log trade details
    price = float(order['last_trade_price'])
    timestamp = pd.Timestamp.now()
    logging.info(f'{action.capitalize()} {quantity} of {symbol} at {price}')
    log_trade(timestamp, symbol, action, price, quantity)

# Function to calculate and log overall performance
def log_performance():
    trades = pd.read_csv(trade_log_file)
    num_trades = len(trades) // 2
    profit = 0
    for i in range(1, len(trades), 2):
        if trades['action'].iloc[i-1] == 'buy' and trades['action'].iloc[i] == 'sell':
            profit += (trades['price'].iloc[i] - trades['price'].iloc[i-1]) * trades['quantity'].iloc[i-1]
    
    logging.info(f'Number of trades: {num_trades}')
    logging.info(f'Total profit: {profit}')
    print(f'Number of trades: {num_trades}')
    print(f'Total profit: {profit}')

# Function to check and sell for profit
def check_for_profit(symbol, buy_price, current_price, quantity):
    target_price = buy_price * (1 + PROFIT_TARGET_PERCENT)
    if current_price >= target_price:
        quantity_to_sell = quantity * PARTIAL_SELL_PERCENT
        execute_trade(symbol, 'sell', quantity_to_sell)
        return True
    return False

# Main trading function
def trade_crypto(symbols):
    holdings = {}

    while True:
        for symbol in symbols:
            try:
                print(f'\nChecking {symbol}...')
                
                data = get_tv_data(symbol)
                data = calculate_bbands_rsi(data)
                
                signal = check_signal(data)
                
                current_price = data['close'].iloc[-1]
                if signal == 'buy' and symbol not in holdings:
                    execute_trade(symbol, 'buy')
                    holdings[symbol] = {'buy_price': current_price, 'quantity': 1}  # Example: 1 unit bought
                    print(f'Buy signal detected for {symbol}. Executing buy order.')
                elif symbol in holdings:
                    if check_for_profit(symbol, holdings[symbol]['buy_price'], current_price, holdings[symbol]['quantity']):
                        # Update holdings after partial sell
                        holdings[symbol]['quantity'] *= (1 - PARTIAL_SELL_PERCENT)
                        print(f'Selling {symbol} for profit. Partial sell executed.')
                    if signal == 'sell':
                        execute_trade(symbol, 'sell', holdings[symbol]['quantity'])
                        del holdings[symbol]
                        print(f'Sell signal detected for {symbol}. Executing sell order.')

            except Exception as e:
                logging.error(f'Error processing {symbol}: {e}')

        # Log performance
        log_performance()

        # Wait for 1 minute before the next check
        time.sleep(60)

# List of cryptocurrencies to trade
crypto_symbols = ['SHIBUSDT', 'AVAXUSDT', 'ETHUSDT', 'LINKUSDT', 'BCHUSDT', 'UNIUSDT', 'LTCUSDT', 'ETCUSDT', 'XLMUSDT', 'AAVEUSDT', 'XTZUSDT', 'COMPUSDT']

# Run the trading function
try:
    trade_crypto(crypto_symbols)
finally:
    r.logout()
