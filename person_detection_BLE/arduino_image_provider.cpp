#include "image_provider.h"
#include "model_settings.h"
#include "tensorflow/lite/micro/micro_log.h"
#include <Arduino_OV767X.h> // The real driver library

// We capture in QQVGA (160x120) because it's the smallest the hardware supports
namespace {
  byte frame[160 * 120 * 2]; // Buffer for the raw camera data
}

TfLiteStatus GetImage(const TfLiteTensor* tensor) {
  static bool is_initialized = false;

  if (!is_initialized) {
    // Start camera with QQVGA resolution and YUV422 format
    // YUV422 is best because the "Y" channel is already grayscale
    if (!Camera.begin(QQVGA, YUV422, 1)) {
      MicroPrintf("Camera failed to initialize!");
      return kTfLiteError;
    }
    is_initialized = true;
  }

  // Grab a frame from the actual hardware
  Camera.readFrame(frame);

  // The model needs 96x96 (kNumCols x kNumRows)
  // We extract the center of the 160x120 image
  int start_x = (160 - kNumCols) / 2;
  int start_y = (120 - kNumRows) / 2;

  int8_t* image_data = tensor->data.int8;

  for (int y = 0; y < kNumRows; y++) {
    for (int x = 0; x < kNumCols; x++) {
      int src_x = start_x + x;
      int src_y = start_y + y;
      
      // YUV422 format: [Y0, U0, Y1, V0]. 
      // Brightness (Y) is every even byte.
      int src_index = (src_y * 160 + src_x) * 2;
      uint8_t y_value = frame[src_index];

      // Convert 0..255 (unsigned) to -128..127 (signed int8)
      image_data[y * kNumCols + x] = (int8_t)(y_value - 128);
    }
  }

  return kTfLiteOk;
}