from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from src.core.logger import get_logger
from src.db.database import SessionLocal

logger = get_logger(__name__)
from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import ProjectState
# Import from submodules to avoid circular imports
from src.core.services.session_cache import SessionCache
from src.core.services.image_analysis_service import ImageAnalysisService
from src.core.services.perspective_service import PerspectiveService
from src.core.services.budget_context_service import BudgetContextService
from src.core.services.generation_service import GenerationService
from src.core.services.sentiment_service import SentimentService
from src.core.services.correction_service import CorrectionService
from src.db.models import ImageAnalysis, ImageMetadata, GenerationHistory


class ServiceIntegration:
    """
    Integration layer for using services from the node.

    Provides a unified interface to access all services with proper
    initialization and cleanup.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        db: Optional[Session] = None,
        cache: Optional[SessionCache] = None
    ):
        self.project_id = project_id
        self._db = db
        self._owns_db = db is None  # Track if we created the db session
        self.cache = cache or SessionCache()

        # Lazy-initialized services
        self._image_analysis_service: Optional[ImageAnalysisService] = None
        self._perspective_service: Optional[PerspectiveService] = None
        self._budget_context_service: Optional[BudgetContextService] = None
        self._generation_service: Optional[GenerationService] = None
        self._sentiment_service: Optional[SentimentService] = None
        self._correction_service: Optional[CorrectionService] = None

    @classmethod
    def from_state(cls, state: ProjectState) -> "ServiceIntegration":
        """Create ServiceIntegration from ProjectState."""
        # Use internal_project_id (UUID) for DB operations, not project_id (token)
        project_id = state.get("internal_project_id") or state.get("project_id")
        return cls(project_id=project_id)

    @property
    def db(self) -> Session:
        """Get or create database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def is_refactored_mode(self) -> bool:
        """Check if we should use refactored (DB-backed) mode."""
        return self.project_id is not None

    # =========================================================================
    # Service Accessors (Lazy Initialization)
    # =========================================================================

    @property
    def image_analysis(self) -> ImageAnalysisService:
        """Get ImageAnalysisService instance."""
        if self._image_analysis_service is None:
            self._image_analysis_service = ImageAnalysisService(
                db=self.db,
                llm_provider=LLMProvider.for_vlm(),
                cache=self.cache
            )
        return self._image_analysis_service

    @property
    def perspective(self) -> PerspectiveService:
        """Get PerspectiveService instance."""
        if self._perspective_service is None:
            self._perspective_service = PerspectiveService(
                db=self.db,
                llm_provider=LLMProvider.for_vlm(),
                cache=self.cache
            )
        return self._perspective_service

    @property
    def budget_context(self) -> BudgetContextService:
        """Get BudgetContextService instance."""
        if self._budget_context_service is None:
            self._budget_context_service = BudgetContextService(
                db=self.db,
                llm_provider=LLMProvider.for_llm(),
                cache=self.cache
            )
        return self._budget_context_service

    @property
    def generation(self) -> GenerationService:
        """Get GenerationService instance."""
        if self._generation_service is None:
            self._generation_service = GenerationService(
                db=self.db,
                vgm_provider=LLMProvider.for_vgm(),
                cache=self.cache
            )
        return self._generation_service

    @property
    def sentiment(self) -> SentimentService:
        """Get SentimentService instance."""
        if self._sentiment_service is None:
            self._sentiment_service = SentimentService(
                llm_provider=LLMProvider.for_llm()
            )
        return self._sentiment_service

    @property
    def correction(self) -> CorrectionService:
        """Get CorrectionService instance."""
        if self._correction_service is None:
            self._correction_service = CorrectionService(
                db=self.db,
                llm_provider=LLMProvider.for_llm(),
                cache=self.cache
            )
        return self._correction_service

    async def generate_with_services(
        self,
        vision: str,
        mode: str = "initial",
        previous_generation_id: Optional[str] = None,
        regional_scope: Optional[list[str]] = None
    ) -> GenerationHistory:
        """
        Generate image using the refactored service layer.

        Args:
            vision: User's renovation vision
            mode: "initial", "additive", or "restart"
            previous_generation_id: Required for additive mode
            regional_scope: Optional regions for partial regeneration

        Returns:
            GenerationHistory record
        """
        if not self.project_id:
            raise ValueError("project_id required for DB-backed operations")

        project_uuid = UUID(self.project_id)

        # Get critical elements and perspective from latest analysis
        analyses = await self.image_analysis.get_analyses_for_project(project_uuid)
        if not analyses:
            raise ValueError("No image analysis found for project")

        latest_analysis = analyses[0]
        critical_elements = latest_analysis.critical_elements or {}

        # Get perspective constraint
        metadata = await self.perspective.get_metadata_for_analysis(latest_analysis.id)
        perspective_constraint = ""
        if metadata:
            perspective_constraint = self.perspective.build_perspective_constraint(
                metadata.perspective_type,
                float(metadata.perspective_confidence or 0)
            )

        # Generate based on mode
        if mode == "initial" or mode == "restart":
            return await self.generation.generate_initial(
                image_analysis_id=latest_analysis.id,
                vision=vision,
                critical_elements=critical_elements,
                perspective_constraint=perspective_constraint
            )
        elif mode == "additive":
            if not previous_generation_id:
                # Get latest generation if not specified
                latest_gen = await self.generation.get_latest_generation(project_uuid)
                if latest_gen:
                    previous_generation_id = str(latest_gen.id)
                else:
                    raise ValueError("No previous generation found for additive mode")

            return await self.generation.generate_additive(
                previous_generation_id=UUID(previous_generation_id),
                changes=vision,
                critical_elements=critical_elements,
                perspective_constraint=perspective_constraint,
                regional_scope=regional_scope
            )
        else:
            raise ValueError(f"Unknown generation mode: {mode}")

    async def handle_user_correction(
        self,
        user_message: str,
        current_data: dict
    ) -> tuple[dict, bool]:
        """
        Handle user correction using the correction service.

        Returns:
            (updated_data, success)
        """
        if not self.project_id:
            return current_data, False

        try:
            project_uuid = UUID(self.project_id)
            updated_data, _ = await self.correction.apply_correction_from_message(
                project_id=project_uuid,
                user_message=user_message,
                current_data=current_data,
                data_type="extraction"
            )
            return updated_data, True
        except Exception as e:
            logger.error(f"[ServiceIntegration] Correction failed: {e}", exc_info=True)
            return current_data, False

    async def handle_undo(self) -> tuple[bool, str]:
        """
        Handle undo request.

        Returns:
            (success, message)
        """
        if not self.project_id:
            return False, "Undo requires project context"

        project_uuid = UUID(self.project_id)
        return await self.correction.undo_last_correction(project_uuid)

    async def detect_budget_if_mentioned(
        self,
        user_message: str
    ) -> Optional[dict]:
        """
        Detect budget context if user mentions budget.

        Returns:
            Budget context dict or None if no budget mentioned
        """
        if not self.budget_context.has_budget_keywords(user_message):
            return None

        if not self.project_id:
            return None

        project_uuid = UUID(self.project_id)
        context = await self.budget_context.detect_budget_sentiment(
            user_message=user_message,
            project_id=project_uuid
        )

        return {
            "sentiment": context.budget_sentiment,
            "suggested_materials": context.suggested_materials
        }

    async def classify_regeneration_intent(
        self,
        user_message: str
    ) -> tuple[str, list[str]]:
        """
        Classify if user wants additive or restart, and detect regions.

        Returns:
            (mode, regions) where mode is "additive" or "restart"
        """
        mode = await self.sentiment.detect_regeneration_mode(user_message)
        regions = await self.sentiment.detect_regional_scope(user_message)
        return mode, regions

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self) -> None:
        """Clean up resources. Call at end of node execution."""
        self.cache.clear()
        if self._owns_db and self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup()
        return False

async def should_use_services(state: ProjectState) -> bool:
    """
    Determine if we should use the refactored services.

    Checks if internal_project_id (UUID) is set in state.
    """
    return state.get("internal_project_id") is not None


async def check_undo_request(user_message: str) -> bool:
    """Check if user message is an undo request."""
    sentiment_service = SentimentService()
    return sentiment_service.contains_undo_request(user_message)
