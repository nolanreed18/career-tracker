"""fresh.check(): the app's modules are unloaded when their files change."""

import os
import sys

import fresh


def test_changed_app_modules_are_unloaded_together(tmp_path, monkeypatch):
    for name in ("alpha", "beta"):
        (tmp_path / f"{name}.py").write_text(f"VALUE = '{name} v1'\n")
    monkeypatch.setattr(fresh, "APP", str(tmp_path))
    monkeypatch.setattr(fresh, "_seen", {})
    monkeypatch.syspath_prepend(str(tmp_path))
    import alpha, beta  # noqa: E401, I001  (two modules from the folder)
    assert alpha.VALUE == "alpha v1" and beta.VALUE == "beta v1"

    assert fresh.check() is False                    # nothing changed: nothing unloaded
    assert "alpha" in sys.modules and "beta" in sys.modules

    (tmp_path / "alpha.py").write_text("VALUE = 'alpha v2'\n")
    stat = (tmp_path / "alpha.py").stat()
    os.utime(tmp_path / "alpha.py", (stat.st_atime, stat.st_mtime + 10))
    assert fresh.check() is True
    assert "alpha" not in sys.modules and "beta" not in sys.modules   # all of them, together
    import alpha as alpha_again  # noqa: I001
    assert alpha_again.VALUE == "alpha v2"
    assert fresh.check() is False                    # the new copy is now what's seen
    for name in ("alpha", "beta"):
        sys.modules.pop(name, None)


def test_the_apps_real_modules_are_left_alone_when_unchanged():
    import data  # noqa: F401
    assert fresh.check() is False
    assert "data" in sys.modules
