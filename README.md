# SpaceAppsChallenge2026
Remeber to update the `requirements.txt` by running `pip freeze > requirements.txt`
--
# Deployed Streamlit App

Access the deployed Health Monitoring application here:

https://nasa-space-apps-2026-group-17-health-monitoring.streamlit.app/

--

# How to Run the Streamlit App Locally

Follow these simple steps to run the Health Monitoring app on your computer using VS Code.

### 1. Open the Project

Open VS Code, go to **File > Open Folder**, and select the `SpaceAppsChallenge2026` folder.

### 2. Open the Terminal

In VS Code, go to **Terminal > New Terminal** (or press `Ctrl + ``).

### 3. Create a Virtual Environment

Run the following command in the terminal to create a clean environment for the project.

**Windows:**
```bash
python -m venv .venv
```

**Mac/Linux:**
```bash
python3 -m venv .venv
```

### 4. Activate the Environment

Activate the virtual environment so the terminal knows where to install the packages.

**Windows:**
```bash
.venv\Scripts\activate
```

**Mac/Linux:**
```bash
source .venv/bin/activate
```

*You will know it worked if you see `(.venv)` at the beginning of your terminal line.*

### 5. Install the Required Libraries

Install all the required Python packages for the project.

```bash
pip install -r requirements.txt
```

If Plotly and Streamlit are not already included in `requirements.txt`, install them separately:

```bash
pip install plotly streamlit
```

### 6. Run the App

Start the Streamlit server using the Python module command. This ensures it runs properly regardless of your system's PATH setup.

```bash
python -m streamlit run main.py
```

### 7. View the App

Your web browser should open automatically at:

`http://localhost:8501`

If it doesn't, simply copy and paste the link into your browser.

---

**Note:** To stop the app when you are done, return to the VS Code terminal and press `Ctrl + C`.
