from flask import Flask, request, jsonify
from paddleocr import PaddleOCR
import tempfile
import os

app = Flask(__name__)

# Load once → stays in GPU memory
ocr = PaddleOCR(lang='en')

@app.route("/ocr", methods=["POST"])
def run_ocr():
    if "image" not in request.files:
        return jsonify({"error": "no image"}), 400

    f = request.files["image"]

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        f.save(tmp.name)
        image_path = tmp.name

    try:
        result = ocr.ocr(image_path, cls=True)

        # Normalize output to FIR-compatible text blobs
        lines = []
        for page in result:
            for box, (text, score) in page:
                lines.append(text)

        return jsonify({
            "text": lines
        })

    finally:
        os.unlink(image_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
