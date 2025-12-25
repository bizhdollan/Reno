import asyncio
import json

from src.core.llm.provider import LLMProvider
from src.core.langgraph.state import (
    ProjectState,
    merge_image_analyses_to_extracted,
)
from src.core.langgraph.utils import get_latest_user_message
from src.core.langgraph.config import VISION_PROMPT

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


async def image_analysis_generation_node(state: ProjectState) -> dict:
    """
    Main image analysis and generation node.

    Sub-states:
    - analyzing: Process new images, extract ALL data
    - confirming_extraction: User reviews/corrects all data at once
    - collecting_vision: OPTIONAL - collect user's renovation vision
    - generating: Generate proposal/preview image
    - confirming_proposal: User reviews generated image
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

    # Clear pending images after using
    if pending_images:
        updates["_pending_images"] = []

    project_type = state.get("project_type", "renovation")

    print(f"[image_analysis] SUB_STATE: {sub_state} | user_message={user_message!r} | "
          f"new_images={len(new_image_urls)} | stored_analyses={len(image_analyses)}")

    # =========================================================================
    # ANALYZING STATE - Extract all data from images
    # =========================================================================
    if sub_state == "analyzing":
        if new_image_urls:
            print(f"[image_analysis] Processing {len(new_image_urls)} images in parallel...")

            # Analyze all images in parallel
            image_analyses = await analyze_images_parallel(new_image_urls, project_type)
            updates["image_analyses"] = image_analyses

            # Merge into extracted_data (kept internally, not shown to user)
            extracted_data = merge_image_analyses_to_extracted(image_analyses)
            updates["extracted_data"] = extracted_data

            # Detect features to retain (parallel with summary generation)
            primary_image_url = new_image_urls[0]

            # Run feature detection and brief summary in parallel
            features_task = detect_features_to_retain(primary_image_url)
            summary_task = generate_brief_room_summary(primary_image_url, project_type, extracted_data)

            features_result, summary_result = await asyncio.gather(features_task, summary_task)

            # Store features to retain for later image generation
            features_to_retain = features_result.get("must_retain_features", [])
            updates["original_features_to_retain"] = features_to_retain
            print(f"[image_analysis] Features to retain: {features_to_retain}")

            # Store brief summary
            brief_summary = summary_result.get("brief_summary", f"A {project_type} space.")
            room_vibe = summary_result.get("room_vibe", "current")
            updates["brief_room_summary"] = brief_summary

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

            response = (
                f"{images_display}\n\n"
                f"**{brief_summary}**\n\n"
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
        return updates

    # =========================================================================
    # DESIGN CONVERSATION STATE - Flexible conversation after extraction
    # =========================================================================
    elif sub_state in ["confirming_extraction", "collecting_vision", "design_conversation"]:
        return await _handle_design_conversation(
            state, updates, user_message, project_type,
            image_analyses, extracted_data, renovation_vision
        )

    # =========================================================================
    # SELECTING SUGGESTIONS STATE
    # =========================================================================
    elif sub_state == "selecting_suggestions":
        return await _handle_selecting_suggestions(state, updates, user_message, extracted_data, project_type)

    # =========================================================================
    # GENERATING STATE - Generate proposal image(s)
    # =========================================================================
    elif sub_state == "generating":
        return await _handle_generating(
            state, updates, project_type, image_analyses, extracted_data, renovation_vision
        )

    # =========================================================================
    # GENERATING PARALLEL STATE
    # =========================================================================
    elif sub_state == "generating_parallel":
        return await _handle_generating_parallel(
            state, updates, project_type, image_analyses, extracted_data
        )

    # =========================================================================
    # CONFIRMING PROPOSAL STATE
    # =========================================================================
    elif sub_state == "confirming_proposal":
        return await _handle_confirming_proposal(
            state, updates, user_message, project_type, image_analyses, extracted_data, renovation_vision
        )

    # Fallback
    updates["messages"] = [{"role": "assistant", "content": "Something went wrong. Please try again."}]
    updates["awaiting_user_input"] = True
    return updates


async def _handle_design_conversation(
    state: ProjectState,
    updates: dict,
    user_message: str,
    project_type: str,
    image_analyses: list,
    extracted_data: dict,
    renovation_vision: dict | None
) -> dict:
    """Handle the design conversation sub-state."""
    expertise_level = state.get("expertise_level", "novice")

    if user_message:
        # Check if user is selecting from pending suggestions
        pending_suggestions = state.get("pending_suggestions", [])
        if pending_suggestions:
            selected_indices = _parse_option_selection(user_message, pending_suggestions)

            if selected_indices:
                print(f"[design_conversation] Option selection detected: indices {selected_indices}")
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
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates
                else:
                    updates["selected_options_for_generation"] = selected_options
                    updates["pending_suggestions"] = []
                    updates["image_sub_state"] = "generating_parallel"
                    updates["awaiting_user_input"] = False
                    updates["messages"] = []
                    return updates

        # Use UNIFIED classifier
        context = (
            f"User is in a {project_type} renovation project. "
            f"Extracted data includes: {list(extracted_data.keys())}. "
            f"User can: confirm extraction, correct data, provide vision, ask suggestions, ask questions, skip steps."
        )
        unified_result = await unified_classify(
            user_message=user_message,
            context=context,
            has_generated_images=len(state.get("generated_image_history", [])) > 0
        )

        primary_intent = unified_result.get("primary_intent", "unclear")
        secondary_intents = unified_result.get("secondary_intents", [])
        extracted_content = unified_result.get("extracted_content", {})

        # Cache expertise level if not already set
        if not state.get("expertise_level"):
            expertise_level = unified_result.get("expertise_level", "novice")
            updates["expertise_level"] = expertise_level

        print(f"[design_conversation] Intent: {primary_intent} | secondary: {secondary_intents}")

        # Handle corrections
        if primary_intent == "correction" or "correction" in secondary_intents:
            corrections = extracted_content.get("corrections") or user_message
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

            suggestions_result = await generate_expert_suggestions(
                project_type=project_type,
                current_state_summary=current_state_summary,
                user_preferences=user_prefs,
                expertise_level=expertise_level
            )

            updates["pending_suggestions"] = suggestions_result.get("options", [])
            response = _format_suggestions_response(suggestions_result)
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        elif primary_intent == "ask_question":
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
            updates["messages"] = [{"role": "assistant", "content": response}]
            updates["awaiting_user_input"] = True
            return updates

        elif primary_intent == "vague_request":
            vague_needs = extracted_content.get("vague_needs") or user_message
            extracted_summary = json.dumps(extracted_data, indent=2)[:500] if extracted_data else ""

            clarification = await clarify_vague_request(
                user_request=vague_needs,
                project_type=project_type,
                extracted_data_summary=extracted_summary,
                expertise_level=expertise_level
            )

            response = clarification.get("suggested_response", "Could you tell me more about what you'd like to change?")
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
    renovation_vision: dict | None
) -> dict:
    """Handle the generating sub-state."""
    print("[image_analysis] Generating renovation preview image(s)...")

    original_image_urls = [img["url"] for img in image_analyses]
    features_to_retain = state.get("original_features_to_retain", [])
    image_history = list(state.get("generated_image_history", []))

    if not original_image_urls:
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
            )

            image_history = add_to_image_history(
                history=image_history,
                url=generated_url,
                description=description,
                base_perspective=0,
                user_satisfied=None
            )
            generated_results = [{"url": generated_url, "description": description, "perspective": 0}]
        except Exception as e:
            print(f"[image_analysis] Image generation failed: {e}")
            generated_url = get_placeholder_image_url()
            generation_prompt = ""
            description = ""
            generated_results = []
            updates["_generation_error"] = str(e)
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
                )
                return {"url": url, "prompt": prompt, "description": desc, "perspective": perspective_idx, "success": True}
            except Exception as e:
                return {"url": get_placeholder_image_url(), "description": str(e), "perspective": perspective_idx, "success": False}

        generated_results = await asyncio.gather(*[
            generate_for_perspective(url, idx) for idx, url in enumerate(original_image_urls)
        ])

        for result in generated_results:
            if result.get("success"):
                image_history = add_to_image_history(
                    history=image_history,
                    url=result["url"],
                    description=result.get("description", ""),
                    base_perspective=result["perspective"],
                    user_satisfied=None
                )

        successful = [r for r in generated_results if r.get("success")]
        if successful:
            generated_url = successful[0]["url"]
            generation_prompt = successful[0].get("prompt", "")
            description = successful[0].get("description", "")
        else:
            generated_url = get_placeholder_image_url()
            generation_prompt = ""
            description = ""
            updates["_generation_error"] = "All perspective generations failed"

    updates["generated_image_url"] = generated_url
    updates["last_generated_image_url"] = generated_url
    updates["generation_prompt"] = generation_prompt
    updates["generation_description"] = description
    updates["original_image_urls"] = original_image_urls
    updates["generated_image_history"] = image_history
    updates["image_sub_state"] = "confirming_proposal"

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
    """Handle the generating parallel sub-state."""
    selected_options = state.get("selected_options_for_generation", [])
    original_image_urls = [img["url"] for img in image_analyses]
    features_to_retain = state.get("original_features_to_retain", [])
    image_history = list(state.get("generated_image_history", []))

    if not selected_options or not original_image_urls:
        response = "Unable to generate options. Please go back and select options again."
        updates["messages"] = [{"role": "assistant", "content": response}]
        updates["image_sub_state"] = "design_conversation"
        updates["awaiting_user_input"] = True
        return updates

    print(f"[image_analysis] Generating {len(selected_options)} options in parallel...")

    async def generate_option(option, perspective_idx=0):
        try:
            vision = {
                "raw_input": f"Style: {option.get('style_name')}",
                "ai_summary": option.get("description", ""),
                "selected_option": option
            }
            base_urls = [original_image_urls[perspective_idx]] if perspective_idx < len(original_image_urls) else original_image_urls
            url, prompt, desc = await generate_renovation_image(
                original_image_urls=base_urls,
                project_type=project_type,
                extracted_data=extracted_data,
                renovation_vision=vision,
                feedback=None,
                previous_prompt=None,
                features_to_retain=features_to_retain,
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
            return {
                "style_name": option.get("style_name"),
                "url": get_placeholder_image_url(),
                "description": f"Failed to generate: {e}",
                "perspective": perspective_idx,
                "success": False
            }

    results = await asyncio.gather(*[generate_option(opt, 0) for opt in selected_options])

    for result in results:
        if result.get("success"):
            image_history = add_to_image_history(
                history=image_history,
                url=result["url"],
                description=result.get("description", ""),
                base_perspective=result.get("perspective", 0),
                user_satisfied=None
            )

    updates["generated_options"] = results
    updates["original_image_urls"] = original_image_urls
    updates["generated_image_history"] = image_history
    updates["image_sub_state"] = "confirming_proposal"

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
    renovation_vision: dict | None
) -> dict:
    """Handle the confirming proposal sub-state."""
    image_history = list(state.get("generated_image_history", []))
    current_generated_url = state.get("generated_image_url", "")
    features_to_retain = state.get("original_features_to_retain", [])

    # Check for pending regeneration from final_review
    pending_regeneration = state.get("_pending_regeneration")
    if pending_regeneration:
        print(f"[confirming_proposal] Handling pending regeneration: {pending_regeneration}")
        user_message = pending_regeneration
        updates["_pending_regeneration"] = None

    if user_message:
        msg_lower = user_message.lower().strip()

        # Quick keyword-based pre-check
        change_keywords = [
            "should be", "should have", "add ", "change ", "make it", "make the",
            "i want", "put ", "use ", "replace", "remove ", "tiles", "marble",
            "wood", "carpet", "paint", "color", "darker", "lighter", "bigger",
            "smaller", "modern", "traditional", "floor", "wall", "ceiling",
            "let's add", "lets add", "can you add", "give me", "show me with"
        ]
        approval_keywords = [
            "looks good", "look good", "perfect", "continue", "proceed",
            "i'm happy", "im happy", "that's good", "thats good", "great",
            "love it", "like it", "yes", "ok", "okay", "done", "finish"
        ]

        is_obvious_change = any(kw in msg_lower for kw in change_keywords)
        is_pure_approval = any(kw in msg_lower for kw in approval_keywords) and not is_obvious_change

        if is_obvious_change:
            conversation_type = "generation_request"
            conv_type = {
                "conversation_type": "generation_request",
                "confidence": 0.95,
                "generation_changes": user_message
            }
        elif is_pure_approval:
            conversation_type = "move_forward"
            conv_type = {"conversation_type": "move_forward", "confidence": 0.95}
        else:
            context = f"User is reviewing a generated renovation preview with {len(image_history)} generated images."
            unified_result = await unified_classify(
                user_message=user_message,
                context=context,
                has_generated_images=len(image_history) > 0
            )
            conversation_type = unified_result.get("conversation_type", "clarify")
            conv_type = {
                "conversation_type": conversation_type,
                "confidence": unified_result.get("confidence", 0.5),
                "extracted_question": unified_result.get("extracted_content", {}).get("questions", [None])[0] if unified_result.get("extracted_content", {}).get("questions") else None,
                "referenced_image_position": unified_result.get("extracted_content", {}).get("referenced_image_position"),
                "generation_changes": unified_result.get("extracted_content", {}).get("generation_changes")
            }

        print(f"[confirming_proposal] Conversation type: {conversation_type}")

        if conversation_type == "discussion":
            question = conv_type.get("extracted_question") or user_message
            image_to_analyze = current_generated_url or (image_analyses[0]["url"] if image_analyses else None)
            if image_to_analyze:
                answer = await answer_image_question(
                    question=question,
                    image_url=image_to_analyze,
                    context=f"This is a {project_type} renovation preview"
                )
                response = f"{answer}\n\n---\n\nAnything else you'd like to know, or are you ready to continue?"
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
            updates["current_stage"] = "final_review"
            updates["awaiting_user_input"] = False
            updates["messages"] = []
            return updates

        elif conversation_type == "generation_request":
            return await _handle_regeneration(
                state, updates, user_message, conv_type, project_type,
                image_analyses, extracted_data, renovation_vision,
                image_history, features_to_retain
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
    features_to_retain: list
) -> dict:
    """Handle image regeneration based on user feedback."""
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

    existing_feedback = state.get("image_generation_feedback", [])
    feedback_list = [str(f) for f in existing_feedback]
    feedback_list.append(str(feedback_content))
    updates["image_generation_feedback"] = feedback_list

    last_generated_url = state.get("last_generated_image_url", "")
    stored_generation_prompt = state.get("generation_prompt", "")

    if regen_mode == "style_change":
        base_image_urls = stored_original_urls
        feedback_list = [str(feedback_content)]
        updates["image_generation_feedback"] = feedback_list
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
        )

        image_history = add_to_image_history(
            history=image_history,
            url=new_url,
            description=new_description,
            base_perspective=0,
            user_satisfied=None
        )

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
    except Exception as e:
        print(f"[confirming_proposal] Regeneration failed: {e}")
        response = f"I encountered an issue. Say **'continue'** to proceed or try a different request."

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
    async def regenerate_single_image(img_idx: int, specific_feedback: str):
        try:
            base_url = generated_options[img_idx].get("url") if img_idx < len(generated_options) else stored_original_urls[0]
            url, prompt, desc = await generate_renovation_image(
                original_image_urls=[base_url],
                project_type=project_type,
                extracted_data=extracted_data,
                renovation_vision=renovation_vision,
                feedback=[specific_feedback],
                previous_prompt=generated_options[img_idx].get("prompt") if img_idx < len(generated_options) else None,
                features_to_retain=features_to_retain,
            )
            return {"position": img_idx + 1, "url": url, "description": desc, "success": True}
        except Exception as e:
            return {"position": img_idx + 1, "url": None, "description": str(e), "success": False}

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
        results = await asyncio.gather(*regen_tasks)

        for result in results:
            if result.get("success"):
                pos = result["position"] - 1
                if pos < len(generated_options):
                    generated_options[pos]["url"] = result["url"]
                    generated_options[pos]["description"] = result["description"]
                image_history = add_to_image_history(
                    history=image_history,
                    url=result["url"],
                    description=result["description"],
                    base_perspective=pos,
                    user_satisfied=None
                )

        updates["generated_options"] = generated_options
        updates["generated_image_history"] = image_history
        updates["image_generation_feedback"] = [str(feedback_content)]

        response = _format_parallel_options_response(generated_options)
        response += "\n\nHow do these look now? Say **'continue'** to proceed, or request more changes."
    else:
        response = "I couldn't determine which images to regenerate. Please specify."

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
    """Format suggestions for display."""
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
