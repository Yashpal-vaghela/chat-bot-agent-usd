import os
import sys
sys.path.insert(0, os.path.abspath("."))
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hm.settings')
django.setup()

import base64
import requests
import cv2
import numpy as np
from PIL import Image
from virtualsmileAI.gemini import get_api_key, get_model_name, get_mediapipe_landmarks

api_key = get_api_key()
model_name = get_model_name()
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

input_path = "media/smile_design/before/before_1788759159_2ebf78b194.jpg"
output_path = "C:/Users/HP/.gemini/antigravity-ide/brain/1a905a69-31ae-481d-a2ad-7ee8046bd17c/scratch/test_structured_prompt_out.jpg"

with open(input_path, "rb") as f:
    b64_img = base64.b64encode(f.read()).decode("utf-8")

prompt_text = """[TASK: IMAGE EDITING]
TARGET_AREA: Upper jaw / Maxillary dental arch ONLY.

[RIGID IMAGE GRID CONSTRAINT]
- DO NOT crop, scale, or zoom the original image matrix. 
- Head placement, shoulder coordinates, and camera zoom must match the input photo with 100% pixel-level alignment.
- Canvas math is 1184x864 (4:3 aspect ratio). Output canvas must be exactly 1184x864 pixels.

[ANATOMICAL BOUNDARIES]
1. GENERATE: Natural, well-proportioned human top teeth with delicate individual scalloping and porcelain ivory luster (zero blue tint).
2. FREEZE / MASK OUT: The lower lip, bottom gumline, and lower jaw. 
3. EXCLUSION RULE: If lower teeth are not present in the input image, DO NOT force an opening to draw them. The lower mouth territory is strictly out-of-bounds for generation.
4. Expressly forbid widening the mouth opening or altering the natural curve of the lip corners.
5. Output ONLY the final rendered photograph of the subject with no text commentary.
"""

payload = {
    "contents": [
        {
            "parts": [
                {"text": prompt_text},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_img
                    }
                }
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0.25,
        "topP": 0.95,
        "seed": 42,
        "thinkingConfig": {
            "thinkingLevel": "HIGH",
            "includeThoughts": True
        }
    },
    "safetySettings": [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
    ]
}

print("Sending request to Gemini with Structured Object Lock prompt...")
resp = requests.post(url, json=payload, timeout=120)
if resp.status_code != 200:
    print("Error:", resp.status_code, resp.text)
    exit(1)

data = resp.json()
img_bytes = None
for c in data.get("candidates", []):
    for p in c.get("content", {}).get("parts", []):
        if p.get("thought"):
            print("[Thought]:", p.get("text", "")[:300])
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            img_bytes = base64.b64decode(inline["data"])

if img_bytes:
    with open(output_path, "wb") as f:
        f.write(img_bytes)
    print("Saved image to:", output_path)

    # Now let's analyze dimensions and landmarks
    b = cv2.imread(input_path)
    a = cv2.imread(output_path)
    print(f"Before shape: {b.shape}, After shape: {a.shape}")
    lm_b = get_mediapipe_landmarks(b)
    lm_a = get_mediapipe_landmarks(a)
    if lm_b is not None and lm_a is not None:
        eye_b = np.linalg.norm(lm_b[33] - lm_b[263])
        eye_a = np.linalg.norm(lm_a[33] - lm_a[263])
        print(f"Eye distance: before={eye_b:.1f}, after={eye_a:.1f}, ratio={eye_a/eye_b:.3f}")
        mouth_w_b = np.linalg.norm(lm_b[61] - lm_b[291])
        mouth_w_a = np.linalg.norm(lm_a[61] - lm_a[291])
        print(f"Mouth width: before={mouth_w_b:.1f}, after={mouth_w_a:.1f}, ratio={mouth_w_a/mouth_w_b:.3f}")
        mouth_h_b = np.linalg.norm(lm_b[13] - lm_b[14])
        mouth_h_a = np.linalg.norm(lm_a[13] - lm_a[14])
        print(f"Mouth opening height: before={mouth_h_b:.1f}, after={mouth_h_a:.1f}, ratio={mouth_h_a/mouth_h_b:.3f}")
else:
    print("No image returned by Gemini")
