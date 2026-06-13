# app.py
import streamlit as st
import pandas as pd
import requests
import base64
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

st.set_page_config(page_title="Pain Consult KU KPS", layout="wide")

# =========================
# Secrets.toml required
# =========================
# [openai]
# api_key = "sk-..."
#
# [github]
# token = "ghp_..."
# owner = "your_github_username"
# repo = "your_repo"
# branch = "main"
# csv_path = "pain_consult.csv"

client = OpenAI(api_key=st.secrets["openai"]["api_key"])

GITHUB_TOKEN = st.secrets["github"]["token"]
OWNER = st.secrets["github"]["owner"]
REPO = st.secrets["github"]["repo"]
BRANCH = st.secrets["github"].get("branch", "main")
CSV_PATH = st.secrets["github"].get("csv_path", "pain_consult.csv")

PASSWORD_DOCTOR = "5942"

FACULTIES = [
    "คณะเกษตร กำแพงแสน",
    "คณะวิศวกรรมศาสตร์ กำแพงแสน",
    "คณะวิทยาศาสตร์การกีฬาและสุขภาพ",
    "คณะศิลปศาสตร์และวิทยาศาสตร์",
    "คณะศึกษาศาสตร์และพัฒนศาสตร์",
    "คณะอุตสาหกรรมบริการ",
    "คณะสัตวแพทยศาสตร์",
    "คณะอื่นๆ",
    "สำนักงานวิทยาเขตกำแพงแสน",
    "สำนักส่งเสริมและฝึกอบรม กำแพงแสน",
    "ศูนย์เทคโนโลยีชีวภาพเกษตร",
    "หน่วยงานอื่นๆ",
    "สหกรณ์ออมทรัพย์มหาวิทยาลัยเกษตรศาสตร์",
    "ร้านสหกรณ์เกษตรศาสตร์ จำกัด",
    "หน่วยงานอื่นๆนอกวิทยาเขต",
]

RED_FLAGS = [
    "ไข้สูง หรือสงสัยติดเชื้อรุนแรง",
    "อุบัติเหตุรุนแรง / กระแทกศีรษะ / หมดสติ",
    "แขนขาอ่อนแรง ชา หรือเดินผิดปกติ",
    "กลั้นปัสสาวะหรืออุจจาระไม่ได้",
    "ปวดศีรษะรุนแรงที่สุดในชีวิต",
    "คอแข็ง ซึม ชัก",
    "เจ็บหน้าอก หายใจเหนื่อย หน้ามืด",
    "ปวดกลางคืนมากขึ้นเรื่อยๆ / น้ำหนักลดผิดปกติ",
]

def bkk_now():
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")

def get_github_file():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{CSV_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers, params={"ref": BRANCH})
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return pd.read_csv(pd.io.common.StringIO(content)), data["sha"]
    elif r.status_code == 404:
        return pd.DataFrame(), None
    else:
        st.error(f"อ่านไฟล์ GitHub ไม่สำเร็จ: {r.status_code} {r.text}")
        st.stop()

def save_github_csv(df, sha=None):
    csv_text = df.to_csv(index=False, encoding="utf-8-sig")
    encoded = base64.b64encode(csv_text.encode("utf-8-sig")).decode("utf-8")
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{CSV_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    payload = {
        "message": f"Update pain consult {bkk_now()}",
        "content": encoded,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=headers, json=payload)
    if r.status_code not in [200, 201]:
        st.error(f"บันทึก GitHub ไม่สำเร็จ: {r.status_code} {r.text}")
        st.stop()

def ask_gpt_for_doctor(record):
    prompt = f"""
คุณเป็นผู้ช่วยแพทย์คลินิก Pain Consult ในมหาวิทยาลัย
กรุณาสรุปข้อมูลผู้ป่วยภาษาไทยแบบกระชับสำหรับแพทย์เท่านั้น

ให้ตอบเป็นหัวข้อ:
1. สรุปอาการสำคัญ
2. ประเภท pain: acute / subacute / chronic
3. Differential diagnosis ที่ควรคิด
4. Red flags ที่ตรวจแล้วพบ/ไม่พบ
5. ข้อมูล function และ PEG score
6. คำแนะนำการตรวจร่างกายเฉพาะจุด
7. แนวทางดูแลเบื้องต้นแบบปลอดภัย
8. ข้อควรส่งต่อ/นัดติดตาม

ข้อมูล:
{json.dumps(record, ensure_ascii=False, indent=2)}
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "คุณช่วยแพทย์สรุปข้อมูล pain consult อย่างระมัดระวัง ไม่วินิจฉัยเกินข้อมูล"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"AI error: {e}"

st.title("Pain Consult 07.00–08.30 น.")
st.caption("สำหรับนักศึกษา/บุคลากร มก. กำแพงแสน — ระบบคัดกรองและบันทึกข้อมูลเบื้องต้น")

menu = st.sidebar.radio(
    "เลือกประเภทอาการปวด",
    ["Acute pain < 2 สัปดาห์", "Subacute pain 1–12 สัปดาห์", "Chronic pain > 3 เดือน"]
)

with st.form("pain_form"):
    st.header("1) ข้อมูลทั่วไป")

    c1, c2, c3 = st.columns(3)
    student_id = c1.text_input("เลขประจำตัวนักศึกษา/บุคลากร")
    age = c2.number_input("อายุ", min_value=10, max_value=100, step=1)
    sex = c3.selectbox("เพศ", ["หญิง", "ชาย", "ไม่ระบุ/อื่นๆ"])

    email = st.text_input("อีเมล์")
    faculty = st.selectbox("คณะ/หน่วยงาน", FACULTIES)

    st.header("2) Red flags")
    red_selected = st.multiselect("ถ้ามีข้อใดข้อหนึ่ง ระบบจะแนะนำให้พบแพทย์/ส่งต่อทันที", RED_FLAGS)

    st.header("3) ความต้องการของผู้มารับบริการ")
    needs = st.multiselect(
        "เลือกได้มากกว่า 1 ข้อ",
        ["ลดปวด", "กลับไปเล่นกีฬา", "ขอใบรับรองแพทย์", "ประเมินความเสี่ยงก่อนแข่งขัน"]
    )
    other_need = st.text_area("ความต้องการอื่นๆ ไม่เกิน 100 คำ", max_chars=700)

    st.header("4) PEG Score")
    peg_pain = st.slider("P: ปวดเฉลี่ยใน 1 สัปดาห์ที่ผ่านมา", 0, 10, 0)
    peg_enjoy = st.slider("E: ปวดรบกวนความสุข/การใช้ชีวิต", 0, 10, 0)
    peg_general = st.slider("G: ปวดรบกวนกิจกรรมทั่วไป", 0, 10, 0)
    peg_score = round((peg_pain + peg_enjoy + peg_general) / 3, 2)
    st.info(f"PEG score = {peg_score}")

    st.header(f"5) รายละเอียดอาการ: {menu}")

    common_location = st.multiselect(
        "ตำแหน่งที่ปวด",
        ["ศีรษะ", "คอ", "บ่า", "ไหล่", "หลัง", "เอว", "สะโพก", "เข่า", "ข้อเท้า", "ข้อมือ", "ท้องน้อย", "อื่นๆ"]
    )
    pain_score_now = st.slider("คะแนนปวดขณะนี้", 0, 10, 0)
    pain_character = st.multiselect(
        "ลักษณะปวด",
        ["ตื้อ", "จี๊ด", "แสบ", "ร้าว", "ตุบๆ", "เกร็ง", "ชา", "หนักๆ", "อื่นๆ"]
    )
    function_limit = st.multiselect(
        "รบกวนการทำงานใด",
        ["เรียน", "นอน", "เดิน", "นั่งนาน", "เล่นกีฬา", "ทำงานหน้าคอม", "กิจวัตรประจำวัน", "ไม่รบกวนมาก"]
    )

    extra = {}

    if menu.startswith("Acute"):
        st.subheader("Acute pain / Sport injury")
        extra["sport_type"] = st.selectbox("ชนิดกีฬา/กิจกรรม", ["ฟุตบอล", "บาสเกตบอล", "วอลเลย์บอล", "วิ่ง", "ฟิตเนส", "เทนนิส", "อื่นๆ"])
        extra["mechanism"] = st.multiselect("กลไกการบาดเจ็บ", ["ล้ม", "บิด", "ปะทะ", "ยกน้ำหนัก", "ใช้งานซ้ำ", "ไม่ชัดเจน"])
        extra["continued_play"] = st.radio("หลังเกิดเหตุ", ["เล่น/เดินต่อได้", "เล่นต่อไม่ได้", "เดินลงน้ำหนักไม่ได้"])
        extra["swelling_bruise"] = st.checkbox("มีบวม/ช้ำ")
        extra["limited_rom"] = st.checkbox("ขยับได้น้อยลง")
        extra["numb_weak"] = st.checkbox("มีชา/อ่อนแรง")

    elif menu.startswith("Subacute"):
        st.subheader("Subacute pain")
        subtype = st.selectbox("กลุ่มอาการ", ["ปวดศีรษะ", "ปวดประจำเดือน", "ปวดอื่นๆ 1–12 สัปดาห์"])
        extra["subtype"] = subtype

        if subtype == "ปวดศีรษะ":
            extra["headache_site"] = st.multiselect("ตำแหน่งปวดศีรษะ", ["ข้างเดียว", "สองข้าง", "หน้าผาก", "ท้ายทอย", "รอบตา"])
            extra["headache_assoc"] = st.multiselect("อาการร่วม", ["คลื่นไส้", "อาเจียน", "แพ้แสง", "แพ้เสียง", "เวียนศีรษะ", "ตาพร่า"])
            extra["trigger"] = st.multiselect("สิ่งกระตุ้น", ["อดนอน", "เครียด", "อ่านหนังสือ", "คอมพิวเตอร์", "มือถือ", "ประจำเดือน", "อาหาร/เครื่องดื่ม"])
        elif subtype == "ปวดประจำเดือน":
            extra["menstrual_day"] = st.selectbox("เริ่มปวด", ["ก่อนมีประจำเดือน", "วันแรก", "วันที่ 2–3", "มากกว่า 3 วัน"])
            extra["menstrual_bleeding"] = st.selectbox("ปริมาณประจำเดือน", ["ปกติ", "มากกว่าปกติ", "กะปริดกะปรอย", "ไม่แน่ใจ"])
            extra["dysmenorrhea_assoc"] = st.multiselect("อาการร่วม", ["คลื่นไส้", "อาเจียน", "ท้องเสีย", "เวียนศีรษะ", "เป็นลม"])
            extra["miss_class"] = st.checkbox("ทำให้ขาดเรียน/ทำกิจกรรมไม่ได้")
        else:
            extra["subacute_note"] = st.text_area("รายละเอียดเพิ่มเติม")

    else:
        st.subheader("Chronic pain / Office syndrome")
        extra["computer_hours"] = st.selectbox("ใช้คอมพิวเตอร์/มือถือรวมต่อวัน", ["<2 ชม.", "2–4 ชม.", "4–8 ชม.", ">8 ชม."])
        extra["office_symptoms"] = st.multiselect("อาการร่วม", ["ปวดศีรษะ", "ตาล้า", "เวียนศีรษะ", "ชามือ", "ปวดร้าวลงแขน", "นอนไม่หลับ"])
        extra["exercise_freq"] = st.selectbox("ออกกำลังกาย", ["ไม่ออก", "1–2 วัน/สัปดาห์", "3–4 วัน/สัปดาห์", "≥5 วัน/สัปดาห์"])
        extra["sleep_hours"] = st.selectbox("นอนเฉลี่ย", ["<5 ชม.", "5–6 ชม.", "7–8 ชม.", ">8 ชม."])
        extra["fear_movement"] = st.slider("กลัวการขยับ/กลัวปวดมากขึ้น", 0, 10, 0)
        extra["catastrophe"] = st.slider("กังวลว่าอาการจะไม่หายหรือร้ายแรง", 0, 10, 0)

    submitted = st.form_submit_button("บันทึกข้อมูล")

if submitted:
    if not student_id or not email:
        st.warning("กรุณากรอกเลขประจำตัวและอีเมล์")
        st.stop()

    record = {
        "timestamp_bkk": bkk_now(),
        "student_id": student_id,
        "age": age,
        "sex": sex,
        "email": email,
        "faculty": faculty,
        "pain_category": menu,
        "red_flags": "; ".join(red_selected),
        "needs": "; ".join(needs),
        "other_need": other_need,
        "pain_location": "; ".join(common_location),
        "pain_score_now": pain_score_now,
        "pain_character": "; ".join(pain_character),
        "function_limit": "; ".join(function_limit),
        "peg_pain": peg_pain,
        "peg_enjoyment": peg_enjoy,
        "peg_general_activity": peg_general,
        "peg_score": peg_score,
        "extra_json": json.dumps(extra, ensure_ascii=False),
    }

    if red_selected:
        record["ai_summary_doctor"] = "พบ Red flags: ควรหยุดแบบฟอร์มและให้พบแพทย์/ส่งต่อทันที"
        df, sha = get_github_file()
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        save_github_csv(df, sha)
        st.error("พบ Red flags กรุณาติดต่อเจ้าหน้าที่/แพทย์ทันที ไม่ต้องทำแบบฟอร์มต่อ")
        st.success("บันทึกข้อมูล Red flags แล้ว")
        st.stop()

    ai_summary = ask_gpt_for_doctor(record)
    record["ai_summary_doctor"] = ai_summary

    df, sha = get_github_file()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    save_github_csv(df, sha)

    st.success("บันทึกข้อมูลเรียบร้อยแล้ว")
    st.info("ข้อมูล AI สำหรับแพทย์ถูกซ่อนไว้ ต้องใช้รหัสแพทย์")

st.divider()
st.header("พื้นที่แพทย์เท่านั้น")

doctor_pass = st.text_input("รหัสแพทย์", type="password")

if doctor_pass == PASSWORD_DOCTOR:
    st.success("เข้าสู่โหมดแพทย์")
    df, sha = get_github_file()

    if df.empty:
        st.info("ยังไม่มีข้อมูล")
    else:
        st.dataframe(df.tail(20), use_container_width=True)

        selected = st.selectbox(
            "เลือก record ล่าสุดเพื่อดู AI summary",
            options=list(range(len(df)-1, -1, -1)),
            format_func=lambda i: f"{df.loc[i, 'timestamp_bkk']} | {df.loc[i, 'student_id']} | {df.loc[i, 'pain_category']}"
        )

        st.subheader("AI Summary สำหรับแพทย์")
        st.write(df.loc[selected, "ai_summary_doctor"])

        st.download_button(
            "ดาวน์โหลด CSV",
            df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="pain_consult.csv",
            mime="text/csv"
        )

elif doctor_pass:
    st.error("รหัสไม่ถูกต้อง")