"""Versioned method-adapter seam for the insurance protocol vertical slice.

The longitudinal claim-loop kernel depends on this protocol-facing surface, not
on the selected proof compiler.  A successor compiler can therefore replace
the current implementation without changing the kernel import closure.
"""

from __future__ import annotations

from .insurance_pace_bridge_v1 import (
    InsurancePACEBridgeError,
    build_registration_authority_v1,
    build_registration_compatibility_action_v1,
    build_verified_neutral_assessment_proposal_v1,
    pace_current_decision_scope_v1,
)


InsuranceProtocolAuthorityError = InsurancePACEBridgeError
current_decision_scope_v1 = pace_current_decision_scope_v1


__all__ = (
    "InsuranceProtocolAuthorityError",
    "build_registration_authority_v1",
    "build_registration_compatibility_action_v1",
    "build_verified_neutral_assessment_proposal_v1",
    "current_decision_scope_v1",
)
