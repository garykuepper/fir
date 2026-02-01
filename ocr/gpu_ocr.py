import time
import requests

class GPUOCR:
    def run(self, image_path: str, label: str, stockpile: str, version: str):
        url = "http://fir-ocr-gpu:9000/ocr"
        last_err = None

        for _ in range(15):  # ~15s total
            try:
                with open(image_path, "rb") as f:
                    r = requests.post(
                        url,
                        files={"image": f},
                        timeout=60,
                    )
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                time.sleep(1)

        raise RuntimeError(f"GPU OCR not ready after retries: {last_err}")
