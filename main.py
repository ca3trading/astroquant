import ccxt
import swisseph as swe
import pandas as pd
import pandas_ta as ta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn
import os

app = FastAPI()

# --- CONFIGURACIÓN DE CORS PARA PRODUCCIÓN ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite peticiones desde cualquier origen (GitHub Pages, Render Static, etc.)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
}

def get_sign(degrees):
    signs = ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", "Libra", "Escorpio", "Sagitario", "Capri", "Acuario", "Piscis"]
    return signs[int(degrees / 30)]

def get_full_astrology():
    now = datetime.utcnow()
    # Cálculo del día juliano basado en UTC
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    astro_data = {}
    for name, code in PLANETS.items():
        res, ret = swe.calc_ut(jd, code)
        deg = res[0]
        astro_data[name] = f"{round(deg, 2)} ({get_sign(deg)})"
    
    sun_pos, _ = swe.calc_ut(jd, swe.SUN)
    moon_pos, _ = swe.calc_ut(jd, swe.MOON)
    return astro_data, sun_pos[0], moon_pos[0]

@app.get("/")
def health_check():
    return {"status": "online", "message": "ASTRO-QUANT OS Backend v2.6.4"}

@app.get("/analisis")
def update_market():
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        ohlcv_6h = exchange.fetch_ohlcv('BTC/USDT', timeframe='6h', limit=50)
        
        history_6h = [{"t": c[0], "c": c[4]} for c in ohlcv_6h]
        current_price = ohlcv_6h[-1][4]
        
        astro_data, sun_deg, moon_deg = get_full_astrology()
        
        # Lógica de Insight Lunar
        diff = abs(sun_deg - moon_deg)
        insight = "Fase Lunar: Neutral."
        if diff < 12 or diff > 348: 
            insight = "Luna Nueva: Fase de Acumulación."
        elif 170 < diff < 190: 
            insight = "Luna Llena: Alta Volatilidad Detectada."
            
        return {
            "btc_price": current_price, 
            "chart": history_6h, 
            "astrology": astro_data, 
            "insight": insight
        }
    except Exception as e:
        return {"error": f"Error en análisis: {str(e)}"}

@app.get("/candles-1h")
def get_1h_candles():
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        # 500 velas para que los indicadores de largo plazo (EMA 200) se calculen correctamente
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=500)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # Indicadores Técnicos
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['ema200'] = ta.ema(df['close'], length=200)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ao'] = ta.ao(df['high'], df['low'])
        df['willr'] = ta.willr(df['high'], df['low'], df['close'], length=14)
        
        macd = ta.macd(df['close'])
        if macd is not None:
            # Mapeo manual de columnas MACD (pueden variar según versión de pandas_ta)
            df['macd'] = macd.iloc[:, 0]
            df['macd_h'] = macd.iloc[:, 1]
            df['macd_s'] = macd.iloc[:, 2]
            
        # Limpieza de NaNs para JSON (JSON no soporta NaN nativo)
        df = df.where(pd.notnull(df), None)
        
        return df.tail(300).to_dict(orient='records')
    except Exception as e:
        print(f"Error en velas: {e}")
        return []

# --- INICIO DINÁMICO PARA RENDER ---
if __name__ == "__main__":
    # Render asigna el puerto mediante la variable de entorno PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
