"""Duplicate upload detection based on deterministic file content hashes."""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.config import Settings, default_settings

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Manages document deduplication and index manifest state."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or default_settings
        self.manifest_path = self.settings.get_processed_path() / "processed_manifest.json"

    def _load_manifest(self) -> Dict[str, dict]:
        """Load the processed manifest ledger."""
        if not self.manifest_path.exists():
            return {}
        try:
            with self.manifest_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to parse manifest %s, resetting: %s", self.manifest_path, e)
            return {}

    def _save_manifest(self, manifest: Dict[str, dict]) -> None:
        """Persist updated manifest ledger to disk atomically."""
        try:
            tmp_path = self.manifest_path.with_suffix(f".tmp_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.manifest_path)
        except Exception as e:
            logger.error("Failed to save manifest %s: %s", self.manifest_path, e)

    def check_duplicate(self, file_path: Path) -> Tuple[bool, str, Optional[Path]]:
        """Check if a file with identical content has already been processed.

        Args:
            file_path: PDF file to inspect.

        Returns:
            Tuple of (is_duplicate, document_id, existing_processed_json_path)
        """
        sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        content_hash = sha256.hexdigest()
        doc_id = f"doc_{content_hash[:16]}"

        processed_json = self.settings.get_processed_path() / f"{doc_id}.json"
        manifest = self._load_manifest()

        if processed_json.exists() or doc_id in manifest:
            logger.info("Duplicate document detected: %s (ID: %s)", file_path.name, doc_id)
            return True, doc_id, processed_json

        return False, doc_id, None

    def register_processed(self, document_id: str, document_name: str, total_chunks: int, status: str) -> None:
        """Record successful document processing in the central manifest."""
        manifest = self._load_manifest()
        manifest[document_id] = {
            "document_name": document_name,
            "total_chunks": total_chunks,
            "status": status,
            "output_json": f"{document_id}.json",
        }
        self._save_manifest(manifest)
