import serial
import numpy as np
import cv2
import time

# Config
PORT = 'COM3'
BAUD = 115200
WIDTH, HEIGHT = 160, 120
EXPECTED_BYTES = WIDTH * HEIGHT # 19200
CHUNK_SIZE = 2000 # Matches Arduino chunkSize

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"Connected to {PORT}. Press 'q' in the image window to quit.")
    time.sleep(2)
except Exception as e:
    print(f"Error: {e}")
    exit()

def start_live_video():
    while True:
        # 1. Request new frame
        ser.write(b'c')
        raw_data = bytearray()
        
        # 2. Handshake loop to get the full frame
        while len(raw_data) < EXPECTED_BYTES:
            remaining = EXPECTED_BYTES - len(raw_data)
            to_read = min(CHUNK_SIZE, remaining)
            
            chunk = ser.read(to_read)
            if chunk:
                raw_data.extend(chunk)
                ser.write(b'n') # Signal for next chunk
            else:
                break # Timeout
        
        if len(raw_data) == EXPECTED_BYTES:
            # 3. Convert to image
            img = np.frombuffer(raw_data, dtype=np.uint8).reshape((HEIGHT, WIDTH))
            
            # 4. Center Crop to 96x96 (matches your AI model's input)
            start_x = (WIDTH - 96) // 2
            start_y = (HEIGHT - 96) // 2
            cropped = img[start_y:start_y+96, start_x:start_x+96]
            
            # 5. Display (Upscaled for visibility)
            display = cv2.resize(cropped, (384, 384), interpolation=cv2.INTER_NEAREST)
            cv2.imshow('Arduino AI Camera View', display)
        
        # Break loop on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    ser.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_live_video()