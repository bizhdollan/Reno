"""
Generation Service.

Handles image generation with critical element preservation:
- Initial generation from original image
- Additive generation (build on previous)
- Restart generation (back to original)
- Partial region regeneration
"""

import json
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from src.db.models import GenerationHistory, ImageAnalysis, PerspectiveChange
from src.core.llm.provider import LLMProvider
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import load_image_as_base64
from .session_cache import SessionCache


class GenerationService:
    """
    Service for generating renovation images.

    Responsibilities:
    - Generate initial image from vision
    - Generate additive (build on last image)
    - Generate restart (back to original)
    - Handle partial region regeneration
    - Always inject critical elements
    """

    def __init__(
        self,
        db: Session,
        vgm_provider: Optional[LLMProvider] = None,
        cache: Optional[SessionCache] = None
    ):
        self.db = db
        self.vgm = vgm_provider or LLMProvider.for_vgm()
        self.cache = cache or SessionCache()

    async def generate_initial(
        self,
        image_analysis_id: UUID,
        vision: str,
        critical_elements: dict,
        perspective_constraint: str = "",
        budget_materials: Optional[dict] = None
    ) -> GenerationHistory:
        """
        Generate initial image from original uploaded image.

        Args:
            image_analysis_id: UUID of the source ImageAnalysis
            vision: User's renovation vision description
            critical_elements: Elements to preserve (windows, doors, etc.)
            perspective_constraint: Camera angle constraint
            budget_materials: Optional budget-appropriate material suggestions

        Returns:
            GenerationHistory object with result_image_url
        """
        # Get source analysis
        analysis = self.db.query(ImageAnalysis).filter_by(id=image_analysis_id).first()
        if not analysis:
            raise ValueError(f"ImageAnalysis not found: {image_analysis_id}")

        print(f"[GenerationService] Generating initial image for project {analysis.project_id}")

        # Build prompt
        prompt = self._build_generation_prompt(
            base_image_url=analysis.image_url,
            vision=vision,
            critical_elements=critical_elements,
            perspective_constraint=perspective_constraint,
            budget_materials=budget_materials,
            mode="initial"
        )

        # Load image and generate
        image_data = await load_image_as_base64(analysis.image_url)
        result = await self._generate_image(image_data, prompt)

        # Store in database
        gen = GenerationHistory(
            project_id=analysis.project_id,
            source_image_id=image_analysis_id,
            generation_type="initial",
            prompt_data={
                "vision": vision,
                "constraints": critical_elements,
                "budget_materials": budget_materials
            },
            critical_elements=critical_elements,
            perspective_constraint=perspective_constraint,
            result_image_url=result.get("data_url")
        )
        self.db.add(gen)
        self.db.commit()
        self.db.refresh(gen)

        # Cache the generation
        self.cache.set_generation(gen.id, gen)

        print(f"[GenerationService] Initial generation complete: {gen.id}")
        return gen

    async def generate_additive(
        self,
        previous_generation_id: UUID,
        changes: str,
        critical_elements: dict,
        perspective_constraint: str = "",
        regional_scope: Optional[list[str]] = None
    ) -> GenerationHistory:
        """
        Generate image building on previous generation (additive mode).

        Args:
            previous_generation_id: UUID of the previous GenerationHistory
            changes: Description of changes to make
            critical_elements: Elements to preserve
            perspective_constraint: Camera angle constraint
            regional_scope: Optional list of regions to change (for partial regeneration)

        Returns:
            GenerationHistory object
        """
        # Get previous generation
        prev_gen = self.db.query(GenerationHistory).filter_by(id=previous_generation_id).first()
        if not prev_gen:
            raise ValueError(f"GenerationHistory not found: {previous_generation_id}")

        if not prev_gen.result_image_url:
            raise ValueError("Previous generation has no result image")

        print(f"[GenerationService] Generating additive on {previous_generation_id}")

        # Build prompt based on whether this is partial or full regeneration
        if regional_scope:
            prompt = self._build_partial_regeneration_prompt(
                changes=changes,
                regions_to_change=regional_scope,
                critical_elements=critical_elements,
                perspective_constraint=perspective_constraint
            )
        else:
            prompt = self._build_generation_prompt(
                base_image_url=prev_gen.result_image_url,
                vision=changes,
                critical_elements=critical_elements,
                perspective_constraint=perspective_constraint,
                mode="additive"
            )

        # Load previous image and generate
        image_data = await load_image_as_base64(prev_gen.result_image_url)
        result = await self._generate_image(image_data, prompt)

        # Store in database
        gen = GenerationHistory(
            project_id=prev_gen.project_id,
            source_image_id=previous_generation_id,
            generation_type="additive",
            prompt_data={
                "changes": changes,
                "constraints": critical_elements,
                "regional_scope": regional_scope
            },
            critical_elements=critical_elements,
            perspective_constraint=perspective_constraint,
            result_image_url=result.get("data_url")
        )
        self.db.add(gen)
        self.db.commit()
        self.db.refresh(gen)

        # Track perspective changes if regional scope specified
        if regional_scope:
            for region in regional_scope:
                change = PerspectiveChange(
                    project_id=prev_gen.project_id,
                    generation_id=gen.id,
                    change_category=region,
                    change_description=changes[:200]
                )
                self.db.add(change)
            self.db.commit()

        # Cache the generation
        self.cache.set_generation(gen.id, gen)

        print(f"[GenerationService] Additive generation complete: {gen.id}")
        return gen

    async def generate_restart(
        self,
        original_image_analysis_id: UUID,
        vision: str,
        critical_elements: dict,
        perspective_constraint: str = ""
    ) -> GenerationHistory:
        """
        Regenerate from original image (restart mode).

        Used when user dislikes the current direction and wants to start fresh.

        Args:
            original_image_analysis_id: UUID of the original ImageAnalysis
            vision: New renovation vision
            critical_elements: Elements to preserve
            perspective_constraint: Camera angle constraint

        Returns:
            GenerationHistory object
        """
        # Get original analysis
        analysis = self.db.query(ImageAnalysis).filter_by(id=original_image_analysis_id).first()
        if not analysis:
            raise ValueError(f"ImageAnalysis not found: {original_image_analysis_id}")

        print(f"[GenerationService] Restarting from original image")

        # Build prompt
        prompt = self._build_generation_prompt(
            base_image_url=analysis.image_url,
            vision=vision,
            critical_elements=critical_elements,
            perspective_constraint=perspective_constraint,
            mode="restart"
        )

        # Load original image and generate
        image_data = await load_image_as_base64(analysis.image_url)
        result = await self._generate_image(image_data, prompt)

        # Store in database
        gen = GenerationHistory(
            project_id=analysis.project_id,
            source_image_id=original_image_analysis_id,
            generation_type="restart",
            prompt_data={
                "vision": vision,
                "constraints": critical_elements
            },
            critical_elements=critical_elements,
            perspective_constraint=perspective_constraint,
            result_image_url=result.get("data_url")
        )
        self.db.add(gen)
        self.db.commit()
        self.db.refresh(gen)

        # Cache the generation
        self.cache.set_generation(gen.id, gen)

        print(f"[GenerationService] Restart generation complete: {gen.id}")
        return gen

    async def _generate_image(self, image_data: str, prompt: str) -> dict:
        """Call VGM to generate image."""
        result = await self.vgm.generate_image(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert renovation visualizer. Generate realistic room transformations while strictly preserving structural constraints."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                }
            ],
            temperature=0.7,
            max_tokens=1024
        )
        return result

    def _build_generation_prompt(
        self,
        base_image_url: str,
        vision: str,
        critical_elements: dict,
        perspective_constraint: str,
        budget_materials: Optional[dict] = None,
        mode: str = "initial"
    ) -> str:
        """Build generation prompt with critical elements injection."""
        constraints = []

        # Inject critical elements
        if critical_elements.get("windows"):
            w = critical_elements["windows"]
            count = w.get("count", 1)
            wall = w.get("wall", "")
            constraints.append(f"PRESERVE: {count} window(s) on {wall} wall - do not add, remove, or relocate")

        if critical_elements.get("doors"):
            d = critical_elements["doors"]
            count = d.get("count", 1)
            wall = d.get("wall", "")
            door_type = d.get("type", "standard")
            constraints.append(f"PRESERVE: {count} {door_type} door(s) on {wall} wall - do not modify")

        if critical_elements.get("ceiling_height"):
            constraints.append(f"PRESERVE: Ceiling height of {critical_elements['ceiling_height']}")

        if critical_elements.get("load_bearing_walls"):
            walls = critical_elements["load_bearing_walls"]
            constraints.append(f"PRESERVE: Load-bearing walls on {', '.join(walls)} sides")

        # Add perspective constraint
        if perspective_constraint:
            constraints.append(perspective_constraint)

        # Build budget hint
        budget_hint = ""
        if budget_materials:
            materials_list = []
            for category, options in budget_materials.items():
                if isinstance(options, list) and options:
                    materials_list.append(f"{category}: {options[0]}")
            if materials_list:
                budget_hint = f"\n\nSuggested materials (budget-appropriate): {', '.join(materials_list)}"

        # Mode-specific instructions
        mode_instruction = {
            "initial": "Transform this room based on the renovation vision while preserving all constraints.",
            "additive": "Apply the requested changes to this already-renovated room while preserving all constraints.",
            "restart": "Create a fresh renovation of this original room based on the new vision while preserving all constraints."
        }.get(mode, "Transform this room while preserving all constraints.")

        prompt = f"""RENOVATION TASK: {mode_instruction}

VISION: {vision}
{budget_hint}

CRITICAL CONSTRAINTS (MUST PRESERVE - DO NOT MODIFY):
{chr(10).join(f"- {c}" for c in constraints) if constraints else "- Maintain room layout and structure"}

GENERATION RULES:
1. Keep the exact same room dimensions and layout
2. Preserve all windows, doors, and structural elements in their original positions
3. Apply the renovation vision only to changeable surfaces and fixtures
4. Maintain realistic proportions and lighting
5. Generate a photorealistic result

Generate the renovated room image."""

        return prompt

    def _build_partial_regeneration_prompt(
        self,
        changes: str,
        regions_to_change: list[str],
        critical_elements: dict,
        perspective_constraint: str
    ) -> str:
        """Build prompt for partial region regeneration."""
        all_regions = ["floor", "walls", "ceiling", "fixtures", "furniture", "lighting"]
        preserve_regions = [r for r in all_regions if r not in regions_to_change]

        constraints = []

        # Critical elements
        if critical_elements.get("windows"):
            constraints.append(f"Windows: {critical_elements['windows']}")
        if critical_elements.get("doors"):
            constraints.append(f"Doors: {critical_elements['doors']}")

        if perspective_constraint:
            constraints.append(perspective_constraint)

        prompt = f"""PARTIAL RENOVATION - CHANGE ONLY SPECIFIC REGIONS

CHANGES REQUESTED: {changes}

REGIONS TO MODIFY: {', '.join(regions_to_change)}

REGIONS TO PRESERVE EXACTLY (do not change these):
{chr(10).join(f"- {r}" for r in preserve_regions)}

CRITICAL STRUCTURAL CONSTRAINTS:
{chr(10).join(f"- {c}" for c in constraints) if constraints else "- Maintain room structure"}

INSTRUCTIONS:
1. ONLY modify the specified regions: {', '.join(regions_to_change)}
2. Keep all other elements EXACTLY as they appear
3. Blend changes naturally with preserved elements
4. Maintain consistent lighting and perspective

Generate the partially modified room image."""

        return prompt

    async def get_generation_by_id(self, generation_id: UUID) -> Optional[GenerationHistory]:
        """Get generation by ID, using cache if available."""
        gen = self.cache.get_generation(generation_id)
        if not gen:
            gen = self.db.query(GenerationHistory).filter_by(id=generation_id).first()
            if gen:
                self.cache.set_generation(generation_id, gen)
        return gen

    async def get_latest_generation(self, project_id: UUID) -> Optional[GenerationHistory]:
        """Get the most recent generation for a project."""
        # Try cache first
        cached = self.cache.get_latest_generation(project_id)
        if cached:
            return cached

        # Query database
        gen = self.db.query(GenerationHistory).filter_by(
            project_id=project_id
        ).order_by(GenerationHistory.created_at.desc()).first()

        if gen:
            self.cache.set_generation(gen.id, gen)

        return gen

    async def update_user_feedback(
        self,
        generation_id: UUID,
        feedback: str
    ) -> GenerationHistory:
        """Update user feedback for a generation."""
        gen = self.db.query(GenerationHistory).filter_by(id=generation_id).first()
        if not gen:
            raise ValueError(f"GenerationHistory not found: {generation_id}")

        gen.user_feedback = feedback
        self.db.commit()
        self.db.refresh(gen)

        # Update cache
        self.cache.set_generation(gen.id, gen)

        return gen
