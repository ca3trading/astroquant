import os
import json
import dropbox
import ccxt
import pandas as pd
import pandas_ta as ta
import swisseph as swe
from datetime import datetime
from dropbox.files import WriteMode

# --- CONFIGURACIÓN ---
DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN")
FILE_PATH_DBX = "/astro_data.json"
exchange = ccxt.kucoin({'enableRateLimit': True})

def get_astrology_data():
    now = datetime.utcnow()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, 
               "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, 
               "Venus": swe.VENUS, "Mercury": swe.MERCURY}
    res = {}
    for name, code in planets.items():
        pos, _ = swe.calc_ut(jd, code)
        res[name] = f"{pos[0]:.2f}"
    return res

def get_market_data():
    bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=250)
    df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema200'] = ta.ema(df['close'], length=200)
    macd = ta.macd(df['close'])
    df['macd_h'] = macd.iloc[:, 1] if macd is not None else 0
    return df.fillna(0).tail(100).to_dict(orient='records')

def run_once():
    """Función que ejecuta el ciclo una sola vez y sube a Dropbox"""
    print("ASTRO-QUANT_OS: TRIGGER_RECEIVED. STARTING_UPLINK...")
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        astro = get_astrology_data()
        candles = get_market_data()
        
        payload = {
            "analysis": {
                "btc_price": ticker['last'],
                "astrology": astro,
                "insight": f"CRON_SYNC // {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "timestamp": datetime.now().isoformat()
            },
            "candles": candles
        }

        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        json_data = json.dumps(payload, indent=2).encode('utf-8')
        dbx.files_upload(json_data, FILE_PATH_DBX, mode=WriteMode('overwrite'))
        print("UPLINK_COMPLETE. SHUTTING_DOWN.")
    except Exception as e:
        print(f"CRON_JOB_ERROR: {e}")

if __name__ == "__main__":
    run_once()
