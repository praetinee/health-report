import numpy as np
import streamlit as st
import pandas as pd
import gspread
import json
import html
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="ระบบรายงานสุขภาพ", layout="wide")

# ==================== STYLE ====================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch&display=swap');
    html, body, [class*="css"] {
        font-family: 'Chakra Petch', sans-serif !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== LOAD SHEET ====================
@st.cache_data(ttl=300)
def load_google_sheet():
    try:
        service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
        client = gspread.authorize(creds)

        sheet_url = "https://docs.google.com/spreadsheets/d/1N3l0o_Y6QYbGKx22323mNLPym77N0jkJfyxXFM2BDmc"
        worksheet = client.open_by_url(sheet_url).sheet1
        raw_data = worksheet.get_all_records()
        if not raw_data:
            st.error("❌ ไม่พบข้อมูลในแผ่นแรกของ Google Sheet")
            st.stop()
        return pd.DataFrame(raw_data)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลด Google Sheet: {e}")
        st.stop()

df = load_google_sheet()
df.columns = df.columns.str.strip()
df['เลขบัตรประชาชน'] = df['เลขบัตรประชาชน'].astype(str).str.strip()
df['HN'] = df['HN'].astype(str).str.strip()
df['ชื่อ-สกุล'] = df['ชื่อ-สกุล'].astype(str).str.strip()

# ==================== YEAR MAPPING ====================
years = list(range(61, 69))
columns_by_year = {
    y: {
        "weight": f"น้ำหนัก{y}" if y != 68 else "น้ำหนัก",
        "height": f"ส่วนสูง{y}" if y != 68 else "ส่วนสูง",
        "waist": f"รอบเอว{y}" if y != 68 else "รอบเอว",
        "sbp": f"SBP{y}" if y != 68 else "SBP",
        "dbp": f"DBP{y}" if y != 68 else "DBP",
        "pulse": f"pulse{y}" if y != 68 else "pulse",
    }
    for y in years
}

# ==================== INTERPRET FUNCTIONS ====================
def interpret_bmi(bmi):
    try:
        bmi = float(bmi)
        if bmi > 30:
            return "อ้วนมาก"
        elif bmi >= 25:
            return "อ้วน"
        elif bmi >= 23:
            return "น้ำหนักเกิน"
        elif bmi >= 18.5:
            return "ปกติ"
        else:
            return "ผอม"
    except (ValueError, TypeError):
        return "-"

def interpret_bp(sbp, dbp):
    try:
        sbp = float(sbp)
        dbp = float(dbp)
        if sbp == 0 or dbp == 0:
            return "-"
        if sbp >= 160 or dbp >= 100:
            return "ความดันสูง"
        elif sbp >= 140 or dbp >= 90:
            return "ความดันสูงเล็กน้อย"
        elif sbp < 120 and dbp < 80:
            return "ความดันปกติ"
        else:
            return "ความดันค่อนข้างสูง"
    except (ValueError, TypeError):
        return "-"

def combined_health_advice(bmi, sbp, dbp):
    try:
        bmi = float(bmi)
    except:
        bmi = None
    try:
        sbp = float(sbp)
        dbp = float(dbp)
    except:
        sbp = dbp = None

    # วิเคราะห์ BMI
    if bmi is None:
        bmi_text = ""
    elif bmi > 30:
        bmi_text = "น้ำหนักเกินมาตรฐานมาก"
    elif bmi >= 25:
        bmi_text = "น้ำหนักเกินมาตรฐาน"
    elif bmi < 18.5:
        bmi_text = "น้ำหนักน้อยกว่ามาตรฐาน"
    else:
        bmi_text = "น้ำหนักอยู่ในเกณฑ์ปกติ"

    # วิเคราะห์ความดัน
    if sbp is None or dbp is None:
        bp_text = ""
    elif sbp >= 160 or dbp >= 100:
        bp_text = "ความดันโลหิตอยู่ในระดับสูงมาก"
    elif sbp >= 140 or dbp >= 90:
        bp_text = "ความดันโลหิตอยู่ในระดับสูง"
    elif sbp >= 120 or dbp >= 80:
        bp_text = "ความดันโลหิตเริ่มสูง"
    else:
        bp_text = ""  # ❗ ถ้าปกติ = ไม่ต้องพูดถึง

    # สร้างคำแนะนำรวม
    if not bmi_text and not bp_text:
        return "ไม่พบข้อมูลเพียงพอในการประเมินสุขภาพ"

    if "ปกติ" in bmi_text and not bp_text:
        return "น้ำหนักอยู่ในเกณฑ์ดี ควรรักษาพฤติกรรมสุขภาพนี้ต่อไป"

    if not bmi_text and bp_text:
        return f"{bp_text} แนะนำให้ดูแลสุขภาพ และติดตามค่าความดันอย่างสม่ำเสมอ"

    if bmi_text and bp_text:
        return f"{bmi_text} และ {bp_text} แนะนำให้ปรับพฤติกรรมด้านอาหารและการออกกำลังกาย"

    return f"{bmi_text} แนะนำให้ดูแลเรื่องโภชนาการและการออกกำลังกายอย่างเหมาะสม"

# ==================== UI FORM ====================
st.markdown("<h1 style='text-align:center;'>ระบบรายงานผลตรวจสุขภาพ</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align:center; color:gray;'>- กลุ่มงานอาชีวเวชกรรม รพ.สันทราย -</h4>", unsafe_allow_html=True)

with st.form("search_form"):
    col1, col2, col3 = st.columns(3)
    id_card = col1.text_input("เลขบัตรประชาชน")
    hn = col2.text_input("HN")
    full_name = col3.text_input("ชื่อ-สกุล")
    submitted = st.form_submit_button("ค้นหา")

# ==================== BLOOD COLUMN MAPPING ====================
blood_columns_by_year = {
    y: {
        "FBS": f"FBS{y}",
        "Uric": f"Uric Acid{y}",
        "ALK": f"ALP{y}",
        "SGOT": f"SGOT{y}",
        "SGPT": f"SGPT{y}",
        "Cholesterol": f"CHOL{y}",
        "TG": f"TGL{y}",
        "HDL": f"HDL{y}",
        "LDL": f"LDL{y}",
        "BUN": f"BUN{y}",
        "Cr": f"Cr{y}",
        "GFR": f"GFR{y}",
    }
    for y in years
}

if submitted:
    query = df.copy()
    if id_card.strip():
        query = query[query["เลขบัตรประชาชน"] == id_card.strip()]
    if hn.strip():
        query = query[query["HN"] == hn.strip()]
    if full_name.strip():
        query = query[query["ชื่อ-สกุล"].str.strip() == full_name.strip()]
    if query.empty:
        st.error("❌ ไม่พบข้อมูล กรุณาตรวจสอบอีกครั้ง")
        st.session_state.pop("person", None)
    else:
        st.session_state["person"] = query.iloc[0]

from collections import defaultdict

cbc_columns_by_year = defaultdict(dict)

for year in range(61, 69):
    cbc_columns_by_year[year] = {
        "hb": f"Hb(%)" + str(year),
        "hct": f"HCT" + str(year),
        "wbc": f"WBC (cumm)" + str(year),
        "plt": f"Plt (/mm)" + str(year),
    }

    if year == 68:
        cbc_columns_by_year[year].update({
            "ne": "Ne (%)68",
            "ly": "Ly (%)68",
            "eo": "Eo68",
            "mo": "M68",
            "ba": "BA68",
            "rbc": "RBCmo68",
            "mcv": "MCV68",
            "mch": "MCH68",
            "mchc": "MCHC",
        })

# ==================== DISPLAY ====================
if "person" in st.session_state:
    person = st.session_state["person"]

    selected_year = st.selectbox(
        "📅 เลือกปีที่ต้องการดูผลตรวจรายงาน", 
        options=sorted(years, reverse=True),
        format_func=lambda y: f"พ.ศ. {y + 2500}"
    )
    selected_cols = columns_by_year[selected_year]

    def render_health_report(person, year_cols):
        sbp = person.get(year_cols["sbp"], "")
        dbp = person.get(year_cols["dbp"], "")
        pulse = person.get(year_cols["pulse"], "-")
        weight = person.get(year_cols["weight"], "-")
        height = person.get(year_cols["height"], "-")
        waist = person.get(year_cols["waist"], "-")
    
        bp_result = "-"
        if sbp and dbp:
            bp_val = f"{sbp}/{dbp} ม.ม.ปรอท"
            bp_desc = interpret_bp(sbp, dbp)
            bp_result = f"{bp_val} - {bp_desc}"
    
        pulse = f"{pulse} ครั้ง/นาที" if pulse != "-" else "-"
        weight = f"{weight} กก." if weight else "-"
        height = f"{height} ซม." if height else "-"
        waist = f"{waist} ซม." if waist else "-"
    
        try:
            weight_val = float(weight.replace(" กก.", "").strip())
            height_val = float(height.replace(" ซม.", "").strip())
            bmi_val = weight_val / ((height_val / 100) ** 2)
        except Exception as e:
            st.warning(f"❌ ไม่สามารถคำนวณ BMI ได้: {e}")
            bmi_val = None
    
        summary_advice = html.escape(combined_health_advice(bmi_val, sbp, dbp))
    
        return f"""
        <div style="font-size: 18px; line-height: 1.8; color: inherit; padding: 24px 8px;">
            <div style="text-align: center; font-size: 22px; font-weight: bold;">รายงานผลการตรวจสุขภาพ</div>
            <div style="text-align: center;">วันที่ตรวจ: {person.get('วันที่ตรวจ', '-')}</div>
            <div style="text-align: center; margin-top: 10px;">
                โรงพยาบาลสันทราย 201 หมู่ที่ 11 ถนน เชียงใหม่ - พร้าว<br>
                ตำบลหนองหาร อำเภอสันทราย เชียงใหม่ 50290 โทร 053 921 199 ต่อ 167
            </div>
            <hr style="margin: 24px 0;">
            <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 32px; margin-bottom: 20px; text-align: center;">
                <div><b>ชื่อ-สกุล:</b> {person.get('ชื่อ-สกุล', '-')}</div>
                <div><b>อายุ:</b> {person.get('อายุ', '-')} ปี</div>
                <div><b>เพศ:</b> {person.get('เพศ', '-')}</div>
                <div><b>HN:</b> {person.get('HN', '-')}</div>
                <div><b>หน่วยงาน:</b> {person.get('หน่วยงาน', '-')}</div>
            </div>
            <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 32px; margin-bottom: 16px; text-align: center;">
                <div><b>น้ำหนัก:</b> {weight}</div>
                <div><b>ส่วนสูง:</b> {height}</div>
                <div><b>รอบเอว:</b> {waist}</div>
                <div><b>ความดันโลหิต:</b> {bp_result}</div>
                <div><b>ชีพจร:</b> {pulse}</div>
            </div>
            <div style="margin-top: 16px; text-align: center;">
                <b>คำแนะนำ:</b> {summary_advice}
            </div>
        </div>
        """

    st.markdown(render_health_report(person, selected_cols), unsafe_allow_html=True)

    # ================== CBC / BLOOD TEST DISPLAY ==================
    def generate_summary_advice(person, cbc_cols, blood_cols, sex):
        messages = []
    
        def abnormal(val, low=None, high=None, higher_is_better=False):
            try:
                val = float(str(val).replace(",", "").strip())
                if higher_is_better:
                    return "low" if val < low else "normal"
                if low is not None and val < low:
                    return "low"
                if high is not None and val > high:
                    return "high"
                return "normal"
            except:
                return None
    
        def highlight(label, value, tooltip):
            return f'<span title="{tooltip}">{label} ({value})</span>'
    
        def add(msg, crit=False):
            messages.append(f"🔸 {msg}")
    
        def cbc_advice(hb_result, wbc_result, plt_result):
            if all(x in ["", "-", None] for x in [hb_result, wbc_result, plt_result]):
                return ""
            hb = str(hb_result).strip()
            wbc = str(wbc_result).strip()
            plt = str(plt_result).strip()
            if plt in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย"]:
                return "ค่าเกล็ดเลือดต่ำผิดปกติ ควรพบแพทย์เพื่อตรวจหาสาเหตุและเฝ้าระวังอาการผิดปกติ"
            if hb == "ปกติ" and wbc == "ปกติ" and plt == "ปกติ":
                return ""
            if hb == "พบภาวะโลหิตจาง" and wbc == "ปกติ" and plt == "ปกติ":
                return "พบค่าภาวะโลหิตจาง ควรพบแพทย์เพื่อตรวจเพิ่มเติมและติดตามรักษา"
            if hb == "พบภาวะโลหิตจาง" and wbc in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"]:
                return "พบค่าผิดปกติของเม็ดเลือดแดงและขาว ควรพบแพทย์เพื่อตรวจเพิ่มเติมและพิจารณาการรักษา"
            if hb == "พบภาวะโลหิตจางเล็กน้อย" and wbc == "ปกติ" and plt == "ปกติ":
                return "ภาวะโลหิตจางเล็กน้อย แนะนำดูแลสุขภาพ ออกกำลังกาย และรับประทานอาหารที่มีธาตุเหล็ก"
            if hb == "ปกติ" and wbc in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"]:
                return "เม็ดเลือดขาวอยู่นอกเกณฑ์เล็กน้อย ควรดูแลสุขภาพและติดตามค่าซ้ำ"
            if plt == "สูงกว่าเกณฑ์":
                return "ค่าเกล็ดเลือดสูง ควรพบแพทย์เพื่อตรวจเพิ่มเติมและพิจารณาสาเหตุ"
            if hb == "พบภาวะโลหิตจางเล็กน้อย" and wbc in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"] and plt == "ปกติ":
                return "พบค่าผิดปกติของเม็ดเลือดแดงและขาว ควรดูแลสุขภาพและพิจารณาการติดตามค่าซ้ำ"
            return "ค่าผิดปกติในระบบเม็ดเลือด ควรพบแพทย์เพื่อตรวจเพิ่มเติม"
    
        hb = person.get(cbc_cols.get("hb"))
        hb_limit = 12 if sex == "หญิง" else 13
        hb_stat = "พบภาวะโลหิตจาง" if abnormal(hb, low=hb_limit) == "low" else "ปกติ"
    
        wbc = person.get(cbc_cols.get("wbc"))
        wbc_stat = abnormal(wbc, low=4000, high=10000)
        wbc_stat = {
            "normal": "ปกติ",
            "low": "ต่ำกว่าเกณฑ์",
            "high": "สูงกว่าเกณฑ์",
            None: "-"
        }.get(wbc_stat, "ผิดปกติ")
    
        plt = person.get(cbc_cols.get("plt"))
        plt_stat = abnormal(plt, low=150000, high=500000)
        plt_stat = {
            "normal": "ปกติ",
            "low": "ต่ำกว่าเกณฑ์",
            "high": "สูงกว่าเกณฑ์",
            None: "-"
        }.get(plt_stat, "ผิดปกติ")
    
        cbc_summary = cbc_advice(hb_stat, wbc_stat, plt_stat)
        if cbc_summary:
            add(cbc_summary, crit="ควรพบแพทย์" in cbc_summary)
    
        return "<br>".join(messages) if messages else "✅ สุขภาพอยู่ในเกณฑ์ดี ไม่มีค่าผิดปกติ"
