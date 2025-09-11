
import logging 
import time 

from bme280 import BME280
from smbus2 import SMBus


logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S")


bus = SMBus(1)
bme280 = BME280(i2c_dev=bus)



def get_cpu_temperature(): 
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f: 
        temp = f.read()
        temp = int(temp) / 1000
    return temp

factor = 2.25

cpu_temps = [get_cpu_temperature()] * 5 

while true: 
    cpu_temp = get_cpu_temperature()
    cpu_temps = cpu_temps[1:] + [cpu_temp]
    avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
    raw_temp = bme280.get_temperature()
    comp_temp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
    logging.info(f"Compensated temperature: {comp_temp:05.2f} °C")
    time.sleep(1.0)