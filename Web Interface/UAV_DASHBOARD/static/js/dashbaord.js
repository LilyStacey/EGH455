function showTab(tabId) {
    document.querySelectorAll('.tab').forEach(tab => tab.style.display = 'none');
    document.getElementById(tabId).style.display = 'block';
}

function toggleDarkLight() {
    document.body.classList.toggle('dark-mode');
    document.body.classList.toggle('light-mode');
}

// --- SENSOR CHARTS ---
let sensorHistory = { time: [], Temperature: [], Humidity: [], Pressure: [], Light: [], "Reducing Gas": [], "Oxidizing Gas": [], Nh3: [] };

const ctx = document.getElementById('chartsCanvas').getContext('2d');
const sensorChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: sensorHistory.time,
        datasets: [
            { label: 'Temperature (°C)', data: sensorHistory.Temperature, borderColor: 'red', fill: false },
            { label: 'Humidity (%)', data: sensorHistory.Humidity, borderColor: 'blue', fill: false },
            { label: 'Pressure (Pa)', data: sensorHistory.Pressure, borderColor: 'green', fill: false },
            { label: 'Light (lux)', data: sensorHistory.Light, borderColor: 'orange', fill: false },
            { label: 'Reducing Gas (ppm)', data: sensorHistory["Reducing Gas"], borderColor: 'purple', fill: false },
            { label: 'Oxidizing Gas (ppm)', data: sensorHistory["Oxidizing Gas"], borderColor: 'pink', fill: false },
            { label: 'NH3 (ppm)', data: sensorHistory.Nh3, borderColor: 'brown', fill: false }
        ]
    },
    options: {
        responsive: true,
        plugins: {
            legend: { position: 'bottom' },
            title: { display: true, text: 'Sensor Data Over Time' }
        },
        scales: { x: { display: true }, y: { display: true } }
    }
});

// --- FETCH DATA ---
async function fetchSensorData() {
    const res = await fetch('/api/sensor');
    const data = await res.json();
    document.getElementById('sensor-data').innerText = JSON.stringify(data, null, 2);

    const time = new Date().toLocaleTimeString();
    sensorHistory.time.push(time);
    for (let key in sensorHistory) {
        if (key !== 'time') sensorHistory[key].push(data[key] || 0);
    }
    if (sensorHistory.time.length > 30) {
        sensorHistory.time.shift();
        for (let key in sensorHistory) { if (key !== 'time') sensorHistory[key].shift(); }
    }
    sensorChart.update();
}

async function fetchCamera() {
    const res = await fetch('/api/camera');
    const data = await res.json();
    if(data.image) document.getElementById('live-feed').src = data.image + "?t=" + new Date().getTime();
}

async function fetchLogs() {
    const res = await fetch('/api/logs');
    const files = await res.json();
    const list = document.getElementById('log-list');
    list.innerHTML = '';
    files.forEach(file => { const li = document.createElement('li'); li.textContent = file; list.appendChild(li); });
}

// --- INTERVALS ---
setInterval(fetchSensorData, 2000);
setInterval(fetchCamera, 5000);
setInterval(fetchLogs, 10000);
