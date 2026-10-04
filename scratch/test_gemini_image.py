import os
import base64
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
print("Using API key:", api_key[:10] if api_key else "None")

client = genai.Client(api_key=api_key)

# Test 1: generate_images with imagen-3.0-generate-002
try:
    print("1. Testing client.models.generate_images(model='imagen-3.0-generate-002')...")
    res = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt="Modern product hero graphic for TaskFlow Pro project management app",
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="16:9",
            output_mime_type="image/png",
        )
    )
    img_bytes = res.generated_images[0].image.image_bytes
    print(f"   SUCCESS! Generated image bytes: {len(img_bytes)}")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 2: generate_images with gemini-3.1-flash-image
try:
    print("2. Testing client.models.generate_images(model='gemini-3.1-flash-image')...")
    res = client.models.generate_images(
        model="gemini-3.1-flash-image",
        prompt="Modern product hero graphic for TaskFlow Pro project management app",
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="16:9",
            output_mime_type="image/png",
        )
    )
    img_bytes = res.generated_images[0].image.image_bytes
    print(f"   SUCCESS! Generated image bytes: {len(img_bytes)}")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 3: generate_content with gemini-2.5-flash
try:
    print("3. Testing client.models.generate_content(model='gemini-2.5-flash')...")
    res = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Draw an image of a product hero banner for TaskFlow Pro",
    )
    print("   Response text:", res.text[:100])
except Exception as e:
    print(f"   FAILED: {e}")
