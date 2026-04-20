import asyncio
from bleak import BleakScanner, BleakClient
import numpy as np
from PIL import Image
import time

# Target device settings
TARGET_DEVICE_NAME = "Nano33BLE"
TARGET_SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
TARGET_CHARACTERISTIC_UUID_READ = "19b10001-e8f2-537e-4f6c-d104768a1214"
TARGET_CHARACTERISTIC_UUID_METRICS = "19b10002-e8f2-537e-4f6c-d104768a1214"

# Image dimensions (96x96 grayscale)
WIDTH, HEIGHT = 96, 96
EXPECTED_SIZE = WIDTH * HEIGHT

# Maximum number of retry attempts and delay in seconds between retries.
MAX_RETRIES = 3 
RETRY_DELAY = 1 
# Global buffer to store incoming image chunks
image_buffer = bytearray()
# Global variable to store BLE round-trip start time
ble_round_trip_start_time = None
# Add a timestamp to track the last received chunk
last_packet_time = time.time()

# Asynchronous method for finding the characteristic for some bluetooth service.
async def find_characteristic(client, service_uuid, characteristic_uuid, property_name):
    for service in client.services:
        if service.uuid == service_uuid:
            for char in service.characteristics:
                if char.uuid == characteristic_uuid and property_name in char.properties:
                    return char
    return None

# Asynchronous method for finding the latency for wake word detection and BLE write.
async def handle_metrics(characteristic, data):
    metric = data.decode('utf-8').strip()
    print(f"Received metric: {metric}")
    if metric.startswith("ble_write_latency:"):
        latency = float(metric.split(":")[1])
        print(f"BLE write latency (Arduino->Server): {latency:.2f} ms")
        global ble_round_trip_start_time
        if ble_round_trip_start_time is not None:
            round_trip_time = (asyncio.get_event_loop().time() - ble_round_trip_start_time) * 1000
            print(f"BLE round-trip latency: {round_trip_time:.2f} ms")
            ble_round_trip_start_time = None # Reset

# Asynchronous method for finding the characteristic for some bluetooth service
async def handle_user_input(command_characteristic, data):
    # Decode and remove any whitespace.
    user_response = data.decode('utf-8').strip()
    print(f"Arduino responded: {user_response}")

    # This global variable is a simple way of interacting with the game logic.
    global latest_user_response 
    latest_user_response = user_response

def process_and_save_image(raw_bytes):
    """Converts int8 raw bytes to a viewable PNG image."""
    if len(raw_bytes) != (HEIGHT * WIDTH):
        print(f"Error: Received {len(raw_bytes)} bytes, expected 9216")
        return

    # Convert to signed int8 numpy array
    raw_array = np.frombuffer(raw_bytes, dtype=np.int8)
    
    # Normalize: Shift -128...127 to 0...255 for standard grayscale
    normalized = (raw_array.astype(np.int16) + 128).astype(np.uint8)
    
    # Reshape and save
    img_array = normalized.reshape((HEIGHT, WIDTH))
    img = Image.fromarray(img_array, mode='L')
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"capture_{timestamp}.png"
    img.save(filename)
    print(f"\n[SUCCESS] Image saved as {filename}")

def notification_handler(sender, data):
    global image_buffer
    image_buffer.extend(data)
    
    # If we accidentally get more than one frame's worth (e.g., from a previous crash)
    if len(image_buffer) > EXPECTED_SIZE:
        print("\n[WARNING] Buffer overflow, clearing for fresh frame.")
        image_buffer.clear()
        return

    progress = (len(image_buffer) / EXPECTED_SIZE) * 100
    print(f"Receiving: {progress:.1f}%", end='\r')

    if len(image_buffer) == EXPECTED_SIZE:
        process_and_save_image(image_buffer)
        image_buffer.clear()

async def main():
    print("Scanning for devices...")
    target_device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name and TARGET_DEVICE_NAME in d.name
    )

    if not target_device:
        print("Device not found. Make sure the Arduino is on and advertising.")
        return

    print(f"Found {target_device.name} at {target_device.address}. Connecting...")

    async with BleakClient(target_device, timeout=30.0, mtu_size=512) as client:
        print(f"Connected: {client.is_connected}")

        read_characteristic = None
        metrics_characteristic = None
        retries = 0
        found_all = False

        # Check for services and characteristics.
        while retries < MAX_RETRIES and not found_all:
            try:
                # Force a refresh of the service cache
                await client.get_services()
                
                # Search the entire client service tree at once
                read_characteristic = await find_characteristic(client, TARGET_SERVICE_UUID, TARGET_CHARACTERISTIC_UUID_READ, "notify")
                metrics_characteristic = await find_characteristic(client, TARGET_SERVICE_UUID, TARGET_CHARACTERISTIC_UUID_METRICS, "notify")

                if read_characteristic and metrics_characteristic:
                    print("Found all required characteristics.")
                    found_all = True
                else:
                    retries += 1
                    print(f"Attempt {retries}: Characteristics not found yet. Retrying...")
                    await asyncio.sleep(RETRY_DELAY)

            except Exception as e:
                print(f"Error during characteristic discovery: {e}")
                retries += 1
                await asyncio.sleep(RETRY_DELAY)

        if not read_characteristic:
            print(f"Failed to find readable command characteristic after {MAX_RETRIES} retries.")
            return
        if not metrics_characteristic:
            print(f"Failed to find notifyable metrics characteristic after {MAX_RETRIES} retries.")
            return

        # Start notifications for the image characteristic
        await client.start_notify(TARGET_CHARACTERISTIC_UUID_READ, notification_handler)
        print("Listening for detection events... (Press Ctrl+C to stop)")

        try:
            while True:
                # Keep the connection alive
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await client.stop_notify(TARGET_CHARACTERISTIC_UUID_READ)
            print("Disconnected.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass