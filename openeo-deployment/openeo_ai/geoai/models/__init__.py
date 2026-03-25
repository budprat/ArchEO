"""
GeoAI Model Directory.

ABOUTME: Contains pre-trained model weights and configurations for GeoAI tasks.
Models are loaded by the ModelRegistry based on model_config.json files.

Directory Structure:
    models/
    ├── __init__.py
    ├── README.md
    ├── segmentation_default/
    │   ├── model_config.json
    │   └── model.onnx (or model.pt)
    ├── change_default/
    │   ├── model_config.json
    │   └── model.onnx
    └── canopy_height_default/
        ├── model_config.json
        └── model.onnx

To add a new model:
1. Create a directory with the model name
2. Add model_config.json with model metadata
3. Add model weights (model.onnx or model.pt)
4. The ModelRegistry will auto-discover the model
"""
