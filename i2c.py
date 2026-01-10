import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15.ads1x15 import Pin

# Initialize I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Create the ADS object
ads = ADS.ADS1115(i2c, data_rate=8)

# Gain = 1 sets the range to +/- 4.096V
ads.gain = 1 

# Connect the Yellow Grove wire to A2 on the ADS1115
chan = AnalogIn(ads, Pin.A0)

print("Reading Grove HCHO Sensor (WSP2110)...")
print("Ensure Sensor is powered by 5V!")

while True:
    voltage = chan.voltage
    
    # If voltage is near 0, the sensor is likely disconnected or unpowered
    if voltage < 0.01:
        status = "OFF/DISCONNECTED"
    else:
        status = "ACTIVE"

    print(f"HCHO Sensor: {voltage:.3f} V [{status}]")
    time.sleep(1)
