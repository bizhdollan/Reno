import asyncio
import json
from enum import Enum
from datetime import datetime, timedelta

from src.core.logger import get_logger
from src.core.llm.provider import LLMProvider, LLMProviderError

logger = get_logger(__name__)
from src.core.langgraph.state import (
    ProjectState,
    merge_image_analyses_to_extracted,
)
from src.core.langgraph.utils import get_latest_user_message
from src.core.langgraph.config import VISION_PROMPT
from src.db.database import SessionLocal
from src.db.models import Project

# Import from split modules
from src.core.langgraph.nodes.image_analysis_generation.image_helpers import (
    get_placeholder_image_url,
)
from src.core.langgraph.nodes.image_analysis_generation.intent_detection import (
    unified_classify,
    generate_expert_suggestions,
    clarify_vague_request,
    detect_regeneration_mode,
    answer_image_question,
    parse_multi_image_feedback,
)
from src.core.langgraph.nodes.image_analysis_generation.image_generation import (
    generate_renovation_image,
)
from src.core.langgraph.nodes.image_analysis_generation.history import (
    add_to_image_history,
    get_image_from_history,
)
from src.core.langgraph.nodes.image_analysis_generation.analysis import (
    analyze_images_parallel,
    format_extracted_data_for_display,
    apply_user_correction,
    generate_brief_room_summary,
    detect_features_to_retain,
)

# Smart search integration
from src.core.services.smart_search_service import extract_search_insights
from src.core.services.renovation_inspiration_service import start_smart_search_background

# NEW: Service integration layer for DB-backed operations
from src.core.langgraph.nodes.image_analysis_generation.node_services import (
    ServiceIntegration,
    should_use_services,
    check_undo_request,
)


# State constants
class ImageSubState(str, Enum):
    """Image analysis sub-states."""
    ANALYZING = "analyzing"
    CONFIRMING_EXTRACTION = "confirming_extraction"
    COLLECTING_VISION = "collecting_vision"
    DESIGN_CONVERSATION = "design_conversation"
    SELECTING_SUGGESTIONS = "selecting_suggestions"
    GENERATING = "generating"
    GENERATING_PARALLEL = "generating_parallel"
    CONFIRMING_PROPOSAL = "confirming_proposal"

# Timeout configuration (in seconds)
IMAGE_GENERATION_TIMEOUT = 90.0  # 90 seconds for image generation operations
INSPIRATION_WAIT_TIMEOUT = 45.0  # 45 seconds max wait for inspirations (smart search takes ~35-40s)
INSPIRATION_RETRY_INTERVAL = 3.0  # Check every 3 seconds


async def get_renovation_inspirations_with_wait(project_id_token: str, max_wait_seconds: float = INSPIRATION_WAIT_TIMEOUT) -> dict:
    """
    Retrieve renovation inspirations from database with wait/retry logic.

    If inspirations are not available:
    - Wait up to max_wait_seconds for background task to complete
    - Check every INSPIRATION_RETRY_INTERVAL seconds
    - If still not available after timeout, return None

    Args:
        project_id_token: Project token (PRJ-XXXXXX)
        max_wait_seconds: Maximum time to wait for inspirations

    Returns:
        Inspirations dict if available, None otherwise
    """
    if not project_id_token:
        logger.warning("[inspirations] No project_id_token provided")
        return None

    db = None
    try:
        db = SessionLocal()
        start_time = asyncio.get_event_loop().time()

        # Get project
        try:
            project = db.query(Project).filter(Project.token == project_id_token).first()
        except Exception as db_error:
            logger.error(f"[inspirations] Database query failed for project {project_id_token}: {db_error}", exc_info=True)
            return None

        if not project:
            logger.info(f"[inspirations] Project not found: {project_id_token}")
            return None

        # Check if inspirations already available AND complete (not pending Tavily)
        if project.renovation_inspirations:
            if not project.renovation_inspirations.get("_tavily_pending"):
                logger.info(f"[inspirations] Retrieved complete inspirations for {project_id_token}")
                return project.renovation_inspirations
            else:
                logger.info(f"[inspirations] Inspirations exist but Tavily search pending, waiting...")

        # Need to wait: either no inspirations or Tavily pending
        # Wait with retries
        elapsed = 0
        while elapsed < max_wait_seconds:
            try:
                await asyncio.sleep(INSPIRATION_RETRY_INTERVAL)
            except asyncio.CancelledError:
                logger.warning("[inspirations] Wait cancelled by asyncio")
                return None

            elapsed = asyncio.get_event_loop().time() - start_time

            # Refresh and check again
            try:
                db.refresh(project)
            except Exception as refresh_error:
                logger.error(f"[inspirations] Failed to refresh project from database: {refresh_error}")
                # Continue waiting, next iteration might succeed
                continue

            if project.renovation_inspirations:
                # Check if Tavily search completed (no pending flag)
                if not project.renovation_inspirations.get("_tavily_pending"):
                    logger.info(f"[inspirations] Complete inspirations available after {elapsed:.1f}s")
                    return project.renovation_inspirations
                else:
                    logger.info(f"[inspirations] Tavily still pending... ({elapsed:.1f}s/{max_wait_seconds}s)")
            else:
                logger.info(f"[inspirations] Still waiting for inspirations... ({elapsed:.1f}s/{max_wait_seconds}s)")

        # Timeout reached - return whatever we have (even if pending)
        if project.renovation_inspirations:
            logger.info(f"[inspirations] Timeout reached, returning partial inspirations (Tavily may be pending)")
            return project.renovation_inspirations

        logger.info(f"[inspirations] Timeout reached, no inspirations available")
        return None

    except Exception as e:
        logger.error(f"[inspirations] Unexpected error retrieving inspirations: {e}", exc_info=True)
        return None
    finally:
        if db:
            try:
                db.close()
            except Exception as close_error:
                logger.error(f"[inspirations] Error closing database session: {close_error}")


async def image_analysis_generation_node(state: ProjectState) -> dict:
    """
    Main image analysis and generation node.

    Sub-states:
    - analyzing: Process new images, extract ALL data
    - confirming_extraction: User reviews/corrects all data at once
    - collecting_vision: OPTIONAL - collect user's renovation vision
    - generating: Generate proposal/preview image
    - confirming_proposal: User reviews generated image

    REFACTORED ARCHITECTURE:
    When project_id is present, data is stored in DB via services.
    Legacy state fields are maintained for backward compatibility.
    """
    sub_state = state.get("image_sub_state", "analyzing")
    messages = state.get("messages", [])
    user_message, new_image_urls = get_latest_user_message(messages)

    # Check for pending images from project_basics transition
    pending_images = state.get("_pending_images", [])
    if pending_images:
        new_image_urls = pending_images

    # IMPORTANT: Always preserve existing state data
    image_analyses = list(state.get("image_analyses", []))
    extracted_data = dict(state.get("extracted_data", {}))
    renovation_vision = state.get("renovation_vision")

    updates = {
        "image_analyses": image_analyses,
        "extracted_data": extracted_data,
    }

    # NEW: Initialize service integration for DB-backed operations
    # Use internal_project_id (UUID) for DB operations, fall back to project_id
    internal_project_id = state.get("internal_project_id") or state.get("project_id")
    services = ServiceIntegration(project_id=internal_project_id) if internal_project_id else None
    use_services = await should_use_services(state)

    # NEW: Check for undo request early
    if user_message and use_services and await check_undo_request(user_message):
        success, message = await services.handle_undo()
        updates["messages"] = [{"role": "assistant", "content": message}]
        updates["awaiting_user_input"] = True
        if services:
            services.cleanup()
        return updates

    # Preserve generation-related state (critical for regeneration)
    if state.get("generated_image_url"):
        updates["generated_image_url"] = state["generated_image_url"]
    if state.get("generation_prompt"):
        updates["generation_prompt"] = state["generation_prompt"]
    if state.get("generation_description"):
        updates["generation_description"] = state["generation_description"]
    if state.get("original_image_urls"):
        updates["original_image_urls"] = state["original_image_urls"]
    if state.get("image_generation_feedback"):
        updates["image_generation_feedback"] = state["image_generation_feedback"]

    # Preserve new conversation state fields
    if state.get("expertise_level"):
        updates["expertise_level"] = state["expertise_level"]
    if state.get("last_generated_image_url"):
        updates["last_generated_image_url"] = state["last_generated_image_url"]
    if state.get("pending_suggestions"):
        updates["pending_suggestions"] = state["pending_suggestions"]
    if state.get("selected_options_for_generation"):
        updates["selected_options_for_generation"] = state["selected_options_for_generation"]
    if state.get("generated_options"):
        updates["generated_options"] = state["generated_options"]
    if state.get("pending_feedback"):
        updates["pending_feedback"] = state["pending_feedback"]

    # Preserve image history and feature retention
    if state.get("generated_image_history"):
        updates["generated_image_history"] = state["generated_image_history"]
    if state.get("selected_final_image_url"):
        updates["selected_final_image_url"] = state["selected_final_image_url"]
    if state.get("original_features_to_retain"):
        updates["original_features_to_retain"] = state["original_features_to_retain"]
    if state.get("brief_room_summary"):
        updates["brief_room_summary"] = state["brief_room_summary"]

    # NEW: Preserve hallucination prevention data
    if state.get("_visible_elements"):
        updates["_visible_elements"] = state["_visible_elements"]
    if state.get("_image_scope"):
        updates["_image_scope"] = state["_image_scope"]
    if state.get("_must_not_add"):
        updates["_must_not_add"] = state["_must_not_add"]

    # Clear pending images after using
    if pending_images:
        updates["_pending_images"] = []

    project_type = state.get("project_type", "renovation")

    logger.info(f"[image_analysis] SUB_STATE: {sub_state} | user_message={user_message!r} | "
          f"new_images={len(new_image_urls)} | stored_analyses={len(image_analyses)}")

    # =========================================================================
    # ANALYZING STATE - Extract all data from images
    # =========================================================================
    if sub_state == "analyzing":
        if new_image_urls:
            logger.info(f"[image_analysis] Processing {len(new_image_urls)} images in parallel...")

            # Get project_id for event broadcasting
            project_id_for_events = state.get("project_id")

            # Emit analysis_start event for SSE streaming
            if project_id_for_events:
                try:
                    from src.core.services.event_broadcaster import emit_analysis_start
                    await emit_analysis_start(project_id_for_events, len(new_image_urls))
                except Exception as event_error:
                    logger.error(f"[image_analysis] Failed to emit analysis_start event: {event_error}")
                    # Continue processing - event emission failure shouldn't block analysis

            # Analyze all images in parallel (with progress events)
            # OPTIMIZED: Now uses unified_image_analysis - 1 VLM call per image instead of 6+
            try:
                image_analyses = await analyze_images_parallel(
                    image_urls=new_image_urls,
                    project_type=project_type,
                    project_id=project_id_for_events,
                    project_title=state.get("project_title")
                )
                updates["image_analyses"] = image_analyses
            except Exception as analysis_error:
                logger.error(f"[image_analysis] Image analysis failed: {analysis_error}", exc_info=True)
                updates["messages"] = [{"role": "assistant", "content": "I encountered an error analyzing your images. Please try uploading them again or contact support if the issue persists."}]
                updates["awaiting_user_input"] = True
                if services:
                    services.cleanup()
                return updates

            # Merge into extracted_data (kept internally, not shown to user)
            try:
                extracted_data = merge_image_analyses_to_extracted(image_analyses)
                updates["extracted_data"] = extracted_data
            except Exception as merge_error:
                logger.error(f"[image_analysis] Failed to merge image analyses: {merge_error}", exc_info=True)
                # Continue with empty extracted_data rather than failing
                extracted_data = {}
                updates["extracted_data"] = extracted_data

            # Detect features to retain (parallel with summary generation)
            primary_image_url = new_image_urls[0]

            # Run feature detection and brief summary in parallel
            features_task = detect_features_to_retain(primary_image_url)
            summary_task = generate_brief_room_summary(primary_image_url, project_type, extracted_data)

            try:
                features_result, summary_result = await asyncio.gather(features_task, summary_task)
            except Exception as gather_error:
                logger.error(f"[image_analysis] Failed to gather features/summary: {gather_error}", exc_info=True)
                # Provide default values to continue gracefully
                features_result = {"must_retain": [], "visible_elements": {}, "image_scope": {"frame_type": "full_room", "room_coverage_pct": 100}, "must_not_add": []}
                summary_result = {"brief_summary": f"A {project_type} space.", "room_vibe": "current"}

            # Store features to retain for later image generation
            # NEW: Also extract visible_elements, image_scope, and must_not_add for hallucination prevention
            features_to_retain = features_result.get("must_retain", features_result.get("must_retain_features", []))
            visible_elements = features_result.get("visible_elements", {})
            image_scope = features_result.get("image_scope", {"frame_type": "full_room", "room_coverage_pct": 100})
            must_not_add = features_result.get("must_not_add", [])

            updates["original_features_to_retain"] = features_to_retain
            updates["_visible_elements"] = visible_elements
            updates["_image_scope"] = image_scope
            updates["_must_not_add"] = must_not_add

            logger.info(f"[image_analysis] Features to retain: {features_to_retain}")
            logger.info(f"[image_analysis] Image scope: {image_scope.get('frame_type')} (~{image_scope.get('room_coverage_pct')}%)")
            logger.info(f"[image_analysis] Must NOT add: {must_not_add}")

            # Store brief summary
            brief_summary = summary_result.get("brief_summary", f"A {project_type} space.")
            room_vibe = summary_result.get("room_vibe", "current")
            updates["brief_room_summary"] = brief_summary

            # NEW: Store analysis in DB when services available
            if use_services and services:
                try:
                    for img_data in image_analyses:
                        img_url = img_data.get("url")
                        analysis_dict = img_data.get("analysis", {})

                        # Store in DB via service
                        db_analysis = await services.image_analysis.analyze_image(
                            image_url=img_url,
                            project_id=services.project_id,
                            project_type=project_type
                        )

                        # Set first analysis as active
                        if not updates.get("active_image_id"):
                            updates["active_image_id"] = str(db_analysis.id)

                    # Update conversation phase
                    updates["conversation_phase"] = "ideating"
                    logger.info(f"[image_analysis] Stored {len(image_analyses)} analyses in DB")
                except Exception as e:
                    logger.info(f"[image_analysis] DB storage failed (continuing with state): {e}")

            # Emit analysis_complete event for SSE streaming
            if project_id_for_events:
                try:
                    from src.core.services.event_broadcaster import emit_analysis_complete
                    # Get categories found from analysis
                    categories_found = list(extracted_data.keys()) if extracted_data else []
                    search_insights_dict = None
                    if extracted_data.get("search_context"):
                        search_insights_dict = extracted_data["search_context"]
                    await emit_analysis_complete(project_id_for_events, categories_found, search_insights_dict)
                except Exception as event_error:
                    logger.error(f"[image_analysis] Failed to emit analysis_complete event: {event_error}")
                    # Continue - event emission failure shouldn't block the workflow

            # NEW: Trigger smart Tavily search with image insights
            # This replaces the generic search that ran on zip code entry
            zip_code = state.get("zip_code")
            project_id_token = state.get("project_id")
            if zip_code and project_id_token:
                db = None
                try:
                    # Extract search insights from image analysis
                    search_insights = extract_search_insights(extracted_data)

                    # Debug: Log the raw search_context data
                    raw_search_context = extracted_data.get("search_context", {})
                    logger.info(f"[image_analysis] DEBUG search_context raw: {raw_search_context}")
                    logger.info(f"[image_analysis] DEBUG search_insights: era={search_insights.detected_era}, "
                          f"style={search_insights.style_assessment}, problems={search_insights.problem_areas}, "
                          f"scope={search_insights.renovation_scope}, materials={search_insights.material_indicators}")

                    if search_insights.has_useful_context():
                        logger.info(f"[image_analysis] 🎯 Extracted search insights: era={search_insights.detected_era}, "
                              f"style={search_insights.style_assessment}, problems={search_insights.problem_areas[:2]}")

                        # Get project UUID from database for smart search
                        db = SessionLocal()
                        try:
                            project = db.query(Project).filter(Project.token == project_id_token).first()
                            if project:
                                # Start smart search in background with image-derived insights
                                try:
                                    start_smart_search_background(
                                        project_id=project.id,
                                        project_type=project_type,
                                        zip_code=zip_code,
                                        search_insights=search_insights
                                    )
                                    logger.info(f"[image_analysis] 🚀 Started smart Tavily search for {project_type} in {zip_code}")
                                except Exception as search_error:
                                    logger.error(f"[image_analysis] Failed to start smart search: {search_error}", exc_info=True)
                                    # Emit context_ready so frontend isn't blocked
                                    try:
                                        from src.core.services.event_broadcaster import emit_context_ready
                                        asyncio.create_task(emit_context_ready(str(project.id)))
                                    except Exception:
                                        pass
                            else:
                                logger.warning(f"[image_analysis] Project not found for token {project_id_token}")
                                # Emit context_ready since no smart search will run
                                try:
                                    from src.core.services.event_broadcaster import emit_context_ready
                                    asyncio.create_task(emit_context_ready(project_id_token))
                                except Exception:
                                    pass
                        except Exception as db_error:
                            logger.error(f"[image_analysis] Database error during smart search setup: {db_error}", exc_info=True)
                            # Continue - search is optional, don't block the flow
                        finally:
                            if db:
                                try:
                                    db.close()
                                except Exception:
                                    pass
                    else:
                        logger.info(f"[image_analysis] No useful search context extracted from images")
                        # Emit context_ready since no smart search will run
                        db = SessionLocal()
                        try:
                            project = db.query(Project).filter(Project.token == project_id_token).first()
                            if project:
                                try:
                                    from src.core.services.event_broadcaster import emit_context_ready
                                    asyncio.create_task(emit_context_ready(str(project.id)))
                                except Exception:
                                    pass
                        except Exception as db_error:
                            logger.error(f"[image_analysis] Database error emitting context_ready: {db_error}")
                        finally:
                            if db:
                                try:
                                    db.close()
                                except Exception:
                                    pass
                except Exception as e:
                    logger.error(f"[image_analysis] Smart search trigger failed: {e}", exc_info=True)
                    # Emit context_ready on error so frontend isn't blocked
                    db = None
                    try:
                        from src.core.services.event_broadcaster import emit_context_ready
                        db = SessionLocal()
                        project = db.query(Project).filter(Project.token == project_id_token).first()
                        if project:
                            asyncio.create_task(emit_context_ready(str(project.id)))
                    except Exception as fallback_error:
                        logger.error(f"[image_analysis] Failed to emit context_ready after search error: {fallback_error}")
                    finally:
                        if db:
                            try:
                                db.close()
                            except Exception:
                                pass
            else:
                # No zip_code or project_id_token available - emit context_ready anyway
                if project_id_token:
                    db = None
                    try:
                        from src.core.services.event_broadcaster import emit_context_ready
                        db = SessionLocal()
                        project = db.query(Project).filter(Project.token == project_id_token).first()
                        if project:
                            asyncio.create_task(emit_context_ready(str(project.id)))
                    except Exception as context_error:
                        logger.error(f"[image_analysis] Failed to emit context_ready: {context_error}")
                    finally:
                        if db:
                            try:
                                db.close()
                            except Exception:
                                pass

            # Initialize empty image history
            updates["generated_image_history"] = []

            # Move to design conversation (flexible flow)
            updates["image_sub_state"] = "design_conversation"

            # Build conversational response with larger images
            image_html_parts = []
            for img in image_analyses:
                image_html_parts.append(
                    f'<img src="{img["url"]}" style="width: 100%; max-width: 600px; '
                    f'border-radius: 12px; margin: 8px 0; cursor: pointer;" />'
                )
            images_display = "\n".join(image_html_parts)

            # Build "What I see" section from extracted data
            what_i_see_parts = []

            # Materials detected
            materials = extracted_data.get("materials", [])
            if materials:
                material_items = [m.get("name", m.get("type", "unknown")) for m in materials[:5]]
                if material_items:
                    what_i_see_parts.append(f"**Materials:** {', '.join(material_items)}")

            # Colors detected
            colors = extracted_data.get("colors", [])
            if colors:
                color_items = []
                for c in colors[:4]:
                    element = c.get("element", "")
                    color = c.get("color", "")
                    if element and color:
                        color_items.append(f"{color} {element.lower()}")
                if color_items:
                    what_i_see_parts.append(f"**Colors:** {', '.join(color_items)}")

            # Features detected
            features = extracted_data.get("features", [])
            if features:
                feature_names = [f.get("name", "") for f in features[:5] if f.get("name")]
                if feature_names:
                    what_i_see_parts.append(f"**Features:** {', '.join(feature_names)}")

            # Measurements if available
            measurements = extracted_data.get("measurements", {})
            if measurements.get("room_width_ft") and measurements.get("room_length_ft"):
                what_i_see_parts.append(
                    f"**Estimated size:** ~{measurements.get('room_width_ft')}×{measurements.get('room_length_ft')} ft"
                )

            # Build the analysis section
            if what_i_see_parts:
                what_i_see = "\n".join([f"• {part}" for part in what_i_see_parts])
                analysis_section = f"**Here's what I see:**\n{what_i_see}\n\n"
            else:
                analysis_section = ""

            response = (
                f"{images_display}\n\n"
                f"**{brief_summary}**\n\n"
                f"{analysis_section}"
                f"What changes would you like to make to this space?\n\n"
                f"You can:\n"
                f"- Describe your vision (e.g., *\"modern minimalist with white marble\"*)\n"
                f"- Ask for suggestions (e.g., *\"what would you recommend?\"*)\n"
                f"- Ask questions (e.g., *\"what style is this currently?\"*)"
            )
        else:
            response = "Please upload one or more images of the space you want to renovate."

        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        if services:
            services.cleanup()
        return updates

    # =========================================================================
    # DESIGN CONVERSATION STATE - Flexible conversation after extraction
    # =========================================================================
    elif sub_state in ["confirming_extraction", "collecting_vision", "design_conversation"]:
        result = await _handle_design_conversation(
            state, updates, user_message, project_type,
            image_analyses, extracted_data, renovation_vision,
            services=services, use_services=use_services
        )
        if services:
            services.cleanup()
        return result

    # =========================================================================
    # SELECTING SUGGESTIONS STATE
    # =========================================================================
    elif sub_state == "selecting_suggestions":
        result = await _handle_selecting_suggestions(state, updates, user_message, extracted_data, project_type)
        if services:
            services.cleanup()
        return result

    # =========================================================================
    # GENERATING STATE - Generate proposal image(s)
    # =========================================================================
    elif sub_state == "generating":
        result = await _handle_generating(
            state, updates, project_type, image_analyses, extracted_data, renovation_vision,
            services=services, use_services=use_services
        )
        if services:
            services.cleanup()
        return result

    # =========================================================================
    # GENERATING PARALLEL STATE
    # =========================================================================
    elif sub_state == "generating_parallel":
        result = await _handle_generating_parallel(
            state, updates, project_type, image_analyses, extracted_data
        )
        if services:
            services.cleanup()
        return result

    # =========================================================================
    # CONFIRMING PROPOSAL STATE
    # =========================================================================
    elif sub_state == "confirming_proposal":
        result = await _handle_confirming_proposal(
            state, updates, user_message, project_type, image_analyses, extracted_data, renovation_vision,
            services=services, use_services=use_services
        )
        if services:
            services.cleanup()
        return result

    # Fallback
    updates["messages"] = [{"role": "assistant", "content": "Something went wrong. Please try again."}]
    updates["awaiting_user_input"] = True
    if services:
        services.cleanup()
    return updates


async def _handle_design_conversation(
    state: ProjectState,
    updates: dict,
    user_message: str,
    project_type: str,
    image_analyses: list,
    extracted_data: dict,
    renovation_vision: dict | None,
    services: ServiceIntegration | None = None,
    use_services: bool = False
) -> dict:
    """Handle the design conversation sub-state."""
    expertise_level = state.get("expertise_level", "novice")

    if user_message:
        # NEW: Detect budget context if user mentions budget
        budget_context = None
        if use_services and services:
            try:
                budget_context = await services.detect_budget_if_mentioned(user_message)
                if budget_context:
                    logger.info(f"[design_conversation] Budget context detected: {budget_context.get('sentiment')}")
                    # Store in context_cache for generation phase
                    context_cache = dict(state.get("context_cache", {}))
                    context_cache["budget_context"] = budget_context
                    updates["context_cache"] = context_cache
            except Exception as e:
                logger.info(f"[design_conversation] Budget detection failed: {e}")

        # Check if user is selecting from pending suggestions
        pending_suggestions = state.get("pending_suggestions", [])
        if pending_suggestions:
            selected_indices = _parse_option_selection(user_message, pending_suggestions)

            if selected_indices:
                logger.info(f"[design_conversation] Option selection detected: indices {selected_indices}")
                selected_options = [pending_suggestions[i] for i in selected_indices if i < len(pending_suggestions)]

                if len(selected_options) == 1:
                    opt = selected_options[0]
                    updates["renovation_vision"] = {
                        "raw_input": f"Style: {opt.get('style_name')}",
                        "ai_summary": opt.get("description", ""),
                        "style_preferences": opt.get("style_name"),
                        "material_preferences": json.dumps(opt.get("materials", {})),
                        "specific_changes": ", ".join(opt.get("key_changes", [])),
                        "selected_option": opt
                    }
                    updates["pending_suggestions"] = []
                    updates["image_sub_state"] = "generating"
                    updates["conversation_phase"] = "generating"  # NEW: Update conversation phase
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates
                else:
                    updates["selected_options_for_generation"] = selected_options
                    updates["pending_suggestions"] = []
                    updates["image_sub_state"] = "generating_parallel"
                    updates["conversation_phase"] = "generating"  # NEW: Update conversation phase
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates

        # Use UNIFIED classifier
        context = (
            f"User is in a {project_type} renovation project. "
            f"Extracted data includes: {list(extracted_data.keys())}. "
            f"User can: confirm extraction, correct data, provide vision, ask suggestions, ask questions, skip steps."
        )
        try:
            unified_result = await unified_classify(
                user_message=user_message,
                context=context,
                has_generated_images=len(state.get("generated_image_history", [])) > 0
            )

            primary_intent = unified_result.get("primary_intent", "unclear")
            secondary_intents = unified_result.get("secondary_intents", [])
            extracted_content = unified_result.get("extracted_content", {})
        except LLMProviderError as llm_error:
            logger.error(f"[design_conversation] LLM provider error during intent classification: {llm_error}", exc_info=True)
            # Fallback to safe default behavior
            primary_intent = "unclear"
            secondary_intents = []
            extracted_content = {}
        except Exception as classify_error:
            logger.error(f"[design_conversation] Intent classification failed: {classify_error}", exc_info=True)
            # Fallback to safe default
            primary_intent = "unclear"
            secondary_intents = []
            extracted_content = {}

        # Cache expertise level if not already set
        if not state.get("expertise_level"):
            expertise_level = unified_result.get("expertise_level", "novice")
            updates["expertise_level"] = expertise_level

        logger.info(f"[design_conversation] Intent: {primary_intent} | secondary: {secondary_intents}")

        # Handle corrections
        if primary_intent == "correction" or "correction" in secondary_intents:
            corrections = extracted_content.get("corrections") or user_message

            # NEW: Use correction service if available
            if use_services and services:
                try:
                    corrected_data, _ = await services.handle_user_correction(
                        user_message=corrections,
                        current_data=extracted_data
                    )
                    updates["extracted_data"] = corrected_data
                    extracted_data = corrected_data
                except Exception as e:
                    logger.info(f"[design_conversation] Correction service failed, using legacy: {e}")
                    corrected_data = await apply_user_correction(extracted_data, corrections, project_type)
                    updates["extracted_data"] = corrected_data
                    extracted_data = corrected_data
            else:
                corrected_data = await apply_user_correction(extracted_data, corrections, project_type)
                updates["extracted_data"] = corrected_data
                extracted_data = corrected_data

        # Handle based on primary intent
        if primary_intent == "confirm" or primary_intent == "mixed":
            vision_details = extracted_content.get("vision_details")
            if vision_details or primary_intent == "mixed":
                updates["renovation_vision"] = {
                    "raw_input": vision_details or user_message,
                    "ai_summary": vision_details or user_message
                }
                updates["image_sub_state"] = "generating"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates
            else:
                updates["image_sub_state"] = "design_conversation"
                response = VISION_PROMPT
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

        elif primary_intent == "direct_vision":
            vision_details = extracted_content.get("vision_details") or user_message
            updates["renovation_vision"] = {
                "raw_input": vision_details,
                "ai_summary": vision_details
            }
            updates["image_sub_state"] = "generating"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif primary_intent == "ask_suggestions":
            current_state_summary = json.dumps(extracted_data, indent=2)[:800]
            user_prefs = renovation_vision.get("raw_input", "") if renovation_vision else ""

            # Retrieve renovation inspirations from database with wait logic
            project_id_token = state.get("project_id")
            logger.info(f"[design_conversation] Retrieving inspirations for {project_id_token}...")
            inspirations = await get_renovation_inspirations_with_wait(project_id_token)

            if inspirations:
                location = inspirations.get("location", {})
                logger.info(f"[design_conversation] Using inspirations for {location.get('city', 'Unknown')}, {location.get('state_code', 'Unknown')}")
            else:
                logger.info(f"[design_conversation] No inspirations available, generating generic suggestions")

            try:
                suggestions_result = await generate_expert_suggestions(
                    project_type=project_type,
                    current_state_summary=current_state_summary,
                    user_preferences=user_prefs,
                    expertise_level=expertise_level,
                    inspirations=inspirations
                )

                suggestions_options = suggestions_result.get("options", [])
                updates["pending_suggestions"] = suggestions_options
                # Store all suggestions permanently so user can switch between options later
                updates["all_suggestions"] = suggestions_options

                # Return structured content for card rendering
                response_content = [
                    {"type": "text", "text": "# Renovation Options\n\nBased on your space and local design trends, here are my recommendations:"},
                    _format_suggestions_as_cards(suggestions_result, inspirations),
                    {"type": "text", "text": "\n\nSelect an option to see it visualized, or tell me if you have a different idea in mind!"}
                ]
                updates["messages"] = [{"role": "assistant", "content": response_content}]
                updates["awaiting_user_input"] = True
                return updates
            except LLMProviderError as llm_error:
                logger.error(f"[design_conversation] LLM provider error generating suggestions: {llm_error}", exc_info=True)
                response = "I'm having trouble generating suggestions right now. Could you tell me what style or changes you have in mind instead?"
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates
            except Exception as suggestions_error:
                logger.error(f"[design_conversation] Failed to generate suggestions: {suggestions_error}", exc_info=True)
                response = "I encountered an error generating suggestions. Please describe the style or changes you'd like to see, and I'll help visualize it."
                updates["messages"] = [{"role": "assistant", "content": response}]
                updates["awaiting_user_input"] = True
                return updates

        elif primary_intent == "ask_question":
            try:
                provider = LLMProvider.for_llm()
                answer_prompt = f"""Answer this renovation question helpfully.
Project type: {project_type}
Current room: {json.dumps(extracted_data, indent=2)[:500] if extracted_data else 'Not analyzed yet'}
User's question: {user_message}

Provide a helpful, informative answer. Keep it concise but educational.
At the end, gently guide them back to the renovation planning."""

                answer = await provider.complete(
                    messages=[
                        {"role": "system", "content": "You are a helpful renovation expert."},
                        {"role": "user", "content": answer_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=500
                )

                response = f"{answer}\n\n---\n\nWould you like to continue with your renovation vision, or do you have more questions?"
            except LLMProviderError as llm_error:
                logger.error(f"[design_conversation] LLM provider error answering question: {llm_error}", exc_info=True)
                response = "I'm having trouble processing your question right now. Could you rephrase it, or would you like to continue with your renovation planning?"
            except Exception as answer_error:
                logger.error(f"[design_conversation] Error answering question: {answer_error}", exc_info=True)
                response = "I encountered an error answering your question. Let's continue with your renovation vision - what changes would you like to make?"

            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        elif primary_intent == "vague_request":
            vague_needs = extracted_content.get("vague_needs") or user_message
            extracted_summary = json.dumps(extracted_data, indent=2)[:500] if extracted_data else ""

            try:
                clarification = await clarify_vague_request(
                    user_request=vague_needs,
                    project_type=project_type,
                    extracted_data_summary=extracted_summary,
                    expertise_level=expertise_level
                )

                response = clarification.get("suggested_response", "Could you tell me more about what you'd like to change?")
            except LLMProviderError as llm_error:
                logger.error(f"[design_conversation] LLM provider error during clarification: {llm_error}", exc_info=True)
                response = "Could you tell me more specifically about what you'd like to change? For example, materials, colors, style, or layout?"
            except Exception as clarify_error:
                logger.error(f"[design_conversation] Failed to clarify vague request: {clarify_error}", exc_info=True)
                response = "I'd love to help! Could you be more specific about what changes you're envisioning?"

            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        elif primary_intent == "skip":
            updates["renovation_vision"] = None
            updates["image_sub_state"] = "generating"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif primary_intent == "correction":
            display = format_extracted_data_for_display(extracted_data, image_analyses)
            response = (
                f"# Updated Information:\n\n"
                f"{display}\n"
                f"---\n\n"
                f"Anything else to change? Or tell me your renovation vision to continue."
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        else:
            response = (
                "I'm here to help! You can:\n"
                "- **Confirm** the extracted info is correct\n"
                "- **Correct** anything that needs fixing\n"
                "- **Share your vision** (e.g., 'add marble tiles and chandelier')\n"
                "- **Ask for suggestions** (e.g., 'what do you recommend?')\n"
                "- **Ask questions** about materials or styles\n"
                "- Say **'skip'** to proceed with a general design"
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

    # No user message - show current data
    display = format_extracted_data_for_display(extracted_data, image_analyses)
    response = (
        f"# Extracted Information:\n\n"
        f"{display}\n"
        f"---\n\n"
        f"What would you like to do?\n"
        f"- Tell me your renovation vision\n"
        f"- Ask for my suggestions\n"
        f"- Correct any details above\n"
        f"- Or say 'skip' to proceed"
    )
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_selecting_suggestions(
    state: ProjectState,
    updates: dict,
    user_message: str,
    extracted_data: dict,
    project_type: str
) -> dict:
    """Handle the selecting suggestions sub-state."""
    pending_suggestions = state.get("pending_suggestions", [])

    if user_message:
        selected_indices = _parse_option_selection(user_message, pending_suggestions)

        if not selected_indices:
            if "all" in user_message.lower():
                selected_indices = list(range(len(pending_suggestions)))
            elif pending_suggestions:
                selected_indices = [0]

        if selected_indices:
            selected_options = [pending_suggestions[i] for i in selected_indices if i < len(pending_suggestions)]

            if len(selected_options) == 1:
                opt = selected_options[0]
                updates["renovation_vision"] = {
                    "raw_input": f"Style: {opt.get('style_name')}",
                    "ai_summary": opt.get("description", ""),
                    "selected_option": opt
                }
                updates["image_sub_state"] = "generating"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates
            else:
                updates["selected_options_for_generation"] = selected_options
                updates["image_sub_state"] = "generating_parallel"
                updates["awaiting_user_input"] = False
                updates["messages"] = []
                return updates
        else:
            response = (
                "I couldn't identify which option(s) you'd like to see. Please specify:\n"
                "- **'Option 1'** or **'Option 2'** to generate that style\n"
                "- **'Generate all'** to see all options\n"
                "- Or describe what you're looking for"
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

    response = "Which option would you like me to generate? You can say 'Option 1', 'Option 2', or 'Generate all'."
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_generating(
    state: ProjectState,
    updates: dict,
    project_type: str,
    image_analyses: list,
    extracted_data: dict,
    renovation_vision: dict | None,
    services: ServiceIntegration | None = None,
    use_services: bool = False
) -> dict:
    """Handle the generating sub-state."""
    logger.info("[image_analysis] Generating renovation preview image(s)...")

    original_image_urls = [img["url"] for img in image_analyses]
    features_to_retain = state.get("original_features_to_retain", [])
    image_history = list(state.get("generated_image_history", []))

    # NEW: Get hallucination prevention data
    visible_elements = state.get("_visible_elements", {})
    image_scope = state.get("_image_scope", {"frame_type": "full_room", "room_coverage_pct": 100})
    must_not_add = state.get("_must_not_add", [])

    if not original_image_urls:
        logger.warning("[image_analysis] No original image URLs provided for generation")
        generated_url = get_placeholder_image_url()
        generation_prompt = ""
        description = ""
        generated_results = []
    elif len(original_image_urls) == 1:
        try:
            generated_url, generation_prompt, description = await generate_renovation_image(
                original_image_urls=original_image_urls,
                project_type=project_type,
                extracted_data=extracted_data,
                renovation_vision=renovation_vision,
                feedback=None,
                previous_prompt=None,
                features_to_retain=features_to_retain,
                visible_elements=visible_elements,
                must_not_add=must_not_add,
                image_scope=image_scope,
            )

            try:
                image_history = add_to_image_history(
                    history=image_history,
                    url=generated_url,
                    description=description,
                    base_perspective=0,
                    user_satisfied=None
                )
            except Exception as history_error:
                logger.error(f"[image_analysis] Failed to add image to history: {history_error}")
                # Continue with existing history - this is not critical

            generated_results = [{"url": generated_url, "description": description, "perspective": 0}]
        except LLMProviderError as llm_error:
            logger.error(f"[image_analysis] LLM provider error during image generation: {llm_error}", exc_info=True)
            generated_url = get_placeholder_image_url()
            generation_prompt = ""
            description = ""
            generated_results = []
            updates["_generation_error"] = f"Image generation service error: {str(llm_error)}"
        except Exception as e:
            logger.error(f"[image_analysis] Image generation failed: {e}", exc_info=True)
            generated_url = get_placeholder_image_url()
            generation_prompt = ""
            description = ""
            generated_results = []
            updates["_generation_error"] = f"Failed to generate image: {str(e)}"
    else:
        # Multiple perspectives - generate in parallel
        async def generate_for_perspective(img_url: str, perspective_idx: int):
            try:
                url, prompt, desc = await generate_renovation_image(
                    original_image_urls=[img_url],
                    project_type=project_type,
                    extracted_data=extracted_data,
                    renovation_vision=renovation_vision,
                    feedback=None,
                    previous_prompt=None,
                    features_to_retain=features_to_retain,
                    visible_elements=visible_elements,
                    must_not_add=must_not_add,
                    image_scope=image_scope,
                )
                return {"url": url, "prompt": prompt, "description": desc, "perspective": perspective_idx, "success": True}
            except LLMProviderError as llm_error:
                logger.error(f"[image_analysis] LLM provider error for perspective {perspective_idx}: {llm_error}", exc_info=True)
                return {"url": get_placeholder_image_url(), "description": f"Image generation service error: {str(llm_error)}", "perspective": perspective_idx, "success": False}
            except Exception as e:
                logger.error(f"[image_analysis] Generation failed for perspective {perspective_idx}: {e}", exc_info=True)
                return {"url": get_placeholder_image_url(), "description": f"Failed to generate: {str(e)}", "perspective": perspective_idx, "success": False}

        try:
            generated_results = await asyncio.gather(*[
                generate_for_perspective(url, idx) for idx, url in enumerate(original_image_urls)
            ])
        except Exception as gather_error:
            logger.error(f"[image_analysis] Error gathering parallel perspective generations: {gather_error}", exc_info=True)
            generated_results = []
            updates["_generation_error"] = f"Parallel generation failed: {str(gather_error)}"

        for result in generated_results:
            if result.get("success"):
                try:
                    image_history = add_to_image_history(
                        history=image_history,
                        url=result["url"],
                        description=result.get("description", ""),
                        base_perspective=result["perspective"],
                        user_satisfied=None
                    )
                except Exception as history_error:
                    logger.error(f"[image_analysis] Failed to add perspective {result['perspective']} to history: {history_error}")
                    # Continue - history failure shouldn't stop the flow

        successful = [r for r in generated_results if r.get("success")]
        if successful:
            generated_url = successful[0]["url"]
            generation_prompt = successful[0].get("prompt", "")
            description = successful[0].get("description", "")
        else:
            logger.error("[image_analysis] All perspective generations failed")
            generated_url = get_placeholder_image_url()
            generation_prompt = ""
            description = ""
            updates["_generation_error"] = "All perspective generations failed. Please try again or contact support."

    updates["generated_image_url"] = generated_url
    updates["last_generated_image_url"] = generated_url
    updates["generation_prompt"] = generation_prompt
    updates["generation_description"] = description
    updates["original_image_urls"] = original_image_urls
    updates["generated_image_history"] = image_history
    updates["image_sub_state"] = "confirming_proposal"
    updates["conversation_phase"] = "reviewing"  # NEW: Update conversation phase

    # NOTE: DB storage via services.generation.generate_initial() was removed
    # because it tries to regenerate the image when we already have it generated.
    # The image URL is already stored in state and image_history.
    # TODO: Add a proper store_generation_record() method if DB tracking is needed.

    # Build response
    error_note = ""
    if updates.get("_generation_error"):
        error_note = "\n\n*Note: Some images encountered issues.*\n\n"

    if len(generated_results) > 1:
        response = _format_multi_perspective_response(generated_results, error_note)
    else:
        desc_section = f"{description}\n\n" if description and not updates.get("_generation_error") else ""
        response = (
            f'<img src="{generated_url}" style="width: 100%; max-width: 800px; '
            f'border-radius: 12px; margin: 16px 0;" />\n\n'
            f"{error_note}"
            f"{desc_section}"
            f"How does this look? Say **'continue'** to proceed, or tell me what to change."
        )

    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_generating_parallel(
    state: ProjectState,
    updates: dict,
    project_type: str,
    image_analyses: list,
    extracted_data: dict
) -> dict:
    """Handle the generating parallel sub-state - generates multiple styles from all perspectives."""

    # Input validation
    if not project_type:
        logger.error("Missing project_type in _handle_generating_parallel")
        updates["messages"] = [{"role": "assistant", "content": "Configuration error. Please restart the process."}]
        updates["image_sub_state"] = ImageSubState.DESIGN_CONVERSATION
        updates["awaiting_user_input"] = True
        return updates

    if not extracted_data:
        logger.warning("No extracted_data available for parallel image generation")

    selected_options = state.get("selected_options_for_generation", [])
    original_image_urls = [img["url"] for img in image_analyses]
    features_to_retain = state.get("original_features_to_retain", [])
    image_history = list(state.get("generated_image_history", []))

    # NEW: Get hallucination prevention data
    visible_elements = state.get("_visible_elements", {})
    image_scope = state.get("_image_scope", {"frame_type": "full_room", "room_coverage_pct": 100})
    must_not_add = state.get("_must_not_add", [])

    if not selected_options or not original_image_urls:
        logger.warning(f"Missing data - options: {len(selected_options)}, images: {len(original_image_urls)}")
        response = "Unable to generate options. Please go back and select options again."
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["image_sub_state"] = ImageSubState.DESIGN_CONVERSATION
        updates["awaiting_user_input"] = True
        return updates

    num_perspectives = len(original_image_urls)
    num_options = len(selected_options)
    total_generations = num_options * num_perspectives

    logger.info(f"[image_analysis] Generating {num_options} style options across {num_perspectives} perspectives (total: {total_generations} images)")

    async def generate_option(option, perspective_idx):
        """Generate a single style option from a specific perspective."""
        try:
            # Validate perspective index
            if perspective_idx >= len(original_image_urls):
                raise ValueError(f"Invalid perspective_idx {perspective_idx}, only {len(original_image_urls)} images available")

            vision = {
                "raw_input": f"Style: {option.get('style_name')}",
                "ai_summary": option.get("description", ""),
                "selected_option": option
            }

            # Use the specific perspective image
            base_urls = [original_image_urls[perspective_idx]]

            url, prompt, desc = await generate_renovation_image(
                original_image_urls=base_urls,
                project_type=project_type,
                extracted_data=extracted_data,
                renovation_vision=vision,
                feedback=None,
                previous_prompt=None,
                features_to_retain=features_to_retain,
                visible_elements=visible_elements,
                must_not_add=must_not_add,
                image_scope=image_scope,
            )

            return {
                "style_name": option.get("style_name"),
                "url": url,
                "prompt": prompt,
                "description": desc,
                "perspective": perspective_idx,
                "success": True
            }
        except Exception as e:
            logger.error(
                f"Failed to generate option '{option.get('style_name')}' for perspective {perspective_idx}: {str(e)}",
                exc_info=True
            )
            return {
                "style_name": option.get("style_name"),
                "url": get_placeholder_image_url(),
                "description": f"Failed to generate: {e}",
                "perspective": perspective_idx,
                "success": False,
                "error": str(e)
            }

    # Generate each style from ALL available perspectives
    generation_tasks = [
        generate_option(opt, perspective_idx)
        for opt in selected_options
        for perspective_idx in range(num_perspectives)
    ]

    # Execute all generations with timeout protection
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*generation_tasks, return_exceptions=True),
            timeout=IMAGE_GENERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[image_analysis] Image generation timed out after {IMAGE_GENERATION_TIMEOUT}s for {total_generations} images")
        updates["messages"] = [{"role": "assistant", "content": "Image generation timed out. This might be due to generating too many images at once. Please try selecting fewer options or perspectives."}]
        updates["image_sub_state"] = ImageSubState.DESIGN_CONVERSATION
        updates["awaiting_user_input"] = True
        return updates
    except Exception as gather_error:
        logger.error(f"[image_analysis] Unexpected error during parallel generation: {gather_error}", exc_info=True)
        updates["messages"] = [{"role": "assistant", "content": "An unexpected error occurred during image generation. Please try again or select different options."}]
        updates["image_sub_state"] = ImageSubState.DESIGN_CONVERSATION
        updates["awaiting_user_input"] = True
        return updates

    # Filter out exceptions from results
    results = [r for r in results if isinstance(r, dict)]

    if not results:
        logger.error("[image_analysis] All generation tasks returned exceptions")
        updates["messages"] = [{"role": "assistant", "content": "All image generation attempts encountered errors. Please try again or adjust your selections."}]
        updates["image_sub_state"] = ImageSubState.DESIGN_CONVERSATION
        updates["awaiting_user_input"] = True
        return updates

    # Check for complete failure
    successful_results = [r for r in results if r.get("success")]

    if not successful_results:
        logger.error("All image generation attempts failed")
        response = "All image generation attempts failed. Please try again or adjust your selections."
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["image_sub_state"] = ImageSubState.DESIGN_CONVERSATION
        updates["awaiting_user_input"] = True
        return updates

    # Log success/failure statistics
    failed_count = len(results) - len(successful_results)
    if failed_count > 0:
        logger.warning(f"Partial failure: {failed_count}/{len(results)} generations failed")
    else:
        logger.info(f"Successfully generated all {len(results)} images")

    # Add successful results to history
    for result in results:
        if result.get("success"):
            try:
                image_history = add_to_image_history(
                    history=image_history,
                    url=result["url"],
                    description=result.get("description", ""),
                    base_perspective=result.get("perspective", 0),
                    user_satisfied=None
                )
            except Exception as history_error:
                logger.error(f"[image_analysis] Failed to add parallel result to history: {history_error}")
                # Continue - history failure shouldn't block the workflow

    updates["generated_options"] = results
    updates["original_image_urls"] = original_image_urls
    updates["generated_image_history"] = image_history
    updates["image_sub_state"] = ImageSubState.CONFIRMING_PROPOSAL

    response = _format_parallel_options_response(results)
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_confirming_proposal(
    state: ProjectState,
    updates: dict,
    user_message: str,
    project_type: str,
    image_analyses: list,
    extracted_data: dict,
    renovation_vision: dict | None,
    services: ServiceIntegration | None = None,
    use_services: bool = False
) -> dict:
    """Handle the confirming proposal sub-state."""
    image_history = list(state.get("generated_image_history", []))
    current_generated_url = state.get("generated_image_url", "")
    features_to_retain = state.get("original_features_to_retain", [])

    # Check for pending regeneration from final_review
    # When final_review sends back with _pending_regeneration, it has already
    # determined this is a change request, so we skip re-classification and
    # go directly to regeneration to avoid infinite loops
    pending_regeneration = state.get("_pending_regeneration")
    if pending_regeneration:
        logger.info(f"[confirming_proposal] Handling pending regeneration from final_review: {pending_regeneration}")
        updates["_pending_regeneration"] = None
        # Directly handle as a regeneration request - final_review already classified this
        conv_type = {
            "conversation_type": "generation_request",
            "confidence": 1.0,
            "generation_changes": pending_regeneration
        }
        return await _handle_regeneration(
            state, updates, pending_regeneration, conv_type, project_type,
            image_analyses, extracted_data, renovation_vision,
            image_history, features_to_retain,
            services=services, use_services=use_services
        )

    if user_message:
        # Check if user is selecting a different option from all_suggestions
        # This allows switching between options even after generating one
        all_suggestions = state.get("all_suggestions", [])
        if all_suggestions:
            selected_indices = _parse_option_selection(user_message, all_suggestions)
            if selected_indices:
                selected_idx = selected_indices[0]
                if selected_idx < len(all_suggestions):
                    opt = all_suggestions[selected_idx]
                    logger.info(f"[confirming_proposal] Switching to option {selected_idx + 1}: {opt.get('style_name')}")

                    # Update renovation vision with the new selected option
                    new_renovation_vision = {
                        "raw_input": f"Style: {opt.get('style_name')}",
                        "ai_summary": opt.get("description", ""),
                        "style_preferences": opt.get("style_name"),
                        "material_preferences": json.dumps(opt.get("materials", {})),
                        "specific_changes": ", ".join(opt.get("key_changes", [])),
                        "selected_option": opt
                    }
                    updates["renovation_vision"] = new_renovation_vision

                    # Clear feedback since this is a fresh generation
                    updates["image_generation_feedback"] = []

                    # Get original image URLs for fresh generation
                    stored_original_urls = state.get("original_image_urls", [])
                    if not stored_original_urls:
                        stored_original_urls = [img["url"] for img in image_analyses]

                    # NEW: Get hallucination prevention data
                    visible_elements = state.get("_visible_elements", {})
                    image_scope = state.get("_image_scope", {"frame_type": "full_room", "room_coverage_pct": 100})
                    must_not_add = state.get("_must_not_add", [])

                    # Generate new image with the selected option
                    try:
                        new_url, new_prompt, new_description = await generate_renovation_image(
                            original_image_urls=stored_original_urls,
                            project_type=project_type,
                            extracted_data=extracted_data,
                            renovation_vision=new_renovation_vision,
                            feedback=None,
                            previous_prompt=None,
                            features_to_retain=features_to_retain,
                            visible_elements=visible_elements,
                            must_not_add=must_not_add,
                            image_scope=image_scope,
                        )

                        try:
                            image_history = add_to_image_history(
                                history=image_history,
                                url=new_url,
                                description=new_description,
                                base_perspective=0,
                                user_satisfied=None
                            )
                        except Exception as history_error:
                            logger.error(f"[confirming_proposal] Failed to add option switch to history: {history_error}")
                            # Continue with existing history

                        updates["generated_image_url"] = new_url
                        updates["last_generated_image_url"] = new_url
                        updates["generation_prompt"] = new_prompt
                        updates["generation_description"] = new_description
                        updates["generated_image_history"] = image_history

                        response = (
                            f'<img src="{new_url}" style="width: 100%; max-width: 800px; '
                            f'border-radius: 12px; margin: 16px 0;" />\n\n'
                            f"{new_description}\n\n"
                            f"How's this? Say **'continue'** when ready, or request more changes."
                        )
                    except LLMProviderError as llm_error:
                        logger.error(f"[confirming_proposal] LLM provider error during option switch: {llm_error}", exc_info=True)
                        response = "I'm having trouble with the image generation service. Please try again in a moment or request specific changes."
                    except Exception as e:
                        logger.error(f"[confirming_proposal] Option switch generation failed: {e}", exc_info=True)
                        response = "I encountered an issue generating the new option. Please try again or request specific changes."

                    updates["messages"] = [{"role": "assistant", "content": response}]
                    updates["awaiting_user_input"] = True
                    return updates

        # Use LLM-based classification for all user messages - no hardcoded keywords
        context = f"User is reviewing a generated renovation preview with {len(image_history)} generated images."
        try:
            unified_result = await unified_classify(
                user_message=user_message,
                context=context,
                has_generated_images=len(image_history) > 0
            )

            # Default to generation_request in confirming_proposal context if classifier fails
            # (Most user messages here are modification requests)
            conversation_type = unified_result.get("conversation_type") or "generation_request"
            confidence = unified_result.get("confidence", 0.5)

            conv_type = {
                "conversation_type": conversation_type,
                "confidence": confidence,
                "extracted_question": unified_result.get("extracted_content", {}).get("questions", [None])[0] if unified_result.get("extracted_content", {}).get("questions") else None,
                "referenced_image_position": unified_result.get("extracted_content", {}).get("referenced_image_position"),
                "generation_changes": unified_result.get("extracted_content", {}).get("generation_changes") or user_message
            }

            logger.info(f"[confirming_proposal] Conversation type: {conversation_type} (confidence: {confidence})")
        except LLMProviderError as llm_error:
            logger.error(f"[confirming_proposal] LLM provider error during classification: {llm_error}", exc_info=True)
            # Fallback to generation_request - safest assumption in this context
            conversation_type = "generation_request"
            conv_type = {
                "conversation_type": "generation_request",
                "confidence": 0.5,
                "extracted_question": None,
                "referenced_image_position": None,
                "generation_changes": user_message
            }
        except Exception as classify_error:
            logger.error(f"[confirming_proposal] Classification failed: {classify_error}", exc_info=True)
            # Fallback to generation_request
            conversation_type = "generation_request"
            conv_type = {
                "conversation_type": "generation_request",
                "confidence": 0.5,
                "extracted_question": None,
                "referenced_image_position": None,
                "generation_changes": user_message
            }

        if conversation_type == "discussion":
            question = conv_type.get("extracted_question") or user_message
            image_to_analyze = current_generated_url or (image_analyses[0]["url"] if image_analyses else None)
            if image_to_analyze:
                try:
                    answer = await answer_image_question(
                        question=question,
                        image_url=image_to_analyze,
                        context=f"This is a {project_type} renovation preview"
                    )
                    response = f"{answer}\n\n---\n\nAnything else you'd like to know, or are you ready to continue?"
                except LLMProviderError as llm_error:
                    logger.error(f"[confirming_proposal] LLM provider error answering question: {llm_error}", exc_info=True)
                    response = "I'm having trouble answering your question right now. Would you like to continue with the renovation, or ask something else?"
                except Exception as answer_error:
                    logger.error(f"[confirming_proposal] Failed to answer image question: {answer_error}", exc_info=True)
                    response = "I encountered an error answering your question. Let's continue - would you like to proceed with this design or make changes?"
            else:
                response = "I don't have an image to analyze. Would you like me to generate a renovation preview?"
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        elif conversation_type == "reference_previous":
            ref = conv_type.get("referenced_image_position") or "previous"
            referenced_image = get_image_from_history(image_history, str(ref))
            if referenced_image:
                for img in image_history:
                    img["user_satisfied"] = img.get("url") == referenced_image.get("url")
                updates["generated_image_history"] = image_history
                updates["selected_final_image_url"] = referenced_image.get("url")
                updates["generated_image_url"] = referenced_image.get("url")
                response = (
                    f'<img src="{referenced_image.get("url")}" style="width: 100%; max-width: 800px; '
                    f'border-radius: 12px; margin: 16px 0;" />\n\n'
                    f"Got it! I've selected this design. Say **'continue'** to proceed to review."
                )
            else:
                response = f"I couldn't find that image. You have {len(image_history)} generated images. Which one would you like?"
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        elif conversation_type == "move_forward":
            if image_history and current_generated_url:
                for img in image_history:
                    if img.get("url") == current_generated_url:
                        img["user_satisfied"] = True
                updates["generated_image_history"] = image_history
            updates["selected_final_image_url"] = current_generated_url
            # Skip final_review and go directly to cost_estimation (simplified flow)
            updates["current_stage"] = "cost_estimation"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif conversation_type == "generation_request":
            return await _handle_regeneration(
                state, updates, user_message, conv_type, project_type,
                image_analyses, extracted_data, renovation_vision,
                image_history, features_to_retain,
                services=services, use_services=use_services
            )

        else:
            response = (
                "I can help! You can:\n"
                "- **Ask questions** about the image (e.g., 'what color is that wall?')\n"
                "- **Request changes** (e.g., 'make the floor darker')\n"
                "- **Reference previous designs** (e.g., 'go back to the first one')\n"
                "- Say **'continue'** when you're happy with the design"
            )
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

    response = "How does this look? Let me know if you'd like any changes, or say **'continue'** to proceed."
    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_regeneration(
    state: ProjectState,
    updates: dict,
    user_message: str,
    conv_type: dict,
    project_type: str,
    image_analyses: list,
    extracted_data: dict,
    renovation_vision: dict | None,
    image_history: list,
    features_to_retain: list,
    services: ServiceIntegration | None = None,
    use_services: bool = False
) -> dict:
    """Handle image regeneration based on user feedback."""

    # NEW: Get hallucination prevention data
    visible_elements = state.get("_visible_elements", {})
    image_scope = state.get("_image_scope", {"frame_type": "full_room", "room_coverage_pct": 100})
    must_not_add = state.get("_must_not_add", [])

    raw_feedback = conv_type.get("generation_changes") or user_message
    if isinstance(raw_feedback, dict):
        feedback_content = json.dumps(raw_feedback) if raw_feedback else user_message
    elif isinstance(raw_feedback, list):
        feedback_content = "; ".join(str(item) for item in raw_feedback)
    else:
        feedback_content = str(raw_feedback) if raw_feedback else user_message

    stored_original_urls = state.get("original_image_urls", [])
    if not stored_original_urls:
        stored_original_urls = [img["url"] for img in image_analyses]

    generated_options = state.get("generated_options", [])
    num_current_images = len(generated_options) if generated_options else 1

    if num_current_images > 1:
        multi_feedback = await parse_multi_image_feedback(feedback_content, num_current_images)
        if multi_feedback.get("references_multiple_images") or multi_feedback.get("applies_to_all"):
            return await _handle_multi_image_regeneration(
                state, updates, multi_feedback, feedback_content, project_type,
                extracted_data, renovation_vision, image_history, features_to_retain,
                generated_options, stored_original_urls
            )

    # Single image regeneration
    current_description = state.get("generation_description", "")

    # NEW: Use sentiment service for regeneration mode detection if available
    if use_services and services:
        try:
            regen_mode, regions = await services.classify_regeneration_intent(feedback_content)
            # Map service result to legacy mode format
            if regen_mode == "restart":
                regen_mode = "style_change"
            elif regen_mode == "additive":
                regen_mode = "iterative_refinement"
            logger.info(f"[_handle_regeneration] Service detected mode: {regen_mode}, regions: {regions}")
        except Exception as e:
            logger.info(f"[_handle_regeneration] Sentiment service failed, using legacy: {e}")
            mode_result = await detect_regeneration_mode(feedback_content, current_description)
            regen_mode = mode_result.get("mode", "iterative_refinement")
    else:
        mode_result = await detect_regeneration_mode(feedback_content, current_description)
        regen_mode = mode_result.get("mode", "iterative_refinement")

    if regen_mode == "ask_user":
        display_feedback = feedback_content[:200] + "..." if len(feedback_content) > 200 else feedback_content
        response = (
            f"I understood you want: *\"{display_feedback}\"*\n\n"
            f"Would you like me to:\n"
            f"- **Start fresh** with a completely different style\n"
            f"- **Refine this design** with the specific changes\n"
        )
        updates["pending_feedback"] = str(feedback_content)
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["awaiting_user_input"] = True
        return updates

    # Get selected image URL from state (user may have selected a specific canvas image)
    selected_image_url = state.get("selected_image_url")
    last_generated_url = state.get("last_generated_image_url", "")
    stored_generation_prompt = state.get("generation_prompt", "")

    # Helper to check if URL is an original (uploaded) image vs generated
    def is_original_image(url: str) -> bool:
        if not url:
            return False
        return "/generated/" not in url

    # Helper to check if URL is a generated image
    def is_generated_image(url: str) -> bool:
        if not url:
            return False
        return "/generated/" in url

    # Determine if user is starting fresh from original image
    # or continuing edits on a generated image
    user_selected_original = selected_image_url and is_original_image(selected_image_url)
    user_selected_different_generated = (
        selected_image_url and
        is_generated_image(selected_image_url) and
        selected_image_url != last_generated_url
    )

    # If user selected an ORIGINAL image, treat as fresh start
    # Reset all edit history - they want to start over from their original photo
    if user_selected_original:
        logger.info(f"[_handle_regeneration] User selected ORIGINAL image - resetting edit history")
        feedback_list = [str(feedback_content)]
        updates["image_generation_feedback"] = feedback_list
        updates["generation_description"] = ""  # Clear previous description
        previous_changes = []
        regen_mode = "style_change"  # Treat as fresh generation
    elif user_selected_different_generated:
        # User selected a different generated image from history
        # Try to get the description for that specific image
        logger.info(f"[_handle_regeneration] User selected different generated image - checking history")
        image_description_for_selected = None
        for hist_img in image_history:
            if hist_img.get("url") == selected_image_url:
                image_description_for_selected = hist_img.get("description", "")
                break

        # Start fresh from that point with only current feedback
        feedback_list = [str(feedback_content)]
        updates["image_generation_feedback"] = feedback_list

        # Use description from that image for context
        previous_changes = []
        if image_description_for_selected:
            for line in image_description_for_selected.split('\n'):
                line = line.strip()
                if line.startswith(('•', '-', '*')) or (len(line) > 0 and line[0].isdigit() and '.' in line[:3]):
                    change = line.lstrip('•-*0123456789. ')
                    if change and len(change) > 5:
                        previous_changes.append(change)
    elif regen_mode == "style_change":
        # Explicit style change request - reset feedback
        feedback_list = [str(feedback_content)]
        updates["image_generation_feedback"] = feedback_list
        previous_changes = []
    else:
        # Iterative refinement on current image
        # IMPORTANT: Only use the CURRENT request as feedback, not accumulated previous requests.
        # Previous changes are already captured in the image description and passed via previous_changes.
        # Accumulating feedback causes the VGM to re-apply old changes that were already made.
        feedback_list = [str(feedback_content)]
        updates["image_generation_feedback"] = feedback_list

        # Get previous changes from the current description for context
        # This tells the VGM what was already done on this image
        current_description = state.get("generation_description", "")
        previous_changes = []
        if current_description:
            # Extract bullet points from description as previous changes
            for line in current_description.split('\n'):
                line = line.strip()
                if line.startswith(('•', '-', '*')) or (len(line) > 0 and line[0].isdigit() and '.' in line[:3]):
                    change = line.lstrip('•-*0123456789. ')
                    if change and len(change) > 5:
                        previous_changes.append(change)

        logger.info(f"[_handle_regeneration] Current feedback: {feedback_list}")
        logger.info(f"[_handle_regeneration] Previous changes (from description): {previous_changes[:3]}..." if len(previous_changes) > 3 else f"[_handle_regeneration] Previous changes: {previous_changes}")

    # Set base image URLs based on mode
    if user_selected_original or regen_mode == "style_change":
        base_image_urls = stored_original_urls
    else:
        base_image_urls = [last_generated_url] if last_generated_url else stored_original_urls

    try:
        new_url, new_prompt, new_description = await generate_renovation_image(
            original_image_urls=base_image_urls,
            project_type=project_type,
            extracted_data=extracted_data,
            renovation_vision=renovation_vision,
            feedback=feedback_list,
            previous_prompt=stored_generation_prompt if regen_mode != "style_change" else None,
            features_to_retain=features_to_retain,
            visible_elements=visible_elements,
            must_not_add=must_not_add,
            image_scope=image_scope,
            selected_image_url=selected_image_url,
            previous_changes=previous_changes,
        )

        try:
            image_history = add_to_image_history(
                history=image_history,
                url=new_url,
                description=new_description,
                base_perspective=0,
                user_satisfied=None
            )
        except Exception as history_error:
            logger.error(f"[_handle_regeneration] Failed to add to history: {history_error}")
            # Continue with existing history

        updates["generated_image_url"] = new_url
        updates["last_generated_image_url"] = new_url
        updates["generation_prompt"] = new_prompt
        updates["generation_description"] = new_description
        updates["generated_image_history"] = image_history

        response = (
            f'<img src="{new_url}" style="width: 100%; max-width: 800px; '
            f'border-radius: 12px; margin: 16px 0;" />\n\n'
            f"{new_description}\n\n"
            f"How's this? Say **'continue'** when ready, or request more changes."
        )
    except LLMProviderError as llm_error:
        logger.error(f"[_handle_regeneration] LLM provider error during regeneration: {llm_error}", exc_info=True)
        response = (
            "I'm having trouble with the image generation service right now. "
            "You can try again in a moment, say **'continue'** to proceed with the current design, "
            "or request a different change."
        )
    except Exception as e:
        logger.error(f"[_handle_regeneration] Regeneration failed: {e}", exc_info=True)
        # Provide helpful error message to user
        response = (
            "I encountered an issue regenerating the image. This could be due to a temporary service issue. "
            "You can try again, say **'continue'** to proceed with your current design, "
            "or request a different change."
        )

    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_multi_image_regeneration(
    state: ProjectState,
    updates: dict,
    multi_feedback: dict,
    feedback_content: str,
    project_type: str,
    extracted_data: dict,
    renovation_vision: dict | None,
    image_history: list,
    features_to_retain: list,
    generated_options: list,
    stored_original_urls: list
) -> dict:
    """Handle regeneration for multiple images."""

    # NEW: Get hallucination prevention data
    visible_elements = state.get("_visible_elements", {})
    image_scope = state.get("_image_scope", {"frame_type": "full_room", "room_coverage_pct": 100})
    must_not_add = state.get("_must_not_add", [])

    # Get selected image URL from state
    selected_image_url = state.get("selected_image_url")

    async def regenerate_single_image(img_idx: int, specific_feedback: str):
        try:
            base_url = generated_options[img_idx].get("url") if img_idx < len(generated_options) else stored_original_urls[0]

            # Get previous changes from the option's description
            prev_description = generated_options[img_idx].get("description", "") if img_idx < len(generated_options) else ""
            prev_changes = []
            if prev_description:
                for line in prev_description.split('\n'):
                    line = line.strip()
                    if line.startswith(('•', '-', '*')) or (len(line) > 0 and line[0].isdigit() and '.' in line[:3]):
                        change = line.lstrip('•-*0123456789. ')
                        if change and len(change) > 5:
                            prev_changes.append(change)

            url, prompt, desc = await generate_renovation_image(
                original_image_urls=[base_url],
                project_type=project_type,
                extracted_data=extracted_data,
                renovation_vision=renovation_vision,
                feedback=[specific_feedback],
                previous_prompt=generated_options[img_idx].get("prompt") if img_idx < len(generated_options) else None,
                features_to_retain=features_to_retain,
                visible_elements=visible_elements,
                must_not_add=must_not_add,
                image_scope=image_scope,
                selected_image_url=selected_image_url,
                previous_changes=prev_changes,
            )
            return {"position": img_idx + 1, "url": url, "description": desc, "success": True}
        except LLMProviderError as llm_error:
            logger.error(f"[_handle_multi_image_regeneration] LLM provider error for image {img_idx + 1}: {llm_error}", exc_info=True)
            return {"position": img_idx + 1, "url": None, "description": f"Image generation service error: {str(llm_error)}", "success": False}
        except Exception as e:
            logger.error(f"[_handle_multi_image_regeneration] Regeneration failed for image {img_idx + 1}: {e}", exc_info=True)
            return {"position": img_idx + 1, "url": None, "description": f"Failed to regenerate: {str(e)}", "success": False}

    regen_tasks = []
    num_current_images = len(generated_options)
    if multi_feedback.get("applies_to_all"):
        general_fb = multi_feedback.get("general_feedback") or feedback_content
        for i in range(num_current_images):
            regen_tasks.append(regenerate_single_image(i, general_fb))
    else:
        for fb_item in multi_feedback.get("image_feedback", []):
            img_pos = fb_item.get("image_position", 1) - 1
            specific_fb = fb_item.get("feedback", feedback_content)
            if 0 <= img_pos < num_current_images:
                regen_tasks.append(regenerate_single_image(img_pos, specific_fb))

    if regen_tasks:
        try:
            results = await asyncio.gather(*regen_tasks, return_exceptions=True)

            # Filter out exceptions
            results = [r for r in results if isinstance(r, dict)]

            if not results:
                logger.error("[_handle_multi_image_regeneration] All regeneration tasks returned exceptions")
                response = "All image regeneration attempts encountered errors. Please try a different request or contact support."
            else:
                for result in results:
                    if result.get("success"):
                        pos = result["position"] - 1
                        if pos < len(generated_options):
                            generated_options[pos]["url"] = result["url"]
                            generated_options[pos]["description"] = result["description"]
                        try:
                            image_history = add_to_image_history(
                                history=image_history,
                                url=result["url"],
                                description=result["description"],
                                base_perspective=pos,
                                user_satisfied=None
                            )
                        except Exception as history_error:
                            logger.error(f"[_handle_multi_image_regeneration] Failed to add to history: {history_error}")
                            # Continue - history failure shouldn't block the workflow

                updates["generated_options"] = generated_options
                updates["generated_image_history"] = image_history
                updates["image_generation_feedback"] = [str(feedback_content)]

                response = _format_parallel_options_response(generated_options)
                response += "\n\nHow do these look now? Say **'continue'** to proceed, or request more changes."
        except Exception as gather_error:
            logger.error(f"[_handle_multi_image_regeneration] Error gathering regeneration tasks: {gather_error}", exc_info=True)
            response = "An unexpected error occurred during image regeneration. Please try again or request different changes."
    else:
        logger.warning("[_handle_multi_image_regeneration] No regeneration tasks created")
        response = "I couldn't determine which images to regenerate. Please specify which option you'd like to change."

    updates["messages"] = [{"role": "assistant", "content": response}]
    updates["awaiting_user_input"] = True
    return updates


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_option_selection(user_message: str, pending_suggestions: list) -> list[int]:
    """Parse option selection from user message."""
    selected_indices = []
    message_lower = user_message.lower()

    for i, opt in enumerate(pending_suggestions):
        if f"option {i+1}" in message_lower or f"#{i+1}" in message_lower or f"option{i+1}" in message_lower:
            selected_indices.append(i)
        style_name = opt.get("style_name", "").lower()
        if style_name and style_name in message_lower:
            selected_indices.append(i)

    if not selected_indices and "all" in message_lower and ("generate" in message_lower or "show" in message_lower):
        selected_indices = list(range(len(pending_suggestions)))

    return list(dict.fromkeys(selected_indices))


def _format_suggestions_response(suggestions_result: dict) -> str:
    """Format suggestions for display (fallback text format)."""
    options = suggestions_result.get("options", [])
    response_parts = ["# Renovation Options\n\nBased on your space, here are my recommendations:\n"]

    for i, opt in enumerate(options, 1):
        response_parts.append(f"\n### Option {i}: {opt.get('style_name', 'Option')}\n")
        response_parts.append(f"{opt.get('description', '')}\n\n")
        response_parts.append("**Key Changes:**\n")
        for change in opt.get("key_changes", []):
            response_parts.append(f"- {change}\n")
        response_parts.append(f"\n*Budget: {opt.get('budget_tier', 'mid-range')} | "
                             f"Transformation: {opt.get('transformation_level', 'moderate')}*\n")

    response_parts.append(f"\n---\n\n{suggestions_result.get('follow_up_message', '')}")
    response_parts.append("\n\nYou can say things like:")
    response_parts.append("\n- \"Show me option 1\"")
    response_parts.append("\n- \"Generate option 2 and 3\"")
    response_parts.append("\n- \"I like the modern style, generate it\"")

    return "".join(response_parts)


def _format_suggestions_as_cards(suggestions_result: dict, inspirations: dict | None = None) -> dict:
    """
    Format suggestions as a special message type for card rendering.

    Returns a structured dict that the frontend can render as beautiful cards
    with horizontal scroll (desktop) or vertical stack (mobile).
    """
    options = suggestions_result.get("options", [])
    sources = []

    # Extract sources from inspirations if available
    if inspirations:
        sources = inspirations.get("_sources", [])

    return {
        "type": "suggestion_cards",
        "options": options,
        "sources": sources,
        "follow_up_message": suggestions_result.get("follow_up_message", "")
    }


def _format_multi_perspective_response(generated_results: list, error_note: str) -> str:
    """Format response for multiple perspectives."""
    response_parts = []
    successful_results = [r for r in generated_results if r.get("success", False)]

    for i, result in enumerate(successful_results, 1):
        response_parts.append(f"**Perspective {i}**\n")
        response_parts.append(
            f'<img src="{result["url"]}" style="width: 100%; max-width: 800px; '
            f'border-radius: 12px; margin: 8px 0;" />\n\n'
        )
        if result.get("description"):
            response_parts.append(f"{result['description']}\n\n")

    response_parts.append(f"{error_note}")
    response_parts.append("---\n\n")
    response_parts.append("How do these look? Say **'continue'** to proceed, or request changes.")
    return "".join(response_parts)


def _format_parallel_options_response(results: list) -> str:
    """Format response for parallel generated options."""
    response_parts = []

    for i, result in enumerate(results, 1):
        response_parts.append(f"**Option {i}: {result.get('style_name', 'Option')}**\n\n")
        response_parts.append(
            f'<img src="{result.get("url")}" style="width: 100%; max-width: 800px; '
            f'border-radius: 12px; margin: 8px 0;" />\n\n'
        )
        if result.get("description") and result.get("success"):
            response_parts.append(f"{result.get('description', '')}\n\n")

    response_parts.append("---\n\n")
    response_parts.append("Which option do you prefer? Say **'option 1'** to continue, or request changes.")

    return "".join(response_parts)
