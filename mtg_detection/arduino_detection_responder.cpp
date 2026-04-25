/* Copyright 2022 The TensorFlow Authors. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================*/

#if defined(ARDUINO) && !defined(ARDUINO_ARDUINO_NANO33BLE)
#define ARDUINO_EXCLUDE_CODE
#endif  // defined(ARDUINO) && !defined(ARDUINO_ARDUINO_NANO33BLE)

#ifndef ARDUINO_EXCLUDE_CODE

#include <cmath>
#include "Arduino.h"
#include "detection_responder.h"
#include "tensorflow/lite/micro/micro_log.h"
#include "model_settings.h"
#include <ArduinoBLE.h>

// Use custom 128-bit UUIDs
//BLEService imageService("19B10000-E8F2-537E-4F6C-D104768A1214");
//BLECharacteristic imageCharacteristic("19B10001-E8F2-537E-4F6C-D104768A1214", BLERead | BLENotify, 64); // Characteristic UUID for read image ops
//BLEStringCharacteristic metricsCharacteristic("19B10002-E8F2-537E-4F6C-D104768A1214", BLERead | BLENotify, 50); // Define a characteristic for sending metrics
// Allocate a separate buffer so the Tensor Arena can't overwrite it
//int8_t snapshot_buffer[kNumRows * kNumCols];

// Flash the yellow (builtin) LED after each inference
void RespondToDetection(float mtg_score, float no_mtg_score, int8_t* image_data) {
  //static bool ble_setup_done = false;
  static bool is_initialized = false;

  // if (ble_setup_done){
  //   BLE.setAdvertisingInterval(32);
  //   BLE.advertise();
  //   delay(5);
  // }

  // if (!ble_setup_done) {
  //   if (!BLE.begin()) {
  //     return; // If BLE fails, don't keep trying to re-init
  //   }
  //   BLE.setLocalName("Nano33BLE"); // Using the same name as your speech project
  //   BLE.setAdvertisedService(imageService);
  //   imageService.addCharacteristic(imageCharacteristic);
  //   imageService.addCharacteristic(metricsCharacteristic);
  //   BLE.addService(imageService);
  //   BLE.advertise();
  //   ble_setup_done = true;
  //   MicroPrintf("BLE initialized and advertising...");
  // }

  if (!is_initialized) {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);
    // Pins for the built-in RGB LEDs on the Arduino Nano 33 BLE Sense
    pinMode(LEDR, OUTPUT);
    pinMode(LEDG, OUTPUT);
    pinMode(LEDB, OUTPUT);
    // Switch the LEDs off
    digitalWrite(LEDG, HIGH);
    digitalWrite(LEDB, HIGH);
    digitalWrite(LEDR, HIGH);
    is_initialized = true;
  }

  // Note: The RGB LEDs on the Arduino Nano 33 BLE
  // Sense are on when the pin is LOW, off when HIGH.

  // Switch on the green LED when a mtg is detected,
  // the blue when no mtg is detected
  if (mtg_score > no_mtg_score && mtg_score > 0.75f) {
    digitalWrite(LEDG, LOW);
    digitalWrite(LEDB, HIGH);

    // Only send the image if a mtg is actually detected to save power/bandwidth
    // Chunks the 96x96 image and sends it via BLE notifications
    // Small optimization: only send if score is high enough
    // if (BLE.connected()) {
    //   MicroPrintf("MTG detected! Sending image...");
    //   size_t totalSize = kNumRows * kNumCols;
    //   size_t chunkSize = 64; 
    //   // Copy data to our stable buffer immediately
    //   //memcpy(snapshot_buffer, image_data, kNumRows * kNumCols);
    //   for (size_t i = 0; i < totalSize; i += chunkSize) {
    //     // Check if we are still connected before sending every chunk
    //     if (!BLE.connected()) {
    //         MicroPrintf("Connection lost during transfer!");
    //         break;
    //     }
    //     size_t currentSize = min(chunkSize, totalSize - i);
    //     imageCharacteristic.writeValue((uint8_t*)&image_data[i], currentSize);
    //     // This keeps the BLE radio alive while we are in the loop
    //     BLE.poll(); 
    //     delay(20);
    //   }
    // }
  } else {
    digitalWrite(LEDG, HIGH);
    digitalWrite(LEDB, LOW);
  }

  // Flash the yellow LED after every inference.
  // The builtin LED is on when the pin is HIGH
  digitalWrite(LED_BUILTIN, LOW);
  delay(100);
  digitalWrite(LED_BUILTIN, HIGH);

  float mtg_score_frac, mtg_score_int;
  float no_mtg_score_frac, no_mtg_score_int;
  mtg_score_frac = std::modf(mtg_score * 100, &mtg_score_int);
  no_mtg_score_frac = std::modf(no_mtg_score * 100, &no_mtg_score_int);
  MicroPrintf("MTG score: %d.%d%% No mtg score: %d.%d%%",
              static_cast<int>(mtg_score_int),
              static_cast<int>(mtg_score_frac * 100),
              static_cast<int>(no_mtg_score_int),
              static_cast<int>(no_mtg_score_frac * 100));
}

#endif  // ARDUINO_EXCLUDE_CODE
