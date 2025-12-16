# """
# Visual Collection Node.

# Processes uploaded images, extracts details, asks confirmation for uncertain items.
# """

# import uuid
# from src.core.llm.provider import LLMProvider
# from src.core.langgraph.state import ProjectState, ImageData, PendingConfirmation
# from tests.conftest import parse_json


# IMAGE_ANALYSIS_PROMPT = """You are a renovation expert analyzing a room image.

# Project type: {project_type}

# Analyze this image and extract:
# 1. Room features (cabinets, countertops, flooring, fixtures, etc.)
# 2. Materials you can identify (granite, wood, tile, etc.)
# 3. Condition/age estimate
# 4. Any measurements you can estimate

# For each item, provide a confidence score (0-1).
# - 0.8+ = confident
# - 0.5-0.8 = somewhat confident  
# - <0.5 = uncertain, needs confirmation

# Return JSON only:
# {{
#     "features": [
#         {{"name": "countertop", "material": "granite", "condition": "good", "confidence": 0.9}},
#         {{"name": "cabinets", "material": "wood", "style": "shaker", "confidence": 0.7}}
#     ],
#     "estimated_dimensions": {{
#         "width_ft": 12,
#         "length_ft": 10,
#         "confidence": 0.5
#     }},
#     "overall_condition": "good/fair/poor",
#     "notes": "any additional observations"
# }}
# """

# CONFIRMATION_PROMPT = """I noticed {feature} that appears to be {material}, but I'm not entirely sure.
# Could you confirm if that's correct?"""

# CONTINUE_PROMPT = """I've analyzed your images. Here's what I found:

# {summary}

# Would you like to:
# 1. Upload more images
# 2. Correct any of the above
# 3. Continue to the next step

# Just let me know!"""


# async def analyze_image(image_url: str, project_type: str) -> dict:
#     """Analyze a single image using VLM."""
#     provider = LLMProvider.for_vlm()
    
#     response = await provider.complete(
#         messages=[
#             {
#                 "role": "system",
#                 "content": "You are a renovation expert. Analyze images and extract details. Return JSON only."
#             },
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": IMAGE_ANALYSIS_PROMPT.format(project_type=project_type)},
#                     {"type": "image_url", "image_url": {"url": image_url}}
#                 ]
#             }
#         ],
#         temperature=0.2,
#         max_tokens=500
#     )
    
#     try:
#         return parse_json(response)
#     except:
#         return {"features": [], "notes": "Failed to parse image analysis"}


# def find_uncertain_items(extracted: dict, threshold: float = 0.7) -> list[dict]:
#     """Find items with confidence below threshold."""
#     uncertain = []
    
#     for feature in extracted.get("features", []):
#         if feature.get("confidence", 1.0) < threshold:
#             uncertain.append({
#                 "field": feature.get("name", "unknown"),
#                 "extracted_value": feature.get("material", "unknown"),
#                 "confidence": feature.get("confidence", 0.5)
#             })
    
#     dims = extracted.get("estimated_dimensions", {})
#     if dims and dims.get("confidence", 1.0) < threshold:
#         uncertain.append({
#             "field": "dimensions",
#             "extracted_value": f"{dims.get('width_ft', '?')}x{dims.get('length_ft', '?')} ft",
#             "confidence": dims.get("confidence", 0.5)
#         })
    
#     return uncertain


# def generate_summary(images: list[ImageData]) -> str:
#     """Generate summary of all extracted data."""
#     if not images:
#         return "No images analyzed yet."
    
#     lines = []
#     all_features = []
    
#     for i, img in enumerate(images, 1):
#         extracted = img.get("extracted", {})
#         features = extracted.get("features", [])
#         all_features.extend(features)
    
#     # Group by feature type
#     feature_map = {}
#     for f in all_features:
#         name = f.get("name", "unknown")
#         if name not in feature_map:
#             feature_map[name] = f
    
#     for name, f in feature_map.items():
#         material = f.get("material", "unknown")
#         conf = f.get("confidence", 0)
#         conf_str = "✓" if conf >= 0.8 else "?"
#         lines.append(f"- {name.title()}: {material} {conf_str}")
    
#     return "\n".join(lines) if lines else "No features extracted."


# async def process_user_confirmation(state: ProjectState, user_message: str) -> dict:
#     """Process user's confirmation or correction."""
#     provider = LLMProvider.for_llm()
    
#     pending = state.get("pending_confirmations", [])
#     if not pending:
#         return {}
    
#     current = pending[0]
    
#     # Check if user confirmed or corrected
#     response = await provider.complete(
#         messages=[
#             {
#                 "role": "system",
#                 "content": """Analyze user's response to a confirmation question.
# Return JSON: {"confirmed": true/false, "corrected_value": "..." or null}"""
#             },
#             {
#                 "role": "user",
#                 "content": f"""Question was about: {current['field']} being {current['extracted_value']}
# User response: "{user_message}"

# Did they confirm or provide a correction?"""
#             }
#         ],
#         temperature=0.0,
#         max_tokens=50
#     )
    
#     try:
#         result = parse_json(response)
#         return {
#             "confirmed": result.get("confirmed", False),
#             "corrected_value": result.get("corrected_value")
#         }
#     except:
#         return {"confirmed": True, "corrected_value": None}


# def get_message_content(msg) -> tuple[str | None, any]:
#     """Extract role and content from message (dict or LangChain Message object)."""
#     if isinstance(msg, dict):
#         return msg.get("role"), msg.get("content", "")
#     role = getattr(msg, "type", None)
#     if role == "human":
#         role = "user"
#     elif role == "ai":
#         role = "assistant"
#     content = getattr(msg, "content", "")
#     return role, content


# async def visual_collection_node(state: ProjectState) -> dict:
#     """
#     Visual collection node.
    
#     - Processes new images if uploaded
#     - Asks confirmation for uncertain extractions
#     - Moves to next stage when user is ready
#     """
#     messages = state.get("messages", [])
#     images = list(state.get("images", []))
#     pending = list(state.get("pending_confirmations", []))
    
#     updates = {}
    
#     # Get latest user message
#     user_message = None
#     new_images = []
    
#     for msg in reversed(messages):
#         role, content = get_message_content(msg)
#         if role == "user":
#             # Check if it's multimodal (has images)
#             if isinstance(content, list):
#                 for item in content:
#                     if isinstance(item, dict):
#                         if item.get("type") == "image_url":
#                             new_images.append(item["image_url"]["url"])
#                         elif item.get("type") == "text":
#                             user_message = item.get("text", "")
#             else:
#                 user_message = content
#             break
    
#     project_type = state.get("project_type", "renovation")
    
#     # Process new images
#     if new_images:
#         for img_url in new_images:
#             img_id = str(uuid.uuid4())[:8]
#             extracted = await analyze_image(img_url, project_type)
            
#             images.append(ImageData(
#                 id=img_id,
#                 url=img_url,
#                 extracted=extracted,
#                 confirmed=False
#             ))
            
#             # Add uncertain items to pending confirmations
#             uncertain = find_uncertain_items(extracted)
#             for item in uncertain:
#                 pending.append(PendingConfirmation(
#                     field=item["field"],
#                     extracted_value=item["extracted_value"],
#                     confidence=item["confidence"],
#                     source_image_id=img_id
#                 ))
        
#         updates["images"] = images
#         updates["pending_confirmations"] = pending
    
#     # Handle confirmation flow
#     if pending and user_message and not new_images:
#         result = await process_user_confirmation(state, user_message)
        
#         # Update the confirmed item
#         confirmed_item = pending.pop(0)
        
#         # Update image extracted data if corrected
#         if result.get("corrected_value"):
#             for img in images:
#                 if img.get("id") == confirmed_item.get("source_image_id"):
#                     for feature in img.get("extracted", {}).get("features", []):
#                         if feature.get("name") == confirmed_item.get("field"):
#                             feature["material"] = result["corrected_value"]
#                             feature["confidence"] = 1.0
        
#         updates["images"] = images
#         updates["pending_confirmations"] = pending
    
#     # Check if user wants to continue
#     if user_message:
#         user_lower = user_message.lower()
#         if any(word in user_lower for word in ["continue", "next", "proceed", "yes", "done"]):
#             if not pending:  # Only if no pending confirmations
#                 updates["current_stage"] = "material_verification"
#                 updates["user_confirmed_continue"] = True
#                 response = "Great! Let's verify the materials I've identified."
#                 updates["messages"] = [{"role": "assistant", "content": response}]
#                 return updates
    
#     # Generate response
#     if pending:
#         # Ask confirmation for next uncertain item
#         item = pending[0]
#         response = CONFIRMATION_PROMPT.format(
#             feature=item["field"],
#             material=item["extracted_value"]
#         )
#     elif new_images:
#         # Just processed images, show summary
#         summary = generate_summary(images)
#         response = CONTINUE_PROMPT.format(summary=summary)
#     elif images:
#         # Has images, waiting for user decision
#         summary = generate_summary(images)
#         response = CONTINUE_PROMPT.format(summary=summary)
#     else:
#         # No images yet
#         response = "Please upload one or more images of the space you want to renovate."
    
#     updates["messages"] = [{"role": "assistant", "content": response}]
#     updates["awaiting_user_input"] = True
    
#     return updates