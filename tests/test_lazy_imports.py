"""
Tests that heavy dependencies (chromadb, google.genai) are NOT imported at
module level in the orchestration layer, ensuring fast initial page load.
"""

import ast
import os

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

HEAVY_IMPORT_PREFIXES = (
    "agents.file_based",
    "agents.rlm",
    "agents.vector",
    "engines.checkpoint_engine",
    "engines.workflow_intelligence",
    "services.calendly",
)


def _get_top_level_import_modules(filepath: str) -> set[str]:
    """Parse a Python file and return the set of module names imported at module level."""
    with open(filepath, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    modules = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def test_agent_dispatch_defers_agent_imports():
    """agent_dispatch.py must not import agent classes or heavy engines at module level."""
    filepath = os.path.join(REPO_ROOT, "components", "agent_dispatch.py")
    top_level = _get_top_level_import_modules(filepath)

    for prefix in HEAVY_IMPORT_PREFIXES:
        matches = [m for m in top_level if m.startswith(prefix)]
        assert not matches, (
            f"Found top-level import(s) starting with '{prefix}': {matches}. "
            f"These should be deferred to inside the functions that use them."
        )


def test_agent_dispatch_no_top_level_chromadb():
    """chromadb must not appear as a top-level import in agent_dispatch.py."""
    filepath = os.path.join(REPO_ROOT, "components", "agent_dispatch.py")
    top_level = _get_top_level_import_modules(filepath)
    assert "chromadb" not in top_level, "chromadb should not be imported at module level"


def test_agent_dispatch_no_top_level_genai():
    """google.genai must not appear as a top-level import in agent_dispatch.py."""
    filepath = os.path.join(REPO_ROOT, "components", "agent_dispatch.py")
    top_level = _get_top_level_import_modules(filepath)
    genai_imports = [m for m in top_level if m.startswith("google")]
    assert not genai_imports, (
        f"Found top-level google import(s): {genai_imports}. "
        f"google.genai should only be imported inside functions."
    )


def test_app_does_not_top_level_import_chromadb():
    """app.py must not directly import chromadb at module level."""
    filepath = os.path.join(REPO_ROOT, "app.py")
    top_level = _get_top_level_import_modules(filepath)
    assert "chromadb" not in top_level


def _get_top_level_imported_names(filepath: str) -> set[str]:
    """Parse a Python file and return the set of names imported at module level."""
    with open(filepath, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def test_app_does_not_top_level_import_generate_voice_answer():
    """generate_voice_answer must be lazy-imported inside the voice mode block, not at module level.

    A top-level import crashes the entire app on Streamlit Cloud if the
    underlying module fails to load (observed with Python 3.13 bytecode caching).
    """
    filepath = os.path.join(REPO_ROOT, "app.py")
    names = _get_top_level_imported_names(filepath)
    assert "generate_voice_answer" not in names, (
        "generate_voice_answer should NOT be a top-level import in app.py — "
        "import it lazily inside the voice mode block to isolate failures."
    )
