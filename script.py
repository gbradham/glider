import smbus
import time

bus = smbus.SMBus(1)
address = 0x48

# Pointer registers
REG_CONVERSION = 0x00
REG_CONFIG = 0x01

print(f"Probing ADS1115 at 0x{address:02X}...")

try:
    # 1. Read the CONFIG register (What does the chip THINK it is doing?)
    # Default power-on value is usually 0x8583
    val = bus.read_i2c_block_data(address, REG_CONFIG, 2)
    config_val = (val[0] << 8) | val[1]
    print(f"Current Config Register: 0x{config_val:04X}")
    print(f"Binary: {config_val:016b}")

    # Check the OS bit (Bit 15 - the first bit)
    # 1 = Device is idle / Ready to start
    # 0 = Device is currently performing a conversion
    if (config_val >> 15) & 1:
        print("Status: IDLE (Ready)")
    else:
        print("Status: BUSY (Converting)")

    print("-" * 20)
    print("Attempting to force a read on A0...")

    # 2. Write configuration for A0 (Single Ended), +/- 4.096V, Single Shot
    # Binary: 1 (Start) 100 (A0) 001 (4V) 1 (Single) ...
    # Hex: 0xC383
    CONFIG_HI = 0xC3
    CONFIG_LO = 0x83
    bus.write_i2c_block_data(address, REG_CONFIG, [CONFIG_HI, CONFIG_LO])

    # Wait for conversion
    time.sleep(0.01)

    # 3. Read the Result
    val = bus.read_i2c_block_data(address, REG_CONVERSION, 2)
    raw_val = (val[0] << 8) | val[1]
    if raw_val > 32767:
        raw_val -= 65536
        
    print(f"Raw Value from A0: {raw_val}")

except Exception as e:
    print(f"Error: {e}")
