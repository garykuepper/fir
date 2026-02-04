import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import sys

# Add the project root to sys.path to import docker_wrapper
sys.path.append(str(Path(__file__).parent.parent))

from docker_wrapper import app

class TestDockerWrapper(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('subprocess.run')
    @patch('docker_wrapper.OUTPUT_DIR')
    def test_process_image_missing_tsv(self, mock_output_dir, mock_run):
        # Setup mock for subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Processed successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Setup mock for OUTPUT_DIR and tsv_path.exists()
        mock_tsv_path = MagicMock()
        mock_tsv_path.exists.return_value = False
        mock_output_dir.__truediv__.return_value = mock_tsv_path

        # Perform request
        data = {
            'label': 'Test_Label',
            'stockpile': 'Public',
            'version': 'airborne-63'
        }
        # Create a dummy image file
        import io
        image = (io.BytesIO(b"dummy image data"), 'test.png')
        
        with patch('docker_wrapper.UPLOAD_FOLDER', Path('/tmp/fir_uploads_test')):
            # Ensure the test upload folder exists
            Path('/tmp/fir_uploads_test').mkdir(parents=True, exist_ok=True)
            
            response = self.app.post('/process', data={**data, 'image': image})
            
            # Check response - should be 500 but WITHOUT crashing on undefined variables
            self.assertEqual(response.status_code, 500)
            json_data = response.get_json()
            self.assertEqual(json_data['error'], "TSV not found after processing")
            self.assertIn('gpu_mode', json_data)
            # Verify no free_vram_mb in the response (as it was removed)
            self.assertNotIn('free_vram_mb', json_data)

if __name__ == '__main__':
    unittest.main()
