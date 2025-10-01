# air_quality.py 
# reads sensor data from enviro+ board 
# Author: Lily Stacey
# Last Update: 18/09/2025

import logging 
import time 
import st7735 
import math 
import paramiko
import json

from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoBold as UserFont
from bme280 import BME280
from smbus2 import SMBus
from enviroplus import gas 

try:
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError: 
    import ltr559

# Sensing Resistance Values for Gas conversion
R0_OXIDISING = 200000  
R0_REDUCING = 150000 
R0_NH3 = 570000    

# Logging Config
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S")

logging.info(""" air_quality.py - Read Data from Enviro+ Sensors  
             Press ctrl+c to exit""") 

# Init LCD 
disp = st7735.ST7735( 
    port = 0, 
    cs = 1, 
    dc = "GPIO9",
    backlight = "GPIO12",
    rotation = 270, 
    spi_speed_hz = 10000000
)

disp.begin()

# write_temp_to_lcd: writes temperature measurements to LCD 
# input: temperature: the current temperature sensor reading 
# return: none 
def write_temp_to_lcd(temperature): 
    img = Image.new('RGB', (disp.width, disp.height), color = (0, 0, 0))
    draw = ImageDraw.Draw(img)
    rect_colour = (0, 180, 180)
    draw.rectangle((0, 0, 160, 80), rect_colour)

    bus = SMBus(1)
    bme280 = BME280(i2c_dev=bus)

    font_size = 18 
    font = ImageFont.truetype(UserFont, font_size)

    colour = (225, 225, 225)
    disp_temperature = "Temp: {:.2f} *C".format(temperature())

    x = 0 
    y = 0 
    draw.text((x, y), temperature, font = font, fill = colour)
    disp.display(img)

# get_cpu_temperature: gets cpu temp for temperature compensation 
# Input: none 
# Output: CPU Temperature 
def get_cpu_temperature(): 
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f: 
        temp = f.read()
        temp = int(temp) / 1000
    return temp

# get_compensate_temperature: temperature compensation 
# Input: none 
# Output: compensated temperature 
def compensate_temperature(): 
    factor = 2.25
    cpu_temps = [get_cpu_temperature()] * 5
    cpu_temp = get_cpu_temperature()
    cpu_temps = cpu_temps[1:] + [cpu_temp]
    avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
    raw_temp = bme280.get_temperature()
    comp_temp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
    return comp_temp

# get_sensor_data: reads data from all enviro+ sensors 
# input: none
# output: a dict containing sensor readings linked with the measurement type 
def get_sensor_data(): 
    temperature = compensate_temperature() 
    gas_readings = gas.read_all()
    pressure = bme280.get_pressure()
    humidity = bme280.get_humidity
    lux = ltr559.get_lux()

    try: 
        raw_oxidising = gas_readings.reducing()
        raw_reducing = gas_readings.reducing()
        raw_nh3 = gas_readings.nh3()

        ratio_oxidising = raw_oxidising / R0_OXIDISING
        ratio_reducing = raw_reducing / R0_REDUCING
        ratio_nh3 = raw_nh3 / R0_NH3

        if ratio_oxidising > 0: 
            ppm_oxidising = math.pow(10, math.log10(ratio_oxidising) - 0.8129)
        else:
            ppm_oxidising = 0

        if ratio_reducing > 0: 
            ppm_reducing = math.pow(10, (-1.25 * math.log10(ratio_reducing)) + 0.64)
        else:
            ppm_reducing = 0

        if ratio_nh3 > 0: 
            ppm_nh3 = math.pow(10, (-1.8 * math.log10(ration_nh3)) - 0.163)
        else: 
            ppm_nh3 = 0

        data = { "Temperature": temperature, 
            "Reducing Gas": ppm_reducing, 
            "Oxidizing Gas": ppm_oxidising, 
            "Nh3": ppm_nh3, 
            "Pressure": pressure, 
            "Humidity": humidity, 
            "Light": lux
    }
    except (TypeError, ValueError):         
        data = { "Temperature": temperature, 
            "Reducing Gas": gas_readings.reducing(), 
            "Oxidizing Gas": gas_readings.oxidising(), 
            "Nh3": gas_readings.nh3(), 
            "Pressure": pressure, 
            "Humidity": humidity, 
            "Light": lux
    }
    return data

# currently a test function for sending data 
def send_data(data): 
    if data is None: 
        return False 
    
    try: 
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(hostname = SSH_HOST, username = SSH_USER, key_filename = SSH_KEY_PATH) 

        sftp = client.open_sftp()
        
        json_data = json.dumps(data)
        with sftp.open(REMOTE_FILE_PATH, 'w') as f: 
            f.write(json_data)
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

# Main Loop
try: 
    while True:
        data = get_sensor_data()
        # Send Data Here <To Do>
        write_temp_to_lcd(data["temperature"])
except KeyboardInterrupt:
    disp.set_backlight(0)