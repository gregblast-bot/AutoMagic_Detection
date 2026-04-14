import asyncio
import struct
import time
import cv2
import numpy as np
import easyocr
import google.generativeai as genai
from bleak import BleakScanner, BleakClient

# --- CONFIGURATION ---
TARGET_DEVICE_NAME = "Nano33BLE"
# Using your existing UUIDs from the previous snippet
TARGET_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
CHAR_SPEECH_READ = "00002a37-0000-1000-8000-00805f9b34fb"
CHAR_COLOR_WRITE = "f0001111-0451-4000-b000-000000000000"
CHAR_METRICS = "f0002222-0451-4000-b000-000000000000"
# NEW: Characteristic for raw image bytes (Ensure this matches your Arduino code)
CHAR_IMAGE_DATA = "f0003333-0451-4000-b000-000000000000"

IMAGE_WIDTH = 96
IMAGE_HEIGHT = 96

# --- INITIALIZATION ---
try:
    with open("GeminiAPIKey/APIKey.txt", "r") as f:
        genai.configure(api_key=f.read().strip())
except FileNotFoundError:
    print("API Key file not found. Gemini features will fail.")

model = genai.GenerativeModel(model_name="gemini-2.0-flash")
reader = easyocr.Reader(['en']) # Initialize OCR once to save time

latest_user_response = None

# --- OCR & IMAGE PROCESSING ---
async def process_ocr_capture(client):
    """Reads raw bytes from Arduino, converts to image, and runs OCR."""
    print("\n[OCR] Person detected! Requesting image buffer...")
    
    total_bytes = IMAGE_WIDTH * IMAGE_HEIGHT
    image_buffer = bytearray()

    try:
        # We read in a loop because BLE packets are smaller than the full image
        while len(image_buffer) < total_bytes:
            chunk = await client.read_gatt_char(CHAR_IMAGE_DATA)
            if not chunk: break
            image_buffer.extend(chunk)
            print(f"[OCR] Transferring: {len(image_buffer)}/{total_bytes} bytes", end='\r')

        print("\n[OCR] Image Received. Analyzing...")
        
        # Convert to OpenCV format
        img_np = np.frombuffer(image_buffer, dtype=np.uint8).reshape((IMAGE_HEIGHT, IMAGE_WIDTH))
        
        # Pre-processing for better OCR: Upscale and Threshold
        img_resized = cv2.resize(img_np, (384, 384), interpolation=cv2.INTER_CUBIC)
        _, img_bin = cv2.threshold(img_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Execute EasyOCR
        results = reader.readtext(img_bin)
        
        if results:
            full_text = " ".join([res[1] for res in results])
            print(f"[OCR RESULT] Text found: {full_text}")
            return full_text
        else:
            print("[OCR RESULT] No text found.")
            return None

    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return None

# --- BLE CALLBACKS ---
def notification_handler(sender, data):
    global latest_user_response
    decoded = data.decode('utf-8').strip()
    latest_user_response = decoded
    print(f"[Arduino Notify] {decoded}")

# --- MAIN LOOP ---
async def main():
    print("Searching for Nano 33 BLE...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name and TARGET_DEVICE_NAME in d.name
    )

    if not device:
        print("Device not found.")
        return

    async with BleakClient(device) as client:
        print(f"Connected to {device.name}")
        
        # Start Notifications
        await client.start_notify(CHAR_SPEECH_READ, notification_handler)

        while True:
            # We use latest_user_response to trigger different modes
            if latest_user_response:
                cmd = latest_user_response
                
                if "PersonDetected" in cmd:
                    # Trigger the OCR pipeline
                    detected_text = await process_ocr_capture(client)
                    
                    if detected_text:
                        # Feed the OCR text to Gemini for "intelligence"
                        prompt = f"The camera saw a person holding a sign that says: '{detected_text}'. Respond with a short, witty comment about this."
                        response = await asyncio.to_thread(model.generate_content, prompt)
                        print(f"Gemini: {response.text}")
                
                # Clear flag after processing
                global latest_user_response
                latest_user_response = None
            
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    import random
    asyncio.run(main())