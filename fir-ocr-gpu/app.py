from flask import Flask, request, jsonify
from paddleocr import PaddleOCR
import paddle
import tempfile
import os
import threading

app = Flask(__name__)

_ocr = None
_lock = threading.Lock()

def get_ocr():
    global _ocr
    if _ocr is None:
        with _lock:
            if _ocr is None:
                print("Initializing PaddleOCR (may download models)...")
                print("compiled_with_cuda:", paddle.device.is_compiled_with_cuda())
                print("device:", paddle.device.get_device())
                _ocr = PaddleOCR(lang="en", show_log=False)  # no paddlex pipeline
    return _ocr

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/ready")
def ready():
    return jsonify({"ready": _ocr is not None})

@app.post("/ocr")
def ocr_endpoint():
    if "image" not in request.files:
        return jsonify({"error": "no image provided"}), 400

    img = request.files["image"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
        img.save(f.name)
        path = f.name

    try:
        ocr = get_ocr()
        result = ocr.ocr(path, cls=False)

        # Flatten to lines (simple return format)
        lines = []
        for page in result:
            for _, (text, _score) in page:
                if text:
                    lines.append(text)

        return jsonify({"lines": lines})

    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
