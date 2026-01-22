"""
Base classes for the multi-agent tool system.

Provides:
- ConfidenceScore: Track confidence levels with HITL thresholds
- HITLQuestion: Structured human-in-the-loop questions
- ToolResult: Standardized result wrapper for all tools
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class Priority(Enum):
    """Priority levels for HITL questions."""
    CRITICAL = 1  # structural, load-bearing, hazards
    HIGH = 2      # dimensions
    MEDIUM = 3    # materials, finishes
    LOW = 4       # style details


class QuestionCategory(Enum):
    """Categories for HITL questions to help with UI grouping."""
    STRUCTURAL = "structural"
    DIMENSIONS = "dimensions"
    MATERIALS = "materials"
    STYLE = "style"
    COMPLIANCE = "compliance"
    COST = "cost"
    GENERAL = "general"


@dataclass
class ConfidenceScore:
    """
    Represents a confidence score for a tool output field.

    Confidence thresholds:
    - 0.90+: High confidence (clearly visible/determinable)
    - 0.70-0.89: Medium confidence (mostly visible)
    - 0.60-0.69: Low confidence (partially visible, HITL trigger zone)
    - <0.60: Very low confidence (cannot determine, triggers HITL)

    Attributes:
        value: Float between 0.0 and 1.0
        reasoning: Explanation for the confidence level
        field_name: Optional name of the field this confidence applies to
    """
    value: float
    reasoning: str
    field_name: Optional[str] = None

    HITL_THRESHOLD = 0.60

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence value must be between 0.0 and 1.0, got {self.value}")

    def requires_human_input(self) -> bool:
        """Returns True if confidence is below HITL threshold."""
        return self.value < self.HITL_THRESHOLD

    def is_high_confidence(self) -> bool:
        """Returns True if confidence is 0.90 or above."""
        return self.value >= 0.90

    def is_medium_confidence(self) -> bool:
        """Returns True if confidence is between 0.70 and 0.89."""
        return 0.70 <= self.value < 0.90

    def is_low_confidence(self) -> bool:
        """Returns True if confidence is below 0.70."""
        return self.value < 0.70

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "value": self.value,
            "reasoning": self.reasoning,
            "field_name": self.field_name,
            "requires_human_input": self.requires_human_input()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConfidenceScore":
        """Deserialize from dictionary."""
        return cls(
            value=data["value"],
            reasoning=data["reasoning"],
            field_name=data.get("field_name")
        )

    @classmethod
    def high(cls, reasoning: str = "Clearly visible/determinable", field_name: Optional[str] = None) -> "ConfidenceScore":
        """Factory for high confidence score (0.95)."""
        return cls(value=0.95, reasoning=reasoning, field_name=field_name)

    @classmethod
    def medium(cls, reasoning: str = "Mostly visible/determinable", field_name: Optional[str] = None) -> "ConfidenceScore":
        """Factory for medium confidence score (0.75)."""
        return cls(value=0.75, reasoning=reasoning, field_name=field_name)

    @classmethod
    def low(cls, reasoning: str = "Partially visible, uncertain", field_name: Optional[str] = None) -> "ConfidenceScore":
        """Factory for low confidence score (0.55) - triggers HITL."""
        return cls(value=0.55, reasoning=reasoning, field_name=field_name)

    @classmethod
    def user_provided(cls, field_name: Optional[str] = None) -> "ConfidenceScore":
        """Factory for user-provided values (1.0 confidence)."""
        return cls(value=1.0, reasoning="User provided value", field_name=field_name)


@dataclass
class HITLQuestion:
    """
    Represents a question to ask the user for human-in-the-loop verification.

    Attributes:
        id: Unique identifier for the question
        question: The question text to display to the user
        field_name: The field this question relates to
        category: Category for UI grouping
        priority: Priority level for ordering questions
        options: Optional list of suggested answers
        current_value: The current (low confidence) value
        confidence: The confidence score that triggered this question
        metadata: Additional context for the question
    """
    question: str
    field_name: str
    category: QuestionCategory
    priority: Priority
    id: str = field(default_factory=lambda: str(uuid4()))
    options: Optional[list[str]] = None
    current_value: Any = None
    confidence: Optional[ConfidenceScore] = None
    metadata: Optional[dict] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolved_value: Any = None
    resolved_at: Optional[datetime] = None

    def resolve(self, value: Any) -> None:
        """Mark the question as resolved with the user's answer."""
        self.resolved = True
        self.resolved_value = value
        self.resolved_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "question": self.question,
            "field_name": self.field_name,
            "category": self.category.value,
            "priority": self.priority.value,
            "options": self.options,
            "current_value": self.current_value,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "resolved": self.resolved,
            "resolved_value": self.resolved_value,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HITLQuestion":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            question=data["question"],
            field_name=data["field_name"],
            category=QuestionCategory(data["category"]),
            priority=Priority(data["priority"]),
            options=data.get("options"),
            current_value=data.get("current_value"),
            confidence=ConfidenceScore.from_dict(data["confidence"]) if data.get("confidence") else None,
            metadata=data.get("metadata"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else lambda: datetime.now(timezone.utc)(),
            resolved=data.get("resolved", False),
            resolved_value=data.get("resolved_value"),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None
        )


@dataclass
class ToolResult:
    """
    Standardized result wrapper for all domain tools.

    Every tool in the system returns a ToolResult, ensuring consistent
    handling of successes, errors, and HITL triggers.

    Attributes:
        success: Whether the tool execution succeeded
        data: The actual result data (type varies by tool)
        confidence: Overall confidence score for the result
        error: Error message if success is False
        hitl_questions: List of questions to ask user if low confidence
        metadata: Additional result metadata (timing, source, etc.)
        tool_name: Name of the tool that produced this result
        execution_time_ms: Time taken to execute the tool
    """
    success: bool
    data: Any
    confidence: ConfidenceScore
    error: Optional[str] = None
    hitl_questions: list[HITLQuestion] = field(default_factory=list)
    metadata: Optional[dict] = None
    tool_name: Optional[str] = None
    execution_time_ms: Optional[float] = None

    def has_hitl_questions(self) -> bool:
        """Returns True if there are unresolved HITL questions."""
        return any(not q.resolved for q in self.hitl_questions)

    def get_unresolved_questions(self) -> list[HITLQuestion]:
        """Returns list of unresolved HITL questions."""
        return [q for q in self.hitl_questions if not q.resolved]

    def get_questions_by_priority(self) -> list[HITLQuestion]:
        """Returns unresolved questions sorted by priority (CRITICAL first)."""
        return sorted(
            self.get_unresolved_questions(),
            key=lambda q: q.priority.value
        )

    def get_next_question(self) -> Optional[HITLQuestion]:
        """Returns the highest priority unresolved question."""
        questions = self.get_questions_by_priority()
        return questions[0] if questions else None

    def add_hitl_question(
        self,
        question: str,
        field_name: str,
        category: QuestionCategory,
        priority: Priority,
        options: Optional[list[str]] = None,
        current_value: Any = None,
        confidence: Optional[ConfidenceScore] = None,
        metadata: Optional[dict] = None
    ) -> HITLQuestion:
        """Helper to add a new HITL question to the result."""
        hitl_q = HITLQuestion(
            question=question,
            field_name=field_name,
            category=category,
            priority=priority,
            options=options,
            current_value=current_value,
            confidence=confidence,
            metadata=metadata
        )
        self.hitl_questions.append(hitl_q)
        return hitl_q

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "success": self.success,
            "data": self.data,
            "confidence": self.confidence.to_dict(),
            "error": self.error,
            "hitl_questions": [q.to_dict() for q in self.hitl_questions],
            "metadata": self.metadata,
            "tool_name": self.tool_name,
            "execution_time_ms": self.execution_time_ms
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ToolResult":
        """Deserialize from dictionary."""
        return cls(
            success=data["success"],
            data=data["data"],
            confidence=ConfidenceScore.from_dict(data["confidence"]),
            error=data.get("error"),
            hitl_questions=[HITLQuestion.from_dict(q) for q in data.get("hitl_questions", [])],
            metadata=data.get("metadata"),
            tool_name=data.get("tool_name"),
            execution_time_ms=data.get("execution_time_ms")
        )

    @classmethod
    def success_result(
        cls,
        data: Any,
        confidence: Optional[ConfidenceScore] = None,
        tool_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> "ToolResult":
        """Factory for successful results."""
        return cls(
            success=True,
            data=data,
            confidence=confidence or ConfidenceScore.high(),
            tool_name=tool_name,
            metadata=metadata
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        tool_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> "ToolResult":
        """Factory for error results."""
        return cls(
            success=False,
            data=None,
            confidence=ConfidenceScore(value=0.0, reasoning="Tool execution failed"),
            error=error,
            tool_name=tool_name,
            metadata=metadata
        )

    @classmethod
    def low_confidence_result(
        cls,
        data: Any,
        confidence: ConfidenceScore,
        hitl_questions: list[HITLQuestion],
        tool_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> "ToolResult":
        """Factory for results that need human verification."""
        return cls(
            success=True,
            data=data,
            confidence=confidence,
            hitl_questions=hitl_questions,
            tool_name=tool_name,
            metadata=metadata
        )
