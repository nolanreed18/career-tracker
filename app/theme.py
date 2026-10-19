"""The app's look: a light palette (the default) and a dark one, drawn from
the "Dark Desk" dashboard style guide, plus the stylesheet that finishes
what Streamlit's theme options can't reach.

Streamlit reads its theme options at the start of every script run, so
apply() changes the theme for the whole process (the app has one user) and
the browser repaints on the next run; ui.setup() takes care of the timing.
Colours mean something: blue/cyan = selected or a key value, green = good,
orange = needs attention, red = closed or overdue, grey = neutral.
"""

from html import escape

from streamlit import config

LIGHT = "light"
DARK = "dark"
MODES = [LIGHT, DARK]
DEFAULT = LIGHT

# Inter for words, JetBrains Mono for numbers; Streamlit adds the stylesheet
# links to the page. The URLs are what Google Fonts hands out.
FONT = ("Inter:https://fonts.googleapis.com/css2"
        "?family=Inter:wght@400;500;600;700&display=swap")
CODE_FONT = ("JetBrains Mono:https://fonts.googleapis.com/css2"
             "?family=JetBrains+Mono:wght@400;500;600&display=swap")
MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

# Chart series, in order (the guide's "strong" row: told apart under
# colour-blindness, on either background).
CHART_COLORS = ["#4f91f2", "#02a998", "#dc701c", "#d863a0", "#b48c05", "#9f79e6",
                "#47ab4f", "#0aa0d2", "#e3645e", "#5b6777"]

# Theme options both modes share.
SHARED = {
    "font": FONT,
    "headingFont": "Inter",
    "codeFont": CODE_FONT,
    "baseFontSize": 15,
    "headingFontSizes": ["1.5rem", "1.2rem", "1.05rem", "1rem", "0.9rem", "0.85rem"],
    "headingFontWeights": [700, 700, 700, 700, 600, 600],
    "baseRadius": "10px",
    "buttonRadius": "6px",
    "showWidgetBorder": True,
    "showSidebarBorder": True,
    "chartCategoricalColors": CHART_COLORS,
    # Badges and coloured text (:blue-badge[...] and friends).
    "blueColor": "#3b82f6",
    "greenColor": "#10b981",
    "orangeColor": "#f59e0b",
    "redColor": "#f43f5e",
    "grayColor": "#64748b",
}

PALETTES = {
    LIGHT: {
        "base": "light",
        "primaryColor": "#2563eb",
        "backgroundColor": "#f8fafc",
        "secondaryBackgroundColor": "#ffffff",
        "textColor": "#0f172a",
        "linkColor": "#0e7490",
        "borderColor": "#e2e8f0",
        "codeBackgroundColor": "#f1f5f9",
        "dataframeBorderColor": "#e2e8f0",
        "dataframeHeaderBackgroundColor": "#f1f5f9",
        "violetColor": "#8b5cf6",
        "sidebar.backgroundColor": "#f1f5f9",
        "sidebar.secondaryBackgroundColor": "#ffffff",
    },
    DARK: {
        "base": "dark",
        "primaryColor": "#3b82f6",
        "backgroundColor": "#0b0f19",
        "secondaryBackgroundColor": "#111827",
        "textColor": "#f8fafc",
        "linkColor": "#22d3ee",
        "borderColor": "#1e293b",
        "codeBackgroundColor": "#0f172a",
        "dataframeBorderColor": "#1e293b",
        "dataframeHeaderBackgroundColor": "#0f172a",
        "violetColor": "#c084fc",
        "sidebar.backgroundColor": "#0d121e",
        "sidebar.secondaryBackgroundColor": "#111827",
    },
}

# Values the stylesheet needs that the theme options don't cover.
TOKENS = {
    LIGHT: {
        "text": "#0f172a", "text2": "#475569", "muted": "#64748b",
        "card": "#ffffff", "card-hover": "#f1f5f9", "border": "#e2e8f0",
        "border-strong": "#94a3b8", "blue": "#2563eb", "cyan": "#0e7490",
        "table-head": "#f1f5f9",
    },
    DARK: {
        "text": "#f8fafc", "text2": "#94a3b8", "muted": "#64748b",
        "card": "#111827", "card-hover": "#1c263d", "border": "#1e293b",
        "border-strong": "#475569", "blue": "#3b82f6", "cyan": "#22d3ee",
        "table-head": "#0f172a",
    },
}

# The one gradient: it means "selected" (and the main action).
GRADIENT = "linear-gradient(135deg, rgba(37, 99, 235, 0.9), rgba(6, 182, 212, 0.75))"
GRADIENT_SOFT = "linear-gradient(135deg, rgba(37, 99, 235, 0.28), rgba(6, 182, 212, 0.18))"


def options(mode: str) -> dict:
    """Every theme option for a mode, keyed as in config.toml ("primaryColor",
    "sidebar.backgroundColor")."""
    if mode not in MODES:
        raise ValueError(f"unknown theme mode {mode!r}")
    return {**SHARED, **PALETTES[mode]}


def apply(mode: str) -> None:
    """Make this the process's theme from the next script run on."""
    for key, value in options(mode).items():
        config.set_option(f"theme.{key}", value)


def current() -> str | None:
    """The mode the process's theme options are in right now, or None when
    they're something else (Streamlit's defaults, before apply() has run)."""
    background = config.get_option("theme.backgroundColor")
    for mode in MODES:
        if PALETTES[mode]["backgroundColor"] == background:
            return mode
    return None


def stylesheet(mode: str) -> str:
    """A <style> element finishing the look for this mode: microlabels,
    mono numbers, cards, segmented filters, the gradient button."""
    t = TOKENS[mode]
    tokens = " ".join(f"--ct-{k}: {v};" for k, v in t.items())
    return f"""<style>
:root {{ {tokens} --ct-mono: {MONO}; --ct-ease: 0.2s ease; }}

/* Less empty space above the page head (the header bar is 3.75rem). */
[data-testid="stMainBlockContainer"] {{ padding-top: 4.5rem; }}

/* Page head: a small bold title and a one-line mono subtitle. */
[data-testid="stHeading"] h1 {{ letter-spacing: -0.01em; padding-bottom: 0.1rem; }}
.ct-sub {{ font-family: var(--ct-mono); font-size: 0.78rem; color: var(--ct-muted);
          margin-top: -0.4rem; }}

/* Section headings (st.subheader) are microlabels: small, uppercase, tracked. */
[data-testid="stHeading"] h3 {{ font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em; color: var(--ct-text2);
    padding-top: 0.75rem; padding-bottom: 0.1rem; }}

/* Labels above inputs: the same microlabel. */
:is([data-testid="stTextInput"], [data-testid="stNumberInput"], [data-testid="stSelectbox"],
    [data-testid="stMultiSelect"], [data-testid="stDateInput"], [data-testid="stTimeInput"],
    [data-testid="stTextArea"], [data-testid="stRadio"], [data-testid="stFileUploader"])
    > [data-testid="stWidgetLabel"] p {{
    font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--ct-text2); }}

/* Stat cards: a muted microlabel over a big mono number. Their columns may
   shrink below Streamlit's 120px minimum so three fit on a phone. */
[data-testid="stColumn"]:has([data-testid="stMetric"]) {{ min-width: 0; }}
[data-testid="stMetric"] {{ background: var(--ct-card); border: 1px solid var(--ct-border);
    border-radius: 10px; padding: 10px; transition: border-color var(--ct-ease); }}
[data-testid="stMetric"]:hover {{ border-color: var(--ct-blue); }}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ overflow: visible;
    white-space: normal; text-overflow: clip; }}
[data-testid="stMetricLabel"] p {{ font-size: 0.62rem; font-weight: 600; line-height: 1.3;
    text-transform: uppercase; letter-spacing: 0.04em; color: var(--ct-muted); }}
[data-testid="stMetricValue"] {{ font-family: var(--ct-mono); font-size: 1.55rem;
    font-weight: 700; font-variant-numeric: tabular-nums; }}

/* Cards (ui.card; the key becomes a class on the bordered block). */
[class*="st-key-card-"] {{
    background: var(--ct-card); border: 1px solid var(--ct-border); border-radius: 16px;
    padding: 0.9rem 1rem; transition: border-color var(--ct-ease), background var(--ct-ease); }}
[class*="st-key-card-"]:hover {{ border-color: var(--ct-blue); background: var(--ct-card-hover); }}
/* A card's text-and-button row: the text column shrinks, the button column
   keeps its width, and nothing inside scrolls. */
[class*="st-key-card-"] [data-testid="stHorizontalBlock"] {{ overflow: visible; }}
[class*="st-key-card-"] [data-testid="stColumn"]:first-child {{ min-width: 0; }}

/* Badges: mono pills with a hairline. */
.stMarkdownBadge {{ font-family: var(--ct-mono); font-size: 0.7rem !important; font-weight: 600;
    padding: 1px 8px; border-radius: 999px; vertical-align: middle; letter-spacing: 0.02em;
    border: 1px solid color-mix(in srgb, currentColor 35%, transparent); }}

/* Buttons: the gradient means the main action; others are quiet cards. */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {{
    background: {GRADIENT}; color: #fff; font-weight: 600;
    border: 1px solid rgba(6, 182, 212, 0.5); transition: filter var(--ct-ease); }}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primary"]:focus-visible,
[data-testid="stBaseButton-primaryFormSubmit"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:focus-visible {{ filter: brightness(1.1);
    color: #fff; border-color: #06b6d4; }}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {{
    background: var(--ct-card); font-weight: 600; border: 1px solid var(--ct-border);
    color: var(--ct-text); transition: border-color var(--ct-ease), background var(--ct-ease); }}
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-secondaryFormSubmit"]:hover {{ border-color: var(--ct-blue);
    background: var(--ct-card-hover); color: var(--ct-text); }}

/* Horizontal radios become a segmented control: one of a few, all visible. */
[data-testid="stRadio"] [role="radiogroup"] {{ gap: 6px; flex-wrap: wrap; }}
[data-testid="stRadioOption"] {{ margin: 0; padding: 5px 12px; border-radius: 6px;
    background: var(--ct-card); border: 1px solid var(--ct-border); color: var(--ct-text2);
    font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.15s ease; }}
[data-testid="stRadioOption"] > div > div > div:not([data-testid]) {{ display: none; }}  /* the dot */
[data-testid="stRadioOption"] p {{ font-size: 0.8rem; }}
[data-testid="stRadioOption"]:hover {{ background: var(--ct-card-hover); color: var(--ct-text); }}
[data-testid="stRadioOption"][data-selected="true"],
[data-testid="stRadioOption"]:has(input:checked) {{ background: {GRADIENT_SOFT};
    border-color: rgba(6, 182, 212, 0.6); color: var(--ct-text);
    box-shadow: 0 0 0 1px rgba(6, 182, 212, 0.15); }}

/* Sub-pages (ui.sections): bigger pills, a hairline under the row. */
[class*="st-key-sections-"] {{ border-bottom: 1px solid var(--ct-border); padding-bottom: 0.6rem;
    margin-bottom: 0.2rem; }}
[class*="st-key-sections-"] [data-testid="stRadioOption"] {{ padding: 7px 14px; }}
[class*="st-key-sections-"] [data-testid="stRadioOption"] p {{ font-size: 0.85rem; }}

/* No "Press Enter to submit form" hint inside inputs: it sits on the value. */
[data-testid="InputInstructions"] {{ display: none; }}

/* Tabs, expanders, sidebar navigation. */
[data-testid="stTab"] p {{ font-weight: 600; font-size: 0.85rem; }}
[data-testid="stExpander"] details {{ background: var(--ct-card); border-radius: 12px;
    transition: border-color var(--ct-ease); }}
[data-testid="stExpander"] details:hover {{ border-color: var(--ct-blue); }}
[data-testid="stExpander"] summary p {{ font-weight: 600; }}
[data-testid="stExpanderIcon"] {{ color: var(--ct-cyan); }}
[data-testid="stSidebarNavLink"] span {{ font-weight: 600; font-size: 0.85rem; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: {GRADIENT}; }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: #fff; }}

/* Empty states (ui.empty): say why it's empty and what to do. */
.ct-empty {{ display: flex; flex-direction: column; align-items: center; gap: 4px;
    text-align: center; padding: 26px 20px; border: 1px dashed var(--ct-border-strong);
    border-radius: 16px; background: var(--ct-card); color: var(--ct-text2);
    font-size: 0.9rem; }}
.ct-empty .ct-icon {{ font-family: "Material Symbols Rounded"; font-size: 30px; line-height: 1;
    color: var(--ct-muted); margin-bottom: 4px; }}
.ct-empty h3 {{ font-size: 0.95rem; font-weight: 700; margin: 0; padding: 0;
    color: var(--ct-text); }}
.ct-empty p {{ margin: 0; }}

/* A small mono note (the signed-in address in the sidebar). */
.ct-note {{ font-family: var(--ct-mono); font-size: 0.75rem; color: var(--ct-muted);
    overflow-wrap: anywhere; }}

@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>"""


def subtitle(text: str) -> str:
    """The page head's mono subtitle, as HTML for st.html."""
    return f'<div class="ct-sub">{escape(text)}</div>'


def note(text: str) -> str:
    """A small mono note, as HTML for st.html (plain text: no links made)."""
    return f'<div class="ct-note">{escape(text)}</div>'


# While nobody is signed in, the sidebar (and its page list) stays out of sight.
LOCKED = ('<style>[data-testid="stSidebar"], [data-testid="stExpandSidebarButton"] '
          '{ display: none; }</style>')


def empty_state(icon: str, title: str, text: str) -> str:
    """An empty-state panel (a Material Symbols icon name, a heading, one
    sentence), as HTML for st.html."""
    return (f'<div class="ct-empty"><span class="ct-icon">{escape(icon)}</span>'
            f'<h3>{escape(title)}</h3><p>{escape(text)}</p></div>')
