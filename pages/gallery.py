import streamlit as st
import os
import base64
import random
from PIL import Image
from utils.sidebar import render_sidebar
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="Gallery", page_icon="🖼️")

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
        .block-container {
            padding: 0;
            max-width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

render_sidebar()

def get_image_data(path):
    """Returns base64 string, original dimensions (w, h), and filename."""
    try:
        with Image.open(path) as img:
            # Capture original size for ratio
            orig_w, orig_h = img.size
            
            # Resize if too large (Max 1200px) - Maintains aspect ratio
            img.thumbnail((1200, 1200))
            
            # Convert to efficient format (JPEG) for transfer
            # Convert RGBA to RGB if needed
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Save to Bytes
            import io
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            
            # Encode
            encoded = base64.b64encode(buffered.getvalue()).decode()
            b64 = f"data:image/jpeg;base64,{encoded}"
            
            # Return filename for captioning
            filename = os.path.basename(path)
            
            return b64, orig_w, orig_h, filename
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None, 0, 0, ""

def calculate_grid_coverage(img_w, img_h):
    """
    Calculates the best grid width (cols) and height (rows) 
    to fit the image into the 8x6 grid while maximizing coverage.
    """
    if img_h == 0: return 4, 3
    
    aspect = img_w / img_h
    
    # Grid limits
    MAX_COLS = 8
    MAX_ROWS = 6
    
    best_w, best_h = 4, 3
    best_score = float('inf')
    
    for c in range(4, MAX_COLS + 1):
        for r in range(3, MAX_ROWS + 1):
            visual_ar = (c / r) * 1.333
            diff = abs(visual_ar - aspect)
            
            if diff < best_score:
                best_score = diff
                best_w = c
                best_h = r
                
    if aspect > 1.8:
        best_w = 8
        best_h = 4 
    
    if aspect < 0.6:
        best_w = 4
        best_h = 6
        
    return best_w, best_h

def generate_gallery_html(image_data_list):
    
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;900&display=swap');
        
        :root { 
            --bg-color: #f4f4f4; 
            --line-color: rgba(17, 17, 17, 0.2); 
            --accent-pink: #ff007f; 
        }
        
        body { 
            margin: 0; 
            padding: 0; 
            overflow-x: hidden; 
            background-color: var(--bg-color); 
            font-family: 'Montserrat', sans-serif; 
        }
        
        /* GRAIN OVERLAY */
        .grain-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 9999; pointer-events: none;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
            opacity: 1; 
            mix-blend-mode: multiply;
        }

        /* FIXED BACKGROUND GRID */
        .fixed-grid-layer {
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            z-index: 0;
            pointer-events: none;
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            grid-template-rows: repeat(6, 1fr);
        }

        .pinned-section {
            height: 100vh; 
            width: 100vw; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            position: relative; 
            overflow: hidden;
            z-index: 1; /* Above fixed grid */
        }
        
        /* CONTENT GRID (For placement logic) */
        .grid-checkerboard {
            display: grid;
            width: 100vw; 
            height: 100vh;
            position: absolute; 
            top: 0; 
            left: 0;
            grid-template-columns: repeat(8, 1fr);
            grid-template-rows: repeat(6, 1fr);
        }

        @media (max-width: 1024px) {
            .fixed-grid-layer, .grid-checkerboard {
                grid-template-columns: repeat(6, 1fr);
                grid-template-rows: repeat(8, 1fr);
            }
        }
        
        @media (max-width: 768px) {
            .fixed-grid-layer, .grid-checkerboard {
                grid-template-columns: repeat(4, 1fr);
                grid-template-rows: repeat(8, 1fr);
            }
        }

        /* DEFAULT TILE (Background Grid) */
        .grid-tile {
            position: relative; 
            border: 1px solid var(--line-color);
            display: flex; 
            align-items: center; 
            justify-content: center;
            background: transparent;
        }
        
        /* IMAGE TILES */
        .image-part {
            border: none !important; 
        }
        
        /* TEXT STYLES */
        .tile-text-wrapper {
             display: flex;
             flex-direction: column;
             align-items: flex-start;
             justify-content: flex-end; /* Align bottom for text block */
             padding: 20px;
             border: none !important; 
             pointer-events: none;
        }

        .tile-text-main {
            font-weight: 900;
            font-size: clamp(3rem, 6vw, 8rem);
            line-height: 0.85;
            text-transform: uppercase;
            color: #111;
            margin-bottom: 10px;
            letter-spacing: -2px;
            display: block;
        }
        
        .tile-text-sub {
            font-weight: 400;
            font-size: clamp(0.8rem, 1.2vw, 1.2rem);
            line-height: 1.4;
            color: #444;
            display: block;
            max-width: 650px;
            text-transform: none; /* Subtitle is normal text */
        }

        .image-wrapper {
            display: grid; 
            gap: 0;
            height: 100%;
            width: 100%;
        }
        
        .tile-img {
            position: absolute; 
            object-fit: cover; 
            display: block;
        }

        /* SCROLL INDICATOR */
        .scroll-indicator {
            position: fixed;
            bottom: 40px;
            right: 40px;
            z-index: 100;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 15px;
            mix-blend-mode: difference;
            opacity: 1; /* Start visible */
        }
        
        .scroll-text {
            writing-mode: vertical-rl;
            text-orientation: mixed;
            font-size: 0.8rem;
            letter-spacing: 2px;
            text-transform: lowercase;
            font-weight: 500;
            color: #fff; /* Difference mode makes this contrasting */
        }
        
        .scroll-arrow {
            font-size: 1.5rem;
            color: #fff;
        }
        
    </style>
    """
    
    # Generate Fixed Background Grid (48 tiles)
    bg_grid_html = f"""
    <div class="fixed-grid-layer">
        {"".join([f'<div class="grid-tile"></div>' for _ in range(48)])}
    </div>
    """
    
    sections = ""
    
    # Abstract captions
    CAPTIONS = [
        "LOVE", "SEA", "CALM", "CHARM", "LAGO", "MOOD", "SIMPLE", 
        "LA LA LAND", "DREAM", "HANOK", "CITY GARDEN"
    ]
    
    # Random subtitles
    SUBTITLES = [
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
    
    for idx, (b64, w, h, fname) in enumerate(image_data_list):
        cols, rows = calculate_grid_coverage(w, h)
        GRID_COLS = 8
        GRID_ROWS = 6
        
        # Calculate content index early for layout overrides
        content_idx = -1
        if idx > 0:
             content_idx = idx - 1

        # PLACEMENT LOGIC
        mode = idx % 6
        
        if mode == 0: # Top Left
            col_start = 1
            row_start = 1
        elif mode == 1: # Bottom Right
            col_start = GRID_COLS - cols + 1
            row_start = GRID_ROWS - rows + 1
        elif mode == 2: # Top Right
            col_start = GRID_COLS - cols + 1
            row_start = 1
        elif mode == 3: # Bottom Left
            col_start = 1
            row_start = GRID_ROWS - rows + 1
        elif mode == 4: # Top Center
            col_start = (GRID_COLS - cols) // 2 + 1
            row_start = 1
        else: # Bottom Center
            col_start = (GRID_COLS - cols) // 2 + 1
            row_start = GRID_ROWS - rows + 1
        
        # Override for specific slides
        if content_idx == 9:
             # Pic in upper right
             col_start = GRID_COLS - cols + 1
             row_start = 1
            
        col_start = max(1, min(col_start, GRID_COLS - cols + 1))
        row_start = max(1, min(row_start, GRID_ROWS - rows + 1))
        
        # Determine Initial Visibility
        is_first = (idx == 0)
        
        clip_path_val = "inset(0% 0 0 0)" if is_first else "inset(100% 0 0 0)"
        text_opacity = "1" if is_first else "0"
        text_transform = "translateY(0px)" if is_first else "translateY(20px)"

        # Image Tiles
        inner_tiles = ""
        for r_i in range(rows):
            for c_i in range(cols):
                style = f"""
                    position: absolute;
                    width: {cols * 100}%;
                    height: {rows * 100}%;
                    left: {-c_i * 100}%;
                    top: {-r_i * 100}%;
                    object-fit: cover;
                    clip-path: {clip_path_val};
                """
                style = " ".join(style.split()) 
                inner_tiles += f"""
                <div class="grid-tile image-part" style="position: relative; overflow: hidden;">
                    <img src="{b64}" class="tile-img" style="{style}">
                </div>
                """
        
        wrapper_style = f"grid-column: {col_start} / span {cols}; grid-row: {row_start} / span {rows}; grid-template-columns: repeat({cols}, 1fr); grid-template-rows: repeat({rows}, 1fr);"
        image_unit_html = f'<div class="image-wrapper" style="{wrapper_style}">{inner_tiles}</div>'
        
        # Text Placement
        img_center_x = col_start + (cols/2)
        if img_center_x <= GRID_COLS / 2:
            txt_col = GRID_COLS - 2
        else:
            txt_col = 1
            
        img_center_y = row_start + (rows/2)
        if img_center_y < GRID_ROWS / 2:
             txt_row = GRID_ROWS - 1
        else:
             txt_row = 2
             
        txt_col = max(1, min(txt_col, GRID_COLS - 2))
        txt_row = max(1, min(txt_row, GRID_ROWS - 1))
        
        # Content Selection
        if is_first:
            main_text = "GALLERY"
            sub_text = "Just some random moments!!!!"
        else:
            main_text = CAPTIONS[content_idx % len(CAPTIONS)]
            sub_text = SUBTITLES[content_idx % len(SUBTITLES)]

        # Override for specific slides
        extra_wrapper_style = ""
        extra_block_style = ""
        
        if content_idx == 0:
             txt_row = 3
        
        if content_idx == 3:
             txt_col = 3
             txt_row = 5
             extra_wrapper_style = "align-items: center;"
             extra_block_style = "text-align: center; align-items: center; display: flex; flex-direction: column;"

        if content_idx == 4:
            # Center horizontally
            txt_col = 3 # Span 4 cols for center
            txt_row = 2
            extra_wrapper_style = "align-items: center; justify-content: flex-start;"
            extra_block_style = "text-align: center; align-items: center; display: flex; flex-direction: column;"
        elif content_idx == 9:
            # Text in lower left
            txt_col = 2
            txt_row = GRID_ROWS - 1
            extra_wrapper_style = "align-items: flex-start; justify-content: flex-end;"
            extra_block_style = "text-align: left;"

        elif content_idx == 10:
             txt_row = 1
             txt_col = 1

        text_html = f"""
        <div class="grid-tile tile-text-wrapper" style="grid-column: {txt_col} / span 4; grid-row: {txt_row} / span 2; border: none; pointer-events: none; {extra_wrapper_style}">
             <div class="text-block" style="opacity: {text_opacity}; transform: {text_transform}; {extra_block_style}">
                <span class="tile-text-main">{main_text}</span>
                <span class="tile-text-sub">{sub_text}</span>
             </div>
        </div>
        """
        
        section_content = f"""
        <section class="pinned-section" id="img-{idx}">
            <div class="grid-checkerboard" style="z-index: 2; pointer-events: none;">
                {image_unit_html}
            </div>
            <div class="grid-checkerboard" style="z-index: 3; pointer-events: none;">
                 {text_html}
            </div>
        </section>
        """
        sections += section_content

    js = """
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/ScrollTrigger.min.js"></script>
    <script>
        gsap.registerPlugin(ScrollTrigger);
        
        // Hide scroll indicator on first scroll
        gsap.to(".scroll-indicator", {
            scrollTrigger: {
                trigger: "body",
                start: "100px top",
                toggleActions: "play none none reverse"
            },
            opacity: 0,
            duration: 0.5,
            pointerEvents: "none"
        });

        const sections = document.querySelectorAll('.pinned-section');
        
        sections.forEach((section, i) => {
            const q = gsap.utils.selector(section);
            
            const images = q('.tile-img');
            const texts = q('.text-block'); // Updated selector
            
            const tl = gsap.timeline({
                scrollTrigger: {
                    trigger: section,
                    start: "top top",
                    end: "+=250%", 
                    pin: true,
                    scrub: 1.5,
                    snap: {
                        snapTo: "labelsDirectional",
                        duration: {min: 0.4, max: 0.8},
                        delay: 0.1,
                        ease: 'power1.inOut'
                    }
                }
            });
            
            tl.addLabel("start");
            
            // --- ENTRANCE (Clip Reveal) ---
            if (i !== 0) {
                if(images.length) {
                    tl.fromTo(images, 
                        { clipPath: 'inset(100% 0 0 0)', scale: 1.1 }, 
                        { 
                            clipPath: 'inset(0% 0 0 0)',
                            scale: 1, 
                            duration: 3, 
                            ease: 'power3.inOut',
                            stagger: 0.1
                        }, 0
                    );
                }
                
                if(texts.length) {
                    tl.fromTo(texts,
                        { opacity: 0, y: 80 },
                        { 
                            opacity: 1, y: 0, 
                            duration: 3,
                            ease: "power2.out"
                        }, 0.5
                    );
                }
            }
            
            tl.addLabel("showcase"); 
            
            // --- HOLD ---
            tl.to({}, { duration: 4 }); 
            
            // --- EXIT ---
            if(texts.length) {
                 tl.to(texts, { opacity: 0, y: -50, duration: 2 }, ">");
            }
            
            if(images.length) {
                 tl.to(images, { 
                    scale: 0.95,
                    filter: "grayscale(100%)",
                    opacity: 0.5, 
                    duration: 3,
                    ease: 'power2.inOut',
                    stagger: 0.1
                 }, "<0.2");
            }
            
            tl.addLabel("end");
        });
        
        ScrollTrigger.refresh();
    </script>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gallery</title>
        {css}
    </head>
    <body>
        <div class="grain-overlay"></div>
        <div class="scroll-indicator">
            <div class="scroll-text">scroll down</div>
            <div class="scroll-arrow">↓</div>
        </div>
        {bg_grid_html}
        {sections}
        {js}
    </body>
    </html>
    """
    return full_html

gallery_dir = "gallery"
if not os.path.exists(gallery_dir):
    st.error("Gallery folder missing")
else:
    files = sorted([os.path.join(gallery_dir, f) for f in os.listdir(gallery_dir) if f.lower().endswith(('.png','.jpg','.jpeg'))])
    if not files:
        st.warning("No images")
    else:
        # Load data
        img_data = []
        for f in files:
            d = get_image_data(f)
            if d[0]: img_data.append(d)
        
        # Duplicate for demo effectiveness if needed
        if len(img_data) < 3:
            img_data = img_data * 2
            
        html = generate_gallery_html(img_data)
        components.html(html, height=900, scrolling=True)

