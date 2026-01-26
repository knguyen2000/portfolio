import streamlit as st
import os
from utils.sidebar import render_sidebar
from st_click_detector import click_detector
import html
import base64
import re

st.set_page_config(layout="wide", page_title="Projects", page_icon="🛋️")

# --- HIDE DEFAULT SIDEBAR ---
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
render_sidebar()

# --- HELPER FUNCTIONS ---
def load_projects(data_dir=os.path.join("data", "projects")):
    projects = []
    if not os.path.exists(data_dir):
        return projects
        
    for f in os.listdir(data_dir):
        if f.endswith(".md"):
            path = os.path.join(data_dir, f)
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
                
            # Naive parsing
            lines = content.split('\n')
            title = f"Project: {f}"
            abstract = "No abstract available."
            tags = []
            
            # Parsing State
            title_found = False
            
            for line in lines:
                stripped = line.strip()
                if not title_found and stripped.startswith("# "):
                    title = stripped.replace("# ", "").strip()
                    title_found = True
                    
                if stripped.startswith("**Tags:**"):
                    tag_str = stripped.replace("**Tags:**", "").strip()
                    if tag_str:
                         tags = [t.strip() for t in tag_str.split(",")]
            
            # Find Abstract (Between ## Abstract and the next ##)
            try:
                if "## Abstract" in content:
                    parts = content.split("## Abstract")
                    if len(parts) > 1:
                        sub_content = parts[1]
                        # Take until next header or end
                        abstract_part = sub_content.split("##")[0].strip()
                        if abstract_part:
                            abstract = abstract_part
            except:
                pass
                
            projects.append({
                "filename": f,
                "title": title,
                "abstract": abstract,
                "tags": tags,
                "path": path,
                "content": content
            })
    return projects

# --- MAIN UI ---

# Check Query Params for Detail View
current_project = st.query_params.get("project")

if current_project:
    # --- DETAIL VIEW ---
    project_path = os.path.join("data", "projects", current_project)
    
    if os.path.exists(project_path):
        with open(project_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        def inject_images_and_get_toc(markdown_text, base_path=os.path.dirname(project_path)):
            # Image Injection
            img_pattern = r'!\[(.*?)\]\((.*?)\)'
            
            def replace_img(match):
                alt_text = match.group(1)
                img_path = match.group(2)
                full_path = os.path.join(base_path, img_path)
                
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "rb") as img_f:
                            encoded_string = base64.b64encode(img_f.read()).decode()
                        
                        ext = os.path.splitext(full_path)[1].lower().replace(".", "")
                        mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                        
                        return f'<img src="data:{mime};base64,{encoded_string}" alt="{alt_text}" style="display: block; margin: 20px auto; max-width: 100%; border-radius: 8px;">'
                    except:
                        return match.group(0)
                return match.group(0) 

            processed_content = re.sub(img_pattern, replace_img, markdown_text)
            
            # Extract Headers for TOC and inject Anchors
            toc_entries = []
            final_lines = []
            existing_slugs = set()
            
            for line in processed_content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('#'):
                    # Determine level
                    level = len(line.split(' ')[0])
                    # Clean title
                    title_text = stripped.lstrip('#').strip()
                    
                    if title_text and level <= 3:
                        # Generate slug
                        raw_slug = title_text.lower().replace(' ', '-').replace('.', '')
                        cleaned_slug = re.sub(r'[^a-z0-9\-]', '', raw_slug)
                        
                        # Handle duplicates
                        slug = cleaned_slug
                        counter = 1
                        while slug in existing_slugs:
                            slug = f"{cleaned_slug}-{counter}"
                            counter += 1
                        existing_slugs.add(slug)
                        
                        toc_entries.append((level, title_text, slug))
                        
                        anchor_tag = f'<span id="{slug}"></span>'
                        final_lines.append(f'{anchor_tag}\n\n{line}')
                    else:
                        final_lines.append(line)
                else:
                    final_lines.append(line)
            
            return '\n'.join(final_lines), toc_entries

        content, toc_headers = inject_images_and_get_toc(content)
        
        # Reduce top padding of the page
        st.markdown("""
            <style>
                .block-container {
                    padding-top: 2rem !important;
                }
            </style>
        """, unsafe_allow_html=True)

        if toc_headers:
             # Columns: TOC (Left) | Content (Right)
            col_content, col_toc = st.columns([0.8, 0.2])
            
            with col_content:
                st.markdown(content, unsafe_allow_html=True)
            
            with col_toc:
                # sticky/fixed TOC
                st.markdown("""
                <style>
                    #toc-container {
                        position: fixed;
                        top: 4rem; 
                        right: 2rem; 
                        width: 20vw; 
                        max-width: 280px;
                        max-height: 85vh;
                        overflow-y: auto;
                        padding-left: 15px;
                        /* Ensure it doesn't hit content */
                        z-index: 100;
                    }
                    
                    /* Mobile: Static position */
                    @media (max-width: 800px) {
                        #toc-container {
                            position: static;
                            width: 100%;
                            max-width: none;
                            margin-bottom: 2rem;
                            border-bottom: 1px solid #333;
                            padding-bottom: 1rem;
                        }
                    }
                    

                    .toc-link {
                        display: block;
                        text-decoration: none;
                        color: inherit;
                        opacity: 0.7;
                        font-size: 0.85em;
                        margin-bottom: 8px;
                        padding-left: 10px;
                        border-left: 2px solid transparent;
                        transition: all 0.2s;
                        line-height: 1.4;
                    }
                    .toc-link:hover {
                        opacity: 1;
                        border-left-color: #00F2EA;
                        color: #00F2EA;
                    }
                    .toc-header {
                        font-weight: 700;
                        margin-bottom: 15px;
                        font-size: 1em;
                        letter-spacing: 0.5px;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                toc_html = f'''
                <div id="toc-container">
                    <div class="toc-header">Table of Contents</div>
                '''
                
                for level, title, slug in toc_headers:
                    padding = (level - 1) * 12
                    toc_html += f'<a href="#{slug}" class="toc-link" style="padding-left: {padding}px;">{title}</a>'
                
                toc_html += '</div>'
                
                st.markdown(toc_html, unsafe_allow_html=True)
        else:
            if st.button("← Back to Projects"):
                st.query_params.clear()
                st.rerun()
            st.markdown(content, unsafe_allow_html=True)
    else:
        st.error(f"Project file '{current_project}' not found.")
        
else:
    st.title("🛋️ My reading corner")
    
    intro_css = """
    <style>
        .intro-text {
            margin-bottom: 30px; 
            line-height: 1.6; 
            color: #555555; /* Dark grey for light mode */
        }
        @media (prefers-color-scheme: dark) {
            .intro-text {
                color: #A0A0A0; /* Light grey for dark mode, easier to read than CCCCCC */
            }
        }
        .intro-italic {
            font-style: italic; 
            opacity: 0.9;
        }
    </style>
    """
    st.markdown(intro_css, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="intro-text">
        <h4 class="intro-italic">Things I tried. Things that broke. Things that taught me something.</h4>
        <p>
            This page is not a portfolio of perfect outcomes.<br>
            It’s more like a notebook detailing what I tried, what went wrong, and what changed how I think.
        </p>
        <p>
            I'm fairly mediocre, but I do take pride in my persistence. I try things, they break, and I spend time understanding why. That cycle — trying, failing, adjusting — is the core of how I learn and work.
        </p>
        <p class="intro-italic">
            Some projects here will remain incomplete.<br>
            Some ideas will turn out to be wrong.<br>
            That’s part of the process, and I’m comfortable leaving it visible.
        </p>
        <p style="font-weight: bold; color: red; letter-spacing: 0.5px; border-left: 3px solid red; padding-left: 10px;">
            This is a work in progress. More to come...
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # LIST VIEW
    projects = load_projects()
    
    if not projects:
        st.info("No projects found in data/projects/")
    else:
        css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600&display=swap');
            
            :root {
                --card-bg-light: #ffffff;
                --card-bg-dark: #1E1E1E; /* Or #262730 */
                --text-light: #31333F;
                --text-dark: #FAFAFA;
                --border-light: rgba(49, 51, 63, 0.2);
                --border-dark: rgba(250, 250, 250, 0.2);
                --shadow-light: 0 4px 6px rgba(0,0,0,0.1);
            }

            .project-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 20px;
                font-family: 'Source Sans Pro', sans-serif;
                padding: 5px; /* prevent shadow crop */
            }
            
            .project-card {
                background-color: var(--card-bg-light); 
                border: 1px solid var(--border-light);
                color: var(--text-light);
                border-radius: 12px;
                padding: 24px;
                transition: all 0.3s ease;
                text-decoration: none;
                display: flex;
                flex-direction: column;
                height: 100%;
                box-sizing: border-box;
                box-shadow: var(--shadow-light);
            }

            @media (prefers-color-scheme: dark) {
                .project-card {
                    background-color: var(--card-bg-dark);
                    border: 1px solid var(--border-dark);
                    color: var(--text-dark);
                    box-shadow: none;
                }
            }

            .project-card:hover {
                transform: translateY(-5px);
                /* Aura Light Effect - Cyan */
                box-shadow: 0 0 25px rgba(0, 242, 234, 0.3), 0 0 10px rgba(0, 242, 234, 0.1); 
                border-color: rgba(0, 242, 234, 0.6);
            }
            
            .card-title {
                font-size: 1.3em;
                font-weight: 600;
                margin-bottom: 2px;
                /* Fallback color if variable fails */
                color: #31333F;
            }
            
            .card-tags {
                margin-bottom: 15px;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            
            .tech-tag {
                font-size: 0.75em;
                background-color: rgba(0, 242, 234, 0.15); /* Subtly tinted bg */
                color: #008f8a; /* Darker teal for light mode text */
                padding: 4px 10px;
                border-radius: 15px;
                border: 1px solid rgba(0, 242, 234, 0.3);
                font-weight: 600;
            }
            
            @media (prefers-color-scheme: dark) {
                 .card-title {
                     color: #FFFFFF;
                 }
                 .tech-tag {
                     background-color: rgba(0, 242, 234, 0.15);
                     color: #00f2ea; /* Bright cyan for dark mode */
                     border: 1px solid rgba(0, 242, 234, 0.5);
                 }
            }

            .card-abstract {
                font-size: 0.95em;
                opacity: 0.8;
                line-height: 1.6;
                flex-grow: 1; /* Pushes content to fill */
            }
        </style>
        """
        
        # Build HTML Grid
        html_content = css + '<div class="project-grid">'
        
        for proj in projects:
            safe_title = html.escape(proj["title"])
            abs_text = proj.get("abstract", "")
            safe_abstract = html.escape(abs_text[:200] + "..." if len(abs_text) > 200 else abs_text)
            
            # Build Tags HTML
            tags_html = ""
            if proj.get("tags"):
                tags_html = '<div class="card-tags">'
                for t in proj["tags"]:
                    tags_html += f'<span class="tech-tag">{html.escape(t)}</span>'
                tags_html += '</div>'
            
            html_content += f"""
            <a href='#' id='{proj["filename"]}' class="project-card">
                <div class="card-title">{safe_title}</div>
                {tags_html}
                <div class="card-abstract">{safe_abstract}</div>
            </a>
            """
        
        html_content += '</div>'
        
        clicked_id = click_detector(html_content)
        
        if clicked_id:
            st.query_params["project"] = clicked_id
            st.rerun()
