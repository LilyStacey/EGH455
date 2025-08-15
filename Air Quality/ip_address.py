import socket
import subprocess
import ST7735

def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to an external host (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            IP = s.getsockname()[0]
        except Exception:
            IP = "N/A"
        finally:
            s.close()
        return IP
def get_ip_from_cmd():
    cmd = "ip addr show eth0 | grep inet | awk '{print $2}' | cut -d/ -f1"
    try:
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        return output
    except subprocess.CalledProcessError:
        return "N/A"
        
# Initialize the display (adjust pins and settings as per your setup)
disp = ST7735.ST7735(
    port=0,
    cs=ST7735.BG_SPI_CS_FRONT,  # or other CS pin
    dc=9,  # or other DC pin
    rst=10, # or other RST pin
    width=128,
    height=160, # or 80 for 0.96" display
    rotation=90, # Adjust for your display orientation
    spi_speed_hz=4000000
    )
disp.begin()

# Clear the display
disp.clear()
# Get the IP address
ip_address = get_local_ip() # or get_ip_from_cmd()

# Display the IP address
disp.draw_text((10, 10), "IP Address:", disp.WHITE)
disp.draw_text((10, 30), ip_address, disp.WHITE)

# You might want to update this periodically in a loop