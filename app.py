import os

os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from flask import Flask, jsonify, render_template, request
from paddleocr import PaddleOCR
from PIL import Image
from io import BytesIO
from openai import OpenAI
import base64
import csv


app = Flask(__name__)

ocr = PaddleOCR(
    lang="ch",
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False
)

client = OpenAI()

scene_elements = []
last_character = None


def load_character_meanings():
    csv_path = os.path.join("data", "character_meanings_visual_filtered.csv")
    meanings = {}

    with open(csv_path, "r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            character = row["character"].strip()

            meanings[character] = {
                "pinyin": row.get("pinyin", "").strip(),
                "meaning": row.get("meaning", "").strip(),
                "visual_category": row.get("visual_category", "object").strip(),
                "prompt_hint": row.get("prompt_hint", "").strip(),
                "usable_for_image": row.get("usable_for_image", "yes").strip().lower()
            }

    return meanings


CHARACTER_MEANINGS = load_character_meanings()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/test")
def test():
    result = process_character_image("test.png", 500, 650)
    return jsonify(result)


@app.route("/add_character", methods=["POST"])
def add_character():
    data = request.get_json()

    image_data = data["image"]
    canvas_width = data.get("canvas_width", 500)
    canvas_height = data.get("canvas_height", 650)

    header, encoded = image_data.split(",", 1)
    image_bytes = base64.b64decode(encoded)

    image = Image.open(BytesIO(image_bytes)).convert("RGB")

    os.makedirs("static", exist_ok=True)
    upload_path = "static/current_drawing.png"
    image.save(upload_path)

    result = process_character_image(
        upload_path,
        canvas_width,
        canvas_height
    )

    return jsonify(result)

@app.route("/generate_scene", methods=["POST"])
def generate_scene():
    if not scene_elements:
        return jsonify({"error": "No artwork elements yet. Add a character first."})

    prompt = build_scene_prompt(scene_elements)
    generated_image_path = generate_image(prompt)

    return jsonify({
        "prompt": prompt,
        "image_path": generated_image_path,
        "scene_elements": scene_elements
    })


@app.route("/reset_scene", methods=["POST"])
def reset_scene():
    global scene_elements, last_character
    scene_elements = []
    last_character = None
    return jsonify({"status": "scene reset"})


def process_character_image(image_path, canvas_width=500, canvas_height=650):
    global last_character

    result = ocr.predict(image_path)

    for page in result:
        texts = page.get("rec_texts", [])
        scores = page.get("rec_scores", [])

        if texts:
            character = texts[0]
            confidence = float(scores[0])

            if character == last_character:
                return {
                    "message": "Same character, skipping regeneration",
                    "character": character,
                    "confidence": confidence,
                    "scene_elements": scene_elements
                }

            last_character = character

            char_info = CHARACTER_MEANINGS.get(character)

            if char_info and char_info["usable_for_image"] == "yes":
                meaning = char_info["meaning"]
                visual = char_info["prompt_hint"] or meaning
                visual_category = char_info["visual_category"]

            elif char_info:
                meaning = char_info["meaning"]
                visual = f"an abstract ink-wash form inspired by the idea of {meaning}"
                visual_category = "abstract"

            else:
                meaning = "abstract symbolic form"
                visual = f"an abstract ink-wash form inspired by the handwritten Chinese character {character}"
                visual_category = "abstract"

            bbox = extract_drawing_bbox(image_path)

            position = classify_position(
                bbox,
                canvas_width,
                canvas_height
            )

            size = classify_size(
                bbox,
                canvas_width,
                canvas_height
            )

            scene_elements.append({
                "character": character,
                "meaning": meaning,
                "visual": visual,
                "visual_category": visual_category,
                "position": position,
                "size": size
            })

            return {
                "character": character,
                "confidence": confidence,
                "meaning": meaning,
                "visual": visual,
                "visual_category": visual_category,
                "position": position,
                "size": size,
                "scene_elements": scene_elements
            }

    return {"error": "No character recognized"}


def extract_drawing_bbox(image_path):
    image = Image.open(image_path).convert("L")
    pixels = image.load()

    width, height = image.size
    xs = []
    ys = []

    for y in range(height):
        for x in range(width):
            if pixels[x, y] < 245:
                xs.append(x)
                ys.append(y)

    if not xs or not ys:
        return None

    return {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "center_x": sum(xs) / len(xs),
        "center_y": sum(ys) / len(ys)
    }


def classify_position(bbox, canvas_width, canvas_height):
    if bbox is None:
        return "center"

    x = bbox["center_x"]
    y = bbox["center_y"]

    if y < canvas_height / 3:
        vertical = "top"
    elif y > canvas_height * 2 / 3:
        vertical = "bottom"
    else:
        vertical = "center"

    if x < canvas_width / 3:
        horizontal = "left"
    elif x > canvas_width * 2 / 3:
        horizontal = "right"
    else:
        horizontal = "center"

    if vertical == "center" and horizontal == "center":
        return "center"

    return f"{vertical} {horizontal}"


def classify_size(bbox, canvas_width, canvas_height):
    if bbox is None:
        return "medium"

    drawing_area = bbox["width"] * bbox["height"]
    canvas_area = canvas_width * canvas_height
    ratio = drawing_area / canvas_area

    if ratio < 0.08:
        return "small"
    elif ratio < 0.22:
        return "medium"
    else:
        return "large"


def build_scene_prompt(elements):
    descriptions = []

    for el in elements:
        descriptions.append(
            f"- The character '{el['character']}' means '{el['meaning']}'. "
            f"Transform only this character into: {el['visual']}. "
            f"Place it near the {el['position']} of the image. "
            f"Make it {el['size']} in visual importance."
        )

    joined = "\n".join(descriptions)

    return f"""
Create a minimal traditional Chinese ink-wash artwork on vertical rice paper.

Important:
- Only include visual elements that come from the user's drawn characters.
- Do not invent extra mountains, trees, boats, people, rivers, forests, buildings, animals, or landscapes unless those characters were drawn.
- If only one character was drawn, create a simple focused composition featuring only that one subject.
- Do not draw readable Chinese text.
- Do not redraw the Chinese character as a symbol.

Characters drawn by the user:
{joined}

Style:
- monochrome black ink and soft gray wash
- textured rice paper
- elegant negative space
- soft brush texture
- poetic and minimal
- no labels, subtitles, captions, or readable text
"""


def generate_image(prompt):
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1536"
    )

    image_base64 = response.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    output_path = "static/generated_art.png"

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return output_path


if __name__ == "__main__":
    app.run(debug=True)