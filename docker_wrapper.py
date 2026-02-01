import os
import subprocess
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# 🔹 NEW: import the OCR adapter selector
from ocr import get_ocr_backend

app = Flask(__name__)

# -----------------------------
# Paths & directories
# -----------------------------

UPLOAD_DIR = Path("/tmp/fir_uploads")
OUTPUT_DIR = Path("/app/sample_output")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Start FIR frontend (unchanged)
# -----------------------------
# This serves the FIR site on http://localhost:8005
# Headless Chromium will connect to this.
subprocess.Popen(
    ["python3", "-m", "http.server", "8005"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)


# -----------------------------
# Flask endpoint
# -----------------------------

@app.route("/process", methods=["POST"])
def process_image():
    """
    This endpoint:
    1. Receives an image
    2. Runs OCR via the selected backend (browser or GPU)
    3. Returns the generated TSV
    """

    label = request.form.get("label", "Default_Label")
    stockpile = request.form.get("stockpile", "Public")
    version = request.form.get("version", "airborne-63")

    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files["image"]

    # Unique filename per request
    uid = str(uuid.uuid4())[:8]
    image_path = UPLOAD_DIR / f"{uid}_{secure_filename(image_file.filename)}"
    image_file.save(image_path)

    try:
        # 🔹 THIS IS THE KEY LINE
        # Select OCR backend based on FIR_OCR_BACKEND env var
        ocr = get_ocr_backend()

        # Run OCR (implementation depends on backend)
        # - BrowserOCR → runs headless_process.js
        # - GPUOCR     → calls PaddleOCR service
        ocr.run(
            image_path=str(image_path),
            label=label,
            stockpile=stockpile,
            version=version,
        )

        # At this point, FIR has produced the TSV
        safe_name = "".join(c if c.isalnum() else "_" for c in label).lower()
        tsv_path = OUTPUT_DIR / f"{safe_name}_report.tsv"

        if not tsv_path.exists():
            return jsonify({
                "error": "OCR completed but TSV was not generated",
                "backend": ocr.__class__.__name__,
            }), 500

        return send_file(tsv_path, as_attachment=True)

    except Exception as e:
        return jsonify({
            "error": str(e),
            "backend": ocr.__class__.__name__,
        }), 500

    finally:
        try:
            image_path.unlink()
        except Exception:
            pass


# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
