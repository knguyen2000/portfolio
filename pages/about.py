import streamlit as st
import pydeck as pdk
import pandas as pd
import os

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="About Me", page_icon="✈️")

# --- HIDE DEFAULT SIDEBAR ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap');

    /* Journey Text Styling - Glassmorphism Cards */
    .journey-card {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 25px;
        margin-left: 20px; /* Reduced from 50px since node is gone */
        position: relative;
        transition: transform 0.2s, border-color 0.2s;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .journey-card:hover {
        border-color: var(--primary-color);
        transform: translateX(5px);
    }
    
    /* The Thread Line */
    .journey-line {
        position: absolute;
        left: 20px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: linear-gradient(to bottom, #00f2ea, #ff00ff);
        z-index: 0;
    }
    
    /* The Bead/Node */
    .journey-node {
        position: absolute;
        left: -59px;
        top: 25px;
        width: 20px;
        height: 20px;
        background: #000;
        border: 2px solid #00f2ea;
        border-radius: 50%;
        z-index: 1;
        box-shadow: 0 0 10px #00f2ea;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
    }
    
    .chapter-title {
        color: var(--primary-color);
        font-weight: bold;
        font-size: 1.2em;
        margin-bottom: 10px;
        font-family: 'Noto Color Emoji', sans-serif;
    }
    
    .journey-text {
        font-family: 'Inter', sans-serif;
        line-height: 1.7;
        font-size: 1.05em;
        color: inherit;
    }
</style>
""", unsafe_allow_html=True)

# --- MAP DATA ---
# Coordinates (Lat, Lon)
LOCATIONS = {
    # Home
    "Vung Tau": [107.0843, 10.3460],
    
    # Asia
    "Japan": [139.6917, 35.6895], # Tokyo
    "Singapore": [103.8198, 1.3521],
    "Poland": [21.0122, 52.2297], # Warsaw
    "Thailand": [100.5018, 13.7563], # Bangkok
    "Malaysia": [101.6869, 3.1390], # Kuala Lumpur
    "South Korea": [126.9780, 37.5665], # Seoul
    
    # Oceania
    "New Zealand": [174.7762, -41.2865], # Wellington
    
    # Europe
    "Finland": [24.9384, 60.1699], # Helsinki
    "Estonia": [24.7536, 59.4370], # Tallinn
    "Hungary": [19.0402, 47.4979], # Budapest
    "Denmark": [12.5683, 55.6761], # Copenhagen
    "Germany": [8.6821, 50.1109], # Frankfurt
    "Sweden": [12.6945, 56.0465], # Helsingborg
    "Austria": [16.3738, 48.2082], # Vienna
    "Italy": [12.4964, 41.9028], # Rome
    "France": [2.3522, 48.8566], # Paris
    
    # USA States
    "Virginia": [-78.4764, 38.0293], # Charlottesville
    "Washington DC": [-77.0369, 38.9072],
    "Maryland": [-76.4922, 38.9784], # Annapolis
    "New York": [-74.0060, 40.7128], # NYC
    "New Jersey": [-74.1724, 40.7357], # Newark
    "Pennsylvania": [-75.1652, 39.9526], # Philadelphia
    "Massachusetts": [-71.0589, 42.3601], # Boston
    "Florida": [-80.1918, 25.7617], # Miami
    "California": [-122.4194, 37.7749], # San Francisco
}

# --- HELPER FUNCTIONS ---

def load_text():
    """Reads the biography from file"""
    path = os.path.join("data", "my_life.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "Biography not found."

def get_map_view(view_state_name):
    """Returns PyDeck view state based on active chapter"""
    states = {
        "Intro": pdk.ViewState(latitude=20, longitude=50, zoom=1, pitch=0), # World View
        "NZ": pdk.ViewState(latitude=-40, longitude=174, zoom=5, pitch=40),
        "Japan": pdk.ViewState(latitude=36, longitude=139, zoom=6, pitch=50),
        "Europe": pdk.ViewState(latitude=50, longitude=15, zoom=4, pitch=30),
        "USA": pdk.ViewState(latitude=38, longitude=-95, zoom=3.5, pitch=0), # Centered on US
    }
    return states.get(view_state_name, states["Intro"])

# --- MAIN LAYOUT ---
with st.sidebar:
    if os.path.exists("data/KhuongProfile.jpeg"):
        st.image("data/KhuongProfile.jpeg", width=250)
    
    st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
    <div style="text-align: center; margin-top: -10px;">
        <h2 style="margin-bottom: 5px;">Khuong Nguyen</h2>
        <p style="font-weight: bold; margin-bottom: 5px;">Master CS @ UVA</p>
        <p style="font-style: italic; font-size: 0.9em; color: inherit; opacity: 0.7;">Research Interest: NLP, LLM, and Trustworthy AI</p>
        <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px;">
            <a href="https://www.linkedin.com/in/khuongng/" target="_blank" style="text-decoration: none; color: #0077b5; font-size: 28px;">
                <i class="fa-brands fa-linkedin"></i>
            </a>
            <a href="https://github.com/knguyen2000" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
                <i class="fa-brands fa-github"></i>
            </a>
            <a href="mailto:khuongnguyen211000@gmail.com" style="text-decoration: none; color: #ea4335; font-size: 28px;">
                <i class="fa-solid fa-envelope"></i>
            </a>
            <a href="https://drive.google.com/file/d/1ZFrhWioHuzSf3SUmp-l_wn0aed4d86vd/view?usp=sharing" target="_blank" style="text-decoration: none; color: inherit; font-size: 28px;">
                <i class="fa-solid fa-address-card"></i>
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.page_link("app.py", label="Chat", icon="🤖", use_container_width=True)

st.title("🌏 As you can see, I love traveling...")
st.caption("Click on any dot in the map to jump to certain part of my story!")

# --- MAIN CONTENT LAYOUT ---

# 1. MAP SECTION
current_view = get_map_view("Intro")

# LOCATIONS dict to list for PyDeck
ICON_DATA = []
for name, coords in LOCATIONS.items():
    # Vung Tau (Home) = Magenta, Others = Cyan
    color = [255, 0, 255] if name == "Vung Tau" else [0, 255, 255] 
    ICON_DATA.append({"name": name, "coordinates": coords, "color": color})

# Convert to DataFrame for PyDeck Selection
df_icons = pd.DataFrame(ICON_DATA)

layer_scatter = pdk.Layer(
    "ScatterplotLayer",
    id="journey_locations",
    data=df_icons,
    get_position="coordinates",
    get_fill_color="color", 
    get_radius=5000,
    pickable=True,
    auto_highlight=True, 
    opacity=0.8,
    stroked=True,
    filled=True,
    radius_min_pixels=4,
    radius_max_pixels=12,
    get_line_color=[255, 255, 255],
    line_width_min_pixels=1,
)

deck = pdk.Deck(
    map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    initial_view_state=current_view,
    layers=[layer_scatter],
    tooltip={"text": "{name}"}
)

# Render map with selection enabled
event = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object")

st.markdown("---")

# NARRATIVE SECTION
st.markdown("### 📜 My Story")
full_text = load_text()
chunks = full_text.split("\n\n")

# Map chunks to chapters
TITLES = [
    {"title": "How it all started 🇻🇳"},
    {"title": "My first trip - New Zealand 🇳🇿"},
    {"title": "Summer in a city I have always dreamed of - Tokyo 🇯🇵"}, 
    {"title": "Undergrad life in Finland 🇫🇮 (🇭🇺, 🇵🇱, 🇩🇰, 🇩🇪, 🇸🇬)"},
    {"title": "Working in Vietnam and business trip to Denmark 🇻🇳 🇩🇰 (🇹🇭, 🇲🇾, 🇰🇷, 🇸🇪, 🇦🇹, 🇮🇹, 🇫🇷)"},
    {"title": "American Dream 🇺🇸"},
    {"title": "A bit more about me..."}
]

# Map locations to chapter indices for auto-scrolling
LOCATION_TO_CHAPTER = {
    "Vung Tau": 0,
    "New Zealand": 1,
    "Japan": 2,
    "Finland": 3, "Hungary": 3, "Poland": 3, "Singapore": 3,
    "Germany": 3, "Estonia": 3, "Denmark": 4,
    "Vietnam": 4,
    "Thailand": 4, "Malaysia": 4, "South Korea": 4, "Sweden": 4, 
    "Austria": 4, "Italy": 4, "France": 4, 
    "Virginia": 5, "Washington DC": 5, "Maryland": 5, "New York": 5,
    "New Jersey": 5, "Pennsylvania": 5, "Massachusetts": 5, "Florida": 5, "California": 5
}

# Container for the thread line
st.markdown('<div style="position: relative; padding-left: 20px; border-left: 2px solid rgba(0, 242, 234, 0.3); margin-left: 10px;">', unsafe_allow_html=True)

for i, chunk in enumerate(chunks):
    if len(chunk) > 50: # Filter empty lines
        header = TITLES[i] if i < len(TITLES) else {"title": "Chapter " + str(i+1)}
        
        # Format the chunk
        lines = chunk.split('\n')
        formatted_html = ""
        in_list = False
        import re # Import locally to avoid top-level clutter
        
        for line in lines:
            stripped = line.strip()
            # Handle Bold Syntax
            stripped = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)
            
            # Handle Markdown Links
            stripped = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank" style="color: #007bff; text-decoration: none; font-weight: bold;">\1</a>', stripped)
            
            # Check for bullet points
            if stripped.startswith("-") or stripped.startswith("*"):
                if not in_list:
                    formatted_html += "<ul>"
                    in_list = True
                # Remove the bullet marker and whitespace
                content = stripped.lstrip("-*").strip()
                formatted_html += f"<li>{content}</li>"
            else:
                if in_list:
                    formatted_html += "</ul>"
                    in_list = False
                formatted_html += f"{stripped}<br><br>"
        
        if in_list:
            formatted_html += "</ul>"
        
        st.markdown(f"""
        <div id="chapter-{i}" style="margin-bottom: 40px; position: relative;">
            <div class='journey-card' style="margin-top: -10px;">
                <div class='chapter-title'>{header['title']}</div>
                <div class='journey-text'>{formatted_html}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# --- HANDLE MAP SELECTION ---
if event.selection and "objects" in event.selection:
    
    # Get the list of selected objects from the specific layer
    selected_objects = event.selection["objects"].get("journey_locations")
    if not selected_objects and event.selection["objects"]:
        selected_objects = list(event.selection["objects"].values())[0]

    if selected_objects:
        location_name = selected_objects[0].get("name")
        chapter_idx = LOCATION_TO_CHAPTER.get(location_name)
        
        if chapter_idx is not None:             
             script = f"""
                <script>
                    function scrollToChapter() {{
                        try {{
                            var doc = window.parent.document;
                            var element = doc.getElementById('chapter-{chapter_idx}');
                            
                            if(element) {{
                                element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                                // Visual feedback: Flash the card
                                var card = element.querySelector('.journey-card');
                                if (card) {{
                                    card.style.transition = "box-shadow 0.5s ease-in-out";
                                    var origShadow = card.style.boxShadow;
                                    card.style.boxShadow = "0 0 30px rgba(255, 0, 255, 0.8)"; // Magenta flash
                                    setTimeout(function() {{
                                        card.style.boxShadow = origShadow;
                                    }}, 1500);
                                }}
                            }}
                        }} catch(e) {{
                            console.error("Scroll error:", e);
                        }}
                    }}
                    
                    // Progressive Retries
                    scrollToChapter();
                    setTimeout(scrollToChapter, 500);
                    setTimeout(scrollToChapter, 1500);
                </script>
             """
             st.components.v1.html(script, height=0)
