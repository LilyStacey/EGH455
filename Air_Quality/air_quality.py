# air_quality.py 
# reads sensor data from enviro+ board 
# Author: Lily Stacey
# Last Update: 09/10/2025

import asyncio
import math
import time 
import threading
from typing import Optional

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

# Sensing Resistance Values for Gas conversion
R0_OXIDISING = 200000  
R0_REDUCING = 150000 
R0_NH3 = 570000    

class AirQualityTask:
    def __init__(
            self, 
            loop: asyncio.AbstractEventLoop,
            stop_event: asyncio.Event,
            results_q: Optional[asyncio.Queue] = None ):
        
        self.loop = loop
        self.stop_flag = threading.Event()
        self.inited = False
        self.stop_event = stop_event or asyncio.Event()
        self.results_q = results_q 
        self.cap = None

        self.disp = st7735.ST7735(
            port = 0, 
            cs = 1, 
            dc = "GPIO9", 
            backlight = "GPIO12", 
            rotation = 270, 
            spi_speed_hz = 10000000
        )

        self.disp.begin()

        self.bus = SMBus(1)
        self.bme280 = BME280(i2c_dev = self.bus)

    # get_cpu_temperature: gets cpu temp for temperature compensation 
    # Input: none 
    # Output: CPU Temperature  
    def get_cpu_temperature(self) -> float: 
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read())/ 1000
                return temp
        except Exception:
            return 0.0

    # get_compensate_temperature: temperature compensation 
    # Input: none 
    # Output: compensated temperature 
    def compensate_temperature(self) -> float: 
        factor = 2.25 
        cpu_temps = [self.get_cpu_temperature()] * 5
        cpu_temp = self.get_cpu_temperature()
        cpu_temps = cpu_temps[1:] + [cpu_temp]
        avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
        raw_temp = self.bme280.get_temperature()
        comp_temp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
        return comp_temp
    
    # get_sensor_data: reads data from all enviro+ sensors 
    # input: none
    # output: a dict containing sensor readings linked with the measurement type 
    def get_sensor_data(self) -> dict: 
        temperature = self.compensate_temperature() 
        gas_readings = gas.read_all()
        pressure = self.bme280.get_pressure()
        humidity = self.bme280.get_humidity()
        lux = ltr559.get_lux() if hasattr(ltr559, "get_lux") else None

        try: 
            raw_oxidising = gas_readings.oxidising()
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
                ppm_nh3 = math.pow(10, (-1.8 * math.log10(ratio_nh3)) - 0.163)
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

    # write_temp_to_lcd: writes temperature measurements to LCD 
    # input: temperature: the current temperature sensor reading 
    # return: none 
    def write_temp_to_lcd(self, temperature: float): 
        img = Image.new('RGB', (self.disp.width, self.disp.height), color = (0, 0, 0))
        draw = ImageDraw.Draw(img)
        rect_colour = (0, 180, 180)
        draw.rectangle((0, 0, 160, 80), rect_colour)

        font_size = 18 
        font = ImageFont.truetype(UserFont, font_size)

        colour = (225, 225, 225)
        disp_temperature = "Temp: {:.2f} *C".format(temperature)

        x = 0 
        y = 0 
        draw.text((x, y), disp_temperature, font = font, fill = colour)
        self.disp.display(img)

    async def step(self): 
        if self.stop_event.is_set():
            return
        data = await asyncio.to_thread(self.get_sensor_data)
        await asyncio.to_thread(self.write_temp_to_lcd, data["Temperature"])

        if self.results_q: 
            try: 
                self.results_q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    def __enter__(self):
        return self 

    def __exit__(self, exc_type, exc_val, exc_tb): 
        self.shutdown()
        if hasattr(self, 'bus'): 
            self.bus.close()

    def shutdown(self):
        try:
            self.disp.set_backlight(0)
        except Exception:
            pass 
