# GeoAI Models Directory

This directory contains pre-trained model configurations for GeoAI inference tasks.

## Directory Structure

```
models/
├── segmentation_default/
│   ├── model_config.json    # Model metadata
│   └── model.onnx           # Model weights (optional)
├── change_default/
│   ├── model_config.json
│   └── model.onnx
└── canopy_height_default/
    ├── model_config.json
    └── model.onnx
```

## Model Configuration

Each model requires a `model_config.json` file with the following fields:

```json
{
  "name": "model_name",
  "task": "segmentation|change_detection|canopy_height",
  "version": "1.0.0",
  "description": "Model description",
  "input_bands": ["red", "green", "blue", "nir"],
  "input_size": 256,
  "output_classes": ["class1", "class2"],
  "framework": "onnx|pytorch",
  "model_file": "model.onnx"
}
```

## Supported Tasks

### Segmentation
- Semantic land cover classification
- Input: 4-band imagery (RGB+NIR)
- Output: Class labels per pixel

### Change Detection
- Bi-temporal change analysis
- Input: Two aligned images (before/after)
- Output: Binary change mask

### Canopy Height
- Tree height estimation from RGB
- Input: 3-band RGB imagery
- Output: Height values in meters

## Adding New Models

1. Create a directory with the model name
2. Add `model_config.json` with metadata
3. Add model weights as `model.onnx` or `model.pt`
4. Restart the application to auto-discover

## Stub Mode

If no model weights are present, the system uses stub models that return
random predictions for testing purposes.

## Supported Frameworks

- **ONNX** (recommended): Place `model.onnx` in model directory
- **PyTorch**: Place `model.pt` in model directory
