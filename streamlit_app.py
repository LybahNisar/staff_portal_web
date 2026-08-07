import streamlit as st
import pandas as pd
import json
import requests
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# --- Configuration & Theme ---
st.set_page_config(page_title="Chocoberry Staff Portal", page_icon="🍫", layout="centered")

# --- PLACEHOLDER FOR YOUR GOOGLE URL ---
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwH21f0lQrxTn02osMx5Bxl3B49_M6_TVOMqQJMwUZYEYyAbsLDQncquq_8NMAM51UoeA/exec"

st.markdown("""
    <style>
    .main { background-color: #0a0b0f; }
    .stSelectbox label, .stTextInput label { color: #6b7094; font-weight: 700; font-size: 14px; }
    div[data-baseweb="select"] > div { background-color: #12141a; border-color: #252836; color: white; }
    .stButton>button {
        width: 100%;
        background: #f5a623;
        color: #0a0b0f;
        font-weight: 800;
        border-radius: 12px;
        border: none;
        padding: 15px;
        margin-top: 20px;
    }
    .header-box {
        text-align: center;
        padding: 20px;
        background: #12141a;
        border-radius: 15px;
        border: 1px solid #252836;
        margin-bottom: 25px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
    <div class="header-box">
        <h1 style='color:#f5a623;margin:0;'>Chocoberry</h1>
        <p style='color:#6b7094;margin:0;'>Staff Availability Portal</p>
    </div>
""", unsafe_allow_html=True)

# --- Data Loading ---
def get_staff():
    try:
        base_dir = Path(__file__).parent
        csv_path = base_dir / "staff_profiles.csv"
        if not csv_path.exists():
            csv_path = base_dir.parent / "staff_profiles.csv"
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]
        active = df[df['Active'].astype(str).str.lower().isin(['true','yes','1'])]
        return active.sort_values("Name")
    except Exception as e:
        st.error(f"Error loading staff_profiles.csv: {e}")
        return pd.DataFrame()

def save_to_local_db(name, week_start_str, avail_dict, notes_str):
    try:
        base_dir = Path(__file__).parent
        db_paths = [
            base_dir / "availability.db",
            base_dir.parent / "availability.db"
        ]
        for db_p in db_paths:
            with sqlite3.connect(db_p) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS availability (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_name TEXT,
                        week_start TEXT,
                        availability TEXT,
                        notes TEXT,
                        submitted_at TEXT
                    )
                ''')
                conn.execute('''
                    INSERT INTO availability (staff_name, week_start, availability, notes, submitted_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, week_start_str, json.dumps(avail_dict), notes_str, datetime.now().isoformat()))
                conn.commit()
        return True
    except Exception as ex:
        print(f"Local DB Save Error: {ex}")
        return False

staff_df = get_staff()

if not staff_df.empty:
    # --- Form ---
    with st.form("avail_form", clear_on_submit=False):
        
        name = st.selectbox("Select Your Name", ["-- Choose --"] + staff_df["Name"].tolist())
        pin  = st.text_input("Security PIN", type="password", help="Enter your 4-digit code")
        
        st.markdown("---")
        st.subheader("Weekly Shifts")
        
        # Calculate target week
        today = datetime.now()
        days_to_mon = (7 - today.weekday()) % 7
        next_mon = today + timedelta(days=days_to_mon if days_to_mon else 7)
        next_sun = next_mon + timedelta(days=6)
        st.info(f"📅 Week: {next_mon.strftime('%d %b')} – {next_sun.strftime('%d %b %Y')}")

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        avail_data = {}
        
        opts = {
            "🟢 Any Shift": "any",
            "💗 Opening Only": "opening",
            "🔘 Closing Only": "closing",
            "🔴 Unavailable": "unavailable"
        }
        
        for day in days:
            st.markdown(f"**{day}**")
            sel = st.selectbox(f"Availability for {day}", options=list(opts.keys()), key=f"sel_{day}", label_visibility="collapsed")
            avail_data[day] = opts[sel]
        
        st.markdown("---")
        notes = st.text_input("Special Requests / Notes (optional)")
        
        submit = st.form_submit_button("🚀 Submit Availability")
        
        if submit:
            if name == "-- Choose --":
                st.warning("Please select your name.")
            elif not pin:
                st.warning("PIN is required.")
            else:
                # Verify PIN
                row = staff_df[staff_df["Name"] == name].iloc[0]
                correct_pin = str(row["PIN"]).strip()
                
                if pin.strip() != correct_pin:
                    st.error("❌ Incorrect PIN. Please try again.")
                else:
                    # 1. Save locally to availability.db
                    week_start_str = next_mon.strftime("%Y-%m-%d")
                    saved_db = save_to_local_db(name, week_start_str, avail_data, notes)
                    
                    # 2. Try sending to Google Sheets Cloud
                    cloud_synced = False
                    if GOOGLE_SCRIPT_URL and "YOUR_GOOGLE_SCRIPT_URL_HERE" not in GOOGLE_SCRIPT_URL:
                        payload = {
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Name": name,
                            "Week_Start": week_start_str,
                            "Availability": json.dumps(avail_data),
                            "Notes": notes
                        }
                        try:
                            response = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=5)
                            if response.status_code == 200:
                                cloud_synced = True
                        except Exception:
                            pass
                    
                    st.balloons()
                    st.success(f"✅ Thank you {name}! Your availability for {next_mon.strftime('%d %b')} is recorded and saved!")
                    st.markdown(f"""
                        <div style='background:#1a1c24;padding:20px;border-radius:10px;border:1px solid #3ecf8e;text-align:center'>
                            <p style='color:#3ecf8e;font-weight:bold;margin:0;'>Synced to Management App Dashboard & Database</p>
                            <p style='color:#6b7094;margin:5px 0 0 0;'>Week of {next_mon.strftime('%d %b')} – {next_sun.strftime('%d %b %Y')}</p>
                        </div>
                    """, unsafe_allow_html=True)
else:
    st.info("Please upload your 'staff_profiles.csv' to activate the portal.")
