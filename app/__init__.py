"""
Secure File Chatbot Application

A HIPAA-compliant file processing and chatbot system with AWS integration.
Supports multi-platform clients with secure data handling.
"""

__version__ = "1.0.0"
__author__ = "Your Company"
__email__ = "contact@yourcompany.com"

import argparse
import hashlib
import http.server
import json
import os
import shutil
import sys
import tempfile
from functools import partial
from pathlib import Path
from typing import Dict, Any

# Simple in-memory project store (kept for process life)
# Structure:
# PROJECTS = {
#   project_name: {
#       "files": {
#           filename: {
#               "path": "/tmp/xxx/filename",
#               "embeddings": [...],
#               "summary_admin": "...",
#               "summary_client": "...",
#               "client_pushed": False
#           }
#       }
#   }
# }
PROJECTS: Dict[str, Dict[str, Any]] = {}
BASE_DATA_DIR = Path(tempfile.gettempdir()) / "file_processor_ai_data"
STATIC_DIR = Path(__file__).parent / "static"

def ensure_dirs():
    BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

def compute_embeddings(file_bytes: bytes):
    # Simple deterministic "embedding" simulation: SHA256 hexdigest -> list of small ints
    h = hashlib.sha256(file_bytes).hexdigest()
    # chunk hex pairs into ints
    vec = [int(h[i:i+2], 16) for i in range(0, len(h), 2)]
    return vec

def assemble_chunks_and_store(project: str, filename: str, chunks_dir: Path, total_chunks: int):
    target_dir = BASE_DATA_DIR / project
    target_dir.mkdir(parents=True, exist_ok=True)
    assembled_path = target_dir / filename
    with assembled_path.open("wb") as w:
        for i in range(total_chunks):
            chunk_file = chunks_dir / f"{filename}.chunk{i}"
            if not chunk_file.exists():
                raise FileNotFoundError(f"missing chunk {i} for {filename}")
            w.write(chunk_file.read_bytes())
    file_bytes = assembled_path.read_bytes()
    embeddings = compute_embeddings(file_bytes)
    # Clean up chunk files
    shutil.rmtree(chunks_dir, ignore_errors=True)
    # Store metadata
    PROJECTS.setdefault(project, {}).setdefault("files", {})[filename] = {
        "path": str(assembled_path),
        "embeddings": embeddings,
        "summary_admin": None,
        "summary_client": None,
        "client_pushed": False,
    }
    return assembled_path, embeddings

def generate_summaries_for_project(project: str):
    proj = PROJECTS.get(project)
    if not proj:
        raise KeyError(f"project {project} not found")
    for fname, meta in proj.get("files", {}).items():
        path = Path(meta["path"])
        text = path.read_text(errors="ignore") if path.exists() else ""
        # Rudimentary summaries
        meta["summary_admin"] = text[:1000].strip() or f"(empty {fname})"
        # client-facing summary is shorter (but not "pushed" until admin does)
        meta["summary_client"] = (text[:300].strip() or f"(short empty {fname})")
    return True

def push_client_summary(project: str):
    proj = PROJECTS.get(project)
    if not proj:
        raise KeyError(f"project {project} not found")
    # mark all files as pushed
    for meta in proj.get("files", {}).values():
        meta["client_pushed"] = True
    return True

def run_server(host: str = "0.0.0.0", port: int = 8000):
    ensure_dirs()
    # create top-level upload chunks dir
    uploads_root = BASE_DATA_DIR / "chunks"
    uploads_root.mkdir(parents=True, exist_ok=True)

    class Handler(http.server.SimpleHTTPRequestHandler):
        # serve static files from STATIC_DIR
        def __init__(self, *args, directory=None, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

        def do_POST(self):
            if self.path != "/upload":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
                return
            # parse multipart form
            content_length = int(self.headers.get("Content-Length", 0))
            content_type = self.headers.get("Content-Type", "")
            # use cgi.FieldStorage for robust parsing
            import cgi
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
            }, keep_blank_values=True)
            project = form.getvalue("project") or "default"
            filename = form.getvalue("filename")
            chunk_index = int(form.getvalue("chunk_index") or 0)
            total_chunks = int(form.getvalue("total_chunks") or 1)
            fileitem = form["data"] if "data" in form else None
            if not filename or fileitem is None:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing filename or data")
                return
            # store chunk
            chunks_dir = uploads_root / project / filename
            chunks_dir.mkdir(parents=True, exist_ok=True)
            chunk_path = chunks_dir / f"{filename}.chunk{chunk_index}"
            # fileitem.file is a file-like
            with chunk_path.open("wb") as f:
                shutil.copyfileobj(fileitem.file, f)
            # if last chunk, assemble
            assembled = None
            embeddings = None
            try:
                if chunk_index + 1 >= total_chunks:
                    assembled, embeddings = assemble_chunks_and_store(project, filename, chunks_dir, total_chunks)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
                return
            # success
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "ok",
                "project": project,
                "filename": filename,
                "assembled": str(assembled) if assembled else None,
                "embeddings_len": len(embeddings) if embeddings else None,
            }
            self.wfile.write(json.dumps(resp).encode())

    server = http.server.ThreadingHTTPServer((host, port), partial(Handler))
    addr = f"http://{host}:{port}"
    print(f"Serving static UI + upload endpoint at {addr} (open in browser)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down server")
        server.shutdown()

def main(argv=None):
    """
    CLI entrypoint.
    Commands:
      runserver         start HTTP server that hosts a small UI and an /upload endpoint
      process-file      process a local file into project (simulate chunking + embeddings)
      generate-summary  create admin/client summaries for a project
      push-summary      mark client summaries as pushed (admin action)
    """
    ensure_dirs()
    parser = argparse.ArgumentParser(prog="app", description="AI file processor")
    sub = parser.add_subparsers(dest="cmd")

    p_server = sub.add_parser("runserver", help="Start the HTTP upload + UI server")
    p_server.add_argument("--host", default="0.0.0.0")
    p_server.add_argument("--port", type=int, default=8000)

    p_proc = sub.add_parser("process-file", help="Process a local file into a project (simulate chunk upload)")
    p_proc.add_argument("--file", "-f", required=True)
    p_proc.add_argument("--project", "-p", default="default")
    p_proc.add_argument("--chunk-size", type=int, default=1024*256, help="chunk size in bytes")

    p_summary = sub.add_parser("generate-summary", help="Generate admin and client summaries for a project")
    p_summary.add_argument("--project", "-p", default="default")

    p_push = sub.add_parser("push-summary", help="Push client summaries (admin action)")
    p_push.add_argument("--project", "-p", default="default")

    args = parser.parse_args(argv)
    if args.cmd == "runserver":
        run_server(args.host, args.port)
        return 0
    if args.cmd == "process-file":
        fpath = Path(args.file)
        if not fpath.exists():
            print("file not found", file=sys.stderr)
            return 2
        # simulate chunked upload locally
        chunks_dir = BASE_DATA_DIR / "chunks" / args.project / fpath.name
        if chunks_dir.exists():
            shutil.rmtree(chunks_dir)
        chunks_dir.mkdir(parents=True, exist_ok=True)
        total = 0
        idx = 0
        with fpath.open("rb") as r:
            while True:
                chunk = r.read(args.chunk_size)
                if not chunk:
                    break
                (chunks_dir / f"{fpath.name}.chunk{idx}").write_bytes(chunk)
                idx += 1
            total = idx
        assembled, embeddings = assemble_chunks_and_store(args.project, fpath.name, chunks_dir, total)
        print(f"Processed {fpath} -> {assembled}, embeddings_len={len(embeddings)}")
        return 0
    if args.cmd == "generate-summary":
        try:
            generate_summaries_for_project(args.project)
            print("Generated summaries for project", args.project)
            return 0
        except KeyError as e:
            print(e, file=sys.stderr)
            return 2
    if args.cmd == "push-summary":
        try:
            push_client_summary(args.project)
            print("Pushed client summaries for project", args.project)
            return 0
        except KeyError as e:
            print(e, file=sys.stderr)
            return 2
    # default: show help
    parser.print_help()
    return 0
