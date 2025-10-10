## ip_address.py 
# This script displays the local and public IP address on a 0.96" LCD using the ST7735 driver.
# Author: Lily Stacey 
# Date: 2025-08-22

import logging
import socket 
import st7735
from fonts.ttf import RobotoMedium as UserFont
from PIL import Image, ImageDraw, ImageFont
import os 
import requests 

# Get IP address by reaching out to Google's public DNS server
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
public_ip = s.getsockname()[0]
s.close()

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S")

logging.info(""" ip_address.py
This script displays the local and public IP address on a 0.96" LCD using the ST7735 driver.
Press Ctrl+C to exit!
""")

# Create LCD class instance.
disp = st7735.ST7735(
    port=0,
    cs=1,
    dc="GPIO9",
    backlight="GPIO12",
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display.
disp.begin()

# Width and height to calculate text position.
WIDTH = disp.width
HEIGHT = disp.height

# New canvas to draw on.
img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)

# Text settings.
font_size = 15
font = ImageFont.truetype(UserFont, font_size)
text_colour = (255, 255, 255)
back_colour = (255, 0, 0)

#message = "IP: " + public_ip
message = "IP: " + public_ip

x1, y1, x2, y2 = font.getbbox(message)
size_x = x2 - x1
size_y = y2 - y1

# Calculate text position
x = (WIDTH - size_x) / 2
y = (HEIGHT / 2) - (size_y / 2)

# Draw background rectangle and write text.
draw.rectangle((0, 0, 160, 80), back_colour)
draw.text((x, y), message, font=font, fill=text_colour)
disp.display(img)

# Keep running.
try:
    while True:
        pass

# Turn off backlight on control-c
except KeyboardInterrupt:
    disp.set_backlight(0)
