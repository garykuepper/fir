# Foxhole Inventory Report (fir)

This is a fork of the original [Foxhole Inventory Report (fir)](https://github.com/GICodeWarrior/fir) by **GICodeWarrior**.

### Recent Changes:
*   **Headless Processing**: Added a CLI-based workflow using Playwright to process screenshots without a manual browser interface.
*   **Dockerized API**: New `Dockerfile.headless` and `docker_wrapper.py` (Flask) to provide a REST API for remote image processing.
*   **Automation Scripts**: Added `headless_process.js` for automated browser interaction and `get_stockpile_dataframe.py` for easy Python integration.

---

This tool prepares [Foxhole](https://www.foxholegame.com/about-foxhole) stockpile screenshots into a visual report and machine-readable numbers.

1. Screenshot multiple inventories from the map view in-game.  Do this in the order you'd like them to appear in the report.
2. Select your screenshots in the tool.
3. Wait for processing.
4. Edit the titles for each inventory in the report by clicking on them.
5. Download the result as a PNG, text report, TSV, or append to a google spreadsheet.

## Status

Under development. However, it is already being used "in production" within regiment(s) for evaluation. 

## Deployment
### Local
To deploy a non-containerized server run:
```
cd fir
python3 -m http.server
```
### Docker
#### Building the Docker Container
To build the docker container run:
```
docker build -f Dockerfile.server --tag 'fir_server' .
```

##### Overriding the listen port
If you'd like to override the override the port the server listens on run:
```
docker build -f Dockerfile.server --build-arg PORT=<override port> --tag 'fir_server' .
```
#### Running the Docker Container
To run the FIR server in the built docker continer:
```
docker run -p <host port>:<fir port> fir_server
```
The `-p` argument maps the host port to the fir server port inside the container. FIR defaults to listening on port
8000. To override the port please see [this section](#overriding-the-listen-port).

### Headless Mode (CLI & API)

For automated processing, CI/CD pipelines, or remote integrations, you can use the headless version.

#### 1. REST API (Docker)
Build and run the headless container to start a Flask API on port 5000:
```bash
docker build -f Dockerfile.headless --tag 'fir_headless' .
docker run -p 5000:5000 fir_headless
```

You can then send images to the `/process` endpoint. See `get_stockpile_dataframe.py` for a Python example using `requests`.

#### 2. Manual CLI Execution
If you want to run a single report via the command line:
```bash
# Usage: node headless_process.js <imagePath> <label> [stockpileName] [version]
node headless_process.js ./sample_pictures/tine.png "Tine Report" "Public" "airborne-63"
```
*Note: This requires Node.js and Playwright dependencies installed locally.*

## Development
