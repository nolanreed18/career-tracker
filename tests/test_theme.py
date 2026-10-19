"""The look: two complete palettes, the light one being what config.toml
draws first, applied through Streamlit's theme options."""

import tomllib
from pathlib import Path

import pytest
from streamlit import config

import theme

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def back_to_light():
    yield
    theme.apply(theme.LIGHT)


def flat(section: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in section.items():
        if isinstance(value, dict):
            out.update(flat(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def test_both_modes_set_the_same_options_and_light_is_the_default():
    light, dark = theme.options(theme.LIGHT), theme.options(theme.DARK)
    assert set(light) == set(dark)
    assert (light["base"], dark["base"]) == ("light", "dark")
    assert theme.DEFAULT == theme.LIGHT
    with pytest.raises(ValueError):
        theme.options("sepia")


def test_config_toml_draws_the_light_look_first():
    with open(ROOT / ".streamlit" / "config.toml", "rb") as handle:
        configured = flat(tomllib.load(handle)["theme"])
    assert configured == theme.options(theme.LIGHT)


def test_apply_switches_the_process_theme():
    theme.apply(theme.DARK)
    assert theme.current() == theme.DARK
    assert config.get_option("theme.backgroundColor") == theme.PALETTES[theme.DARK]["backgroundColor"]
    assert config.get_option("theme.sidebar.backgroundColor") == "#0d121e"
    theme.apply(theme.LIGHT)
    assert theme.current() == theme.LIGHT
    assert config.get_option("theme.backgroundColor") == theme.PALETTES[theme.LIGHT]["backgroundColor"]
    config.set_option("theme.backgroundColor", "#123456")      # neither palette: not applied yet
    assert theme.current() is None


def test_the_stylesheet_carries_its_mode_tokens():
    light, dark = theme.stylesheet(theme.LIGHT), theme.stylesheet(theme.DARK)
    assert light.startswith("<style>") and light.endswith("</style>")
    assert "--ct-card: #ffffff;" in light and "--ct-card: #111827;" in dark
    assert "st-key-card-" in light and "stRadioOption" in light
    assert "stBaseButton-primaryFormSubmit" in light     # form Save/Add buttons too
    assert "stSidebar" in theme.LOCKED


def test_html_helpers_escape_text():
    assert theme.subtitle("<b>") == '<div class="ct-sub">&lt;b&gt;</div>'
    panel = theme.empty_state("inbox", "No leads", "Try <later>")
    assert ">inbox<" in panel and "Try &lt;later&gt;" in panel
    assert theme.note("me@example.com") == '<div class="ct-note">me@example.com</div>'
