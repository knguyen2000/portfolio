"""
Data and constants for the About & Gallery pages.
"""

ABOUT_INTRO_VIDEO_URL = "https://github.com/knguyen2000/portfolio/raw/main/static/AboutMe.mp4"
PROJECTS_INTRO_VIDEO_URL = "https://github.com/knguyen2000/portfolio/raw/main/static/ProjectIntro.mp4"

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
    
    # USA
    "Virginia": [-78.4764, 38.0293], # Charlottesville
    "Washington DC": [-77.0369, 38.9072],
    "Maryland": [-76.4922, 38.9784], # Annapolis
    "New York": [-74.0060, 40.7128], # NYC
    "New Jersey": [-74.1724, 40.7357], # Newark
    "Pennsylvania": [-75.1652, 39.9526], # Philadelphia
    "Massachusetts": [-71.0589, 42.3601], # Boston
    "Florida": [-80.1918, 25.7617], # Miami
    "California": [-122.4194, 37.7749], # San Francisco
    "Illinois": [-87.6298, 41.8781], # Chicago
    "Colorado": [-104.9903, 39.7392], # Denver
}

TITLES = [
    {"title": "How it all started 🇻🇳"},
    {"title": "My first trip - New Zealand 🇳🇿"},
    {"title": "Summer in a city I have always dreamed of - Tokyo 🇯🇵"}, 
    {"title": "Undergrad life in Finland 🇫🇮 (🇭🇺, 🇵🇱, 🇩🇰, 🇩🇪, 🇸🇬)"},
    {"title": "Working in Vietnam and business trip to Denmark 🇻🇳 🇩🇰 (🇹🇭, 🇲🇾, 🇰🇷, 🇸🇪, 🇦🇹, 🇮🇹, 🇫🇷)"},
    {"title": "American Dream 🇺🇸"},
    {"title": "A bit more about me..."}
]

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
    "New Jersey": 5, "Pennsylvania": 5, "Massachusetts": 5, "Florida": 5, "California": 5, "Illinois": 5, "Colorado": 5
}

GALLERY_CAPTIONS = [
    "LOVE", "SEA", "CALM", "CHARM", "LAGO", "MOOD", "SIMPLE", 
    "LA LA LAND", "DREAM", "HANOK", "CITY GARDEN"
]

GALLERY_MAIN_TITLE = "GALLERY"
GALLERY_MAIN_SUBTITLE = "Just some random moments captured in my trips!"

GALLERY_SUBTITLES = [
    '"Auroras are the light created when Earth, forever unable to reach the Sun, draws in minute traces of solar plasma with the pull of its magnetic field. Perhaps this dazzling, mesmerizing light is but a tragic, fleeting illusion born from the Earth’s yearning for the Sun, fooling it into believing that a mere brush with the Sun has brought the two closer." - A quote from Can this love be translated?',
    "On this bench watching the world go by",
    "The harbor is busy, but there’s a sense of hygge here that you just can't find anywhere else",
    "Timeless, historic charm that makes you want to wander around for hours just looking at the buildings",
    "Alpine air and turquoise water; how great to wake up to this",
    "Lost in a fairytale",
    "Happiness really is just a good cone of gelato",
    "Grow up seeing this exact street in a hundred different movies, and then you’re suddenly standing right in the middle of it",
    "A million lights and a million dreams",
    "Sometimes you just need to trade skyscrapers for mountains and busy streets for flower fields",
    "Will never get tired of how colorful this city is when the sun is out"
]

