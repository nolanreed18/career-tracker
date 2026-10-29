# THEME.md: the look, ready to copy

Everything another Streamlit app needs to look and behave like the Career
Tracker, in one file: the design rules in words, the steps to apply them, and
the code. Copy this file into the other app's repository and tell Claude Code
**"Apply THEME.md"**.

The code below is the Career Tracker's own, word for word: its
`tests/test_theme.py` fails if `app/theme.py` or `.streamlit/config.toml`
changes without this file being refreshed. So the newest copy of this file is
always the one in `nolanreed18/career-tracker`.

## The idea

A quiet desk, not a dashboard. White (or near-black) cards on a soft
background, one accent gradient that always means "this one" or "the main
action", small uppercase labels, numbers in a monospace face, and colour only
where it carries meaning. It works at phone width first; a computer gets the
wide layout and side-by-side views.

## Colour

| Role | Light | Dark |
|---|---|---|
| Page background | `#f8fafc` | `#0b0f19` |
| Card / surface | `#ffffff` | `#111827` |
| Card under the pointer | `#f1f5f9` | `#1c263d` |
| Text | `#0f172a` | `#f8fafc` |
| Secondary text | `#475569` | `#94a3b8` |
| Muted (labels, hints) | `#64748b` | `#64748b` |
| Border (hairlines) | `#e2e8f0` | `#1e293b` |
| Accent | `#2563eb` | `#3b82f6` |
| Link | `#0e7490` | `#22d3ee` |
| Sidebar | `#f1f5f9` | `#0d121e` |
| Pill selector track | `#eaeff5` | `#111827` |

**The one gradient**, `linear-gradient(135deg, rgba(37, 99, 235, 0.9),
rgba(6, 182, 212, 0.75))` (blue to cyan), means "selected" or "the main
action": the primary button, the open page in the sidebar, the chosen pill.
Nothing else is a gradient.

**Colour means something, always the same thing.** Blue = in progress or
informational, green = good or done, orange = needs attention soon, red =
overdue, closed or bad, grey = neutral or inactive, yellow = unverified (an
estimate, a missing value), violet = a category of its own (sparingly). Never
pick a colour for looks. Badges use Streamlit's `:blue-badge[...]` and
friends, drawn in blue `#3b82f6`, green `#10b981`, orange `#f59e0b`, red
`#f43f5e`, grey `#64748b`, violet `#8b5cf6` / `#c084fc` (dark), yellow
`#ca8a04` / `#facc15` (dark).

Charts take their series colours in order from `CHART_COLORS` (ten,
told apart under colour-blindness, on either background).

## Type

- **Words:** Inter, 15px base, weights 400 to 700.
- **Numbers, subtitles, badges, notes:** JetBrains Mono, tabular numerals.
- **Headings:** 1.5rem page title, then 1.2, 1.05 and 1rem; all bold.
- **Microlabels:** section headings (`st.subheader`) and input labels are
  small (0.7rem), bold, uppercase and letter-spaced, in the secondary text
  colour. They organise; they don't shout.
- **Page head:** a bold title with a one-line mono subtitle under it
  (`setup(title, subtitle)`).

## Surfaces and controls

- **Corners:** 10px on inputs, 6px on buttons, 12 to 16px on cards and
  empty states. Borders are 1px hairlines.
- **Cards** (`card(key)`): a bordered surface; on hover the border turns
  blue and the surface lifts a shade. One record, one card. Inside a card, a
  text column plus a button column is the standard row.
- **Stat cards** (`st.metric(..., border=True)`): a muted microlabel over a
  big mono number, in a row of columns; on a phone they sit two to a row.
- **Buttons:** the gradient for the one main action on a page and for form
  submits (`type="primary"`); every other button is a quiet card with a
  hairline that turns blue on hover. Use `width="stretch"` in cards and
  column pairs.
- **Badges:** mono pills with a hairline in their own colour (`badge(color,
  text)`). A status always looks the same everywhere: give each its own
  helper (e.g. `status_badge`).
- **The pill selector:** every row of choices is a horizontal `st.radio`. The
  stylesheet draws all of them alike: the options sit in one grey rounded
  track, and the chosen one is a solid gradient pill with white text. A
  page's sub-pages use `sections(key, names)`, the same a size up. Never
  `st.tabs` (they forget their place when the page reruns), `st.pills`,
  `st.segmented_control` or a row of buttons. On a phone the pills are a
  little smaller, and a row that doesn't fit wraps inside its track.
- **Empty states** (`empty(icon, title, text)`): a dashed panel with a
  Material Symbols icon, a short heading and one sentence saying why it's
  empty and what to do next. Every list that can be empty has one.
- **Add forms** open from a `disclosure(label, key)` button, which shows
  "Close" while open. Not `st.expander`: it snaps shut when a click lands
  while the page is still loading.
- **Deletes** need a tick first (`delete_button(what, key)`). A "pick one"
  dropdown whose options change takes `round_key(name)` and
  `bump_round(name)` after a delete, or it keeps showing the vanished choice.
- **Claude's spark:** a button that calls Claude is `claude_button` /
  `claude_submit`. Its key starts `claude_`, and the stylesheet puts a small
  coral Claude mark before the label, so you can see what costs money
  before you tap it.
- **Icons** are Material Symbols names (`:material/add:`, or the empty-state
  helper). No emoji in the interface.

## Phone and computer

The app reads the browser's User-Agent (`on_phone()`): phones get the phone
layout, while tablets, computers and anything unknown get the computer one.

- **Phone:** one centred column and the everyday tasks. Wide editing grids
  show an empty state ("use your computer") instead of squeezing.
- **Computer:** the wide layout, capped at `COMPUTER_MAX_WIDTH` (1440px), and
  side-by-side views (a list beside the open record).

Every page is checked at about 380px wide. There must be no sideways scroll,
labels must wrap rather than cut off, and a number must never be split from
its label (use a non-breaking space) or a range at its dash (use a word
joiner, `⁠`).

## Behaviour that is part of the look

- **Dark mode:** light by default. The sidebar's **Dark mode** switch is
  saved where every device reads it (a settings table), so a phone and a
  computer follow each other. Both looks must read well: check the yellow
  badge and the pills in dark.
- **Confirmations:** after an action, a green banner plus a toast say what
  happened (`done(message)` then `setup()` on the next run). The toast is
  there for phones, where the banner scrolls away.
- **Tables** show blanks, never "None" or "nan".
- **User text** goes into `st.markdown` through `md()`, so a `$` or `*`
  can't turn into maths or bold.
- **Reduced motion:** when the system asks for it, there are no transitions.
- **One person per app:** `theme.apply()` sets Streamlit's theme for the
  whole server process. That's right for a personal app, but a shared app
  would need another way.

## Applying it (steps for Claude Code in the other app)

1. **Create `app/theme.py`** from the block below, word for word. It needs
   only Streamlit.
2. **Write `.streamlit/config.toml`** from the block below. Keep any
   sections the app already has that aren't `[theme]` (`[server]` and so
   on). The `[theme]` values must equal `theme.PALETTES["light"]` plus
   `theme.SHARED`, so the first paint already matches; add a test that
   checks it.
3. **Add the helpers** below to the app's `ui.py` (create it if there isn't
   one). Adjust `APP_NAME` and `APP_ICON`, put the app's sign-in where
   `setup()` says, and pass `appearance()` the app's saved-setting functions
   so Dark mode follows across devices (without them the switch lasts until
   the app restarts).
4. **Start every page with `setup(title, subtitle)`**, then convert the
   pages to the components: rows of choices to horizontal `st.radio` (or
   `sections`), records to `card`, lists that can be empty to `empty`, add
   forms to `disclosure`, deletes to `delete_button`, Claude buttons to
   `claude_button`, user text through `md`, and the one main action per page
   to `type="primary"`. Remove emoji from labels and any colour that doesn't
   follow the meanings above.
5. **Add the rules** in the next section to the app's `CLAUDE.md`.
6. **Check it** in light and dark, at phone width (about 380px) and on a
   computer.

## Rules for the app's CLAUDE.md

```markdown
- **The look lives in `app/theme.py`** (copied from the Career Tracker's
  THEME.md): a light palette (the default) and a dark one as Streamlit theme
  options, applied per run by `ui.setup()`, plus one stylesheet.
  `.streamlit/config.toml` must equal the light palette (a test checks).
  Pages use `ui.card()`, `ui.empty()` and badge helpers rather than emoji or
  raw HTML; colour means something (blue = in progress, green = good,
  orange = attention, red = overdue/closed, grey = neutral, yellow =
  unverified). Every row of choices is a horizontal `st.radio` (sub-pages:
  `ui.sections()`), drawn as the one pill selector; never `st.tabs`,
  `st.pills`, `st.segmented_control` or a row of buttons. Add forms sit
  behind `ui.disclosure()`, not `st.expander`; every delete goes through
  `ui.delete_button()`; a button that calls Claude is `ui.claude_button`.
  `ui.on_phone()` picks the layout: a phone gets one centred column, a
  computer the wide layout (`theme.COMPUTER_MAX_WIDTH`).
```

## The code

### app/theme.py

```python
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
from urllib.parse import quote

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
        "yellowColor": "#ca8a04",
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
        "yellowColor": "#facc15",
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
        # The pill selector: a grey track the options sit in, lighter under the pointer.
        "track": "#eaeff5", "track-hover": "#ffffff",
    },
    DARK: {
        "text": "#f8fafc", "text2": "#94a3b8", "muted": "#64748b",
        "card": "#111827", "card-hover": "#1c263d", "border": "#1e293b",
        "border-strong": "#475569", "blue": "#3b82f6", "cyan": "#22d3ee",
        "table-head": "#0f172a",
        "track": "#111827", "track-hover": "#1c263d",
    },
}

# The one gradient: it means "selected" (and the main action).
GRADIENT = "linear-gradient(135deg, rgba(37, 99, 235, 0.9), rgba(6, 182, 212, 0.75))"

_applied: str | None = None       # the mode apply() last set in this process


def options(mode: str) -> dict:
    """Every theme option for a mode, keyed as in config.toml ("primaryColor",
    "sidebar.backgroundColor")."""
    if mode not in MODES:
        raise ValueError(f"unknown theme mode {mode!r}")
    return {**SHARED, **PALETTES[mode]}


def apply(mode: str) -> None:
    """Make this the process's theme from the next script run on."""
    global _applied
    for key, value in options(mode).items():
        config.set_option(f"theme.{key}", value)
    _applied = mode


def applied() -> str | None:
    """The mode apply() last set, or None before the first apply() in this
    process (config.toml's light palette, whatever the saved choice is)."""
    return _applied


def current() -> str | None:
    """The mode the process's theme options are in right now, or None when
    they're something else (Streamlit's defaults, before apply() has run)."""
    background = config.get_option("theme.backgroundColor")
    for mode in MODES:
        if PALETTES[mode]["backgroundColor"] == background:
            return mode
    return None


def _claude_mark() -> str:
    """A small spark in Claude's coral, as a data URI: rays of a few lengths
    around a centre, the way Claude's own mark looks."""
    rays = "".join(
        f"<rect x='11' y='{12 - length:g}' width='2.2' height='{length - 1.6:g}' rx='1.1' "
        f"transform='rotate({angle} 12 12)'/>"
        for angle, length in zip(range(0, 360, 30), (11, 8.5, 10, 8, 11, 9, 10.5, 8, 11, 8.5,
                                                     10, 9)))
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='#D97757'>{rays}</svg>"
    return "data:image/svg+xml," + quote(svg)


CLAUDE_MARK = _claude_mark()
CLAUDE_KEY = "claude_"            # a widget key starting with this gets the mark (ui.claude_button)


# On a computer pages use the full width, up to this many pixels.
COMPUTER_MAX_WIDTH = 1440

# On a phone the pills are a little smaller, so most rows fit on one line; one
# that doesn't wraps inside its track.
PHONE_PILLS = """
[data-testid="stRadioOption"],
[class*="st-key-sections-"] [data-testid="stRadioOption"] { padding: 6px 11px; }
[class*="st-key-sections-"] [data-testid="stRadioOption"] p { font-size: 0.8rem; }"""


def layout_css(phone: bool) -> str:
    """The part of the stylesheet that differs by device: a phone's pills
    are a little smaller; a computer's page stops at a comfortable width."""
    if phone:
        return PHONE_PILLS
    return ('[data-testid="stMainBlockContainer"] { margin: 0 auto; max-width: '
            f"{COMPUTER_MAX_WIDTH}px; }}")


def stylesheet(mode: str, phone: bool = False) -> str:
    """A <style> element finishing the look for this mode: microlabels,
    mono numbers, cards, pill selectors, the gradient button, the Claude
    mark, and the layout for a phone or a computer."""
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
   shrink below Streamlit's 120px minimum. */
[data-testid="stColumn"]:has([data-testid="stMetric"]) {{ min-width: 0; }}
@media (max-width: 640px) {{   /* four don't fit across a phone: two to a row */
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {{
        flex-wrap: wrap !important; }}
    [data-testid="stColumn"]:has([data-testid="stMetric"]) {{ flex: 1 1 40% !important; }}
}}
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

/* Something Claude does (ui.claude_button): its mark before the label. */
[class*="st-key-{CLAUDE_KEY}"] button p::before {{ content: ""; display: inline-block;
    width: 1.05em; height: 1.05em; margin-right: 0.42em; vertical-align: -0.17em;
    background: url("{CLAUDE_MARK}") center / contain no-repeat; }}
[class*="st-key-{CLAUDE_KEY}"] [data-testid^="stBaseButton-primary"] p::before {{
    background-color: #fff; background-size: 78%; border-radius: 50%;
    box-shadow: 0 0 0 1.5px #fff; }}   /* on the gradient: a white disc behind the mark */

/* The pill selector: every row of options (each st.radio, ui.sections
   included) sits in one grey track, and the chosen one is a solid pill in
   the gradient, like the sidebar's open page. */
[data-testid="stRadio"] [role="radiogroup"] {{ display: inline-flex; flex-wrap: wrap;
    width: fit-content; max-width: 100%; gap: 2px; padding: 3px; border-radius: 20px;
    background: var(--ct-track); border: 1px solid var(--ct-border); }}
[data-testid="stRadioOption"] {{ margin: 0; padding: 6px 14px; border-radius: 999px;
    background: transparent; border: none; color: var(--ct-text2); font-weight: 600;
    white-space: nowrap; cursor: pointer;
    transition: background var(--ct-ease), color var(--ct-ease); }}
[data-testid="stRadioOption"] > div > div > div:not([data-testid]) {{ display: none; }}  /* the dot */
[data-testid="stRadioOption"] div, [data-testid="stRadioOption"] p {{ color: inherit; }}
[data-testid="stRadioOption"] p {{ font-size: 0.8rem; }}
[data-testid="stRadioOption"]:hover {{ background: var(--ct-track-hover); color: var(--ct-text); }}
[data-testid="stRadioOption"][data-selected="true"],
[data-testid="stRadioOption"]:has(input:checked) {{ background: {GRADIENT}; color: #fff;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.2); }}

/* Sub-pages (ui.sections): the same, a size up. */
[class*="st-key-sections-"] {{ margin-bottom: 0.4rem; }}
[class*="st-key-sections-"] [data-testid="stRadioOption"] {{ padding: 7px 16px; }}
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

/* The device's own rules, last so they win. */
{layout_css(phone)}
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
```

### .streamlit/config.toml

```toml
# The light look, as app/theme.py defines it (tests/test_theme.py checks they
# match): what the page is drawn with before the app applies the saved choice.
[theme]
base = "light"
primaryColor = "#2563eb"
backgroundColor = "#f8fafc"
secondaryBackgroundColor = "#ffffff"
textColor = "#0f172a"
linkColor = "#0e7490"
borderColor = "#e2e8f0"
codeBackgroundColor = "#f1f5f9"
dataframeBorderColor = "#e2e8f0"
dataframeHeaderBackgroundColor = "#f1f5f9"
font = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
headingFont = "Inter"
codeFont = "JetBrains Mono:https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap"
baseFontSize = 15
headingFontSizes = ["1.5rem", "1.2rem", "1.05rem", "1rem", "0.9rem", "0.85rem"]
headingFontWeights = [700, 700, 700, 700, 600, 600]
baseRadius = "10px"
buttonRadius = "6px"
showWidgetBorder = true
showSidebarBorder = true
chartCategoricalColors = ["#4f91f2", "#02a998", "#dc701c", "#d863a0", "#b48c05", "#9f79e6", "#47ab4f", "#0aa0d2", "#e3645e", "#5b6777"]
blueColor = "#3b82f6"
greenColor = "#10b981"
orangeColor = "#f59e0b"
redColor = "#f43f5e"
grayColor = "#64748b"
violetColor = "#8b5cf6"
yellowColor = "#ca8a04"

[theme.sidebar]
backgroundColor = "#f1f5f9"
secondaryBackgroundColor = "#ffffff"

[browser]
gatherUsageStats = false

[client]
# No "Deploy" button or developer menu in the toolbar.
toolbarMode = "minimal"
```

### The helpers (in the app's ui.py)

```python
"""The look's helpers, from the Career Tracker's ui.py: the page head, the
saved Dark mode switch, phone or computer, and the components the stylesheet
draws (cards, pill selectors, empty states, disclosures, deletes, badges,
Claude's spark)."""

import re

import streamlit as st

import theme

APP_NAME = "My App"               # the browser tab says "Page · My App"
APP_ICON = "✨"                    # the browser tab's icon

_MARKDOWN = str.maketrans({c: "\\" + c for c in "\\`*_[]#<>$|~"})

PHONE_AGENT = re.compile(r"iPhone|iPod|Android.+Mobile|Windows Phone|IEMobile|BlackBerry|"
                         r"Opera Mini|Mobile.+Firefox", re.I)


def device_from_agent(agent) -> str:
    """"phone" for a phone's browser (its User-Agent says so), else
    "computer": a tablet, a computer or an unknown browser gets the bigger
    layout."""
    return "phone" if PHONE_AGENT.search(str(agent or "")) else "computer"


def device() -> str:
    """"phone" or "computer", from what the browser says it is."""
    try:
        agent = st.context.headers.get("User-Agent", "")
    except Exception:                                  # no browser: a test or a script
        agent = ""
    return device_from_agent(agent)


def on_phone() -> bool:
    return device() == "phone"


def setup(title: str, subtitle: str | None = None) -> None:
    """Page config, the look, and the page head. A phone gets one centred
    column; a computer the full width (up to a limit), which pages use for
    side-by-side layouts."""
    st.set_page_config(
        page_title=title if title == APP_NAME else f"{title} · {APP_NAME}",
        page_icon=APP_ICON,
        layout="centered" if on_phone() else "wide",
    )
    # The app's sign-in goes here, before anything else is drawn.
    appearance()
    st.title(title)
    if subtitle:
        st.html(theme.subtitle(subtitle))
    if message := st.session_state.pop("flash", None):   # what the last action did
        st.success(message)
        st.toast(message)                                # also where the eye is


def appearance(saved=None, save=None) -> None:
    """Apply the look (light unless Dark mode was switched on), draw the
    sidebar's Dark mode switch, and add the stylesheet.

    saved() returns the stored choice ("light" or "dark", or None) and
    save(mode) stores it, e.g. in a settings table, so every device follows;
    without them the switch lasts until the app restarts. The choice is read
    once per process. Streamlit reads its theme options as a script run
    starts, so a change made during a run shows on the next one: after a
    switch, or when this run began with other options (the first run after
    the app started), the page reruns once.
    """
    started_with = theme.current()
    mode = theme.applied()
    if mode is None:                                 # the first run in this process
        mode = saved() if saved else None
        if mode not in theme.MODES:
            mode = theme.DEFAULT
        theme.apply(mode)
    if "dark_mode" not in st.session_state or st.session_state.get("theme_shown") != mode:
        # First draw, or the choice was changed on another device: the switch
        # follows the saved choice rather than flipping it back.
        st.session_state["dark_mode"] = mode == theme.DARK
        st.session_state["theme_shown"] = mode
    with st.sidebar:
        dark = st.toggle("Dark mode", key="dark_mode")
    picked = theme.DARK if dark else theme.LIGHT
    if picked != mode:
        if save:
            save(picked)
        st.session_state["theme_shown"] = picked
        theme.apply(picked)
        st.rerun()
    if started_with != mode and not st.session_state.get("theme_rerun"):
        st.session_state["theme_rerun"] = True       # once: never loop on a surprise
        st.rerun()
    st.session_state["theme_rerun"] = False
    st.html(theme.stylesheet(mode, phone=on_phone()))


def done(message: str, counter: str | None = None) -> None:
    """Finish an action: remember what happened (setup() shows it on the
    next run), bump a form's counter so it comes back empty, and rerun."""
    if counter:
        st.session_state[counter] = st.session_state.get(counter, 0) + 1
    st.session_state["flash"] = message
    st.rerun()


def claude_button(label: str, key: str, active: bool = True, **kwargs) -> bool:
    """A button for something Claude does: its key starts "claude_", which
    the stylesheet marks with Claude's spark (active=False: an ordinary
    button, e.g. when no Claude key is set and the click won't call it)."""
    return st.button(label, key=f"{theme.CLAUDE_KEY}{key}" if active else key, **kwargs)


def claude_submit(label: str, key: str, **kwargs) -> bool:
    """A form's submit button for something Claude does, with the mark."""
    return st.form_submit_button(label, key=f"{theme.CLAUDE_KEY}{key}", **kwargs)


def card(key: str):
    """A bordered container styled as a card (the stylesheet finds the key)."""
    return st.container(border=True, key=f"card-{key}")


def disclosure(label: str, key: str) -> bool:
    """A button that opens and closes a form below it: True while open. The
    state lives on the server, so a click that lands while the page is still
    loading can't snap it shut (an st.expander forgets it was open then)."""
    flag = f"open_{key}"
    is_open = bool(st.session_state.get(flag, False))
    if st.button("Close" if is_open else label, key=f"toggle_{key}",
                 icon=":material/close:" if is_open else ":material/add:", width="stretch"):
        st.session_state[flag] = not is_open
        st.rerun()
    return is_open


def sections(key: str, names: list[str]) -> str:
    """A page's sub-pages as pills. Unlike st.tabs, the chosen one stays put
    when an action reruns the page."""
    with st.container(key=f"sections-{key}"):
        return st.radio("Section", names, horizontal=True, key=f"section_{key}",
                        label_visibility="collapsed")


def delete_button(what: str, key: str) -> bool:
    """A Delete button that needs its tick box first: nothing goes in one click."""
    sure = st.checkbox(f"I want to delete this {what}", key=f"sure_{key}")
    return st.button(f"Delete {what}", disabled=not sure, key=f"delete_{key}")


def round_key(name: str) -> str:
    """A widget key with a counter in it. A widget whose options change (a
    "pick one" dropdown after a delete) keeps showing its old choice; a new
    key (bump_round) gives a fresh widget instead."""
    return f"{name}_{st.session_state.get(f'{name}_round', 0)}"


def bump_round(name: str) -> None:
    st.session_state[f"{name}_round"] = st.session_state.get(f"{name}_round", 0) + 1


def empty(icon: str, title: str, text: str) -> None:
    """An empty state: a Material Symbols icon name, a heading, one sentence
    saying why it's empty and what to do."""
    st.html(theme.empty_state(icon, title, text))


def md(text) -> str:
    """Text safe to put inside st.markdown."""
    return "" if text is None else str(text).translate(_MARKDOWN)


def badge(color: str, text: str) -> str:
    """A coloured markdown badge (:blue-badge[text])."""
    return f":{color}-badge[{text}]"
```
