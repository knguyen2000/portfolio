"""
Base utilities for the RLM agent.

This module provides:
  * build_corpus(docs)       -- bundle a dict of {filename: content} into a
                                single pseudo-XML string for the `context`
                                variable.
  * execute_sandbox_code()   -- run Python code inside a restricted namespace
                                and return a structured REPLResult dict.

The shape of the result mirrors the reference RLM's REPLResult (stdout,
stderr, execution_time) so the agent loop can truncate long outputs and
surface stderr cleanly.
"""

import io
import contextlib
import time


# ---------------------------------------------------------------------------
# Safe builtins — a subset of Python's __builtins__ that blocks obviously
# dangerous operations (eval, exec, compile, input) while still letting the
# LLM write realistic data-processing code (map/filter/sorted/tuple, regex
# imports, etc.). Mirrors rlm/environments/local_repl.py:_SAFE_BUILTINS.
# ---------------------------------------------------------------------------
_SAFE_BUILTINS = {
    # Core types and functions
    "print": print,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "bool": bool,
    "type": type,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "any": any,
    "all": all,
    "pow": pow,
    "divmod": divmod,
    "chr": chr,
    "ord": ord,
    "hex": hex,
    "bin": bin,
    "oct": oct,
    "repr": repr,
    "ascii": ascii,
    "format": format,
    "hash": hash,
    "id": id,
    "iter": iter,
    "next": next,
    "slice": slice,
    "callable": callable,
    "hasattr": hasattr,
    "getattr": getattr,
    "setattr": setattr,
    "delattr": delattr,
    "dir": dir,
    "vars": vars,
    "bytes": bytes,
    "bytearray": bytearray,
    "memoryview": memoryview,
    "complex": complex,
    "object": object,
    "super": super,
    "property": property,
    "staticmethod": staticmethod,
    "classmethod": classmethod,
    # Needed so that `import re`, `import json` etc. work inside the sandbox.
    "__import__": __import__,
    # Exceptions
    "Exception": Exception,
    "BaseException": BaseException,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "NameError": NameError,
    "ImportError": ImportError,
    "StopIteration": StopIteration,
    "AssertionError": AssertionError,
    "NotImplementedError": NotImplementedError,
    "ArithmeticError": ArithmeticError,
    "LookupError": LookupError,
    "Warning": Warning,
    # Deliberately blocked
    "input": None,
    "eval": None,
    "exec": None,
    "compile": None,
    "globals": None,
    "locals": None,
    "open": None,     # No filesystem access from LLM code
}


def build_corpus(docs):
    """
    Flatten a {filename: content} dict into a single pseudo-XML string.

    The system prompt teaches the model to search this string with regex
    like  re.findall(r"<file name='(.*?)'>", context).
    """
    if not docs:
        return ""
    if not isinstance(docs, dict):
        return str(docs)

    parts = []
    for fname, content in docs.items():
        parts.append(f"<file name='{fname}'>\n{content}\n</file>")
    return "\n".join(parts)


def execute_sandbox_code(code, repl_globals):
    """
    Execute `code` in the persistent `repl_globals` namespace.

    Returns a dict shaped like the reference REPLResult:
        {
            "stdout": str,
            "stderr": str,
            "execution_time": float,   # seconds
        }

    Persistence: variables the LLM defines in one turn (e.g. `buffers = []`)
    remain visible in subsequent turns because `repl_globals` is the same
    object across calls. This matches gold-truth's LocalREPL persistence.
    """
    # Lazily install the safe-builtins sandbox on first call.
    if "__builtins__" not in repl_globals or not isinstance(
        repl_globals.get("__builtins__"), dict
    ):
        repl_globals["__builtins__"] = _SAFE_BUILTINS.copy()

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    t0 = time.perf_counter()
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exec(code, repl_globals)
        stdout = stdout_buf.getvalue()
        stderr = stderr_buf.getvalue()
    except Exception as e:
        stdout = stdout_buf.getvalue()
        stderr = stderr_buf.getvalue() + f"\n{type(e).__name__}: {e}"

    return {
        "stdout": stdout,
        "stderr": stderr,
        "execution_time": time.perf_counter() - t0,
    }


def format_execution_result(result):
    """
    Render a REPL result dict as a string for inclusion in chat history.

    Matches the gold-truth format ("REPL output:\n{stdout}\n{stderr}")
    closely enough that the model interprets it the same way.
    """
    parts = []
    if result.get("stdout"):
        parts.append(result["stdout"].rstrip())
    if result.get("stderr"):
        parts.append("stderr:\n" + result["stderr"].rstrip())
    return "\n\n".join(parts) if parts else "No output"
