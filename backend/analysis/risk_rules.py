from backend.models.analysis_result import (
    AnalysisResult,
    Severity,
    DeploymentStrategy
)


class RiskRules:
    """
    Deterministic rules for calculating:

    - Business impact
    - Severity
    - Deployment strategy
    - Rollback requirement

    AI is NOT used here.
    """

    def apply(self, result: AnalysisResult) -> AnalysisResult:

        # --------------------------------------------------
        # 1. Calculate business impact
        #
        # Business impact is calculated by ChangeAnalysisEngine from the
        # configurable data/business_map.yaml file. This class only uses the
        # result to determine severity and deployment guidance.

        # --------------------------------------------------
        # 2. Calculate severity
        #
        # Critical infrastructure or high customer impact
        # increases the severity.
        # --------------------------------------------------

        if (
            "customer_database" in result.changed_resources
            or result.business_impact >= 80
            or len(result.affected_business_capabilities) >= 3
        ):
            result.severity = Severity.CRITICAL

        elif (
            result.business_impact >= 50
            or len(result.affected_services) >= 3
            or len(result.affected_apis) >= 3
        ):
            result.severity = Severity.HIGH

        elif (
            result.business_impact > 0
            or len(result.affected_services) > 0
        ):
            result.severity = Severity.MEDIUM

        else:
            result.severity = Severity.LOW

        # --------------------------------------------------
        # 3. Choose deployment strategy
        # --------------------------------------------------

        if result.severity == Severity.CRITICAL:

            result.deployment_strategy = (
                DeploymentStrategy.MANUAL_APPROVAL
            )

        elif result.severity == Severity.HIGH:

            result.deployment_strategy = (
                DeploymentStrategy.CANARY
            )

        elif result.severity == Severity.MEDIUM:

            result.deployment_strategy = (
                DeploymentStrategy.ROLLING
            )

        else:

            result.deployment_strategy = (
                DeploymentStrategy.ROLLING
            )

        # --------------------------------------------------
        # 4. Decide whether rollback planning is required
        # --------------------------------------------------

        if result.severity in [
            Severity.HIGH,
            Severity.CRITICAL
        ]:
            result.rollback_required = True

        else:
            result.rollback_required = False

        # --------------------------------------------------
        # 5. Estimate confidence
        #
        # Unknown resources make our analysis less certain.
        # --------------------------------------------------

        if result.unknown_resources:

            result.confidence = 70

        else:

            result.confidence = 100

        return result
