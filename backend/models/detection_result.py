from pydantic import BaseModel, Field


class DetectionResult(BaseModel):
    """
    Output of the Resource Detector.

    detected_resources:
        Resources successfully mapped to our dependency graph.

    unknown_resources:
        Files that were changed but could not be mapped.
    """

    detected_resources: list[str] = Field(default_factory=list)

    unknown_resources: list[str] = Field(default_factory=list)