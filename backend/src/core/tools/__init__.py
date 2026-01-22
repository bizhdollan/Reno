"""
Multi-Agent Tool System

This package provides specialized tools organized by domain:
- location: Address validation, NYC DOB lookup, market data
- space: Room analysis, measurement estimation, structural detection
- designer: Intent detection, style suggestions, preferences
- compliance: Permit requirements, structural validation
- estimator: Quantity takeoff, labor estimation, pricing

All tools return ToolResult with confidence scores and HITL support.
"""

from .base import (
    ConfidenceScore,
    HITLQuestion,
    ToolResult,
    Priority,
    QuestionCategory,
)

__all__ = [
    "ConfidenceScore",
    "HITLQuestion",
    "ToolResult",
    "Priority",
    "QuestionCategory",
]
