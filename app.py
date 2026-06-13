import streamlit as st
import pandas as pd

from config import get_credentials, get_service_account_email
from slide_builder import extract_presentation_id, build_keyword_slides

st.set_page_config(page_title="Keyword Performance Report", page_icon="📊", layout="wide")
st.title("Keyword Performance Report Generator")

# ── Sidebar: usage guide + credentials ───────────────────────────────────────
with st.sidebar:
    st.subheader("使用流程")

    st.markdown("**Step 1 — 匯出 keyword.com CSV**")
    st.markdown(
        "1. 登入 [keyword.com](https://app.keyword.com/dashboard)\n"
        "2. 選擇 Project，勾選想生成 Slide 的 Keywords\n"
        "3. Export → CSV 下載\n"
        "> 每個 keyword = 一頁 Slide"
    )

    st.markdown("**Step 2 — 匯出 GSC 對比數據**")
    st.markdown(
        "1. 登入 Google Search Console\n"
        "2. Performance → Search Results\n"
        "3. 日期範圍選 **Compare** 模式（建議 Last 6M vs Previous 6M）\n"
        "4. 切換到 **Queries** 分頁\n"
        "5. Export → CSV 或 Excel 下載\n"
        "> Column 順序需為：B=Last 6M Clicks, C=Prev 6M Clicks, D=Last 6M Impressions, E=Prev 6M Impressions"
    )

    st.markdown("**Step 3 — 填寫工具並生成**")
    st.markdown(
        "1. 上傳 keyword.com CSV\n"
        "2. 上傳 GSC 檔案\n"
        "3. 確認 Preview Table 的 GSC Match 狀態\n"
        "4. 貼上 Google Slides URL\n"
        "5. 按 **Generate Slides**\n"
        "> 推薦使用 Presentation："
    )
    st.markdown(
        "[開啟 Bannershop Progress Report ↗](https://docs.google.com/presentation/d/"
        "1TLQOQOAOhL3k9htchljFyd7N6cWoqEizVvanaMtaESk/edit)"
    )

    st.markdown("---")
    st.markdown("**注意事項**")
    st.markdown(
        "- GSC matching 為 exact match（大小寫不敏感）\n"
        "- Slides 插入在 Presentation **最前面**\n"
        "- 重新生成前請先手動刪除舊頁面"
    )

    st.markdown("---")
    sa_email = get_service_account_email()
    if sa_email:
        st.info(f"Presentation 需分享給 Service Account（Editor）：\n\n`{sa_email}`")
    else:
        st.warning("Service account credentials not configured.")

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

# Parse keyword.com CSV — try common encodings
try:
    for enc in ["utf-8", "utf-16", "utf-8-sig", "latin-1"]:
        try:
            kw_file.seek(0)
            kw_df = pd.read_csv(kw_file, encoding=enc)
            break
        except (UnicodeDecodeError, Exception):
            continue
    else:
        raise ValueError("Could not decode file with utf-8, utf-16, utf-8-sig, or latin-1.")
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
        import io
        gsc_file.seek(0)
        raw = gsc_file.read()
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
            content = raw.decode('utf-16')
        elif raw[:3] == b'\xef\xbb\xbf':
            content = raw.decode('utf-8-sig')
        else:
            content = raw.decode('utf-8', errors='replace')
        gsc_raw = pd.read_csv(io.StringIO(content), header=None)
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
