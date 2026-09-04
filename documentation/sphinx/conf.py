"""Sphinx configuration for the Big_Agent documentation.

The version is read from ``app/version.py`` so the documentation cannot drift
from the application it describes. Nothing else in ``app`` is imported: the
build must stay offline and model-free, exactly like the test suite.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _app_version() -> str:
    version_file = REPO_ROOT / "app" / "version.py"
    try:
        match = re.search(
            r'APP_VERSION\s*=\s*"([^"]+)"', version_file.read_text(encoding="utf-8")
        )
    except OSError:
        return "0.0.0"
    return match.group(1) if match else "0.0.0"


project = "Big_Agent"
author = "Big_Agent project"
copyright = "Big_Agent project"
release = _app_version()
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.todo",
    "sphinx.ext.githubpages",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
language = "en"

# Every literal block in this documentation is a shell/PowerShell transcript,
# a JSON payload or a config snippet; PowerShell is the project's own shell.
highlight_language = "powershell"
pygments_style = "friendly"

todo_include_todos = False
nitpicky = False

html_theme = "alabaster"
html_static_path = ["_static"]
html_title = f"Big_Agent {release}"
html_short_title = "Big_Agent"
html_theme_options = {
    "description": "Local-first report assistant for vehicle test and analysis documents",
    "fixed_sidebar": True,
    "page_width": "62em",
    "sidebar_width": "16em",
}

# `make latexpdf` in this directory produces a Sphinx-rendered PDF. It is a
# different artefact from documentation/latex/, which is a hand-authored LaTeX
# report of the same material -- see documentation/README.md.
latex_engine = "pdflatex"
latex_documents = [
    (
        "index",
        "big_agent_sphinx.tex",
        r"Big\_Agent Documentation",
        author,
        "manual",
    ),
]
latex_elements = {
    "papersize": "a4paper",
    "pointsize": "11pt",
    "preamble": r"""
\usepackage[T1]{fontenc}
""",
}

man_pages = [("index", "big_agent", "Big_Agent Documentation", [author], 1)]
