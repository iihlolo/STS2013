"""
Streamlit-GPT 초개인화 식단 추천 서비스
업데이트: 2025-05-02
필수 패키지 (requirements.txt):
    streamlit>=1.34
    openai>=1.0.0
    streamlit-authenticator>=0.2.3
    python-dotenv>=1.0
    pandas>=2.2

실행 절차:
    $ python source venv/bin/activate
    $ export OPENAI_API_KEY="sk-..."
    $ streamlit run app.py
"""

import os
import sqlite3
from datetime import date
from pathlib import Path

import streamlit as st
from openai import OpenAI
import streamlit_authenticator as stauth

import textwrap
import re

DEFAULT_PROFILE = (
    50,                 # weight
    160,                # height
    20,                 # age
    "여성",              # gender
    "보통(운동 주2-3회)",  # activity
    "유지",              # goal
    3,                  # meal_count
    "",                 # allergies
    ""                  # dislikes
)

# ────────────────────── UI ──────────────────────
st.markdown(
    """
    <style>
    /* 전체 배경 */
    [data-testid="stApp"] {
        background-color: #FFFDEB;
    }
    /* 글자 크기 */
    h1,h2,h3,h4,h5,h6 {
        margin: 0.35rem 0;
        text-align: center;
    }
    h5, h6 {
        font-size: 0.9rem;
        margin: 0.4rem 0 0.2rem 0;
    }
    /* 표 서식 */
    div.table-wrapper
    { width:100% !important; }
    table {
        background:#FFFFFF !important;
        border-collapse:collapse;
    }
    table thead{display:none;}
    table td {
        border:1px solid #DDD;
        padding:4px 8px;
    }
    table td:first-child {
        background:#F5F5F5;
        width:120px;
        white-space:nowrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ────────────────────── DB 초기화 ──────────────────────
DB_PATH = Path("ingredients.db")

def init_db(path: Path = DB_PATH):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    # 사용자 프로필
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            weight   REAL,
            height   REAL,
            age      INTEGER,
            gender   TEXT,
            activity TEXT,
            goal     TEXT,
            meal_count INTEGER,
            allergies TEXT,
            dislikes  TEXT
        )
    """)
    # 사용자별 재료
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            user TEXT NOT NULL,
            item TEXT NOT NULL,
            PRIMARY KEY (user, item)
        )
    """)
    cur.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cur.fetchall()]
    if "meal_count" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN meal_count INTEGER DEFAULT 3")
        conn.commit()
    conn.close()

init_db()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ────────────────────── 인증 설정 ──────────────────────
# 커넥션 · 커서 먼저 열기
conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# 사용자 없으면 데모 계정 삽입
cur.execute("SELECT COUNT(*) FROM users")
if cur.fetchone()[0] == 0:
    demo_hash = stauth.Hasher(["asdf1234"]).generate()[0]
    cur.execute("INSERT INTO users(username,password) VALUES(?,?)",
                ("eehni", demo_hash))
    conn.commit()
    
# 로그인 계정 읽기
cur.execute("SELECT username, password FROM users")
rows = cur.fetchall()

credentials = {"usernames": {
    u: {"name": u, "email": f"{u}@example.com", "password": p}
    for u, p in rows
}}

authenticator = stauth.Authenticate(credentials, "diet_app", "abcdef",
                                    cookie_expiry_days=1)

name, auth_status, username = authenticator.login("로그인", "main")

# ────────────────────── 계정 생성 ─────────────────────
if auth_status is None:
    with st.sidebar.expander("➕ 회원가입", expanded=False):
        new_user     = st.text_input("아이디")
        new_pass1    = st.text_input("비밀번호", type="password")
        new_pass2    = st.text_input("비밀번호 확인", type="password")
        if st.button("회원가입"):
            if not new_user or not new_pass1:
                st.warning("아이디와 비밀번호를 모두 입력하세요.")
            elif new_pass1 != new_pass2:
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                cur.execute("SELECT 1 FROM users WHERE username=?", (new_user,))
                if cur.fetchone():
                    st.error("이미 존재하는 아이디입니다.")
                else:
                    pw_hash = stauth.Hasher([new_pass1]).generate()[0]
                    cur.execute("""INSERT INTO users
                                   (username, password,
                                    weight, height, age, gender,
                                    activity, goal, meal_count,
                                    allergies, dislikes)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                                (new_user, pw_hash, *DEFAULT_PROFILE))
                    conn.commit()
                    st.success("🎉 회원가입 완료! 새로고침 후 다시 로그인해 주세요.")
                    st.stop()

if auth_status is False:
    st.error("😕 아이디 또는 비밀번호가 틀렸어요.")
elif auth_status is None:
    st.stop()

if auth_status:
    cur.execute("""SELECT weight, height, age, gender, activity, goal,
                          meal_count, allergies, dislikes
                   FROM users WHERE username=?""", (username,))
    data = cur.fetchone()
    if data is None:
        cur.execute("""INSERT INTO users
                       (username, password, weight, height, age, gender,
                        activity, goal, meal_count, allergies, dislikes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (username, "<dummy>", *DEFAULT_PROFILE))
        conn.commit()
        data = DEFAULT_PROFILE
    else:
        data = tuple( d if v is None else v
                      for v, d in zip(data, DEFAULT_PROFILE) )
    
    (def_w, def_h, def_age, def_gender, def_act, def_goal, def_meal, def_allerg, def_dis) = data
    
# ────────────────────── 유틸 함수 ──────────────────────

def calculate_bmr(weight: float, height: float, age: int, gender: str) -> float:
    if gender == "남성":
        return 10 * weight + 6.25 * height - 5 * age + 5
    return 10 * weight + 6.25 * height - 5 * age - 161

ACTIVITY_LEVELS = {
    "매우 적음(운동 거의 안 함)": 1.2,
    "보통(운동 주2-3회)"      : 1.375,
    "많음(운동 주4-5회)"      : 1.55,
    "매우 많음(거의 매일 운동함)": 1.725,
}

def tdee(bmr: float, activity: str) -> int:
    return int(bmr * ACTIVITY_LEVELS[activity])

def calorie_goal(tdee_val: int, goal: str) -> int:
    if goal == "감량":
        return tdee_val - 500
    if goal == "증량":
        return tdee_val + 300
    return tdee_val

def generate_plan(calorie_target: int, ingredients: str,
                  allergies: str, dislikes: str, meal_count: int) -> str:
    label_map = {
        1: ["오늘의 식사"],
        2: ["첫 번째 식사", "두 번째 식사"],
        3: ["아침", "점심", "저녁"],
        4: ["아침", "점심", "저녁", "간식"],
    }
    labels = label_map[meal_count]

    prompt = textwrap.dedent(f"""
    당신은 한국의 공인 영양사이자 가정 요리 전문가입니다.
    총 열량 **{calorie_target} kcal 이하** 로 {meal_count}회 식단을 작성하세요.
    
    **각 식사별로 표 1개**씩 만들되, ‘항목 = 행’ 구조 형식은 아래와 같습니다.

    ##### 아침: 계란찜과 현미밥
    |항목|내용|
    |---|---|
    |조리 시간|예) 15분|
    |열량 및 영양성분|예) 420kcal / 탄수 65 g · 단백 18 g · 지방 8 g|
    |레시피|예) 1) … <br>2) …<br>3) … |

    같은 형식으로 **{', '.join(labels)}** 모두 작성하세요.

    **#### 장보기 추천 레시피** 섹션도 동일한 표 형식에, 맨 위에 추가 재료 행을 덧붙여 2 가지 작성  
    (내 재료 + 추가 재료 ≤ 2 개 포함).
    예) ##### 1. 아보카도 샌드위치
    |항목|내용|
    |---|---|
    |추가 재료| 식빵, 마요네즈|
    |조리 시간| 15분|
    |열량 및 영양성분| 420kcal / 탄수 65 g · 단백 18 g · 지방 8 g|
    |레시피|1) … <br>2) …<br>3) … | 

    기본 재료 : {ingredients or '없음'}  
    제외 재료 : {(allergies+','+dislikes).strip(',') or '없음'}

    마크다운 표만 사용, 한국어로 작성
    """)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":"You are a helpful nutrition assistant."},
                  {"role":"user","content":prompt}],
        temperature=0.5,
    )
    return resp.choices[0].message.content

# ─────────────────── 사이드바: 프로필 입력 ───────────────────
with st.sidebar:
    authenticator.logout("🔓 로그아웃", "sidebar")
    st.header(f"👩🏻‍ {name}님 프로필")
    weight = st.number_input("체중(kg)", 30.0, 200.0, value=def_w, step=0.5)
    height = st.number_input("키(cm)", 120.0, 230.0, value=def_h, step=0.5)
    age = st.number_input("나이", 10, 100, value=def_age, step=1)
    GENDER_OPTIONS = ["여성", "남성"]
    gender_default = (GENDER_OPTIONS.index(def_gender)
                      if def_gender in GENDER_OPTIONS else 0)
    gender = st.selectbox("성별", GENDER_OPTIONS, index=gender_default)
    MEAL_OPTIONS = (1, 2, 3, 4)
    meal_default = MEAL_OPTIONS.index(def_meal) if def_meal in MEAL_OPTIONS else 2
    meal_count = st.selectbox("일일 식사 횟수", MEAL_OPTIONS, index=meal_default,
                              format_func=lambda x: {1:"1회",2:"2회",3:"3회",4:"4회"}[x])
    ACT_KEYS = list(ACTIVITY_LEVELS.keys())
    act_default = ACT_KEYS.index(def_act) if def_act in ACT_KEYS else 1
    activity = st.selectbox("활동량", ACT_KEYS, index=act_default)
    GOAL_OPTIONS = ["감량", "유지", "증량"]
    goal_default = GOAL_OPTIONS.index(def_goal) if def_goal in GOAL_OPTIONS else 1
    goal = st.radio("체중 목표", GOAL_OPTIONS, index=goal_default)
    allergies = st.text_input("알레르기(쉼표로 구분)", value=def_allerg)
    dislikes = st.text_input("비선호 식품(쉼표로 구분)", value=def_dis)
    if st.button("프로필 저장"):
        cur.execute("""
            UPDATE users SET weight=?, height=?, age=?, gender=?,
                             activity=?, goal=?, meal_count=?, allergies=?, dislikes=?
            WHERE username=?""",
            (weight, height, age, gender, activity, goal, meal_count, allergies, dislikes, username))
        conn.commit()
        st.success("✅ 프로필이 저장되었습니다!")

# ────────────────────── 내 재료 관리 ──────────────────────
st.title("🍽️ AI 식단 플래너")
st.markdown("###### 내 재료·내AI표에 딱 맞춘 집밥 식단을 AI로 뚝딱!")
st.divider()

with st.container():
    st.subheader("🛒 내 재료 목록")

    # 현재 재료 불러오기
    cur.execute("SELECT item FROM ingredients WHERE user=? ORDER BY item", (username,))
    current_items = [row[0] for row in cur.fetchall()]

    col1, col2 = st.columns([4, 1], gap="small")
    st.markdown(
        """
        <style>
        /* 두 번째 column 안의 첫 번째 버튼(추가)만 살짝 ↓ */
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(2) button {
            transform: translateY(28px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 재료 추가
    with col1:
        new_item = st.text_input("재료 추가(쉼표로 구분)", placeholder="예: 시금치, 두부, 양파")
    with col2:
        if st.button("추가", use_container_width=True) and new_item:
            items = [x.strip() for x in new_item.split(",") if x.strip()]
            cur.executemany(
                "INSERT OR IGNORE INTO ingredients(user, item) VALUES(?,?)",
                [(username, itm) for itm in items],
            )
            conn.commit()
            st.rerun()

    # 재료 삭제 
    if current_items:
        del_col1, del_col2 = st.columns([4, 1], gap="small")

        with del_col1:
            remove = st.multiselect("삭제할 재료 선택", current_items)

        with del_col2:
            if st.button("삭제", use_container_width=True, disabled=not remove):
                cur.executemany(
                    "DELETE FROM ingredients WHERE user=? AND item=?",
                    [(username, r) for r in remove]
                )
                conn.commit()
                st.rerun()

    conn.close()

    ingredients = ", ".join(current_items)

    st.markdown("---")

# ────────────────────── 식단 생성 ──────────────────────
if st.button("🍳 식단 생성"):
    if not client.api_key:
        st.error("OPENAI_API_KEY 환경 변수를 설정하세요.")
        st.stop()

    bmr_val   = calculate_bmr(weight, height, age, gender)
    tdee_val  = tdee(bmr_val, activity)
    target_kcal = calorie_goal(tdee_val, goal)

    st.success(f"일일 목표 열량: {target_kcal} kcal (TDEE: {tdee_val})")

    with st.spinner("GPT-4o가 식단을 작성 중입니다…"):
        plan_md = generate_plan(
            target_kcal, ingredients, allergies, dislikes, meal_count
        )

    plan_md = re.sub(r'^[ \t]+', '', plan_md, flags=re.MULTILINE)

    st.markdown("#### 🍱 오늘의 추천 식단")
    st.markdown(f"##### 1일 {meal_count}식 구성 ({target_kcal} kcal)")
    st.markdown(plan_md, unsafe_allow_html=True)    # 태그 랜더링
    st.caption(f"생성일: {date.today()}  •  모델: GPT-4o-mini")

st.info("💡 본 식단은 참고용으로, 의학적 조언을 대체하지 않습니다.")




