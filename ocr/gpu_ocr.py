import requests

class GPUOCR:
    def run(self, image_path: str, label: str, stockpile: str, version: str):
        with open(image_path, "rb") as f:
            r = requests.post(
                "http://fir-ocr-gpu:9000/ocr",
                files={"image": f},
                timeout=30,
            )

        r.raise_for_status()
        return {"backend": "gpu"}
