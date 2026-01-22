"""
Domain 4: Compliance Tools

Provides building code and permit analysis:
- Permit requirement detection via Tavily + Cerebras
- Structural validation rules
- Building age compliance checks
"""

from .permit_requirements import (
    detect_permit_requirements,
    search_building_codes,
    check_scope_for_permits,
    PermitAnalysis,
    PermitRequirement,
)
from .structural_validation import (
    validate_structural_scope,
    check_building_age_requirements,
    validate_scope_safety,
    StructuralValidationResult,
)

__all__ = [
    # Permit requirements
    "detect_permit_requirements",
    "search_building_codes",
    "check_scope_for_permits",
    "PermitAnalysis",
    "PermitRequirement",
    # Structural validation
    "validate_structural_scope",
    "check_building_age_requirements",
    "validate_scope_safety",
    "StructuralValidationResult",
]
