# Implements the drilling mechanism
# Author: Andrew Kennard
# Last Update: 11/10/2025 by Andrew Kennard

from gpiozero import Servo
from time import sleep

servo = Servo(13)

# TODO: Set the extension and retraction durations to 4.2 seconds for 3 rotations (30 mm) if testing shows it is viable.
#  The drill is designed to function with a travel of 30 mm (25 mm of ground penetration), but due to tolerance issues,
#  the drill could fall out. The drill should be tested with the longer travel, and if it works we can keep it.

# Durations to extend and retract by 2.5 rotations (25 mm) each way
extension_duration = 3.5 # seconds
retraction_duration = 3.5 # seconds

def perform_drilling():
    # Extend drill
    servo.value = 1
    sleep(extension_duration)

    # Wait for a second
    servo.value = 0
    sleep(1)

    # Retract drill
    servo.value = -1
    sleep(retraction_duration)

    # Stop the drill
    servo.value = 0

    # TODO: Should we notify something that the drilling was successful (like web server)?