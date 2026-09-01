#!/usr/bin/env python3
"""Tiny static server that's safe even when launcher's cwd is sandboxed."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# теперь импортируем (http.server резолвит cwd при импорте)
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else "8800"))
HTTPServer(("127.0.0.1", PORT), SimpleHTTPRequestHandler).serve_forever()
