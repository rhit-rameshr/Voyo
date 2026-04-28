from __future__ import annotations
from pathlib import Path
import base64
import sys
import streamlit as st
from streamlit_option_menu import option_menu
from PIL import Image

#Make local modules importable no matter how Streamlit launches the app 
sys.path.append(str(Path(__file__).resolve().parent))
import trips          # local trips.py
import log_in         # local log_in.py 
import recommendations

import log_in

if not log_in.cookies.ready():
    st.stop()


# App config
logo_image = Image.open("images/voyoLogo.png")

st.set_page_config(
    page_title="Voyo",
    page_icon=logo_image,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Give buttons a consistent “Voyo green” vibe.
st.markdown("""
<style>
.stButton > button, .stDownloadButton > button, form button {
  background-color: #228B22 !important;
  color: #ffffff !important;
  border: none !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, form button:hover {
  background-color: #1e7c1e !important;
  color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# Lock the sidebar open & hide collapse controls + top header
# Goal: always-visible sidebar (no chevrons), plus hide Streamlit’s default header/toolbar.
st.markdown("""
<style>
/* Always show the sidebar, never collapsible */
[data-testid="stSidebar"] {
  display: block !important;
  visibility: visible !important;
  opacity: 1 !important;
  transform: none !important;
  width: 18rem !important;
  min-width: 18rem !important;
}
/* Hide all known collapse/chevron controls */
button[title="Toggle sidebar"],
button[aria-label="Toggle sidebar"],
button[title="Hide sidebar"],
button[aria-label="Hide sidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {
  display: none !important;
}
/* Hide Streamlit top header/toolbar (white strip) */
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
  display: none !important;
}
/* Remove extra top padding in main area */
.block-container { padding-top: 0 !important; }
[data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }
</style>
""", unsafe_allow_html=True)

# Session defaults
# We park a few keys in session_state so pages can “talk” to each other.
st.session_state.setdefault("active_trip_id", None)
st.session_state.setdefault("active_trip_name", None)
st.session_state.setdefault("user", None)  # set by log_in.render()

# App constants
# These are just easy-to-tweak bits that affect the look/feel.
home_bg   = "images/homeBackground.jpg"
logo_path = "images/voyoLogo.png"
slogan    = "Turn Moments into Maps"
width_pix = 260

# Helpers 
def set_page_background(image: str | Path | None, overlay: float = 0.30) -> None:
    """Paint a full-page background image. overlay ∈ [0..1] → darkens for readability."""
    if not image:
        # No image? Guess we can just reset to Streamlit’s default background then
        st.markdown(
            """
            <style>
              [data-testid="stAppViewContainer"] {
                  background-image: none !important;
                  background-color: var(--background-color) !important;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )
        return

    path = Path(image)
    if not path.exists():
        st.warning(f"Background image not found: {path}")
        return

    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode()

    # Inline the image via data URI → we can avoids extra network hops and works in Streamlit
    st.markdown(
        f"""
        <style>
          [data-testid="stAppViewContainer"] {{
            background:
              linear-gradient(rgba(0,0,0,{overlay}), rgba(0,0,0,{overlay})),
              url("data:{mime};base64,{data}") !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_home_hero(logo_path: str, slogan: str, width_px: int = 240) -> None:
    """Simple centered “hero” section → logo on top, tagline underneath."""
    p = Path(logo_path)
    if not p.exists():
        st.warning(f"Logo not found: {p}")
        return

    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    b64  = base64.b64encode(p.read_bytes()).decode()

    st.markdown(
        f"""
        <style>
          .hero {{
            min-height: 72vh;
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            gap: 0.75rem; text-align: center;
          }}
          .hero img {{
            width: {width_px}px; height: auto;
            filter: drop-shadow(0 8px 24px rgba(0,0,0,.35));
          }}
          .hero .tagline {{
            margin: 0; font-weight: 700; letter-spacing: .02em;
            font-size: clamp(1.1rem, 2.5vw, 1.8rem);
            color: white;
          }}
        </style>
        <div class="hero">
          <img src="data:{mime};base64,{b64}" alt="Voyo logo"/>
          <div class="tagline">{slogan}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar_nav() -> tuple[str, str]:
    """Draw the sidebar menu and tell us what the user picked.
    Returns (selected_label, account_tab_label)."""
    user = st.session_state.get("user")
    logged_in = user is not None
    # If logged in → show their name in the menu; otherwise show “Log In”.
    account_label = user["name"] if logged_in else "Log In"
    account_icon  = "person-circle" if logged_in else "box-arrow-in-right"

    options = ["Home", account_label, "Trips", "Recommendations", "About Us"]
    icons   = ["house", account_icon, "map",  "stars", "info-circle", "gear"]

    with st.sidebar:
        choice = option_menu(
            menu_title=None,
            options=options,
            icons=icons,
            orientation="vertical",
            default_index=0,
            key="main_menu",
            styles={
                "container": {"padding": "0", "background-color": "transparent", "width": "100%"},
                "icon": {"font-size": "20px"},
                "nav-link": {"font-size": "16px", "padding": "8px 12px", "margin": "2px 0", "--hover-color": "rgba(0,0,0,0.05)"},
                "nav-link-selected": {"background-color": "#02ab21", "color": "white", "border-radius": "8px"},
            },
        )

    return choice, account_label

# UI 
selected, account_tab_label = render_sidebar_nav()

# Quick landing page:
if selected == "Home":
    set_page_background(home_bg, overlay=0.35)   # darker overlay → punchier white text
    render_home_hero(logo_path=logo_path, slogan=slogan, width_px=width_pix)
else:
    set_page_background(None)  


AUTH_REQUIRED = {"Trips", "Recommendations"}


if selected in AUTH_REQUIRED and not st.session_state.get("user"):
    st.title("Please Log In")
    st.info("This page is locked. Log in to continue.")
    log_in.render()
    st.stop()


# Routing

def page_about():
    st.header("About Us")
    st.write("We're a team of 5 travel enthusiasts who built Voyo to help people turn their travel memories into personalized recommendations. We believe that the best travel advice comes from your own experiences, and Voyo is our way of making that advice actionable and shareable. Whether you're looking for your next adventure or want to relive past trips, Voyo is here to inspire your wanderlust!")


# The router: menu label -> function to call.
PAGES = {
    "Trips":            lambda: trips.render(),
    "Log In":           lambda: log_in.render(),
    "Recommendations":  lambda: recommendations.render(),
    "About Us":         page_about
}

# If they clicked the dynamic account tab (either “Log In” or their username), jump to the login page.
# Otherwise → route to the selected page if we have a handler.
if selected == account_tab_label:
    log_in.render()
elif selected in PAGES:
    PAGES[selected]()
