"""
Axway brand helpers.

Call apply_branding() at the top of every Streamlit page (after set_page_config)
to inject the Axway colour palette, custom CSS, and the sidebar logo.

Axway palette used
------------------
Griffin Red   #D22630   primary brand / headings accent
Dark Red      #B0001A   hover / active states
Black Text    #22272B   body copy
Dark Gray     #4A4F54   secondary labels
Medium Gray   #7F8184   muted text / borders
Light Gray    #EBECEC   dividers / backgrounds
Teal          #00A0CC   informational accents
Tan           #F3ECE3   sidebar / input background  (set in config.toml)
"""

import base64
import os

import streamlit as st

# ------------------------------------------------------------------
# Brand palette
# ------------------------------------------------------------------
GRIFFIN_RED  = "#D22630"
DARK_RED     = "#B0001A"
BLACK_TEXT   = "#22272B"
DARK_GRAY    = "#4A4F54"
MEDIUM_GRAY  = "#7F8184"
LIGHT_GRAY   = "#EBECEC"
TEAL         = "#00A0CC"
DARK_TEAL    = "#006580"
TAN          = "#F3ECE3"

LOGO_PATH = "resources/286823-axway_logo_horiz_gray_red_rgb.png"

# ------------------------------------------------------------------
# Axway icon filenames  (relative to resources/images/)
# ------------------------------------------------------------------
_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "resources", "images")

ICO_SUCCESS    = "296091-ok-circle_icon_gray-teal.png"
ICO_WARNING    = "296489-attention_icon_gray-teal.png"
ICO_ERROR      = "296489-attention_icon_gray-teal.png"
ICO_INFO       = "296087-info-circle_icon_gray-teal.png"
ICO_ROCKET     = "296381-rocket_icon_gray-teal.png"
ICO_REFRESH    = "296094-refresh_icon_gray-teal.png"
ICO_PIN        = "296388-pushpin-fill_icon_gray-teal.png"
ICO_ADMIN      = "734655-product-rd_icon_gray-teal.png"
ICO_UPLOAD     = "296616-upload_icon_gray-teal.png"
ICO_DOWNLOAD   = "296506-download_icon_gray-teal.png"
ICO_PAPERCLIP  = "296372-paperclip_icon_gray-teal.png"
ICO_STOP       = "296076-block_icon_gray-teal.png"
ICO_SEARCH     = "296609-search_icon_gray-teal.png"
ICO_CONNECT    = "296500-connect_icon_gray-teal.png"
ICO_SETTINGS   = "296615-settings_icon_gray-teal.png"
ICO_SECURETRANSPORT = "295611-securetransport_icon_gray-teal.png"

# Module-level cache so each PNG is read from disk only once per process.
_b64_cache: dict = {}


def icon_b64(filename: str) -> str:
    """Return a base64 data URI for an Axway icon PNG (cached after first read)."""
    if filename in _b64_cache:
        return _b64_cache[filename]
    path = os.path.join(_IMAGES_DIR, filename)
    try:
        with open(path, "rb") as fh:
            uri = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    except FileNotFoundError:
        uri = ""
    _b64_cache[filename] = uri
    return uri


def icon_img(filename: str, size: int = 20) -> str:
    """Return an HTML <img> tag for an Axway icon, embedded as a base64 data URI."""
    uri = icon_b64(filename)
    if not uri:
        return ""
    return (
        f'<img src="{uri}" width="{size}" height="{size}" '
        f'style="vertical-align:middle;margin-right:8px;">'
    )


# ------------------------------------------------------------------
# Branded notification banners
# ------------------------------------------------------------------

def _ax_banner(
    message: str,
    bg: str,
    border_color: str,
    text_color: str,
    icon_filename: str,
    size: int = 20,
) -> None:
    """Render a branded notification box with an Axway icon."""
    img = icon_img(icon_filename, size)
    st.markdown(
        f'<div style="background:{bg};border-left:5px solid {border_color};'
        f'padding:12px 16px;border-radius:4px;color:{text_color};'
        f'line-height:1.6;margin:6px 0;">{img}{message}</div>',
        unsafe_allow_html=True,
    )


def ax_success(message: str, icon: str = ICO_SUCCESS) -> None:
    """Success banner styled in Axway teal with the ok-circle icon."""
    _ax_banner(message, "#E8F7F3", TEAL, DARK_TEAL, icon)


def ax_warning(message: str, icon: str = ICO_WARNING) -> None:
    """Warning banner with amber styling and the attention icon."""
    _ax_banner(message, "#FFF8E1", "#F5A623", "#7A5000", icon)


def ax_error(message: str, icon: str = ICO_ERROR) -> None:
    """Error banner styled in Axway red with the attention icon."""
    _ax_banner(message, "#FDECEA", GRIFFIN_RED, DARK_RED, icon)


def ax_info(message: str, icon: str = ICO_INFO) -> None:
    """Info banner styled in Axway teal with the info-circle icon."""
    _ax_banner(message, "#E6F4F8", TEAL, DARK_TEAL, icon)


def ax_button(label: str, icon_filename: str, icon_size: int = 28, **kwargs) -> bool:
    """
    Render an Axway icon image alongside a Streamlit button.

    Returns True when the button is clicked (same contract as st.button).
    Uses base64-embedded HTML for the icon so no file-path serving issues occur.
    Only use outside st.form() contexts.
    """
    ic, bc, _ = st.columns([1, 6, 7])
    ic.markdown(icon_img(icon_filename, icon_size), unsafe_allow_html=True)
    return bc.button(label, **kwargs)


# ------------------------------------------------------------------
# Custom CSS
# ------------------------------------------------------------------
_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,400&display=swap');

/* ── Global font ─────────────────────────────────────────────── */
html, body, [class*="css"], [data-testid] {{
    font-family: 'Roboto', sans-serif !important;
}}

/* ── Sidebar ────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    border-right: 4px solid {GRIFFIN_RED};
}}

[data-testid="stSidebar"] [data-testid="stImage"] img {{
    padding: 12px 16px 8px 16px;
}}

/* ── Top header bar ─────────────────────────────────────────── */
[data-testid="stHeader"] {{
    background-color: {LIGHT_GRAY};
    border-bottom: 3px solid {MEDIUM_GRAY};
}}

/* Hamburger / nav icons in the header — dark on light background */
[data-testid="stHeader"] button svg,
[data-testid="stHeader"] a svg {{
    fill: {DARK_GRAY} !important;
}}

/* ── Page titles (h1) ───────────────────────────────────────── */
h1 {{
    color: {BLACK_TEXT};
    border-bottom: 3px solid {GRIFFIN_RED};
    padding-bottom: 0.25em;
    margin-bottom: 0.6em;
}}

/* ── Section headings (h2, h3) ──────────────────────────────── */
h2, h3 {{
    color: {DARK_GRAY};
}}

/* ── Primary buttons ────────────────────────────────────────── */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
    background-color: {GRIFFIN_RED} !important;
    border-color:     {GRIFFIN_RED} !important;
    color: white !important;
    font-weight: 600;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {{
    background-color: {DARK_RED} !important;
    border-color:     {DARK_RED} !important;
    color: white !important;
}}

/* ── Secondary buttons ──────────────────────────────────────── */
.stButton > button[kind="secondary"],
.stButton > button[data-testid="baseButton-secondary"] {{
    border-color: {GRIFFIN_RED} !important;
    color:        {GRIFFIN_RED} !important;
}}
.stButton > button[kind="secondary"]:hover {{
    background-color: {GRIFFIN_RED}18 !important;
}}

/* ── Form submit button ─────────────────────────────────────── */
.stFormSubmitButton > button {{
    background-color: {GRIFFIN_RED} !important;
    border-color:     {GRIFFIN_RED} !important;
    color: white !important;
    font-weight: 600;
}}
.stFormSubmitButton > button:hover {{
    background-color: {DARK_RED} !important;
    border-color:     {DARK_RED} !important;
}}

/* ── Horizontal dividers ────────────────────────────────────── */
hr {{
    border-color: {LIGHT_GRAY};
    margin: 1em 0;
}}

/* ── Expander headers ───────────────────────────────────────── */
[data-testid="stExpander"] summary {{
    color: {DARK_GRAY};
    font-weight: 600;
}}
[data-testid="stExpander"] summary:hover {{
    color: {GRIFFIN_RED};
}}


/* ── Success / info alert left-border accent ────────────────── */
[data-testid="stAlert"][data-baseweb="notification"] {{
    border-left-width: 5px;
}}

/* ── Radio and checkbox accent ──────────────────────────────── */
[data-testid="stRadio"] label:hover,
[data-testid="stCheckbox"] label:hover {{
    color: {GRIFFIN_RED};
}}

/* ── Sidebar nav links (active page) ───────────────────────── */
[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background-color: {LIGHT_GRAY} !important;
    border-left: 3px solid {MEDIUM_GRAY};
    font-weight: 700;
}}

/* ── Progress bar ───────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {{
    background-color: {GRIFFIN_RED};
}}

/* ── Spinner ────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div > div {{
    border-top-color: {GRIFFIN_RED} !important;
}}
</style>
"""


def apply_branding() -> None:
    """
    Inject Axway CSS and place the logo in the sidebar.

    Call once per page, immediately after st.set_page_config().
    """
    st.markdown(_CSS, unsafe_allow_html=True)

    # Sidebar logo - use_container_width keeps it responsive
    st.sidebar.image(LOGO_PATH, use_container_width=True)
