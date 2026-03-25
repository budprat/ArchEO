"""Tests for openeo_app/storage/results.py.

Verifies result saving in different formats, data validation,
result lookup, and log management -- all using temporary directories
so no persistent state is created.
"""

import json
import uuid
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from openeo_app.storage.results import (
    ResultStorage,
    validate_result_data,
)


@pytest.fixture
def storage(tmp_results_dir):
    """Create a ResultStorage using the temporary directory."""
    return ResultStorage(base_path=str(tmp_results_dir))


@pytest.fixture
def job_id():
    """Return a deterministic job UUID."""
    return uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


# ---------------------------------------------------------------------------
# validate_result_data
# ---------------------------------------------------------------------------


class TestValidateResultData:
    """Tests for the validate_result_data function."""

    def test_valid_dataarray(self, sample_dataarray):
        """Valid DataArray should pass validation."""
        result = validate_result_data(sample_dataarray)

        assert result["is_valid"] is True
        assert result["warnings"] == []
        assert "min" in result["stats"]
        assert "max" in result["stats"]
        assert "shape" in result["stats"]

    def test_empty_dataarray_raises(self):
        """Empty DataArray should raise ValueError."""
        data = xr.DataArray(np.array([]).reshape(0, 0), dims=["y", "x"])

        with pytest.raises(ValueError, match="empty"):
            validate_result_data(data)

    def test_all_nan_warns(self, all_nan_dataarray):
        """All-NaN DataArray should produce warnings."""
        result = validate_result_data(all_nan_dataarray)

        assert len(result["warnings"]) > 0
        assert result["stats"]["nan_percent"] == 100.0
        assert any("NaN" in w for w in result["warnings"])

    def test_partial_nan_reports_percentage(self):
        """Partial NaN data should report correct percentage."""
        arr = np.ones((10, 10))
        arr[:5, :] = np.nan  # 50% NaN
        data = xr.DataArray(arr, dims=["y", "x"])

        result = validate_result_data(data)
        assert result["stats"]["nan_percent"] == 50.0

    def test_high_nan_warns(self):
        """More than 90% NaN should trigger a warning."""
        arr = np.ones((100, 100))
        arr[:, :95] = np.nan  # 95% NaN
        data = xr.DataArray(arr, dims=["y", "x"])

        result = validate_result_data(data)
        assert any("NaN" in w for w in result["warnings"])

    def test_dataset_validation(self, sample_dataset):
        """xarray Dataset should be validated per-variable."""
        result = validate_result_data(sample_dataset)

        assert result["is_valid"] is True
        assert "ndvi" in result["stats"]
        assert "evi" in result["stats"]

    def test_dataset_empty_variable_raises(self):
        """Dataset with an empty variable should raise ValueError."""
        ds = xr.Dataset(
            {"empty_var": xr.DataArray(np.array([]).reshape(0, 0), dims=["y", "x"])}
        )

        with pytest.raises(ValueError, match="empty"):
            validate_result_data(ds)


# ---------------------------------------------------------------------------
# ResultStorage -- save_result
# ---------------------------------------------------------------------------


class TestSaveResult:
    """Tests for ResultStorage.save_result()."""

    def test_save_json(self, storage, job_id):
        """Saving JSON data should create a .json file."""
        data = {"ndvi_mean": 0.65, "pixels": 1000}
        path = storage.save_result(job_id, data, format="JSON")

        assert path.exists()
        assert path.suffix == ".json"

        with open(path) as f:
            saved = json.load(f)
        assert saved["ndvi_mean"] == 0.65

    def test_save_json_list(self, storage, job_id):
        """Saving a list as JSON should work."""
        data = [1, 2, 3, 4, 5]
        path = storage.save_result(job_id, data, format="JSON")

        assert path.exists()
        with open(path) as f:
            saved = json.load(f)
        assert saved == [1, 2, 3, 4, 5]

    def test_save_netcdf(self, storage, job_id, sample_dataarray):
        """Saving NetCDF should create a .nc file."""
        path = storage.save_result(job_id, sample_dataarray, format="netCDF")

        assert path.exists()
        assert path.suffix == ".nc"

        # Verify we can load it back
        ds = xr.open_dataset(str(path))
        assert "data" in ds.data_vars
        ds.close()

    def test_save_custom_filename(self, storage, job_id):
        """Custom filename should be used."""
        data = {"test": True}
        path = storage.save_result(
            job_id, data, format="JSON", filename="custom_name.json"
        )

        assert path.name == "custom_name.json"
        assert path.exists()

    def test_save_creates_job_directory(self, storage, job_id):
        """Saving should create a job-specific directory."""
        data = {"test": True}
        storage.save_result(job_id, data, format="JSON")

        job_dir = storage.results_dir / str(job_id)
        assert job_dir.exists()
        assert job_dir.is_dir()

    def test_save_creates_metadata(self, storage, job_id):
        """Saving should create a metadata.json file."""
        data = {"test": True}
        storage.save_result(job_id, data, format="JSON")

        metadata_path = storage.results_dir / str(job_id) / "metadata.json"
        assert metadata_path.exists()

        with open(metadata_path) as f:
            meta = json.load(f)

        assert meta["job_id"] == str(job_id)
        assert meta["format"] == "JSON"
        assert "created" in meta

    def test_save_metadata_includes_validation(self, storage, job_id, sample_dataarray):
        """Metadata should include validation info for xarray data."""
        storage.save_result(job_id, sample_dataarray, format="netCDF")

        metadata_path = storage.results_dir / str(job_id) / "metadata.json"
        with open(metadata_path) as f:
            meta = json.load(f)

        assert "validation" in meta
        assert meta["validation"]["is_valid"] is True


# ---------------------------------------------------------------------------
# ResultStorage -- get_result
# ---------------------------------------------------------------------------


class TestGetResult:
    """Tests for ResultStorage.get_result()."""

    def test_get_existing_result(self, storage, job_id):
        """get_result should return path for an existing result."""
        data = {"test": True}
        saved_path = storage.save_result(job_id, data, format="JSON")

        retrieved = storage.get_result(job_id)

        assert retrieved is not None
        assert retrieved == saved_path

    def test_get_nonexistent_result(self, storage):
        """get_result should return None for a non-existent job."""
        fake_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        result = storage.get_result(fake_id)

        assert result is None

    def test_get_result_prefers_tif(self, storage, job_id):
        """get_result should find .tif files."""
        # Create a fake .tif file
        job_dir = storage.results_dir / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        tif_path = job_dir / "result.tif"
        tif_path.write_bytes(b"fake tif data")

        result = storage.get_result(job_id)
        assert result is not None
        assert result.suffix == ".tif"

    def test_get_result_from_metadata(self, storage, job_id):
        """get_result should fall back to metadata for custom filenames."""
        job_dir = storage.results_dir / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        # Create file with custom name
        custom_path = job_dir / "my_output.nc"
        custom_path.write_bytes(b"fake nc data")

        # Create metadata pointing to custom filename
        metadata = {"result_file": "my_output.nc"}
        with open(job_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        result = storage.get_result(job_id)
        assert result is not None
        assert result.name == "my_output.nc"


# ---------------------------------------------------------------------------
# ResultStorage -- delete_result
# ---------------------------------------------------------------------------


class TestDeleteResult:
    """Tests for ResultStorage.delete_result()."""

    def test_delete_existing_result(self, storage, job_id):
        """Deleting an existing result should remove the directory."""
        storage.save_result(job_id, {"test": True}, format="JSON")
        assert storage.get_result(job_id) is not None

        success = storage.delete_result(job_id)

        assert success is True
        assert storage.get_result(job_id) is None

    def test_delete_nonexistent_result(self, storage):
        """Deleting a non-existent result should return False."""
        fake_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        success = storage.delete_result(fake_id)

        assert success is False


# ---------------------------------------------------------------------------
# ResultStorage -- logging
# ---------------------------------------------------------------------------


class TestLogManagement:
    """Tests for ResultStorage log saving and retrieval."""

    def test_save_log(self, storage, job_id):
        """Saving a log entry should create a JSONL file."""
        storage.save_log(job_id, "info", "Job started")

        log_file = storage.logs_dir / f"{job_id}.jsonl"
        assert log_file.exists()

    def test_get_logs(self, storage, job_id):
        """get_logs should return saved log entries."""
        storage.save_log(job_id, "info", "Step 1")
        storage.save_log(job_id, "info", "Step 2")
        storage.save_log(job_id, "warning", "Step 3 slow")

        logs = storage.get_logs(job_id)

        assert len(logs) == 3
        assert logs[0]["message"] == "Step 1"
        assert logs[2]["level"] == "warning"

    def test_get_logs_with_limit(self, storage, job_id):
        """get_logs should respect the limit parameter."""
        for i in range(10):
            storage.save_log(job_id, "info", f"Message {i}")

        logs = storage.get_logs(job_id, limit=3)

        assert len(logs) == 3
        # Should return the most recent 3
        assert logs[-1]["message"] == "Message 9"

    def test_get_logs_empty(self, storage):
        """get_logs for non-existent job should return empty list."""
        fake_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        logs = storage.get_logs(fake_id)

        assert logs == []

    def test_save_log_with_data(self, storage, job_id):
        """Log entry should include additional data when provided."""
        storage.save_log(
            job_id, "error", "Processing failed", data={"node": "load1"}
        )

        logs = storage.get_logs(job_id)
        assert logs[0]["data"]["node"] == "load1"

    def test_clear_logs(self, storage, job_id):
        """clear_logs should remove the log file."""
        storage.save_log(job_id, "info", "test")
        assert len(storage.get_logs(job_id)) == 1

        result = storage.clear_logs(job_id)
        assert result is True
        assert len(storage.get_logs(job_id)) == 0

    def test_clear_nonexistent_logs(self, storage):
        """clear_logs for non-existent job should return False."""
        fake_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        result = storage.clear_logs(fake_id)
        assert result is False


# ---------------------------------------------------------------------------
# ResultStorage -- directory structure
# ---------------------------------------------------------------------------


class TestStorageDirectoryStructure:
    """Tests for the storage directory structure."""

    def test_directories_created_on_init(self, tmp_results_dir):
        """ResultStorage should create results/ and logs/ subdirs."""
        storage = ResultStorage(base_path=str(tmp_results_dir))

        assert storage.results_dir.exists()
        assert storage.logs_dir.exists()

    def test_base_path_attribute(self, storage, tmp_results_dir):
        """base_path should match the provided path."""
        assert storage.base_path == tmp_results_dir
