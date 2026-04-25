#include <Arduino_OV767X.h>

byte frame[160 * 120]; 
int bytesPerFrame;

void setup() {
  Serial.begin(115200);
  while (!Serial); 

  if (!Camera.begin(QQVGA, GRAYSCALE, 5)) { // 5 FPS internal clock
    while (1);
  }
  bytesPerFrame = Camera.width() * Camera.height();
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == 'c') {
      Camera.readFrame(frame);
      
      uint8_t* ptr = (uint8_t*)frame;
      int chunkSize = 2000; // Increased chunk size for slightly better FPS
      
      for (int i = 0; i < bytesPerFrame; i += chunkSize) {
        int toSend = min(chunkSize, bytesPerFrame - i);
        Serial.write(&ptr[i], toSend);
        Serial.flush(); 

        // Wait for 'n' (Next) from Python
        while (true) {
          if (Serial.available() > 0) {
            if (Serial.read() == 'n') break;
          }
        }
      }
    }
  }
}