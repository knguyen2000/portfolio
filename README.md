## Installation

1.  **Clone the repository** (or download the source code):

    ```bash
    git clone <repository-url>
    cd portfolio
    ```

2.  **Install Dependencies**:
    Ensure you have Python 3.9+ installed.
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

You need a Google Gemini API Key to run this application.

1.  Create a file named `secrets.toml` inside the `.streamlit/` directory:

    ```bash
    mkdir .streamlit
    # Create the file (Windows PowerShell)
    New-Item -Path .streamlit/secrets.toml -ItemType File
    ```

2.  Add your API key and admin passcode to `.streamlit/secrets.toml`:
    ```toml
    GOOGLE_API_KEY = "your-google-api-key-here"
    ADMIN_PASSCODE = "your-desired-passcode"
    ```

## Running the App

Run the application using Streamlit:

```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`