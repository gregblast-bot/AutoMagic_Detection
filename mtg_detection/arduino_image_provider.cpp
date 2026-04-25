#include "image_provider.h"
#include "model_settings.h"
#include "tensorflow/lite/micro/micro_log.h"
#include <Arduino_OV767X.h> // The real driver library

// We capture in QQVGA (160x120) because it's the smallest the hardware supports
namespace {
  byte frame[160 * 120]; // Buffer for the raw camera data
}

TfLiteStatus GetImage(const TfLiteTensor* tensor) {
  static bool is_initialized = false;

  if (!is_initialized) {
    // Start camera with QQVGA resolution and YUV422 format
    // YUV422 is best because the "Y" channel is already grayscale
    if (!Camera.begin(QQVGA, GRAYSCALE, 1)) {
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
  float input_scale = 0.004500297363847494f;
  int input_zero_point = -128;
  // Pre-calculate: 1.0 / (255.0 * 0.00450029...)
  //const float effective_multiplier = 0.87140f; 

  for (int y = 0; y < kNumRows; y++) {
    for (int x = 0; x < kNumCols; x++) {
      // Calculate the source pixel index (centered crop)
      int src_index = (start_y + y) * 160 + (start_x + x);
      uint8_t y_value = frame[src_index];

      // Mirror the training normalization (Rescaling 1/255)
      float normalized_pixel = y_value / 255.0f;

      // Apply the Quantization formula: (value / scale) + zero_point
      // This maps the 0.0-1.0 float to a -128 to 127 integer
      float quantized_val = (normalized_pixel / input_scale) + input_zero_point;

      // Clip and cast to int8
      if (quantized_val > 127) quantized_val = 127;
      if (quantized_val < -128) quantized_val = -128;
      
      //image_data[index] = (int8_t)(y_value * effective_multiplier - 128);
      image_data[y * kNumCols + x] = (int8_t)quantized_val;
    }
  }

  return kTfLiteOk;
}