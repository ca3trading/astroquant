import os
import json
import dropbox
import ccxt
import pandas as pd
import pandas_ta as ta
import swisseph as swe
from datetime import datetime
from dropbox.files import WriteMode
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()

DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN")
FILE_PATH_DBX = "/astro_data.json"
exchange = ccxt.kucoin({'enableRateLimit': True})

def run_astro_logic():
    print("ASTRO-QUANT_OS: CALCULATING_FULL_INDICATORS...")
    try:
        # 1. Mercado (Pedimos 400 velas para que los indicadores largos se estabilicen)
        ticker = exchange.fetch_ticker('BTC/USDT')
        bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=400)
        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

        # --- CÁLCULOS CUANTITATIVOS ---
        # EMAs
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['ema200'] = ta.ema(df['close'], length=200)
        
        # Osciladores
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['willr'] = ta.willr(df['high'], df['low'], df['close'], length=14)
        df['ao'] = ta.ao(df['high'], df['low']) # Awesome Oscillator
        
        # MACD
        macd = ta.macd(df['close'])
        df['macd_h'] = macd.iloc[:, 1] if macd is not None else 0
        
        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bbands.iloc[:, 2] if bbands is not None else 0
        df['bb_lower'] = bbands.iloc[:, 0] if bbands is not None else 0

        # Limpieza y toma de las últimas 150 velas para el frontend
        candles = df.fillna(0).tail(150).to_dict(orient='records')

        # 2. Astronomía (Lo que ya teníamos)
        now = datetime.utcnow()
        jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
        planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, 
                   "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, 
                   "Venus": swe.VENUS, "Mercury": swe.MERCURY}
        astro = {name: f"{swe.calc_ut(jd, code)[0][0]:.2f}" for name, code in planets.items()}

        # 3. Payload
        payload = {
            "analysis": {
                "btc_price": ticker['last'],
                "astrology": astro,
                "insight": f"CRON_SYNC // {datetime.now().strftime('%H:%M')}",
                "timestamp": datetime.now().isoformat(),
                # Enviamos los valores actuales de los osciladores para el header
                "indicators": {
                    "rsi": float(df['rsi'].iloc[-1]),
                    "willr": float(df['willr'].iloc[-1]),
                    "ao": float(df['ao'].iloc[-1])
                }
            },
            "candles": candles
        }

        # 4. Dropbox Upload
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        dbx.files_upload(json.dumps(payload, indent=2).encode('utf-8'), 
                         FILE_PATH_DBX, mode=WriteMode('overwrite'))
        print("UPLINK_SUCCESSFUL")
        
    except Exception as e:
        print(f"ERROR: {e}")

@app.get("/")
def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_astro_logic)
    return {"status": "Syncing", "message": "Calculando indicadores completos..."}
