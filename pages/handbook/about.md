## 1. What Does This Page Do?
The `about.py` file renders an interactive 3D map and a scrolling biography. When a user clicks a location on the map, the text below automatically scrolls to the matching chapter of the biography.

## 2. PyDeck for 3D Maps

**How it works:**
We use a library called `pydeck` (Deck.gl) to draw the world map. We give it a list of locations (like "Tokyo" and "Finland") and it plots coordinates on a 3D globe.

**Why we chose it over simple 2D maps (like Folium):**
- **Performance:** PyDeck runs on WebGL, which means it uses your computer's graphics card to draw the map. This makes spinning and zooming very fast and smooth.
- **Visuals:** It looks much more premium and fits the dark mode aesthetic of a modern portfolio.

**The Tradeoff:**
- PyDeck is heavy. It takes a second to load on slow internet connections.
- The code for drawing layers (`ScatterplotLayer`) is complicated and hard to debug if a coordinate is wrong.

## 3. Auto-Scroll

Streamlit is generally designed to build dashboards, not storytelling websites. This means making a webpage automatically scroll down to a specific paragraph when you click a map pin is actually very difficult in pure Python.

We solved this by:
1. When you select a dot on the PyDeck map, Streamlit reruns the whole page.
2. We detect which location you clicked using `on_select="rerun"`.
3. We inject a hidden HTML script: `st.components.v1.html("<script>window.parent.document.getElementById('chapter-3').scrollIntoView();</script>")`

**Tradeoff:**
Because Streamlit does not natively support "Targeted Scrolling", we have to use Javascript injections. This works well, but if Streamlit updates their platform in the future and blocks `window.parent`, this scrolling feature will break and need to be rewritten.

## 5. Video Modal

At the top, we render an intro video. We do not use `st.video()`. Instead, we import `render_video_modal` from `utils.video_modal.py`.
**Tradeoff:** Standard `st.video()` pushes all content down safely, but looks boring. Our custom modal overlays on top of the screen, but requires managing complex CSS z-indexes.

---

## Maintaining:

Do not touch the PyDeck logic unless you know WebGL layers. If you just want to update the story, edit the `data/my_life.txt` file and update the variables in `config/about_data.py`.
