# ABOUTME: Persistent job archive — saves completed job results permanently.
# Uses PostgreSQL (saved_results table) for metadata and
# copies result files to ~/.openeo_jobs/results/{save_id}/.

import uuid
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import logging
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine, select, delete as sa_delete, desc
from sqlalchemy.orm import sessionmaker

from .models import SavedResult

_RESULTS_DIR = Path.home() / ".openeo_jobs" / "results"
_lock = threading.Lock()

# Lazy-initialised engine + session factory
_engine = None
_SessionLocal = None


def _get_session():
    """Get a sync SQLAlchemy session using the existing OpenEO DB config."""
    global _engine, _SessionLocal
    if _engine is None:
        try:
            from openeo_fastapi.client.psql.engine import get_engine
            _engine = get_engine()
        except Exception:
            # Fallback: build URL from env vars
            import os
            url = (
                f"postgresql://{os.environ.get('POSTGRES_USER', 'macbookpro')}"
                f":{os.environ.get('POSTGRES_PASSWORD', '')}"
                f"@{os.environ.get('POSTGRESQL_HOST', 'localhost')}"
                f":{os.environ.get('POSTGRESQL_PORT', '5432')}"
                f"/{os.environ.get('POSTGRES_DB', 'openeo')}"
            )
            _engine = create_engine(url)
        _SessionLocal = sessionmaker(bind=_engine)

    # Ensure the table exists (idempotent)
    SavedResult.__table__.create(bind=_engine, checkfirst=True)

    return _SessionLocal()


def _ensure_dirs():
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def save_job(
    source_path: str,
    title: str,
    bounds: Optional[list] = None,
    colormap: str = "viridis",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    source_query: str = "",
    job_id: str = "",
) -> Optional[str]:
    """Copy a result file to permanent storage and save metadata to PostgreSQL."""
    source = Path(source_path)
    if not source.exists():
        logger.error(f"Source file not found: {source_path}")
        return None

    save_id = str(uuid.uuid4())[:8]
    dest_dir = _RESULTS_DIR / save_id

    with _lock:
        try:
            _ensure_dirs()
            dest_dir.mkdir(exist_ok=True)

            # Copy the result file
            dest_file = dest_dir / source.name
            shutil.copy2(str(source), str(dest_file))

            # Copy metadata.json if it exists alongside the source
            source_meta = source.parent / "metadata.json"
            if source_meta.exists():
                shutil.copy2(str(source_meta), str(dest_dir / "metadata.json"))

            size_bytes = dest_file.stat().st_size

            # Save to PostgreSQL
            session = _get_session()
            try:
                row = SavedResult(
                    save_id=save_id,
                    title=title,
                    result_path=str(dest_file),
                    original_path=source_path,
                    bounds=bounds,
                    colormap=colormap,
                    vmin=vmin,
                    vmax=vmax,
                    size_bytes=size_bytes,
                    source_query=source_query,
                    job_id=job_id,
                )
                session.add(row)
                session.commit()
            except Exception as db_err:
                session.rollback()
                raise db_err
            finally:
                session.close()

            logger.info(f"Saved job {save_id}: {title} -> {dest_file}")
            return save_id

        except Exception as e:
            logger.error(f"Failed to save job: {e}")
            if dest_dir.exists():
                shutil.rmtree(dest_dir, ignore_errors=True)
            return None


def list_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """List saved jobs from PostgreSQL, newest first. Validates files still exist."""
    try:
        session = _get_session()
        try:
            stmt = (
                select(SavedResult)
                .order_by(desc(SavedResult.created_at))
                .limit(limit)
            )
            results = session.execute(stmt).scalars().all()
            valid = []
            for row in results:
                if Path(row.result_path).exists():
                    valid.append(row.to_dict())
            return valid
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to list jobs from DB: {e}")
        return []


def get_job(save_id: str) -> Optional[Dict[str, Any]]:
    """Get a single saved job by save_id."""
    try:
        session = _get_session()
        try:
            stmt = select(SavedResult).where(SavedResult.save_id == save_id)
            row = session.execute(stmt).scalar_one_or_none()
            if row and Path(row.result_path).exists():
                return row.to_dict()
            return None
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get job {save_id}: {e}")
        return None


def delete_job(save_id: str) -> bool:
    """Delete a saved job: remove from DB and delete files."""
    try:
        session = _get_session()
        try:
            stmt = select(SavedResult).where(SavedResult.save_id == save_id)
            row = session.execute(stmt).scalar_one_or_none()
            if not row:
                return False

            session.execute(
                sa_delete(SavedResult).where(SavedResult.save_id == save_id)
            )
            session.commit()
        except Exception as db_err:
            session.rollback()
            raise db_err
        finally:
            session.close()

        # Remove files
        dest_dir = _RESULTS_DIR / save_id
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        return True

    except Exception as e:
        logger.error(f"Failed to delete job {save_id}: {e}")
        return False
