# air_quality.py 
# reads sensor data from enviro+ board 
# Author: Lily Stacey
# Last Update: 12/09/2025

import logging 
import time 
import st7735 

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

# Logging Config
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S")

logging.info(""" air_quality.py - Read Data from Enviro+ Sensors 
             
             Press ctrl+c to exit""") 

# LCD Config
disp = st7735.ST7735( 
    port = 0, 
    cs = 1, 
    dc = "GPIO9", 
    backlight = "GPIO12", 
    rotation = 270, 
    spi_speed_hz = 10000000
)

disp.begin()
img = Image.new('RGB', (disp.width, disp.height), color = (0, 0, 0))
draw = Image.Draw(img)
rect_colour = (0, 180, 180)
draw.rectangle((0, 0, 160, 80), rect_colour)

bus = SMBus(1)
bme280 = BME280(i2c_dev=bus)

font_size = 18 
font = ImageFont.truetype(UserFont, font_size)

colour = (225, 225, 225)
temperature = "Temp: {:.2f} *C".format(bme280.get_temperature())

x = 0 
y = 0 
draw.text((x, y), temperature, font = font, fill = colour)
disp.display(img)

gas.enable_adc()
gas.set_adc_gain(4.096)

# get_cpu_temperature: gets cpu temp for temperature compensation 
def get_cpu_temperature(): 
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f: 
        temp = f.read()
        temp = int(temp) / 1000
    return temp

factor = 2.25

cpu_temps = [get_cpu_temperature()] * 5 

while True: 
    cpu_temp = get_cpu_temperature()
    cpu_temps = cpu_temps[1:] + [cpu_temp]
    avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
    raw_temp = bme280.get_temperature()
    comp_temp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
    readings = gas.read_all()
    logging.info(readings)
    pressure = bme280.get_pressure()
    humidity = bme280.get_humidity()
    lux = ltr559.get_lux()
    logging.info(f"""Compenstated Temperature: {comp_temp:05.2f} °C
                 Pressure: {pressure:05.2f} hPa
                 Relative Humidity: {humidity:05.2f} %
                Light: {lux:05.02f} Lux """)
    logging.info(readings)
    time.sleep(1.0)