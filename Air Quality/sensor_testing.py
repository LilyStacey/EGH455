import time
import json
import paramiko
import ST7735
from PIL import Image, ImageDraw, ImageFont

from bme280 import BME280
from ltr559 import LTR559
from pms5003 import PMS5003, ReadTimeoutError, SerialTimeoutError

# Initialize the sensors
try:
    bme280 = BME280()
except:
    print("BME280 sensor not found. Please check your Enviro+ board.")
    exit()

try:
    ltr559 = LTR559()
except:
    print("LTR559 sensor not found. Please check your Enviro+ board.")
    exit()

try:
    pms5003 = PMS5003()
except:
    print("PMS5003 sensor not found. Please check your Enviro+ board or connection.")

# Initialize the LCD screen
disp = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rst=11,
    rotation=270,
    spi_speed_hz=10000000
)

disp.begin()

# Create a new image and drawing object
WIDTH = disp.width
HEIGHT = disp.height
img = Image.new('RGB', (WIDTH, HEIGHT))
draw = ImageDraw.Draw(img)

# Load fonts for the display
font_size = 20
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)

# SSH Configuration
SSH_HOST = "your_server_ip_or_hostname"
SSH_USER = "your_username"
SSH_KEY_PATH = "/home/pi/.ssh/id_rsa" # Path to your private key
REMOTE_FILE_PATH = "/var/www/html/sensor_data.json" # Path on the remote server

def read_sensor_data():
    """
    Reads data from all available sensors.
    Returns a dictionary of sensor values.
    """
    try:
        temperature = bme280.get_temperature()
        pressure = bme280.get_pressure()
        humidity = bme280.get_humidity()

        lux = ltr559.get_lux()
        prox = ltr559.get_proximity()

        try:
            pms_data = pms5003.read()
            pm2_5 = pms_data.pm_2_5
            pm10 = pms_data.pm_10
        except (ReadTimeoutError, SerialTimeoutError):
            print("PMS5003 read failed, skipping this reading.")
            pm2_5 = None
            pm10 = None

        data = {
            "temperature": round(temperature, 2),
            "pressure": round(pressure, 2),
            "humidity": round(humidity, 2),
            "lux": round(lux, 2),
            "proximity": prox,
            "pm2_5": pm2_5,
            "pm10": pm10,
            "timestamp": int(time.time())
        }
        return data

    except Exception as e:
        print(f"An error occurred while reading sensors: {e}")
        return None

def display_temperature_on_lcd(temp):
    """
    Clears the LCD and displays the temperature value.
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), "black")
    
    label = "Temperature:"
    temp_str = f"{temp}°C"

    label_size = draw.textbbox((0, 0), label, font=font_small)
    temp_size = draw.textbbox((0, 0), temp_str, font=font)
    
    label_x = (WIDTH - label_size[2]) // 2
    label_y = (HEIGHT // 2) - 30
    temp_x = (WIDTH - temp_size[2]) // 2
    temp_y = (HEIGHT // 2) - (temp_size[3] // 2) + 10

    draw.text((label_x, label_y), label, font=font_small, fill="white")
    draw.text((temp_x, temp_y), temp_str, font=font, fill="white")
    
    disp.display(img)

def send_data_via_ssh(data):
    """
    Connects to the remote server via SSH and sends the data.
    This example writes the data to a file on the remote server.
    """
    if data is None:
        print("No data to send.")
        return False
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"Connecting to {SSH_HOST} as {SSH_USER}...")
        client.connect(hostname=SSH_HOST, username=SSH_USER, key_filename=SSH_KEY_PATH)
        
        sftp = client.open_sftp()
        
        # Write the JSON data to a file on the remote server
        json_data = json.dumps(data)
        with sftp.open(REMOTE_FILE_PATH, 'w') as f:
            f.write(json_data)
        
        print(f"Data successfully written to {REMOTE_FILE_PATH} on remote server.")
        
        sftp.close()
        client.close()
        return True

    except paramiko.AuthenticationException:
        print("Authentication failed. Please check your SSH key and username.")
        return False
    except paramiko.SSHException as ssh_err:
        print(f"SSH error occurred: {ssh_err}")
        return False
    except Exception as e:
        print(f"Failed to send data over SSH: {e}")
        return False

# Main loop
try:
    while True:
        sensor_data = read_sensor_data()
        
        if sensor_data:
            display_temperature_on_lcd(sensor_data.get("temperature"))
            print("Attempting to send data via SSH...")
            send_data_via_ssh(sensor_data)
        
        time.sleep(300) # 5 minutes
except KeyboardInterrupt:
    print("\nScript terminated by user.")
    draw.rectangle((0, 0, WIDTH, HEIGHT), "black")
    disp.display(img)