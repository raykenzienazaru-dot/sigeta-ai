import requests

url = "http://127.0.0.1:5000/data"  # endpoint sesuai app.py
data = {
    "mq": 750,          # ubah nilai simulasi
    "temperature": 29,  # suhu
    "humidity": 85      # kelembapan
}

response = requests.post(url, json=data)
print(response.json())
