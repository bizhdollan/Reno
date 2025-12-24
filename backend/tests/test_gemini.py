import os
import base64
from litellm import completion
from PIL import Image
from io import BytesIO
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
def generate_renovated_bedroom_with_description(input_image_path="bedroom.jpg"):
    print(f"🏠 Analyzing & renovating bedroom from: {input_image_path}")
    
    # ✅ CRITICAL: Explicit 2-step structure for image generation
    renovation_prompt = """
    1. Describe the changes made to this bedroom:
    - Floor: glossy black hexagonal tiles
    - Ceiling: crystal chandelier (center)  
    - Wall: 3 sci-fi posters (Cyberpunk 2077, Blade Runner, Star Wars)
    - Lighting: 2 modern floor lamps (warm light)
    - Walls: dark blue accent paint
    - Furniture: sleeker modern versions
    
    2. GENERATE THE RENOVATED IMAGE showing these exact changes. 
    Keep original room layout and proportions. Photorealistic, high-res.
    """
    
    try:
        base64_image = encode_image_to_base64(input_image_path)
        messages = [{
            "role": "user", 
            "content": [
                {"type": "text", "text": renovation_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{base64_image}"}}
            ]
        }]
        
        print("🎨 Generating description + image...")
        
        response = completion(
            model="gemini/gemini-2.5-flash-image",
            messages=messages,
            # ✅ Remove extra_body - it was blocking image gen
            temperature=0.3,  # Consistent results
            max_tokens=2048
        )
        
        # ✅ CORRECT parsing from your debug output
        choice = response.choices[0]
        message_content = choice.message.content
        
        # Print TEXT (already working perfectly)
        print("\n📝 CHANGES IMPLEMENTED:")
        if isinstance(message_content, str):
            print(message_content)
        else:
            for part in message_content:
                if hasattr(part, 'text') and part.text:
                    print(part.text)
                    break
        
        print("\n" + "="*60 + "\n")
        
        # ✅ Check for image in multiple possible locations
        image_generated = False
        
        # Location 1: Native Gemini structure (most likely)
        if 'candidates' in response:
            for candidate in response['candidates']:
                if 'content' in candidate and 'parts' in candidate['content']:
                    for part in candidate['content']['parts']:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            img_data = base64.b64decode(part.inline_data.data)
                            img = Image.open(BytesIO(img_data))
                            img.save("renovated_bedroom_final.png")
                            img.show()
                            print("✅ IMAGE SAVED: 'renovated_bedroom_final.png' (~$0.039)")
                            image_generated = True
                            break
                    if image_generated:
                        break
        
        # Location 2: LiteLLM images array  
        if not image_generated and hasattr(choice.message, 'images') and choice.message.images:
            image_data_url = choice.message.images[0]["image_url"]["url"]
            base64_string = image_data_url.split(",")[1]
            img_data = base64.b64decode(base64_string)
            img = Image.open(BytesIO(img_data))
            img.save("renovated_bedroom_final.png")
            img.show()
            print("✅ IMAGE SAVED: 'renovated_bedroom_final.png' (~$0.039)")
            image_generated = True
        
        if not image_generated:
            print("⚠️ No image found. Try this simpler prompt:")
            print("\n'RENOVATE this bedroom with black tiles + chandelier. GENERATE IMAGE'")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    generate_renovated_bedroom_with_description("/Users/chhabi/Desktop/Reno/backend/tests/20251223_100352_e09dc00e.webp")
