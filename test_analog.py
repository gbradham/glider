import asyncio
from telemetrix_aio import telemetrix_aio

async def the_callback(data):
    print(f"Pin: {data[1]}, Value: {data[2]}")

async def main():
    board = telemetrix_aio.TelemetrixAIO(autostart=False)
    await board.start_aio()

    # Set A0 (analog pin 0) as input
    await board.set_pin_mode_analog_input(0, differential=1, callback=the_callback)

    print("Monitoring A0 - connect 3.3V to see value change to ~675")
    print("Press Ctrl+C to quit")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await board.shutdown()

asyncio.run(main())