from flask import Flask, render_template, jsonify # type: ignore
import random

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/sensor_data')
def sensor_data():
    data = {
        'temperature': round(random.uniform(20.0, 30.0), 1),
        'pressure': round(random.uniform(990.0, 1020.0), 1),  # hPa
        'humidity': round(random.uniform(30.0, 70.0), 1),
        'ambient_light': round(random.uniform(100.0, 1000.0), 1),  # lux
        'gas_co2': round(random.uniform(400, 800), 0),  # ppm
        'gas_voc': round(random.uniform(0, 500), 0)  # ppb or similar
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)

