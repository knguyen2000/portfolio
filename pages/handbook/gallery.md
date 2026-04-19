## 1. What Does This Page Do?
The `gallery.py` file reads photos from a specific folder, compresses them on the fly, and stacks them efficiently in a responsive grid. If a user clicks a photo, it opens in a full-screen cinematic view.

## 2. Processing Images with PIL

Inside `get_image_data()`, we use the Python Imaging Library (PIL). Before sending an image to the user's screen, we open the file, check its width and height (so we know if it is portrait or landscape), and shrink it if it is larger than 1200 pixels. We also convert everything to standard RGB JPEG format.

**Why we chose this:**
Photos straight from a phone or camera can be 10+ Megabytes each. If we have 30 photos on the gallery page, forcing the browser to download 300MB of data would crash the app or freeze the user's phone. By resizing them down to 1200px max and converting to JPEG on the server side, we save massive amounts of bandwidth.

**Tradeoff:**
PIL processing takes time. If you have 50 photos, the server has to open, process, and compress every single one before the page loads. 
*Solution:* We solved this by using `@st.cache_data`. This tells Streamlit to process the images *once* during the very first page load, and then memorize the result. Subsequent visits to the page are instant.

## 3. Building a Masonry Grid

Native Streamlit columns (`st.columns`) do not support "Masonry" layouts (where images seamlessly stack under each other regardless of height differences). If you use native columns, shorter images will leave awkward blank whitespace below them.

To fix this, we bypassed Streamlit's layout entirely:
1. We convert our processed images into `Base64` strings (translating an image into text data).
2. We inject custom HTML and CSS Grid code (`display: grid`, `grid-auto-flow: dense`).
3. We calculate `span_cols` and `span_rows` algorithmically using `calculate_grid_coverage(w, h)`. If an image is a tall panorama, we tell the CSS to make it span 2 columns and 1 row.
4. We feed the Base64 strings directly into `st.components.v1.html()`.

**Tradeoff:**
Injecting massive Base64 strings into HTML causes the browser memory to spike slightly, but the layout flexibility is worth it. Because we are bypassing Streamlit columns, any changes to the grid design (like adding padding) must be done by editing the massive CSS string block at the top of the file, not by using standard Streamlit methods.

## 4. Full-Screen Overlays Using Query Params

When you click on an image in our custom HTML grid, how do we tell Python to zoom in on it?
We embedded a tiny Javascript block inside the HTML. When you click, the Javascript uses `window.parent` to modify the URL parameters (adding `?selected_image=filename.jpg`).

Because the URL changed, Streamlit automatically reruns the Python script. The script detects `st.query_params.get("selected_image")` and knows to immediately render the fullscreen overlay UI instead of the grid.

---

## Maintaining

1. **The Loading Screen:** You will notice CSS for a `loader` object (`Curating Moments...`) that fades out. Because Base64 strings take a second for the browser to render, this loader hides the messy drawing process from the user. Do not remove it unless you want users to see images jumping around as they load.
2. **Missing Folders:** If the `data/gallery/` folder is empty, the logic throws a safe, friendly warning. Always ensure you add `.png` or `.jpg` or `.jpeg` files. No other extensions are allowed currently.
