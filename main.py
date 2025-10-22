from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import numpy as np
from sklearn.linear_model import LogisticRegression
import logging
import time
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# 🧠 AI Model untuk Deteksi Bau
# =========================
try:
    # Data training yang lebih realistis
    X_train = np.array([
        # Aman - nilai MQ rendah, suhu & kelembaban normal
        [150, 25, 60], [200, 26, 65], [300, 27, 70], [250, 28, 55],
        [180, 24, 58], [220, 25, 62], [280, 26, 68], [190, 27, 63],
        
        # Borderline - mulai mendekati bau
        [500, 28, 72], [450, 29, 75], [600, 30, 78], [550, 31, 80],
        
        # Bau - nilai MQ tinggi
        [800, 30, 80], [900, 31, 85], [1000, 32, 90], [1200, 33, 95],
        [750, 29, 82], [850, 30, 88], [950, 31, 92], [1100, 32, 94]
    ])
    
    # Label: 0 = Aman, 1 = Bau
    y_train = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1])

    model = LogisticRegression()
    model.fit(X_train, y_train)
    logger.info("✅ AI Model berhasil dilatih dengan 20 sampel data")
except Exception as e:
    logger.error(f"❌ Error training model: {e}")
    model = None

# Simpan data terakhir dan history
latest_data = {
    "gas_level": 0,
    "temperature": 0,
    "humidity": 0,
    "status": "Menunggu data pertama...",
    "time": "",
    "spray_active": False,
    "prediction": 0,
    "confidence": 0
}

# =========================
# 🌐 Endpoint untuk ESP32
# =========================
@app.route('/data', methods=['POST', 'GET', 'OPTIONS'])
def receive_data():
    try:
        # Handle preflight request
        if request.method == 'OPTIONS':
            return jsonify({"status": "ok"}), 200
            
        if request.method == 'GET':
            return jsonify({
                "status": "ready", 
                "message": "SIGETA Server aktif",
                "timestamp": datetime.now().isoformat()
            })
        
        # Handle POST request dari ESP32
        data = request.get_json()
        
        if not data:
            logger.warning("⚠️ Data kosong diterima")
            return jsonify({"status": "error", "message": "Data kosong"}), 400

        # Extract data dengan default value
        mq_value = data.get("mq", data.get("gas_level", 0))
        temperature = data.get("temperature", 0)
        humidity = data.get("humidity", 0)
        
        # Konversi ke float
        try:
            mq_value = float(mq_value)
            temperature = float(temperature)
            humidity = float(humidity)
        except (ValueError, TypeError):
            logger.error("❌ Error konversi data ke float")
            return jsonify({"status": "error", "message": "Data tidak valid"}), 400

        logger.info(f"📥 Data sensor: MQ={mq_value}, Temp={temperature}, Hum={humidity}")

        # Prediksi menggunakan AI model
        spray_active = False
        if model is not None:
            try:
                prediction = model.predict([[mq_value, temperature, humidity]])[0]
                probability = model.predict_proba([[mq_value, temperature, humidity]])[0]
                confidence = round(float(probability[prediction]), 2)
                
                # Tentukan status berdasarkan prediksi
                if prediction == 1:
                    status = "⚠️ BAU TINGGI - PENYEMPROTAN AKTIF"
                    spray_active = True
                else:
                    if mq_value > 400:  # Threshold untuk bau ringan
                        status = "⚠️ BAU RINGAN"
                    else:
                        status = "✅ BERSIH"
                    spray_active = False
                    
            except Exception as e:
                logger.error(f"❌ Error prediksi AI: {e}")
                # Fallback ke rule-based
                if mq_value > 700:
                    status = "⚠️ BAU TINGGI - PENYEMPROTAN AKTIF"
                    spray_active = True
                    prediction = 1
                    confidence = 0.95
                elif mq_value > 400:
                    status = "⚠️ BAU RINGAN"
                    spray_active = False
                    prediction = 0
                    confidence = 0.85
                else:
                    status = "✅ BERSIH"
                    spray_active = False
                    prediction = 0
                    confidence = 0.90
        else:
            # Fallback jika model tidak tersedia
            if mq_value > 700:
                status = "⚠️ BAU TINGGI - PENYEMPROTAN AKTIF"
                spray_active = True
                prediction = 1
                confidence = 0.95
            elif mq_value > 400:
                status = "⚠️ BAU RINGAN"
                spray_active = False
                prediction = 0
                confidence = 0.85
            else:
                status = "✅ BERSIH"
                spray_active = False
                prediction = 0
                confidence = 0.90

        # Simpan data terbaru
        current_time = datetime.now()
        waktu_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        global latest_data
        latest_data = {
            "gas_level": mq_value,
            "temperature": temperature,
            "humidity": humidity,
            "status": status,
            "time": waktu_str,
            "spray_active": spray_active,
            "prediction": int(prediction),
            "confidence": confidence
        }

        logger.info(f"[{waktu_str}] MQ: {mq_value}, Suhu: {temperature}°C, Humidity: {humidity}% → {status}")

        # Response untuk ESP32 - format yang diharapkan Arduino
        response_message = "BAU TERDETEKSI" if spray_active else "AMAN"
        
        return jsonify({
            "status": "success", 
            "message": response_message,
            "prediction": int(prediction),
            "spray_active": spray_active,
            "timestamp": waktu_str
        })

    except Exception as e:
        logger.error(f"⚠️ Error processing data: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500

# =========================
# 🌐 Endpoint untuk web interface
# =========================
@app.route('/latest', methods=['GET'])
def get_latest():
    """Endpoint untuk mengambil data terbaru (digunakan web interface)"""
    return jsonify(latest_data)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "SIGETA Flask Server",
        "model_loaded": model is not None,
        "latest_data_time": latest_data.get("time", "N/A"),
        "timestamp": datetime.now().isoformat()
    })

# =========================
# 🌐 Serve HTML Page
# =========================
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# =========================
# 🚀 Inisialisasi dan Jalankan Server
# =========================
def initialize_server():
    """Inisialisasi server"""
    app.start_time = time.time()
    logger.info("🚀 SIGETA Flask Server diinisialisasi")

if __name__ == '__main__':
    initialize_server()
    
    # Jalankan server
    print("=" * 60)
    print("🚀 SIGETA - Sistem IoT Gas Effectiveness Tawas")
    print("📡 Server Flask dengan AI Deteksi Bau")
    print("📍 Running on http://0.0.0.0:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
else:
    # Untuk Vercel deployment
    initialize_server()