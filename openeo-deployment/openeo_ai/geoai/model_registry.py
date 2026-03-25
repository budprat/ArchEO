# ABOUTME: Model registry for managing GeoAI ML models.
# Handles model discovery, loading, caching with support for ONNX and PyTorch.

"""
Model registry for GeoAI inference.

Manages loading, caching, and metadata for ML models used in
segmentation, change detection, and other GeoAI tasks.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Model metadata."""
    name: str
    task: str  # segmentation, change_detection, canopy_height
    version: str
    input_bands: List[str]
    input_size: int = 256
    output_classes: Optional[List[str]] = None
    description: str = ""
    path: Optional[str] = None
    loaded: bool = False


# Default model configurations
DEFAULT_MODELS = {
    "segmentation_default": ModelInfo(
        name="segmentation_default",
        task="segmentation",
        version="1.0.0",
        input_bands=["red", "green", "blue", "nir"],
        input_size=256,
        output_classes=[
            "background",
            "water",
            "vegetation",
            "urban",
            "agriculture",
            "bare_soil"
        ],
        description="Default semantic segmentation model for land cover classification"
    ),
    "change_default": ModelInfo(
        name="change_default",
        task="change_detection",
        version="1.0.0",
        input_bands=["red", "green", "blue", "nir"],
        input_size=256,
        output_classes=["no_change", "change"],
        description="Default change detection model for bi-temporal analysis"
    ),
    "canopy_height_default": ModelInfo(
        name="canopy_height_default",
        task="canopy_height",
        version="1.0.0",
        input_bands=["red", "green", "blue"],
        input_size=256,
        description="Canopy height estimation from RGB imagery"
    ),
}


class ModelRegistry:
    """
    Registry for managing GeoAI models.

    Handles model discovery, loading, and caching.
    """

    def __init__(self, models_path: Optional[str] = None):
        """
        Initialize model registry.

        Args:
            models_path: Path to directory containing model files
        """
        self.models_path = Path(models_path) if models_path else None
        self._models: Dict[str, ModelInfo] = {}
        self._loaded_models: Dict[str, Any] = {}

        # Register default models
        for name, info in DEFAULT_MODELS.items():
            self._models[name] = info

        # Discover additional models from path
        if self.models_path and self.models_path.exists():
            self._discover_models()

        logger.info(f"ModelRegistry initialized with {len(self._models)} models")

    def _discover_models(self) -> None:
        """Discover models from the models directory."""
        if not self.models_path:
            return

        # Look for model config files
        for config_path in self.models_path.glob("*/model_config.json"):
            try:
                with open(config_path) as f:
                    config = json.load(f)

                model_info = ModelInfo(
                    name=config["name"],
                    task=config["task"],
                    version=config.get("version", "1.0.0"),
                    input_bands=config.get("input_bands", ["red", "green", "blue"]),
                    input_size=config.get("input_size", 256),
                    output_classes=config.get("output_classes"),
                    description=config.get("description", ""),
                    path=str(config_path.parent)
                )
                self._models[model_info.name] = model_info
                logger.info(f"Discovered model: {model_info.name}")

            except Exception as e:
                logger.warning(f"Failed to load model config from {config_path}: {e}")

    def list_models(self, task: Optional[str] = None) -> List[ModelInfo]:
        """
        List available models.

        Args:
            task: Filter by task type (segmentation, change_detection, canopy_height)

        Returns:
            List of model info objects
        """
        models = list(self._models.values())
        if task:
            models = [m for m in models if m.task == task]
        return models

    def get_model_info(self, name: str) -> Optional[ModelInfo]:
        """
        Get model information.

        Args:
            name: Model name

        Returns:
            Model info or None if not found
        """
        return self._models.get(name)

    def load_model(self, name: str) -> Any:
        """
        Load a model for inference.

        Args:
            name: Model name

        Returns:
            Loaded model object

        Raises:
            ValueError: If model not found
        """
        if name not in self._models:
            raise ValueError(f"Model not found: {name}")

        # Return cached model if already loaded
        if name in self._loaded_models:
            return self._loaded_models[name]

        model_info = self._models[name]

        # For default models without path, return a stub model
        if not model_info.path:
            logger.info(f"Loading stub model for {name} (no model path configured)")
            model = StubModel(model_info)
            self._loaded_models[name] = model
            model_info.loaded = True
            return model

        # Load actual model from path
        model_path = Path(model_info.path)

        try:
            # Try to load ONNX model
            onnx_path = model_path / "model.onnx"
            if onnx_path.exists():
                import onnxruntime as ort
                session = ort.InferenceSession(str(onnx_path))
                model = ONNXModel(model_info, session)
                self._loaded_models[name] = model
                model_info.loaded = True
                logger.info(f"Loaded ONNX model: {name}")
                return model

            # Try to load PyTorch model
            pt_path = model_path / "model.pt"
            if pt_path.exists():
                import torch
                model = torch.load(pt_path, map_location="cpu")
                model.eval()
                wrapped_model = PyTorchModel(model_info, model)
                self._loaded_models[name] = wrapped_model
                model_info.loaded = True
                logger.info(f"Loaded PyTorch model: {name}")
                return wrapped_model

            raise ValueError(f"No model file found in {model_path}")

        except ImportError as e:
            logger.warning(f"ML framework not available for {name}: {e}")
            # Fall back to stub model
            model = StubModel(model_info)
            self._loaded_models[name] = model
            model_info.loaded = True
            return model

    def unload_model(self, name: str) -> bool:
        """
        Unload a model to free memory.

        Args:
            name: Model name

        Returns:
            True if unloaded, False if not loaded
        """
        if name in self._loaded_models:
            del self._loaded_models[name]
            if name in self._models:
                self._models[name].loaded = False
            logger.info(f"Unloaded model: {name}")
            return True
        return False

    def get_loaded_models(self) -> List[str]:
        """Get list of currently loaded models."""
        return list(self._loaded_models.keys())


class StubModel:
    """Stub model for testing when no real model is available."""

    def __init__(self, info: ModelInfo):
        self.info = info

    def predict(self, data):
        """Return mock predictions."""
        import numpy as np

        if self.info.task == "segmentation":
            # Return random class predictions
            return np.random.randint(
                0,
                len(self.info.output_classes or [6]),
                size=data.shape[-2:]
            )
        elif self.info.task == "change_detection":
            # Return random change mask
            return np.random.random(data.shape[-2:]) > 0.5
        elif self.info.task == "canopy_height":
            # Return random height values
            return np.random.uniform(0, 30, size=data.shape[-2:])
        else:
            return data


class ONNXModel:
    """Wrapper for ONNX Runtime inference."""

    def __init__(self, info: ModelInfo, session):
        self.info = info
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.output_name = session.get_outputs()[0].name

    def predict(self, data):
        """Run ONNX inference."""
        import numpy as np

        # Ensure float32
        if data.dtype != np.float32:
            data = data.astype(np.float32)

        # Add batch dimension if needed
        if data.ndim == 3:
            data = np.expand_dims(data, 0)

        # Run inference
        outputs = self.session.run(
            [self.output_name],
            {self.input_name: data}
        )

        return outputs[0]


class PyTorchModel:
    """Wrapper for PyTorch model inference."""

    def __init__(self, info: ModelInfo, model):
        self.info = info
        self.model = model

    def predict(self, data):
        """Run PyTorch inference."""
        import torch
        import numpy as np

        # Convert to tensor
        if isinstance(data, np.ndarray):
            tensor = torch.from_numpy(data).float()
        else:
            tensor = data.float()

        # Add batch dimension if needed
        if tensor.ndim == 3:
            tensor = tensor.unsqueeze(0)

        # Run inference
        with torch.no_grad():
            output = self.model(tensor)

        # Convert back to numpy
        if isinstance(output, torch.Tensor):
            return output.cpu().numpy()
        return output
