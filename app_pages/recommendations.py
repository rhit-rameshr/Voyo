import streamlit as st
import urllib.request
import json
import re
import requests

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

def render():
    st.title("Recommendations")
    
    prompt = recommendation_helper()

    
    if prompt is None:
        return
    
    if st.button("Get Recommendations"):
        with st.spinner("Generating recommendations..."):
            recs = call_api(prompt)
        if recs:
            st.session_state.rec_results = recs

    if st.session_state.get("rec_results"):
        for rec in st.session_state.rec_results:
            st.subheader(rec["destination"])
            st.write(f"*{rec['tagline']}*")
            st.write("**Reasons to visit:**")
            for reason in rec["reasons"]:
                st.write(f"- {reason}")
            img_url = _get_rec_image(rec["image_query"])
            st.image(img_url, use_container_width=True)
    

def recommendation_helper():
    trips = st.session_state.get("trips", [])
    if not trips:
        st.info("No trips found. Add a trip to get recommendations.")
        return None
    
    cities = set()
    categories = set()
    notes = []
    activities = set()
    hotels = set()
    flights = set()
    
    for trip in trips:
        if trip.get("notes"):
            notes.append(trip["notes"].strip())
        if trip.get("itinerary"):
            activities.update(item["title"].strip() for item in trip["itinerary"] if item.get("title"))
        for hotel in trip.get("hotels", []):
            if hotel.get("name"):
                hotels.add(hotel["name"].strip())
        for flight in trip.get("flights", []):
            if flight.get("to"):
                cities.add(flight["to"].strip())
        for place in trip.get("places", []):
            if place.get("category"):
                categories.add(place["category"].strip())
            if place.get("city"):
                cities.add(place["city"].strip())
            if place.get("name"):
                activities.add(place["name"].strip())
    
    data = {
        "cities": list(cities),
        "categories": list(categories),
        "notes": notes,
        "activities": list(activities),
        "hotels": list(hotels),
        "flights": list(flights),
    }
    
    prompt = (
        f"The user has visited these cities: {', '.join(data['cities']) or 'unknown'}. "
        f"They enjoy these types of activities: {', '.join(data['categories']) or 'unknown'}. "
        f"Specific things they've done: {', '.join(data['activities']) or 'unknown'}. "
        f"Hotels they've stayed at: {', '.join(data['hotels']) or 'unknown'}. "
        f"Their notes: {'; '.join(data['notes']) or 'none'}. "
        f"Based on this, recommend 6 new destinations they haven't visited yet."
    )
    
    return prompt

def call_api(prompt):
    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a travel recommendation expert. Return a JSON array only — no markdown, no extra text. Each object must have: destination (string), tagline (string), reasons (array of 3 strings), image_query (2-3 words for an image search e.g. 'kyoto temples')."},
            {"role": "user", "content": prompt}
        ]
    }).encode("utf-8")
    
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {st.secrets['GROQ_API_KEY']}",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        st.error(e.read().decode("utf-8"))
        return None

    raw = data["choices"][0]["message"]["content"]
    clean = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        st.error("Failed to parse API response.")
        st.code(raw)
        return None
    
def _get_rec_image(query):
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