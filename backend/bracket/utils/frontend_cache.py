"""
Cache headers for the frontend files served by the backend (`SERVE_FRONTEND`).

Vite puts a content hash in the names of the files in `assets/`, so those never change and can be
cached for a year. Everything else (index.html, translations, icons) keeps its name across
deploys, so browsers must check for a new version every time; unchanged files then only cost a
short "304 Not Modified" thanks to the ETag. Without these headers browsers guess a lifetime from
the file's age and can keep showing an old version for days after a deploy.
"""

from pathlib import PurePosixPath

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


def cache_control_for(full_path: str) -> str:
    parts = PurePosixPath(full_path).parts
    return IMMUTABLE if len(parts) > 1 and parts[0] == "assets" else REVALIDATE
