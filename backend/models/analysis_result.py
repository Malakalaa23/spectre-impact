from enum import Enum

from pydantic import BaseModel, Field


# Possible severity levels
class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Suggested deployment strategy
class DeploymentStrategy(str, Enum):
    ROLLING = "Rolling"
    BLUE_GREEN = "Blue-Green"
    CANARY = "Canary"
    MANUAL_APPROVAL = "Manual Approval"


# Main result produced by our change analysis
class AnalysisResult(BaseModel):

    # ==================================================
    # INPUT
    # ==================================================

    # Files that GitHub says were changed in the PR
    changed_files: list[str] = Field(default_factory=list)

    # Resources we successfully mapped from those files
    changed_resources: list[str] = Field(default_factory=list)

    # Files/resources that we could not identify
    unknown_resources: list[str] = Field(default_factory=list)

    # ==================================================
    # TECHNICAL BLAST RADIUS
    # ==================================================

    affected_databases: list[str] = Field(default_factory=list)

    affected_services: list[str] = Field(default_factory=list)

    affected_apis: list[str] = Field(default_factory=list)

    affected_frontends: list[str] = Field(default_factory=list)

    # ==================================================
    # CUSTOMER IMPACT
    # ==================================================

    affected_customer_journeys: list[str] = Field(default_factory=list)

    # ==================================================
    # BUSINESS IMPACT
    # ==================================================

    affected_business_capabilities: list[str] = Field(default_factory=list)

    # Estimated percentage of users potentially affected.
    # This is an estimate based on our dependency map,
    # NOT a prediction of actual production users.
    business_impact: int = Field(default=0, ge=0, le=100)

    # ==================================================
    # RISK
    # ==================================================

    severity: Severity = Severity.LOW

    # How confident our deterministic analysis is (0-100)
    confidence: int = Field(default=100, ge=0, le=100)

    # ==================================================
    # DEPLOYMENT RECOMMENDATIONS
    # ==================================================

    deployment_strategy: DeploymentStrategy = DeploymentStrategy.ROLLING

    rollback_required: bool = False

    # ==================================================
    # EVIDENCE
    # ==================================================

    # Actual paths through the dependency graph.
    #
    # Example:
    #
    # [
    #     [
    #         "customer_database",
    #         "login_service",
    #         "login_api",
    #         "login_journey"
    #     ]
    # ]
    #
    # This lets the AI and dashboard see WHY
    # something was considered affected.
    evidence: list[list[str]] = Field(default_factory=list)