import json
from pathlib import PurePosixPath

from backend.models.detection_result import DetectionResult


class ResourceDetector:
    """
    Converts changed file paths into resources
    that exist in our dependency graph.

    Example:

    terraform/customer_database.tf

            ↓

    customer_database
    """

    def __init__(self, mapping_file: str):

        # Load the file → resource mapping
        with open(mapping_file, "r") as file:
            self.resource_map = json.load(file)

    def detect_resources(self, changed_files: list[str]) -> DetectionResult:

        result = DetectionResult()

        for file in changed_files:
            normalized_file = file.replace("\\", "/").lstrip("./")

            # We know this file
            if normalized_file in self.resource_map:

                result.detected_resources.append(
                    self.resource_map[normalized_file]
                )

            else:
                resource = self._detect_from_path(normalized_file)
                if resource:
                    result.detected_resources.append(resource)
                else:
                    result.unknown_resources.append(file)

        # A PR can modify several files in one resource. Return each once,
        # preserving the first-seen order for deterministic output.
        result.detected_resources = list(dict.fromkeys(result.detected_resources))

        return result

    def _detect_from_path(self, file_path: str) -> str | None:
        """Infer a mapped resource from a file anywhere within its folder."""
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
