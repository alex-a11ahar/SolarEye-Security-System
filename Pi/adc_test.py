import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# Initialize the I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Create the ADS1115 ADC instance
ads = ADS.ADS1115(i2c)

# Set the gain (adjust based on your input voltage range)
ads.gain = 1  # Available options: 1, 2/3, 1, 2, 4, 8, 16

# Create single-ended input channels for A0 and A1
chan_a0 = AnalogIn(ads, ADS.P0)  # A0 corresponds to ADS.P0
chan_a1 = AnalogIn(ads, ADS.P1)  # A1 corresponds to ADS.P1

while True:
    # Read the voltage values
    voltage_a0 = chan_a0.voltage
    voltage_a1 = chan_a1.voltage
    print(f'Voltage at A0: {voltage_a0:.2f} V')
    print(f'Voltage at A1: {voltage_a1:.2f} V')
    time.sleep(1)