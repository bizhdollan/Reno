"""
HITL (Human-in-the-Loop) Manager

Coordinates HITL questions across all domain tools.
Tracks unresolved questions, prioritizes by criticality,
and records user-provided answers.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from src.core.logger import get_logger
from src.core.tools.base import (
    ToolResult,
    ConfidenceScore,
    HITLQuestion,
    Priority,
    QuestionCategory,
)

logger = get_logger(__name__)


class HITLManager:
    """
    Manages Human-in-the-Loop questions for a project.

    Responsibilities:
    - Collect HITL questions from tool results
    - Track question status (pending, resolved)
    - Prioritize questions by criticality
    - Store user-provided answers
    - Provide questions to chatbot for user interaction
    """

    def __init__(self, project_id: str):
        """
        Initialize HITL Manager for a project.

        Args:
            project_id: Project UUID or token
        """
        self.project_id = project_id
        self._questions: Dict[str, HITLQuestion] = {}  # id -> question
        self._domain_questions: Dict[str, List[str]] = {}  # domain -> [question_ids]

    def add_tool_result(self, domain: str, tool_result: ToolResult) -> int:
        """
        Add HITL questions from a tool result.

        Args:
            domain: Domain name (e.g., "location", "space", "compliance")
            tool_result: ToolResult that may contain HITL questions

        Returns:
            Number of new questions added
        """
        if not tool_result.hitl_questions:
            return 0

        added = 0
        if domain not in self._domain_questions:
            self._domain_questions[domain] = []

        for question in tool_result.hitl_questions:
            if question.id not in self._questions:
                self._questions[question.id] = question
                self._domain_questions[domain].append(question.id)
                added += 1
                logger.info(f"[HITL] Added question: {question.field_name} (priority: {question.priority.name})")

        return added

    def add_question(
        self,
        question: str,
        field_name: str,
        category: QuestionCategory,
        priority: Priority,
        domain: str = "general",
        options: Optional[List[str]] = None,
        current_value: Any = None,
        confidence: Optional[ConfidenceScore] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> HITLQuestion:
        """
        Add a single HITL question.

        Args:
            question: Question text
            field_name: Field this question relates to
            category: Question category
            priority: Question priority
            domain: Domain that generated this question
            options: Optional answer options
            current_value: Current (low confidence) value
            confidence: Confidence score that triggered this
            metadata: Additional context

        Returns:
            The created HITLQuestion
        """
        hitl_question = HITLQuestion(
            question=question,
            field_name=field_name,
            category=category,
            priority=priority,
            options=options,
            current_value=current_value,
            confidence=confidence,
            metadata=metadata
        )

        self._questions[hitl_question.id] = hitl_question

        if domain not in self._domain_questions:
            self._domain_questions[domain] = []
        self._domain_questions[domain].append(hitl_question.id)

        logger.info(f"[HITL] Added question: {field_name} (priority: {priority.name})")

        return hitl_question

    def get_all_questions(self) -> List[HITLQuestion]:
        """Get all questions (resolved and unresolved)."""
        return list(self._questions.values())

    def get_unresolved_questions(self) -> List[HITLQuestion]:
        """Get all unresolved questions."""
        return [q for q in self._questions.values() if not q.resolved]

    def get_resolved_questions(self) -> List[HITLQuestion]:
        """Get all resolved questions."""
        return [q for q in self._questions.values() if q.resolved]

    def get_questions_by_priority(self) -> List[HITLQuestion]:
        """
        Get unresolved questions sorted by priority.

        Priority order: CRITICAL -> HIGH -> MEDIUM -> LOW
        """
        unresolved = self.get_unresolved_questions()
        return sorted(unresolved, key=lambda q: q.priority.value)

    def get_questions_by_category(self, category: QuestionCategory) -> List[HITLQuestion]:
        """Get unresolved questions of a specific category."""
        return [
            q for q in self.get_unresolved_questions()
            if q.category == category
        ]

    def get_questions_by_domain(self, domain: str) -> List[HITLQuestion]:
        """Get questions from a specific domain."""
        question_ids = self._domain_questions.get(domain, [])
        return [self._questions[qid] for qid in question_ids if qid in self._questions]

    def get_next_question(self) -> Optional[HITLQuestion]:
        """
        Get the highest priority unresolved question.

        Returns:
            HITLQuestion or None if no unresolved questions
        """
        questions = self.get_questions_by_priority()
        return questions[0] if questions else None

    def get_critical_questions(self) -> List[HITLQuestion]:
        """Get all CRITICAL priority unresolved questions."""
        return [
            q for q in self.get_unresolved_questions()
            if q.priority == Priority.CRITICAL
        ]

    def resolve_question(self, question_id: str, user_value: Any) -> bool:
        """
        Mark a question as resolved with the user's answer.

        Args:
            question_id: ID of the question to resolve
            user_value: User's provided answer

        Returns:
            True if question was found and resolved
        """
        if question_id not in self._questions:
            logger.warning(f"[HITL] Question not found: {question_id}")
            return False

        question = self._questions[question_id]
        question.resolve(user_value)

        logger.info(f"[HITL] Resolved: {question.field_name} = {user_value}")

        return True

    def resolve_by_field_name(self, field_name: str, user_value: Any) -> bool:
        """
        Resolve a question by its field name.

        Args:
            field_name: Field name of the question
            user_value: User's provided answer

        Returns:
            True if a matching question was found and resolved
        """
        for question in self._questions.values():
            if question.field_name == field_name and not question.resolved:
                question.resolve(user_value)
                logger.info(f"[HITL] Resolved by field: {field_name} = {user_value}")
                return True

        logger.warning(f"[HITL] No unresolved question found for field: {field_name}")
        return False

    def get_resolved_values(self) -> Dict[str, Any]:
        """
        Get all resolved values as a dictionary.

        Returns:
            Dict mapping field_name to resolved_value
        """
        return {
            q.field_name: q.resolved_value
            for q in self._questions.values()
            if q.resolved
        }

    def has_critical_unresolved(self) -> bool:
        """Check if there are any CRITICAL unresolved questions."""
        return len(self.get_critical_questions()) > 0

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of HITL status.

        Returns:
            Dict with counts and status
        """
        all_questions = list(self._questions.values())
        unresolved = self.get_unresolved_questions()
        resolved = self.get_resolved_questions()

        by_priority = {}
        for priority in Priority:
            by_priority[priority.name] = len([
                q for q in unresolved if q.priority == priority
            ])

        by_category = {}
        for category in QuestionCategory:
            by_category[category.value] = len([
                q for q in unresolved if q.category == category
            ])

        return {
            "total_questions": len(all_questions),
            "unresolved": len(unresolved),
            "resolved": len(resolved),
            "has_critical": self.has_critical_unresolved(),
            "by_priority": by_priority,
            "by_category": by_category,
            "domains": list(self._domain_questions.keys())
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager state to dictionary for storage."""
        return {
            "project_id": self.project_id,
            "questions": [q.to_dict() for q in self._questions.values()],
            "domain_questions": self._domain_questions
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HITLManager":
        """Deserialize manager state from dictionary."""
        manager = cls(project_id=data["project_id"])

        for q_data in data.get("questions", []):
            question = HITLQuestion.from_dict(q_data)
            manager._questions[question.id] = question

        manager._domain_questions = data.get("domain_questions", {})

        return manager

    def format_for_chatbot(self, max_questions: int = 3) -> str:
        """
        Format questions for chatbot display.

        Args:
            max_questions: Maximum questions to include

        Returns:
            Formatted string for chatbot
        """
        questions = self.get_questions_by_priority()[:max_questions]

        if not questions:
            return ""

        lines = ["I have a few questions to ensure accuracy:\n"]

        for i, q in enumerate(questions, 1):
            priority_label = ""
            if q.priority == Priority.CRITICAL:
                priority_label = " [IMPORTANT]"
            elif q.priority == Priority.HIGH:
                priority_label = " [High Priority]"

            lines.append(f"{i}. {q.question}{priority_label}")

            if q.options:
                options_str = " | ".join(q.options[:4])
                lines.append(f"   Options: {options_str}")

            if q.current_value is not None:
                lines.append(f"   (Current estimate: {q.current_value})")

            lines.append("")

        return "\n".join(lines)


async def load_hitl_manager(project_id: str) -> HITLManager:
    """
    Load HITL Manager from database for a project.

    Args:
        project_id: Project UUID or token

    Returns:
        HITLManager instance
    """
    from src.db.database import SessionLocal
    from src.db.models import Project

    db = SessionLocal()
    try:
        # Try UUID first, then token
        try:
            project = db.query(Project).filter(Project.id == UUID(project_id)).first()
        except ValueError:
            project = db.query(Project).filter(Project.token == project_id).first()

        if not project:
            logger.warning(f"[HITL] Project not found: {project_id}")
            return HITLManager(project_id=project_id)

        # Load from pending_hitl_questions JSONB field
        if project.pending_hitl_questions:
            return HITLManager.from_dict(project.pending_hitl_questions)
        else:
            return HITLManager(project_id=str(project.id))

    finally:
        db.close()


async def save_hitl_manager(manager: HITLManager) -> bool:
    """
    Save HITL Manager state to database.

    Args:
        manager: HITLManager instance to save

    Returns:
        True if saved successfully
    """
    from src.db.database import SessionLocal
    from src.db.models import Project

    db = SessionLocal()
    try:
        # Try UUID first, then token
        try:
            project = db.query(Project).filter(Project.id == UUID(manager.project_id)).first()
        except ValueError:
            project = db.query(Project).filter(Project.token == manager.project_id).first()

        if not project:
            logger.error(f"[HITL] Cannot save - project not found: {manager.project_id}")
            return False

        project.pending_hitl_questions = manager.to_dict()
        db.commit()

        logger.info(f"[HITL] Saved {len(manager.get_all_questions())} questions for project {manager.project_id}")
        return True

    except Exception as e:
        logger.error(f"[HITL] Save failed: {e}")
        db.rollback()
        return False

    finally:
        db.close()
