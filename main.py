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

# --- CONFIGURACIÓN DE CRDENCIALES ---
APP_KEY = os.environ.get('DROPBOX_APP_KEY')
APP_SECRET = os.environ.get('DROPBOX_APP_SECRET')
REFRESH_TOKEN = os.environ.get('DROPBOX_REFRESH_TOKEN')
FILE_PATH_DBX = "/astro_data.json"

# Inicializamos el exchange con un timeout para evitar que el worker se quede colgado
exchange = ccxt.kucoin({'enableRateLimit': True, 'timeout': 30000})

def get_dropbox_client():
    """Crea un cliente de Dropbox que se auto-renueva usando el Refresh Token"""
    return dropbox.Dropbox(
        oauth2_refresh_token=REFRESH_TOKEN,
        app_key=APP_KEY,
        app_secret=APP_SECRET
    )

def run_astro_logic():
    print("ASTRO-QUANT_OS: CALCULATING_FULL_INDICATORS...")
    try:
        # 1. Mercado con manejo de errores para KuCoin
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=400)
        except Exception as e:
            print(f"ERROR KuCoin: {e}. Reintentando con Binance...")
            # Backup por si KuCoin falla
            ex_back = ccxt.binance()
            ticker = ex_back.fetch_ticker('BTC/USDT')
            bars = ex_back.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=400)

        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

        # --- CÁLCULOS CUANTITATIVOS ---
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['ema200'] = ta.ema(df['close'], length=200)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['willr'] = ta.willr(df['high'], df['low'], df['close'], length=14)
        
        # Awesome Oscillator (Aseguramos que devuelva valores numéricos)
        ao = ta.ao(df['high'], df['low'])
        df['ao'] = ao if ao is not None else 0
        
        # MACD
        macd = ta.macd(df['close'])
        df['macd_h'] = macd.iloc[:, 1] if macd is not None else 0
        
        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bbands.iloc[:, 2] if bbands is not None else 0
        df['bb_lower'] = bbands.iloc[:, 0] if bbands is not None else 0

        # Limpieza para el frontend
        candles = df.fillna(0).tail(150).to_dict(orient='records')

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
                "timestamp": datetime.now().isoformat(),
                "indicators": {
                    "rsi": float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 0,
                    "willr": float(df['willr'].iloc[-1]) if not pd.isna(df['willr'].iloc[-1]) else 0,
                    "ao": float(df['ao'].iloc[-1]) if not pd.isna(df['ao'].iloc[-1]) else 0
                }
            },
            "candles": candles
        }

        # 4. Dropbox Upload (Usando el nuevo cliente auto-renovables)
        dbx = get_dropbox_client()
        dbx.files_upload(
            json.dumps(payload, indent=2).encode('utf-8'), 
            FILE_PATH_DBX, 
            mode=WriteMode('overwrite')
        )
        print("UPLINK_SUCCESSFUL: astro_data.json actualizado en Dropbox.")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

@app.get("/")
def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_astro_logic)
    return {"status": "Syncing", "message": "Calculando indicadores y despertando sistema..."}
