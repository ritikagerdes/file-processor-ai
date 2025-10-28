# file-processor-ai

AI File Processor — chunked uploads, simple embeddings simulation, and summary generation.

Overview
- Accepts file uploads in chunks and marks stored files with embeddings (simulated).
- Files are stored per-project and used to create admin and client-facing summaries.
- Admin can push client summaries to mark them as delivered.
- Minimal HTTP UI is included for browser uploads (no external deps).

CLI / Module usage
You can run the package as a module:

- Start the server with the static UI and upload endpoint:
  python -m app runserver --host 0.0.0.0 --port 8000
  Then open in the devcontainer host browser:
  "$BROWSER" http://localhost:8000

- Process a local file (simulate chunking + embedding) without the HTTP server:
  python -m app process-file --file path/to/file.txt --project myproject --chunk-size 262144

- Generate admin and client summaries for a project:
  python -m app generate-summary --project myproject

- Push (mark) client summaries as delivered (admin action):
  python -m app push-summary --project myproject

What the server provides
- Static UI at / (serves app/static/index.html and upload.js)
- Upload endpoint: POST /upload
  Form fields:
    - project: project name
    - filename: original file name
    - chunk_index: zero-based chunk index (integer)
    - total_chunks: total number of chunks (integer)
    - data: binary file chunk (multipart form field)

Server behavior
- Chunks are stored under a temp data dir (by default under the system temp directory).
- When the final chunk is received, server assembles the file, computes a deterministic embeddings vector (SHA256-based), and stores metadata in-memory for the life of the process.
- Summaries are simple substring summaries (for demo) created by the generate-summary command.

Files added
- app/__init__.py — main CLI implementation, server and processing logic
- app/__main__.py — module entrypoint so `python -m app` works
- app/static/index.html — simple upload UI
- app/static/upload.js — chunked upload client

Notes & next steps
- The current embeddings implementation is a placeholder; replace with a real vector embedding service (OpenAI, Cohere, etc.) for production use.
- Storage is temporary and in-memory; for persistence use external storage (S3, DB) and persistent indexes (FAISS, Milvus).
- Authentication, quotas, and security are not implemented — add before deploying externally.

Running tests
- A minimal import test can be added to tests/ to let pytest collect something; otherwise pytest may report "collected 0 items".
- Example:
  tests/test_import.py:
  ```python
  import importlib
  def test_import_app():
      importlib.import_module("app")
  ```

Development notes (devcontainer)
- The devcontainer is Ubuntu 24.04.2 LTS.
- Use "$BROWSER" <url> to open links in your host's default browser from inside the container.
- No third-party web framework is required for the demo server (uses Python stdlib).

License
- (Add license here)