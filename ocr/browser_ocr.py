import subprocess

class BrowserOCR:
    def run(self, image_path: str, label: str, stockpile: str, version: str):
        cmd = [
            "node",
            "headless_process.js",
            image_path,
            label,
            stockpile,
            version,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return {"backend": "browser"}
