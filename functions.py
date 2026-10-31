import os
import re
import calendar
from datetime import date
import pandas as pd
import zipfile

CSV_FILE = "student-dataset.csv"
EVENTS_FILE = "events.csv"

COLUMNS = [
    "id", "student_id", "name", "gender", "place", "age",
    "rank", "physics", "chemistry", "maths", "total", "average", "attendance"
]

def load_data():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(CSV_FILE, index=False)
        return df
    df = pd.read_csv(CSV_FILE)
    numeric_cols = ["id", "age", "rank", "physics", "chemistry", "maths", "total", "average", "attendance"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def recalculate_ranks(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and "total" in df.columns:
        df["rank"] = df["total"].rank(ascending=False, method="min").astype(int)
    return df

def save_data(df: pd.DataFrame):
    df = recalculate_ranks(df)
    try:
        df.to_csv(CSV_FILE, index=False)
        return df, True
    except PermissionError:
        return df, False

def load_events():
    if not os.path.exists(EVENTS_FILE) or os.path.getsize(EVENTS_FILE) == 0:
        df_ev = pd.DataFrame(columns=["id", "event", "Date"])
        df_ev.to_csv(EVENTS_FILE, index=False)
        return df_ev

    try:
        if EVENTS_FILE.endswith(".xlsx"):
            df_ev = pd.read_excel(EVENTS_FILE, engine="openpyxl")
        else:
            df_ev = pd.read_csv(EVENTS_FILE)
    except (zipfile.BadZipFile, pd.errors.EmptyDataError, ValueError, Exception):
        df_ev = pd.DataFrame(columns=["id", "event", "Date"])
        df_ev.to_csv(EVENTS_FILE, index=False)
        return df_ev

    df_ev.columns = [str(c).strip() for c in df_ev.columns]
    for col in ["id", "event", "Date"]:
        if col not in df_ev.columns:
            df_ev[col] = None

    if "Date" in df_ev.columns:
        df_ev["Date"] = pd.to_datetime(df_ev["Date"], errors="coerce").dt.date

    return df_ev

def save_event(event_name: str, event_date: date):
    df_ev = load_events()
    next_id = 1 if df_ev.empty or df_ev["id"].isna().all() else int(df_ev["id"].max()) + 1
    new_row = pd.DataFrame([{"id": next_id, "event": event_name.strip(), "Date": event_date}])
    df_ev = pd.concat([df_ev, new_row], ignore_index=True)
    
    if EVENTS_FILE.endswith(".xlsx"):
        df_ev.to_excel(EVENTS_FILE, index=False, engine="openpyxl")
    else:
        df_ev.to_csv(EVENTS_FILE, index=False)
        
    return next_id

def query_student_bot(prompt: str, df: pd.DataFrame, lang: str = "English"):
    q = prompt.lower().strip()
    if df.empty:
        return ("لا توجد بيانات للطلاب بعد." if lang == "العربية" else "No student records found in the dataset."), None

    # 1. Total Student Count
    if any(k in q for k in ["how many student", "student count", "total student", "number of student", "عدد الطلاب", "كم طالب", "كم عدد الطلاب", "إجمالي الطلاب"]):
        count = len(df)
        if lang == "العربية":
            return f"📊 إجمالي عدد الطلاب المسجلين هو **{count}** طالباً.", None
        return f"📊 The total number of registered students is **{count}**.", None

    # 2. Highest / Top Mark in a Specific Subject
    for sub in ["physics", "chemistry", "maths"]:
        sub_ar = {"physics": "الفيزياء", "chemistry": "الكيمياء", "maths": "الرياضيات"}[sub]
        if sub in q or sub_ar in q:
            if any(k in q for k in ["highest", "max", "top", "best", "أعلى", "اعلى", "أفضل"]):
                max_score = df[sub].max()
                top_students = df[df[sub] == max_score]
                names = ", ".join(top_students["name"].dropna().astype(str).tolist())
                msg = (f"🌟 أعلى درجة في مادة **{sub_ar}** هي **{max_score}** وحققها: **{names}**."
                       if lang == "العربية"
                       else f"🌟 The highest mark in **{sub.capitalize()}** is **{max_score}**, achieved by: **{names}**.")
                return msg, top_students[["rank", "name", sub, "total"]]
            
            elif any(k in q for k in ["lowest", "min", "worst", "fail", "أقل", "اقل", "ضعيف", "راسب"]):
                min_score = df[sub].min()
                low_students = df[df[sub] == min_score]
                names = ", ".join(low_students["name"].dropna().astype(str).tolist())
                msg = (f"📉 أقل درجة في مادة **{sub_ar}** هي **{min_score}** لدى: **{names}**."
                       if lang == "العربية"
                       else f"📉 The lowest mark in **{sub.capitalize()}** is **{min_score}**, scored by: **{names}**.")
                return msg, low_students[["rank", "name", sub, "total"]]

    # 3. Overall Class Topper
    if any(k in q for k in ["topper", "rank 1", "highest mark", "highest score", "الأول", "الاول", "المتفوق"]):
        top_row = df.loc[df['total'].idxmax()]
        name = top_row['name']
        score = top_row['total']
        rank = top_row['rank']
        msg = (f"🏆 **الأول على الفصل** هو **{name}** بمجموع **{score:.0f}/300** والترتيب **#{rank}**."
               if lang == "العربية"
               else f"🏆 The **Class Topper** is **{name}** with a total score of **{score:.0f}/300** (Rank **#{rank}**).")
        return msg, df[df['name'] == name]

    # 4. Attendance Queries
    if any(k in q for k in ["attendance", "حضور", "غياب"]):
        low_att = df[df['attendance'] < 75].sort_values(by="attendance")
        if any(k in q for k in ["low", "below", "less", "اقل", "أقل", "ضعيف", "غياب"]):
            msg = (f"⚠️ تم العثور على **{len(low_att)}** طلاب بنسبة حضور أقل من 75%:"
                   if lang == "العربية"
                   else f"⚠️ Found **{len(low_att)}** students with attendance below 75%:")
            return msg, low_att
        else:
            avg_att = df['attendance'].mean()
            return (f"متوسط الحضور العام للفصل هو **{avg_att:.1f}%**."
                    if lang == "العربية"
                    else f"The overall class average attendance is **{avg_att:.1f}%**."), None

    # 5. Place / Country Search
    places = df['place'].dropna().unique()
    matched_place = next((p for p in places if str(p).lower() in q), None)
    if matched_place:
        place_df = df[df['place'].str.lower() == matched_place.lower()]
        msg = (f"📍 تم العثور على **{len(place_df)}** طلاب من **{matched_place}**:"
               if lang == "العربية"
               else f"📍 Found **{len(place_df)}** students from **{matched_place}**:")
        return msg, place_df

    # 6. Specific Student Lookup
    for _, row in df.iterrows():
        student_name = str(row['name']).strip()
        parts = [p.lower() for p in student_name.split() if len(p) > 2]
        if student_name.lower() in q or any(re.search(rf"\b{re.escape(p)}\b", q) for p in parts):
            msg = (f"📋 بيانات الطالب **{row['name']}**: الترتيب: **#{row['rank']}** | المجموع: **{row['total']:.0f}/300** | الحضور: **{row['attendance']}%** | المكان: **{row['place']}**"
                   if lang == "العربية"
                   else f"📋 Details for **{row['name']}**: Rank: **#{row['rank']}** | Total: **{row['total']:.0f}/300** | Attendance: **{row['attendance']}%** | Location: **{row['place']}**")
            return msg, df[df['name'] == row['name']]

    # 7. Fallback
    if lang == "العربية":
        return "لم أتمكن من العثور على نتيجة دقيقة. يمكنك السؤال عن: 'كم عدد الطلاب؟'، 'أعلى درجة في الفيزياء'، 'الأول على الفصل'، أو نسبة الحضور.", None
    return "I couldn't quite find what you're looking for. You can ask: 'How many students are there?', 'Highest mark in physics', 'Who is the topper?', or 'Attendance below 75%'.", None

def get_theme_css(dark_mode: bool) -> str:
    return f"""
    <style>
        .stApp {{
            background-color: {"#0e1117" if dark_mode else "#ffffff"};
            color: {"#f0f6fc" if dark_mode else "#31333F"};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {"#161b22" if dark_mode else "#f0f2f6"};
        }}
        h1, h2, h3, h4, h5, h6, label {{
            color: {"#f0f6fc" if dark_mode else "#1e293b"} !important;
        }}
        p, span {{
            color: {"#f0f6fc" if dark_mode else "#31333F"};
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {"#161b22" if dark_mode else "#ffffff"} !important;
            border: 1px solid {"#30363d" if dark_mode else "#e2e8f0"} !important;
            border-radius: 12px !important;
            padding: 16px !important;
            box-shadow: {"0 4px 14px rgba(0,0,0,0.3)" if dark_mode else "0 2px 8px rgba(0,0,0,0.04)"} !important;
        }}
        [data-testid="stExpander"] details {{
            background-color: {"#161b22" if dark_mode else "#ffffff"} !important;
            border: 1px solid {"#30363d" if dark_mode else "#e2e8f0"} !important;
            border-radius: 8px !important;
            overflow: hidden !important;
        }}
        [data-testid="stExpander"] summary {{
            background-color: {"#21262d" if dark_mode else "#f8fafc"} !important;
            color: {"#f0f6fc" if dark_mode else "#1e293b"} !important;
            border-radius: 8px !important;
            border: none !important;
        }}
        [data-testid="stExpander"] summary:hover {{
            background-color: {"#30363d" if dark_mode else "#f1f5f9"} !important;
        }}
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span,
        [data-testid="stExpander"] summary svg {{
            color: {"#f0f6fc" if dark_mode else "#1e293b"} !important;
            fill: {"#f0f6fc" if dark_mode else "#1e293b"} !important;
        }}
        [data-testid="stExpander"] div[data-testid="stExpanderDetails"] {{
            background-color: {"#161b22" if dark_mode else "#ffffff"} !important;
        }}
        button[kind="secondary"] {{
            background-color: {"#21262d" if dark_mode else "#ffffff"} !important;
            color: {"#f0f6fc" if dark_mode else "#24292f"} !important;
            border: 1px solid {"#30363d" if dark_mode else "#d0d7de"} !important;
        }}
        button[kind="secondary"] p,
        button[kind="secondary"] span {{
            color: {"#f0f6fc" if dark_mode else "#24292f"} !important;
        }}
        button[kind="secondary"]:hover {{
            background-color: {"#30363d" if dark_mode else "#f3f4f6"} !important;
            border-color: {"#8b949e" if dark_mode else "#cbd5e1"} !important;
        }}
        div[data-testid="stChatMessage"] {{
            background-color: {"#161b22" if dark_mode else "#f8fafc"} !important;
            border: 1px solid {"#30363d" if dark_mode else "#e2e8f0"} !important;
            border-radius: 10px !important;
        }}
        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] span {{
            color: {"#f0f6fc" if dark_mode else "#1e293b"} !important;
        }}
        div[data-testid="stMetricValue"] {{
            color: {"#58a6ff" if dark_mode else "#2563eb"} !important;
            font-weight: 700;
        }}
        div[data-testid="stMetricLabel"] {{
            color: {"#8b949e" if dark_mode else "#64748b"} !important;
        }}
    </style>
    """

def style_chart(fig, dark_mode: bool, height: int = 360):
    fig.update_layout(
        template="plotly_dark" if dark_mode else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f0f6fc" if dark_mode else "#334155"),
        margin=dict(l=20, r=20, t=45, b=25),
        height=height
    )
    return fig

def render_calendar_html(year: int, month: int, today: date, event_map: dict, dark_mode: bool) -> str:
    cal_matrix = calendar.monthcalendar(year, month)
    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dark_class = "dark" if dark_mode else ""
    
    html = "<table class='cal-table'><thead><tr>"
    for d in days_header:
        html += f"<th class='cal-header'>{d}</th>"
    html += "</tr></thead><tbody>"

    for week in cal_matrix:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td class='cal-cell empty'></td>"
            else:
                d_str = f"{year}-{month:02d}-{day:02d}"
                is_today = "today" if (d_str == today.strftime("%Y-%m-%d")) else ""
                day_events = event_map.get(d_str, [])

                badges_html = "".join([
                    f"<span class='cal-event-badge' title='{ev}'>📌 {ev}</span>"
                    for ev in day_events[:2]
                ])
                if len(day_events) > 2:
                    badges_html += f"<span style='font-size:0.65rem; color:#60a5fa;'>+{len(day_events)-2} more</span>"

                html += f"<td class='cal-cell {dark_class} {is_today}'><span class='cal-num'>{day}</span>{badges_html}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html