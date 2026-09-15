"""
resource_detector.py — Converts changed file paths into graph resources.

The detector accepts file paths in various formats and resolves them
against the project's resource map. Resolution is fuzzy:

    1. Exact match against the resource map.
    2. Normalize backslashes → forward slashes, strip leading "./".
    3. Try common prefixes (terraform/, services/, apis/, frontend/).
    4. Match by basename (e.g. "customer_database.tf" → any key ending
       with "/customer_database.tf").
    5. Match by filename stem (without extension).
    6. Fall back to path-based inference (_detect_from_path) for files
       that live inside known directories but aren't explicitly mapped.

This makes the detector resilient to how callers format paths —
the LLM may pass "customer_database.tf", a user may type
"terraform/customer_database.tf", and both should resolve.
"""

from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath

from backend.models.detection_result import DetectionResult


logger = logging.getLogger(__name__)


# Common directory prefixes to try when resolving bare filenames.
_COMMON_PREFIXES = ("terraform/", "services/", "apis/", "frontend/")


class ResourceDetector:
    """
    Converts changed file paths into resources that exist in the
    dependency graph.

    Examples:
        terraform/customer_database.tf   →   customer_database
        customer_database.tf             →   customer_database
        services/payment/app.py          →   payment_service
        services/payment/routes/charge.py →  payment_service
    """

    def __init__(self, mapping_file: str):
        with open(mapping_file, encoding="utf-8") as file:
            self.resource_map: dict[str, str] = json.load(file)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect_resources(self, changed_files: list[str]) -> DetectionResult:
        """Convert a list of file paths into a DetectionResult."""
        result = DetectionResult()

        for file in changed_files:
            normalized = file.replace("\\", "/").lstrip("./")
            resource = self._resolve(normalized)

            if resource:
                result.detected_resources.append(resource)
            else:
                result.unknown_resources.append(file)

        # Deduplicate, preserving order
        result.detected_resources = list(dict.fromkeys(result.detected_resources))
        return result

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def _resolve(self, normalized: str) -> str | None:
        """
        Resolve one file path to a resource name.

        Tries, in order:
            1. Exact match
            2. Prefix candidates
            3. Basename match
            4. Filename stem match
            5. Path-based inference (for unmapped files inside known dirs)

        Returns the resource name, or None if unresolvable.
        """
        # 1. Exact match
        if normalized in self.resource_map:
            return self.resource_map[normalized]

        # 2. Try common prefixes
        for prefix in _COMMON_PREFIXES:
            candidate = f"{prefix}{normalized}"
            if candidate in self.resource_map:
                return self.resource_map[candidate]

        # 3. Match by basename
        basename = normalized.split("/")[-1]
        for key, resource in self.resource_map.items():
            if key.split("/")[-1] == basename:
                return resource

        # 4. Match by filename stem (drop extension)
        stem = basename.rsplit(".", 1)[0]
        for key, resource in self.resource_map.items():
            key_stem = key.split("/")[-1].rsplit(".", 1)[0]
            if key_stem == stem:
                return resource

        # 5. Path-based inference
        return self._detect_from_path(normalized)

    # ------------------------------------------------------------------
    # Path-based inference
    # ------------------------------------------------------------------
    def _detect_from_path(self, file_path: str) -> str | None:
        """
        Infer a mapped resource from a file path that lives inside a known
        directory but isn't explicitly mapped.

        Example:
            services/payment/routes/charge.py → payment_service
        """
        parts = PurePosixPath(file_path).parts
        candidates = {
            "terraform": {
                "customer_database": "customer_database",
                "redis": "redis_cache",
            },
            "services": {
                "login": "login_service",
                "payment": "payment_service",
                "profile": "profile_service",
            },
            "apis": {
                "login": "login_api",
                "checkout": "checkout_api",
                "profile": "profile_api",
            },
            "frontend": {
                "login": "login_journey",
                "checkout": "checkout_journey",
                "profile": "profile_journey",
            },
        }

        for directory, names in candidates.items():
            if directory in parts:
                remainder = "/".join(parts[parts.index(directory) + 1:])
                for name, resource in names.items():
                    if name in remainder:
                        return resource
        return None


__all__ = ["ResourceDetector"]