import requests

import logging 

import st7735  
from fonts.ttf import RobotoMedium as UserFont
from PIL import Image, ImageDraw, ImageFont

def get_public_ip():
    """Fetches the public IP address of the machine."""
    try:
        response = requests.get("https://api.ipify.org") # or "https://checkip.amazonaws.com"
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error getting public IP: {e}"

public_ip = get_public_ip()
print(f"Your Public IP Address: {public_ip}")

logging.basicConfig(format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", 
        level = logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S")
logging.info(f"Your Public IP Address: {public_ip}")

# Display the public IP address on a small TFT display

disp = st7735.ST7735(
    port=0,
    cs=1,
    dc="GPI09", 
    backlight="GPI012",
    rotation=270,
    spi_speed_hz = 10000000
    )

# Initialize the display
disp.begin()

WIDTH = disp.width
HEIGHT = disp.height

# Create a new image with a white background
image = Image.new("RGB", (WIDTH, HEIGHT), "white")
draw = ImageDraw.Draw(image)

# text configuration
font_size = 25
font = ImageFont.truetype(UserFont, 20)
text_color = (255, 225, 225)  
back_colour = (0, 170, 170)

message = f"Public IP: {public_ip}"
text_width, text_height = draw.textsize(message, font=font)

# Calculate text position to center it
text_x = (WIDTH - text_width) // 2
text_y = (HEIGHT - text_height) // 2    

# Draw the text on the image
draw.rectangle([0, 0, WIDTH, HEIGHT], fill=back_colour)
draw.text((text_x, text_y), message, font=font, fill=text_color)       

try: 
    while True:
        pass
except KeyboardInterrupt:
    logging.info("Exiting on keyboard interrupt.")  