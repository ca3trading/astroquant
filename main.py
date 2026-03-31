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

# --- CONFIGURACIÓN ---
# Asegúrate de poner esto en Environment de Render
DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN")
FILE_PATH_DBX = "/astro_data.json"
exchange = ccxt.kucoin({'enableRateLimit': True})

def run_astro_logic():
    """Toda tu lógica de análisis y subida a Dropbox"""
    print("ASTRO-QUANT_OS: STARTING_UPLINK...")
    try:
        # 1. Mercado
        ticker = exchange.fetch_ticker('BTC/USDT')
        bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=250)
        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema200'] = ta.ema(df['close'], length=200)
        macd = ta.macd(df['close'])
        df['macd_h'] = macd.iloc[:, 1] if macd is not None else 0
        candles = df.fillna(0).tail(100).to_dict(orient='records')

        # 2. Astronomía
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
                "timestamp": datetime.now().isoformat()
            },
            "candles": candles
        }

        # 4. Dropbox
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        dbx.files_upload(json.dumps(payload, indent=2).encode('utf-8'), 
                         FILE_PATH_DBX, mode=WriteMode('overwrite'))
        print("UPLINK_SUCCESSFUL")
    except Exception as e:
        print(f"ERROR: {e}")

@app.get("/")
def trigger_sync(background_tasks: BackgroundTasks):
    """Esta es la ruta que llamará Cloudflare"""
    background_tasks.add_task(run_astro_logic)
    return {"status": "Syncing", "message": "Astro-logic started in background"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
