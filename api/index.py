"""Vercel Serverless entrypoint adapter for Intelligent Resume Analyzer.

Provides a lightweight, zero-dependency HTTP entrypoint satisfying Vercel's
serverless function detection without modifying any core application files.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

HTML_RESPONSE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intelligent Resume Analyzer — Deployment Status</title>
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #34d399;
            --accent-amber: #fbbf24;
            --border-color: #334155;
        }
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            max-width: 720px;
            margin: 2rem;
            padding: 2.5rem;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            font-size: 0.85rem;
            font-weight: 600;
            border-radius: 9999px;
            background-color: rgba(56, 189, 248, 0.15);
            color: var(--accent-blue);
            margin-bottom: 1rem;
        }
        h1 {
            font-size: 1.85rem;
            margin-top: 0;
            margin-bottom: 0.5rem;
            color: var(--text-primary);
        }
        p {
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 1.25rem;
        }
        .card {
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
        }
        .card-title {
            font-weight: 600;
            color: var(--accent-amber);
            margin-top: 0;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        code {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            background-color: rgba(255, 255, 255, 0.08);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-size: 0.9em;
            color: var(--accent-blue);
        }
        pre {
            background-color: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 1rem;
            overflow-x: auto;
            color: #e2e8f0;
            font-size: 0.88rem;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent-green);
            font-weight: 500;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-green);
        }
        .footer {
            margin-top: 1.5rem;
            padding-top: 1.25rem;
            border-top: 1px solid var(--border-color);
            font-size: 0.85rem;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">Vercel Serverless Adapter</div>
        <h1>Intelligent Resume Analyzer</h1>
        <p>AI-Powered Smart Hiring Assistant with Deterministic Core</p>

        <div class="card">
            <div class="card-title">⚠️ Deployment Architecture Notice</div>
            <p>
                The serverless endpoint at this URL is active (<span class="status-pill"><span class="status-dot"></span>HTTP 200 OK</span>).
            </p>
            <p>
                This application's interactive graphical interface is engineered with <strong>Streamlit</strong> (<code>src/resume_analyzer/ui/streamlit_app.py</code>).
                Streamlit relies on long-lived, persistent bidirectional WebSocket connections and in-memory server session state.
                Because Vercel executes serverless functions on an ephemeral, request-driven lifecycle without persistent WebSockets, running the full interactive Streamlit UI on serverless lambdas is architecturally unsupported.
            </p>
        </div>

        <h3>Recommended Hosting for Interactive UI</h3>
        <p>
            To run the interactive Streamlit UI in production, use a containerized or long-running Python host:
        </p>
        <ul>
            <li><strong>Streamlit Community Cloud:</strong> Direct 1-click native deployment from GitHub.</li>
            <li><strong>Docker / Container Platforms:</strong> Render, Railway, Fly.io, or AWS ECS/Fargate.</li>
        </ul>

        <h3>Local Execution</h3>
        <pre># Launch Streamlit web app locally
streamlit run src/resume_analyzer/ui/streamlit_app.py

# Or use the CLI
resume-analyzer analyze --resume &lt;path&gt; --job &lt;path&gt;</pre>

        <div class="footer">
            <span>Version: <strong>1.0.0</strong></span>
            <span>API Health: <a href="/health" style="color: var(--accent-blue);">/health</a></span>
        </div>
    </div>
</body>
</html>
"""


class handler(BaseHTTPRequestHandler):  # noqa: N801
    """Vercel serverless HTTP request handler."""

    def do_GET(self) -> None:
        """Handle HTTP GET requests."""
        if self.path in ("/health", "/api/health"):
            payload = {
                "status": "healthy",
                "service": "Intelligent Resume Analyzer",
                "version": "1.0.0",
                "architecture": "Deterministic Core + Streamlit UI + CLI",
                "deployment": "Vercel Serverless Function",
            }
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = HTML_RESPONSE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def app(environ: dict[str, Any], start_response: Any) -> list[bytes]:
    """WSGI callable compatibility fallback."""
    path = environ.get("PATH_INFO", "/")
    if path in ("/health", "/api/health"):
        payload = {
            "status": "healthy",
            "service": "Intelligent Resume Analyzer",
            "version": "1.0.0",
            "architecture": "Deterministic Core + Streamlit UI + CLI",
            "deployment": "Vercel Serverless Function (WSGI)",
        }
        body = json.dumps(payload, indent=2).encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    body = HTML_RESPONSE.encode("utf-8")
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]
