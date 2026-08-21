"""
Advanced AI Features for Spectre Impact

This package contains advanced features that make the platform unstoppable:
1. Post-Incident Report Generator - Professional post-mortem reports
2. Root Cause Analysis (RCA) Simulator - Trace failures to root cause
3. Team-Specific Recommendations - Targeted advice for different teams
4. Change Type Detection - Identify database, API, security changes
"""

from .post_incident_report import (
    generate_post_incident_report,
    format_report_for_display
)

from .rca_simulator import (
    generate_root_cause_analysis,
    format_rca_for_display
)

from .team_recommendations import (
    get_team_specific_recommendations,
    format_recommendations_for_display
)

from .change_detector import (
    detect_change_type,
    format_change_detection_for_display
)

__all__ = [
    'generate_post_incident_report',
    'format_report_for_display',
    'generate_root_cause_analysis',
    'format_rca_for_display',
    'get_team_specific_recommendations',
    'format_recommendations_for_display',
    'detect_change_type',
    'format_change_detection_for_display'
]