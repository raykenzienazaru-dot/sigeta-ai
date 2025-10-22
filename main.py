from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import numpy as np
from sklearn.linear_model import LogisticRegression
import os

app = Flask(__name__)
CORS(app)

# =========================
# 🧠 Mini AI Model
# =========================
X_train = np.array([
    [200, 28, 60],   # Aman
    [300, 30, 70],   # Aman
    [800, 32, 85],   # Bau
    [750, 29, 82],   # Bau
    [500, 27, 75],   # Aman
])
y_train = np.array([0, 0, 1, 1, 0])  # 0 = Aman, 1 = Bau

model = LogisticRegression()
model.fit(X_train, y_train)

# Simpan data terakhir dari ESP32
latest_data = {"mq": 0, "temperature": 0, "humidity": 0, "status": "Belum ada data", "time": ""}

# =========================
# 🌐 Endpoint menerima data dari ESP32
# =========================
@app.route('/data', methods=['POST'])
def receive_data():
    try:
        data = request.get_json(force=True)
        mq = float(data.get("mq", 0))
        temperature = float(data.get("temperature", 0))
        humidity = float(data.get("humidity", 0))

        # Prediksi AI
        prediction = model.predict([[mq, temperature, humidity]])[0]
        status = "⚠️ BAU TERDETEKSI" if prediction == 1 else "✅ AMAN"

        # Simpan waktu dan data
        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        global latest_data
        latest_data = {
            "mq": mq,
            "temperature": temperature,
            "humidity": humidity,
            "status": status,
            "time": waktu
        }

        print(f"[{waktu}] 🌡 Temp: {temperature}, 💧 Hum: {humidity}, 💨 MQ: {mq} → {status}")

        return jsonify({"status": "ok", "message": status, "timestamp": waktu})
    except Exception as e:
        print("⚠️ Error:", e)
        return jsonify({"status": "error", "message": str(e)})

# =========================
# 🌐 Endpoint ambil data terbaru
# =========================
@app.route('/latest', methods=['GET'])
def get_latest():
    return jsonify(latest_data)

# =========================
# 🌐 Route tampilkan halaman web
# =========================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# =========================
# 🚀 Jalankan server
# =========================
if __name__ == '__main__':
    print("🚀 Server Flask dengan AI & web real-time dijalankan di http://localhost:5000")
    app.run(host='0.0.0.0', port=5000)
