import os
import subprocess
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Directories
UPLOAD_FOLDER = Path("/tmp/fir_uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path("/app/sample_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Start the FIR Website server in the background (serves /app contents on 8005)
subprocess.Popen(
    ["python3", "-m", "http.server", "8005"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)




@app.route("/process", methods=["POST"])
def process_image():
    label = request.form.get("label", "Default_Label")
    stockpile = request.form.get("stockpile", "Public")
    version = request.form.get("version", "airborne-63")

    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]

    unique_id = str(uuid.uuid4())[:8]
    temp_image_path = UPLOAD_FOLDER / f"{unique_id}_{secure_filename(file.filename)}"
    file.save(temp_image_path)

    try:
        node_cmd = ["node", "headless_process.js", str(temp_image_path), label, stockpile, version]


        # Run the Node automation
        result = subprocess.run(
            node_cmd,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("FIR_NODE_TIMEOUT_SEC", "180")),
        )

        if result.returncode != 0:
            return jsonify({
                "error": "headless_process failed",
                "stdout_tail": (result.stdout or "")[-2000:],
                "stderr_tail": (result.stderr or "")[-2000:],
            }), 500

        safe_name = "".join([c if c.isalnum() else "_" for c in label]).lower()
        tsv_path = OUTPUT_DIR / f"{safe_name}_report.tsv"

        if not tsv_path.exists():
            return jsonify({
                "error": "TSV not found after processing",
                "expected_path": str(tsv_path),
                "gpu_mode": os.environ.get("FIR_GPU_MODE"),
                "stdout_tail": (result.stdout or "")[-2000:],
                "stderr_tail": (result.stderr or "")[-2000:],
            }), 500

        return send_file(tsv_path, as_attachment=True)

    except subprocess.TimeoutExpired:
        return jsonify({"error": "headless_process timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if temp_image_path.exists():
                temp_image_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    # Keep as 0.0.0.0 inside container; control exposure via docker-compose port binding.
    app.run(host="0.0.0.0", port=5000)
