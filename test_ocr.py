from paddleocr import PaddleOCR
from app import CHARACTER_MEANINGS

ocr = PaddleOCR(
    lang="ch",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False
)

result = ocr.predict("test.png")

for page in result:
    texts = page.get("rec_texts", [])
    scores = page.get("rec_scores", [])

    for text, score in zip(texts, scores):
        char_info = CHARACTER_MEANINGS.get(text)

        if char_info:
            meaning = char_info["meaning"]
            visual = char_info["prompt_hint"] or meaning
        else:
            meaning = "unknown meaning"
            visual = f"abstract ink-wash form inspired by {text}"

        prompt = f"Create an ink-style artwork representing {visual}, inspired by the handwritten Chinese character {text}."

        print("Character:", text)
        print("Confidence:", score)
        print("Meaning:", meaning)
        print("Image prompt:", prompt)