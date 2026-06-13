import streamlit as st
import pandas as pd

from config import get_credentials, get_service_account_email
from slide_builder import extract_presentation_id, build_keyword_slides

st.set_page_config(page_title="Keyword Performance Report", page_icon="📊", layout="wide")
st.title("Keyword Performance Report Generator")

# ── Sidebar: credentials info ────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Setup")
    sa_email = get_service_account_email()
    if sa_email:
        st.info(f"Share your Google Slides presentation with:\n\n`{sa_email}`")
    else:
        st.warning("Service account credentials not configured.")
    st.markdown("---")
    st.caption("Columns used from keyword.com CSV: Keyword, Start, Best, Google, Search Volume, Ranking URL")
    st.caption("GSC columns: col B = last 6M clicks, col C = prev 6M clicks, col D = last 6M impressions, col E = prev 6M impressions")

# ── File uploads ─────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. keyword.com Export")
    kw_file = st.file_uploader("Upload keyword.com CSV", type=["csv"])

with col2:
    st.subheader("2. GSC Performance Data")
    gsc_file = st.file_uploader("Upload GSC Export (.csv / .xlsx)", type=["csv", "xlsx", "xls"])

st.subheader("3. Google Slides URL")
slides_url = st.text_input(
    "Presentation URL",
    placeholder="https://docs.google.com/presentation/d/..."
)

# ── Process files ─────────────────────────────────────────────────────────────
if not (kw_file and gsc_file):
    st.info("Upload both files to continue.")
    st.stop()

# Parse keyword.com CSV
try:
    kw_df = pd.read_csv(kw_file)
except Exception as e:
    st.error(f"Failed to read keyword.com CSV: {e}")
    st.stop()

required_kw_cols = ["Keyword", "Start", "Best", "Google", "Search Volume", "Ranking URL"]
missing = [c for c in required_kw_cols if c not in kw_df.columns]
if missing:
    st.error(f"Missing columns in keyword.com CSV: {missing}")
    st.stop()

# Parse GSC file — supports CSV or Excel
try:
    if gsc_file.name.lower().endswith(".csv"):
        gsc_raw = pd.read_csv(gsc_file, header=None)
    else:
        gsc_raw = pd.read_excel(gsc_file, sheet_name="Queries", header=None)
except Exception as e:
    st.error(f"Failed to read GSC file: {e}")
    st.stop()

# Show the date ranges detected so the user can verify column mapping
gsc_header_row = gsc_raw.iloc[0]
st.caption(
    f"GSC columns detected — "
    f"Last 6M Clicks: **{gsc_header_row[1]}** | "
    f"Prev 6M Clicks: **{gsc_header_row[2]}** | "
    f"Last 6M Impressions: **{gsc_header_row[3]}** | "
    f"Prev 6M Impressions: **{gsc_header_row[4]}**"
)

gsc_data_rows = gsc_raw.iloc[1:].reset_index(drop=True)

def to_num(val):
    try:
        return float(str(val).replace(",", ""))
    except Exception:
        return 0.0

gsc_lookup = {}
for _, row in gsc_data_rows.iterrows():
    kw_key = str(row[0]).strip().lower()
    gsc_lookup[kw_key] = {
        "last_clicks":       to_num(row[1]),
        "prev_clicks":       to_num(row[2]),
        "last_impressions":  to_num(row[3]),
        "prev_impressions":  to_num(row[4]),
    }

# ── Preview table ─────────────────────────────────────────────────────────────
st.subheader("Preview")

preview_rows = []
kw_list = []

for _, kw_row in kw_df.iterrows():
    kw = str(kw_row["Keyword"]).strip()
    gsc = gsc_lookup.get(kw.lower())
    kw_list.append({"row": kw_row, "gsc": gsc})
    preview_rows.append({
        "Keyword":        kw,
        "Start":          kw_row["Start"],
        "Best":           kw_row["Best"],
        "Google":         kw_row["Google"],
        "Search Volume":  kw_row["Search Volume"],
        "Ranking URL":    kw_row["Ranking URL"],
        "GSC Match":      "✓" if gsc else "✗",
        "Last 6M Clicks": int(gsc["last_clicks"]) if gsc else "—",
        "Prev 6M Clicks": int(gsc["prev_clicks"]) if gsc else "—",
    })

preview_df = pd.DataFrame(preview_rows)
matched = preview_df["GSC Match"].eq("✓").sum()
total   = len(preview_df)

st.dataframe(preview_df, use_container_width=True, hide_index=True)
st.markdown(f"**{total} slides** will be generated. GSC match: **{matched}/{total}** keywords found.")

if matched < total:
    unmatched = preview_df[preview_df["GSC Match"] == "✗"]["Keyword"].tolist()
    with st.expander(f"⚠️ {total - matched} keyword(s) without GSC data"):
        for kw in unmatched:
            st.write(f"- {kw}")

# ── Generate ──────────────────────────────────────────────────────────────────
st.subheader("4. Generate Slides")

if not slides_url.strip():
    st.info("Enter the Google Slides URL above to enable generation.")
    st.stop()

pres_id = extract_presentation_id(slides_url)
if not pres_id:
    st.error("Could not extract presentation ID from URL.")
    st.stop()

if st.button("Generate Slides", type="primary"):
    try:
        creds = get_credentials()
    except Exception as e:
        st.error(f"Credentials error: {e}")
        st.stop()

    progress = st.progress(0, text="Starting…")
    status   = st.empty()

    try:
        from slide_builder import get_slides_service
        import time

        svc = get_slides_service(creds)

        from slide_builder import _build_single_slide

        for i, item in enumerate(kw_list):
            kw_label = str(item["row"]["Keyword"])
            status.write(f"Creating slide {i + 1}/{total}: **{kw_label}**")
            _build_single_slide(svc, pres_id, item["row"], item["gsc"], i)
            progress.progress((i + 1) / total, text=f"{i + 1}/{total} slides done")
            time.sleep(0.4)

        progress.progress(1.0, text="Done!")
        status.empty()
        st.success(f"✅ {total} slides generated successfully.")
        st.markdown(f"[Open Presentation ↗]({slides_url})", unsafe_allow_html=False)

    except Exception as e:
        st.error(f"Error during slide generation: {e}")
        raise
