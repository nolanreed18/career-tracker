"""Keep the app's own modules fresh after a redeploy.

Streamlit Community Cloud pulls new code into a running app. Pages are read
again on every run, but modules they import (ui, data, theme...) stay
loaded as they were, so a page that imports something new fails until the
app is rebooted. Streamlit's file watcher is meant to unload them, and does
on a laptop, but didn't there. check(), called first thing on every page,
does the same job from file timestamps: when any module in this folder has
changed since it was loaded, every module from this folder is unloaded
(they import each other, so a partial reload would mix old and new) and the
page's imports load the new code.
"""

import os
import sys

APP = os.path.dirname(os.path.abspath(__file__))
_seen: dict[str, float] = {}       # module name -> its file's mtime when first seen


def _app_modules() -> dict[str, str]:
    """Loaded modules whose file is in this folder (not this one)."""
    found = {}
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and name != __name__ and os.path.dirname(os.path.abspath(path)) == APP:
            found[name] = path
    return found


def check() -> bool:
    """Unload this folder's modules if any of them changed on disk; True if so."""
    modules = _app_modules()
    changed = False
    for name, path in modules.items():
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if _seen.setdefault(name, mtime) != mtime:
            changed = True
    if not changed:
        return False
    data = sys.modules.get("data")
    if data is not None and hasattr(data, "reset_connection"):
        data.reset_connection()            # the old copy's database connection
    for name in modules:
        sys.modules.pop(name, None)
        _seen.pop(name, None)
    return True
