import re
import time
import uuid
from googleapiclient.discovery import build

# Slide canvas: 10" x 5.625" in EMU (1 inch = 914400 EMU)
SLIDE_W  = 9144000
SLIDE_H  = 5143500
MARGIN_X = 457200   # 0.5"
MARGIN_Y = 300000   # ~0.33"
CONTENT_W = SLIDE_W - 2 * MARGIN_X   # 8229600

TABLE_COLS   = ["Keyword", "Start", "Best", "Google", "Search Volume"]
# Column widths must sum to CONTENT_W = 8229600
COL_WIDTHS   = [3200000, 1257400, 1257400, 1257400, 1257400]
ROW_H_HEAD   = 340000
ROW_H_DATA   = 420000
TABLE_H      = ROW_H_HEAD + ROW_H_DATA   # 760000

DARK    = {"red": 0.10, "green": 0.10, "blue": 0.10}
WHITE   = {"red": 1.00, "green": 1.00, "blue": 1.00}
GRAY    = {"red": 0.45, "green": 0.45, "blue": 0.45}
ACCENT  = {"red": 0.94, "green": 0.37, "blue": 0.26}   # #EF5E43 (company orange)

# Layout ID with the blue border + three-dot background design
BRANDED_LAYOUT_ID = "g3ea77991fea_0_3047"


def _uid(prefix, idx):
    return f"{prefix}_{idx}_{uuid.uuid4().hex[:8]}"


def _to_num(val):
    try:
        return float(str(val).replace(",", ""))
    except Exception:
        return 0.0


def _pct(last, prev):
    if prev == 0:
        return "N/A"
    p = (last - prev) / prev * 100
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.1f}%"


def extract_presentation_id(url_or_id: str) -> str:
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def get_slides_service(creds):
    return build("slides", "v1", credentials=creds)


def build_keyword_slides(creds, presentation_id: str, kw_list: list):
    """
    kw_list: [{"row": pandas_series, "gsc": dict_or_None}, ...]
    Inserts one slide per keyword at the front of the presentation.
    """
    svc = get_slides_service(creds)
    for idx, item in enumerate(kw_list):
        _build_single_slide(svc, presentation_id, item["row"], item["gsc"], idx)
        time.sleep(0.4)   # stay well under API quota


def _rgb(d):
    return {"rgbColor": d}


def _build_single_slide(svc, pres_id, kw_row, gsc_data, idx):
    slide_id = _uid("sl", idx)
    table_id = _uid("tb", idx)
    tk_id    = _uid("tk", idx)
    tp_id    = _uid("tp", idx)
    bar_id   = _uid("br", idx)
    gsc_l_id = _uid("gl", idx)
    gsc_r_id = _uid("gr", idx)

    # ── Layout constants ─────────────────────────────────────────────────────
    table_y = MARGIN_Y                                # 300 000
    tk_y    = table_y + TABLE_H + 120000              # 1 180 000
    tp_y    = tk_y + 310000                           # 1 490 000
    bar_y   = tp_y + 360000                           # 1 850 000
    gsc_y   = bar_y + 160000                          # 2 010 000

    half_w  = CONTENT_W // 2 - 150000                # 3 964 800
    gsc_h   = SLIDE_H - gsc_y - MARGIN_Y             # 2 833 500
    gsc_rx  = MARGIN_X + half_w + 300000             # right col x

    # ── 1. Create slide with branded layout (border + three dots) ────────────
    svc.presentations().batchUpdate(
        presentationId=pres_id,
        body={"requests": [
            {"createSlide": {
                "objectId": slide_id,
                "insertionIndex": idx,
                "slideLayoutReference": {"layoutId": BRANDED_LAYOUT_ID}
            }}
        ]}
    ).execute()

    # Remove any placeholder shapes the layout injects onto the slide
    snap = svc.presentations().get(presentationId=pres_id, fields="slides").execute()
    placeholder_ids = []
    for s in snap["slides"]:
        if s["objectId"] == slide_id:
            placeholder_ids = [el["objectId"] for el in s.get("pageElements", [])]
            break
    if placeholder_ids:
        svc.presentations().batchUpdate(
            presentationId=pres_id,
            body={"requests": [{"deleteObject": {"objectId": oid}} for oid in placeholder_ids]}
        ).execute()

    # ── 2. Create all shapes ───────────────────────────────────────────────────
    def text_box(obj_id, x, y, w, h):
        return {"createShape": {
            "objectId": obj_id, "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width":  {"magnitude": w, "unit": "EMU"},
                    "height": {"magnitude": h, "unit": "EMU"}
                },
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": x, "translateY": y, "unit": "EMU"
                }
            }
        }}

    svc.presentations().batchUpdate(
        presentationId=pres_id,
        body={"requests": [
            {"createTable": {
                "objectId": table_id,
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width":  {"magnitude": CONTENT_W, "unit": "EMU"},
                        "height": {"magnitude": TABLE_H,   "unit": "EMU"}
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": MARGIN_X, "translateY": table_y, "unit": "EMU"
                    }
                },
                "rows": 2, "columns": 5
            }},
            text_box(tk_id, MARGIN_X, tk_y, CONTENT_W, 300000),
            text_box(tp_id, MARGIN_X, tp_y, CONTENT_W, 300000),
            {"createShape": {
                "objectId": bar_id, "shapeType": "RECTANGLE",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width":  {"magnitude": CONTENT_W, "unit": "EMU"},
                        "height": {"magnitude": 55000,     "unit": "EMU"}
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": MARGIN_X, "translateY": bar_y, "unit": "EMU"
                    }
                }
            }},
            text_box(gsc_l_id, MARGIN_X, gsc_y, half_w, gsc_h),
            text_box(gsc_r_id, gsc_rx,   gsc_y, half_w, gsc_h),
        ]}
    ).execute()

    # ── 3. Insert text ─────────────────────────────────────────────────────────
    keyword     = str(kw_row.get("Keyword",     "")).strip()
    ranking_url = str(kw_row.get("Ranking URL", "")).strip()

    if gsc_data:
        lc = _to_num(gsc_data["last_clicks"])
        pc = _to_num(gsc_data["prev_clicks"])
        li = _to_num(gsc_data["last_impressions"])
        pi = _to_num(gsc_data["prev_impressions"])
        left_text  = f"Clicks\n\nPrevious 6M:  {int(pc):,}\nLast 6M:  {int(lc):,}  ({_pct(lc, pc)})"
        right_text = f"Impressions\n\nPrevious 6M:  {int(pi):,}\nLast 6M:  {int(li):,}  ({_pct(li, pi)})"
    else:
        left_text  = "Clicks\n\nNo GSC data found for this keyword."
        right_text = "Impressions\n\nNo GSC data found for this keyword."

    text_reqs = []
    for ci, v in enumerate(TABLE_COLS):
        text_reqs.append({"insertText": {
            "objectId": table_id,
            "cellLocation": {"rowIndex": 0, "columnIndex": ci},
            "text": v, "insertionIndex": 0
        }})
    data_vals = [
        keyword,
        str(kw_row.get("Start", "")),
        str(kw_row.get("Best",  "")),
        str(kw_row.get("Google", "")),
        str(kw_row.get("Search Volume", ""))
    ]
    for ci, v in enumerate(data_vals):
        text_reqs.append({"insertText": {
            "objectId": table_id,
            "cellLocation": {"rowIndex": 1, "columnIndex": ci},
            "text": v, "insertionIndex": 0
        }})
    text_reqs += [
        {"insertText": {"objectId": tk_id,    "insertionIndex": 0, "text": f"Target Keyword:   {keyword}"}},
        {"insertText": {"objectId": tp_id,    "insertionIndex": 0, "text": f"Target Page:   {ranking_url}"}},
        {"insertText": {"objectId": gsc_l_id, "insertionIndex": 0, "text": left_text}},
        {"insertText": {"objectId": gsc_r_id, "insertionIndex": 0, "text": right_text}},
    ]
    svc.presentations().batchUpdate(
        presentationId=pres_id, body={"requests": text_reqs}
    ).execute()

    # ── 4. Style ────────────────────────────────────────────────────────────────
    style_reqs = []

    # Table header cells: orange bg + white bold text + center align
    for ci in range(5):
        style_reqs.append({"updateTableCellProperties": {
            "objectId": table_id,
            "tableRange": {"location": {"rowIndex": 0, "columnIndex": ci}, "rowSpan": 1, "columnSpan": 1},
            "tableCellProperties": {
                "tableCellBackgroundFill": {"solidFill": {"color": _rgb(ACCENT)}}
            },
            "fields": "tableCellBackgroundFill"
        }})
        style_reqs.append({"updateTextStyle": {
            "objectId": table_id,
            "cellLocation": {"rowIndex": 0, "columnIndex": ci},
            "style": {
                "bold": True,
                "foregroundColor": {"opaqueColor": _rgb(WHITE)},
                "fontSize": {"magnitude": 11, "unit": "PT"}
            },
            "textRange": {"type": "ALL"},
            "fields": "bold,foregroundColor,fontSize"
        }})
        style_reqs.append({"updateParagraphStyle": {
            "objectId": table_id,
            "cellLocation": {"rowIndex": 0, "columnIndex": ci},
            "style": {"alignment": "CENTER"},
            "textRange": {"type": "ALL"},
            "fields": "alignment"
        }})

    # Table data row: centered, 12pt
    for ci in range(5):
        style_reqs.append({"updateTextStyle": {
            "objectId": table_id,
            "cellLocation": {"rowIndex": 1, "columnIndex": ci},
            "style": {"fontSize": {"magnitude": 12, "unit": "PT"}},
            "textRange": {"type": "ALL"},
            "fields": "fontSize"
        }})
        style_reqs.append({"updateParagraphStyle": {
            "objectId": table_id,
            "cellLocation": {"rowIndex": 1, "columnIndex": ci},
            "style": {"alignment": "CENTER"},
            "textRange": {"type": "ALL"},
            "fields": "alignment"
        }})

    # Column widths
    for ci, w in enumerate(COL_WIDTHS):
        style_reqs.append({"updateTableColumnProperties": {
            "objectId": table_id,
            "columnIndices": [ci],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "EMU"}},
            "fields": "columnWidth"
        }})

    # Target Keyword: bold 14pt dark
    style_reqs.append({"updateTextStyle": {
        "objectId": tk_id,
        "style": {
            "bold": True,
            "fontSize": {"magnitude": 14, "unit": "PT"},
            "foregroundColor": {"opaqueColor": _rgb(DARK)}
        },
        "textRange": {"type": "ALL"},
        "fields": "bold,fontSize,foregroundColor"
    }})

    # Target Page: 13pt gray
    style_reqs.append({"updateTextStyle": {
        "objectId": tp_id,
        "style": {
            "fontSize": {"magnitude": 13, "unit": "PT"},
            "foregroundColor": {"opaqueColor": _rgb(GRAY)}
        },
        "textRange": {"type": "ALL"},
        "fields": "fontSize,foregroundColor"
    }})

    # Accent bar fill (no border)
    style_reqs.append({"updateShapeProperties": {
        "objectId": bar_id,
        "shapeProperties": {
            "shapeBackgroundFill": {"solidFill": {"color": _rgb(ACCENT)}},
            "outline": {"propertyState": "NOT_RENDERED"}
        },
        "fields": "shapeBackgroundFill,outline"
    }})

    # GSC boxes: 16pt dark (all text)
    for obj_id in [gsc_l_id, gsc_r_id]:
        style_reqs.append({"updateTextStyle": {
            "objectId": obj_id,
            "style": {
                "fontSize": {"magnitude": 16, "unit": "PT"},
                "foregroundColor": {"opaqueColor": _rgb(DARK)}
            },
            "textRange": {"type": "ALL"},
            "fields": "fontSize,foregroundColor"
        }})

    # Bold the "Clicks" / "Impressions" section labels (first word in each box)
    style_reqs.append({"updateTextStyle": {
        "objectId": gsc_l_id,
        "style": {"bold": True, "fontSize": {"magnitude": 18, "unit": "PT"}},
        "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": 6},   # "Clicks"
        "fields": "bold,fontSize"
    }})
    style_reqs.append({"updateTextStyle": {
        "objectId": gsc_r_id,
        "style": {"bold": True, "fontSize": {"magnitude": 18, "unit": "PT"}},
        "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": 11},  # "Impressions"
        "fields": "bold,fontSize"
    }})

    svc.presentations().batchUpdate(
        presentationId=pres_id, body={"requests": style_reqs}
    ).execute()
