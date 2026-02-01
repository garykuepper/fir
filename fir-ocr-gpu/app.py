from flask import Flask, request, jsonify
from paddleocr import PaddleOCR
import tempfile
import os
import threading

app = Flask(__name__)

_ocr = None
_ocr_lock = threading.Lock()


def get_ocr():
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:
                # Lazy init: downloads happen on first request, not container startup
                print("Initializing PaddleOCR (may download models)...")
                _ocr = PaddleOCR(lang="en", show_log=False)
    return _ocr


@app.get("/health")
def health():
    return jsonify({"status": "ok", "ready": _ocr is not None})


@app.route("/ocr", methods=["POST"])
def run_ocr():
    if "image" not in request.files:
        return jsonify({"error": "no image"}), 400

    f = request.files["image"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        f.save(tmp.name)
        image_path = tmp.name

    try:
        ocr = get_ocr()

        # cls=False for stability/speed. Re-enable later if you want.
        result = ocr.ocr(image_path, cls=False)

        lines = []
        for page in result:
            for box, (text, score) in page:
                lines.append(text)

        return jsonify({"text": lines})

    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass


if __name__ == "__main__":
    # Flask starts immediately now
    app.run(host="0.0.0.0", port=9000)
