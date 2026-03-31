import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ccxt
import pandas as pd
import pandas_ta as ta
import swisseph as swe
from datetime import datetime

app = FastAPI()

# --- CONFIGURACIÓN DE CORS ---
# Permite que tu index.html (en GitHub o Local) lea los datos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# CAMBIO CRÍTICO: Usamos KuCoin para evitar el geobloqueo de Binance en Render
exchange = ccxt.kucoin({
    'enableRateLimit': True,
})

def get_astrology_data():
    """Calcula posiciones geocéntricas actuales con Swisseph"""
    try:
        now = datetime.utcnow()
        # Cálculo del Día Juliano
        jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
        
        planets = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, 
            "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Venus": swe.VENUS,
            "Mercury": swe.MERCURY
        }
        
        res = {}
        for name, code in planets.items():
            # calc_ut devuelve (posiciones, flag) donde pos[0] es la longitud
            pos, _ = swe.calc_ut(jd, code)
            res[name] = f"{pos[0]:.2f}°"
        return res
    except Exception as e:
        return {"Error": "Astro Calc Fail"}

@app.get("/")
def read_root():
    return {"status": "ASTRO-QUANT_OS Online", "version": "2.6.4", "engine": "KuCoin-Bridge"}

@app.get("/candles-1h")
def get_candles():
    try:
        # Obtenemos 300 velas para que la EMA 200 tenga datos suficientes
        bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=300)
        df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # --- INDICADORES TÉCNICOS ---
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema200'] = ta.ema(df['close'], length=200)
        df['willr'] = ta.willr(df['high'], df['low'], df['close'], length=14)
        
        # MACD (Retorna un DataFrame con varias columnas)
        macd = ta.macd(df['close'])
        if macd is not None:
            df['macd_h'] = macd['MACDh_12_26_9']
        else:
            df['macd_h'] = 0

        # Limpiar NaNs para evitar errores en el JSON del Frontend
        df = df.fillna(0)
        
        return df.to_dict(orient='records')
    except Exception as e:
        return {"error": f"Error en velas: {str(e)}"}

@app.get("/analisis")
def get_analisis():
    try:
        # Obtenemos el precio actual
        ticker = exchange.fetch_ticker('BTC/USDT')
        astro = get_astrology_data()
        
        # Lógica de Insight simplificada para la v2.6.4
        price = ticker['last']
        insight = "MONITORING_NETWORK: Buscando confluencia técnica/astral..."
        
        if price > 50000: # Ejemplo de condición lógica
            insight = "SOPORTE PSICOLÓGICO SUPERIOR. Verificar aspectos de Saturno."

        return {
            "btc_price": price,
            "astrology": astro,
            "insight": insight,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": f"Error en análisis: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    # Puerto dinámico para Render
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
