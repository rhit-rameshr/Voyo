# app_pages/trips.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any
import re
import streamlit as st
import requests

# ---------- Storage paths  ----------
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
TRIPS_PATH = DATA_DIR / "trips.json"

# ---------- Persistence ----------
def _ensure_store():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TRIPS_PATH.exists():
        TRIPS_PATH.write_text("[]", encoding="utf-8")

def load_trips() -> list[dict]:
    _ensure_store()
    try:
        return json.loads(TRIPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_trips(trips: list[dict]) -> None:
    _ensure_store()
    TRIPS_PATH.write_text(json.dumps(trips, indent=2, ensure_ascii=False), encoding="utf-8")

# ---------- Session bootstrap ----------
# Runs at the start of every page load to make sure the session state
# has the keys that the rest of the page depends on.
def _bootstrap_state():
    if "trips" not in st.session_state:
        user_id = (st.session_state.get("user") or {}).get("id")
        st.session_state.trips = [t for t in load_trips() if t.get("user_id") == user_id]
    st.session_state.setdefault("show_add_trip", False)
    st.session_state.setdefault("trip_basics", None)

# ---------- Global Styles (forest green everywhere) ----------
def _apply_green_theme():
    st.markdown(
        """
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
        .trip-card img {
            border-radius: 10px;
            width: 100%;
            height: 200px;
            object-fit: cover;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------- Helpers ----------
def _delete_trip(idx: int):
    trips = st.session_state.trips
    if 0 <= idx < len(trips):
        trips.pop(idx)
        save_trips(trips)
        st.session_state.trips = trips
        st.rerun()

def _first_nonempty(*vals) -> str:
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return ""

def _make_cover_url(trip: dict) -> str:
    places = trip.get("places") or []

    city = ""
    for p in places:
        city = (p.get("city") or "").strip()
        if city:
            break

    keywords = []

    if city:
        keywords.append(city)

    if trip.get("name"):
        keywords.append(trip.get("name"))

    query = " ".join(keywords)
    query = re.sub(r"[^a-zA-Z ]", " ", query)
    query = re.sub(r"\s+", " ", query).strip()

    if not query:
        query = "travel destination"

    try:
        api_key = st.secrets["PEXELS_API_KEY"]

        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={
                "query": f"{query} travel landscape",
                "per_page": 1,
                "orientation": "landscape",
            },
            timeout=5,
        )

        if response.status_code != 200:
            raise Exception(f"Bad response: {response.status_code}")

        data = response.json()
        photos = data.get("photos", [])

        if photos and "src" in photos[0]:
            return photos[0]["src"]["large2x"]

    except Exception as e:
        st.warning(f"Pexels failed: {e}")

    return "https://images.pexels.com/photos/1051073/pexels-photo-1051073.jpeg"
    
def _trip_card(trip: dict, idx: int):
    title = trip.get("name", "Untitled Trip")
    start = trip.get("start_date") or "?"
    end   = trip.get("end_date") or "?"

    cover = _make_cover_url(trip)

    # Validate or regenerate
    if not (isinstance(cover, str) and cover.startswith("http")):
        cover = _make_cover_url(trip)

    with st.container(border=True):
        st.markdown('<div class="trip-card">', unsafe_allow_html=True)
        st.image(cover, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        c1, c2 = st.columns([0.8, 0.2])
        with c1:
            st.subheader(title)
            st.caption(f"{start} to {end}")
            if trip.get("departureCity"):
                st.caption(f"Departure City: **{trip['departureCity']}**")
            if trip.get("notes"):
                st.write(trip["notes"])
        with c2:
            st.download_button(
                "Export JSON",
                data=json.dumps(trip, indent=2, ensure_ascii=False),
                file_name=f"{title.replace(' ', '_')}.json",
                use_container_width=True,
            )
            if st.button("Delete", key=f"del_{idx}", use_container_width=True):
                _delete_trip(idx)

        with st.expander("Details", expanded=False):
            st.markdown("**Flights**")
            st.dataframe(trip.get("flights", []), use_container_width=True)
            st.markdown("**Hotels**")
            st.dataframe(trip.get("hotels", []), use_container_width=True)
            st.markdown("**Places to Visit**")
            st.dataframe(trip.get("places", []), use_container_width=True)
            st.markdown("**Itinerary**")
            st.dataframe(trip.get("itinerary", []), use_container_width=True)
    

def _normalize_date(v) -> str | None:
    if not v:
        return None
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]

def _normalize_table_dates(rows: List[Dict[str, Any]], date_cols: List[str]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        if not any(str(v).strip() for v in row.values()):
            continue
        r2 = dict(row)
        for c in date_cols:
            if c in r2:
                r2[c] = _normalize_date(r2[c])
        out.append(r2)
    return out

def _daterange_iso(start_iso: str, end_iso: str) -> List[str]:
    s, e = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    days = []
    cur = s
    while cur <= e:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days

def _auto_itinerary(basics: dict, flights, hotels, places) -> list[dict]:
    days = _daterange_iso(basics["start_date"], basics["end_date"])
    out = []
    for f in flights:
        if f.get("date"):
            title = "Flight"
            frm, to = (f.get("from") or "").strip(), (f.get("to") or "").strip()
            if frm or to:
                title += f" {frm} → {to}"
            if f.get("flight_no"):
                title += f" ({str(f['flight_no']).strip()})"
            out.append({"date": f["date"], "time": "08:00", "title": title, "location": to or "", "notes": f.get("airline", "")})
    for h in hotels:
        if h.get("check_in"):
            out.append({"date": h["check_in"], "time": "15:00", "title": f"Hotel check-in: {h.get('name', '')}".strip(": "), "location": h.get("address", "")})
        if h.get("check_out"):
            out.append({"date": h["check_out"], "time": "11:00", "title": f"Hotel check-out: {h.get('name', '')}".strip(": "), "location": h.get("address", "")})
    if places and days:
        slots = ["10:00", "15:00"]
        di, si = 0, 0
        for p in places:
            if not (p.get("name") or p.get("city")):
                continue
            out.append({
                "date": days[di % len(days)], "time": slots[si % 2],
                "title": p.get("name", "Visit"), "location": p.get("city", ""),
                "notes": (p.get("category") or "")
            })
            si += 1
            if si % 2 == 0:
                di += 1
    out.sort(key=lambda x: (x["date"], x["time"]))
    return out

# ---------- Two Forms ----------
def _form_basics():
    with st.form("trip_basic_form", clear_on_submit=False, border=True):
        st.markdown("### Trip Basics")
        name = st.text_input("Trip name*", placeholder="Thailand Adventure")
        cA, cB, cC = st.columns(3)
        with cA:
            start_date = st.date_input("Start date*", value=date.today())
        with cB:
            end_date = st.date_input("End date*", value=date.today())
        with cC:
            dep_city = st.text_input("Departure City*", placeholder="San Francisco")
        notes = st.text_area("Notes", placeholder="Anything important (visas, reminders, etc.)")

        col1, col2 = st.columns(2)
        with col1:
            next_btn = st.form_submit_button("Save Basics →")
        with col2:
            cancel = st.form_submit_button("Cancel")

    if cancel:
        st.session_state["show_add_trip"] = False
        st.session_state["trip_basics"] = None
        st.rerun()

    if not next_btn:
        return

    if not name.strip():
        st.error("Trip name required.")
        return
    if start_date > end_date:
        st.error("End date must be after start date.")
        return
    if not dep_city.strip():
        st.error("Departure City required.")
        return

    # Save basics to session state and rerun — render() will now show the details form
    st.session_state["trip_basics"] = {
        "name": name.strip(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "departureCity": dep_city.strip(),
        "notes": notes.strip(),
    }
    st.rerun()


def _form_details_and_save():
    with st.form("trip_details_form", clear_on_submit=False, border=True):
        st.markdown("### Trip Details")
        tabs = st.tabs(["Flights", "Hotels", "Places", "Itinerary"])

        with tabs[0]:
            flights = st.data_editor(
                [{"date": None, "from": "", "to": "", "airline": "", "flight_no": "", "conf#": ""}],
                num_rows="dynamic", use_container_width=True,
                column_config={"date": st.column_config.DateColumn("date")}
            )

        with tabs[1]:
            hotels = st.data_editor(
                [{"check_in": None, "check_out": None, "name": "", "address": "", "conf#": "", "phone": ""}],
                num_rows="dynamic", use_container_width=True,
                column_config={
                    "check_in": st.column_config.DateColumn("check_in"),
                    "check_out": st.column_config.DateColumn("check_out"),
                },
            )

        with tabs[2]:
            places = st.data_editor(
                [{"name": "", "city": "", "category": "", "notes": ""}],
                num_rows="dynamic", use_container_width=True,
                column_config={
                    "category": st.column_config.SelectboxColumn(
                        "category", options=["Sight", "Food", "Cafe", "Bar", "Shopping", "Nature", "Other"]
                    )
                },
            )

        with tabs[3]:
            itinerary = st.data_editor(
                [{"date": None, "time": "", "title": "", "location": "", "notes": ""}],
                num_rows="dynamic", use_container_width=True,
                column_config={"date": st.column_config.DateColumn("date")}
            )

        col1, col2 = st.columns(2)
        with col1:
            save = st.form_submit_button("Save Trip")
        with col2:
            cancel = st.form_submit_button("Cancel")

    if cancel:
        st.session_state["show_add_trip"] = False
        st.session_state["trip_basics"] = None
        st.rerun()

    if not save:
        return

    basics = st.session_state.get("trip_basics")
    if not basics:
        st.error("Trip basics missing — please go back and fill in the basics.")
        return

    flights   = _normalize_table_dates(flights,   ["date"])
    hotels    = _normalize_table_dates(hotels,    ["check_in", "check_out"])
    places    = _normalize_table_dates(places,    [])
    itinerary = _normalize_table_dates(itinerary, ["date"])

    if not any(row for row in itinerary if any(str(v).strip() for v in row.values())):
        itinerary = _auto_itinerary(basics, flights, hotels, places)

    trip = {**basics, "flights": flights, "hotels": hotels, "places": places, "itinerary": itinerary}
    
    trip["user_id"] = (st.session_state.get("user") or {}).get("id")


    try:
        # Always read fresh from disk to avoid stale state conflicts
        on_disk = load_trips()
        on_disk.append(trip)
        save_trips(on_disk)
        user_id = (st.session_state.get("user") or {}).get("id")
        st.session_state["trips"] = [t for t in on_disk if t.get("user_id") == user_id]
        st.session_state["show_add_trip"] = False
        st.session_state["trip_basics"] = None
    except Exception as e:
        st.error(f"Failed to save: {e}")
        return

    st.rerun()


# ---------- Public render ----------
def render():
    _bootstrap_state()
    _apply_green_theme()
    st.title("Trips")

    st.button("Add Trip", on_click=lambda: _toggle_add(True))

    if st.session_state["show_add_trip"]:
        if st.session_state.get("trip_basics") is None:
            # Step 1: fill in basics
            _form_basics()
        else:
            # Step 2: fill in details and save
            _form_details_and_save()

    trips = st.session_state["trips"]
    if not trips:
        st.info("No trips yet. Click **Add Trip** to get started.")
    else:
        st.markdown("### Your Trips")
        for i, t in enumerate(trips):
            _trip_card(t, i)


def _toggle_add(v: bool):
    st.session_state["show_add_trip"] = v