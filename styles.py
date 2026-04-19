"""
CSS styles injected into the Streamlit app.
Centralized here to keep app.py clean.
"""

# Highlight styling for trace-verified text + layout tweaks
APP_CSS = """
<style>
   .verbatim-match {
        background-color: #d4edda; 
        border-bottom: 2px solid #28a745;
        color: #155724;
        cursor: pointer;
        padding: 0 2px;
        border-radius: 3px;
        text-decoration: none;
    }
   .verbatim-match:hover {
        background-color: #c3e6cb;
    }
    .main-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
        position: sticky;
        top: 4rem;
        align-self: flex-start;
        max-height: 90vh;
        overflow-y: auto;
    }
    div[role="radiogroup"], div[data-testid="stRadio"] > div {
        display: flex;
        justify-content: center;
        width: 100%;
    }
</style>
"""

# Inline warning banner style (reused across agent mode descriptions)
WARNING_STYLE = "text-align: center; color: #856404; background-color: #fff3cd; border: 1px solid #ffeeba; padding: 0.5rem; border-radius: 0.25rem; font-size: 0.85em;"
