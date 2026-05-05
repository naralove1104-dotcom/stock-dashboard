import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import bcrypt
import os
import textwrap # <--- 완벽 조립 도구

# --- 1. 보안 및 DB 설정 ---
def get_db():
    if "google" not in st.secrets:
        return "secret_missing", "Streamlit Settings -> Secrets 설정이 누락되었습니다."
    
    try:
        # 1. 금고에서 안전한 한 줄짜리 암호 가져오기
        raw_key = st.secrets["google"]["key"]
        email = st.secrets["google"]["email"]
        
        # 2. 파이썬이 구글이 좋아하는 형태로 암호를 자동 조립합니다. (복사/붙여넣기 에러 차단)
        wrapped_key = '\n'.join(textwrap.wrap(raw_key, 64))
        real_private_key = f"-----BEGIN PRIVATE KEY-----\n{wrapped_key}\n-----END PRIVATE KEY-----\n"
        
        # 3. 신분증 완성하기
        key_dict = {
            "type": "service_account",
            "project_id": "custom-temple-495412-u8",
            "private_key_id": "28ef0598aa85da298f2c8a6a74b62c048decbcce",
            "private_key": real_private_key,
            "client_email": email,
            "client_id": "100974354815304032949",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{email.replace('@', '%40')}",
            "universe_domain": "googleapis.com"
        }
        
        # 4. 구글 시트 연결
        client = gspread.service_account_from_dict(key_dict)
        sheet = client.open("회원DB").get_worksheet(0)
        return "success", sheet
        
    except Exception as e:
        return "auth_error", f"구글 시트 연결 오류: {e}"

# --- 2. 회원가입 및 로그인 로직 ---
def register_user(user_id, pw, name, pen, phone):
    status, db = get_db()
    if status != "success": return False
    hashed = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.append_row([user_id, hashed, name, pen, phone, "정상"])
    return True

def check_login(user_id, pw):
    status, db = get_db()
    if status != "success": return None
    records = db.get_all_records()
    for row in records:
        if str(row['ID']) == str(user_id):
            if bcrypt.checkpw(pw.encode('utf-8'), row['비밀번호(암호화)'].encode('utf-8')):
                return row['상태']
    return None

# --- 3. UI 구성 ---
st.set_page_config(layout="wide")

status, data = get_db()

if status != "success":
    st.error("🚫 시스템 연결 설정 확인 중...")
    st.warning(f"상세 원인: {data}")
    st.stop()

if 'auth' not in st.session_state:
    st.session_state['auth'] = False
    st.session_state['status'] = None

# --- 로그인 / 회원가입 화면 ---
if not st.session_state['auth']:
    st.title("🔐 정회원 전용 시스템")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        login_id = st.text_input("아이디")
        login_pw = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            status_val = check_login(login_id, login_pw)
            if status_val:
                st.session_state['auth'] = True
                st.session_state['status'] = status_val
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                
    with tab2:
        st.subheader("신규 회원가입")
        new_id = st.text_input("사용할 아이디", key="reg_id")
        new_pw = st.text_input("사용할 비밀번호", type="password", key="reg_pw")
        new_name = st.text_input("실명", key="reg_name")
        new_pen = st.text_input("필명", key="reg_pen")
        new_phone = st.text_input("전화번호", key="reg_phone")
        
        if st.button("가입 신청하기"):
            if new_id and new_pw and new_name:
                if register_user(new_id, new_pw, new_name, new_pen, new_phone):
                    st.success("✅ 회원가입 신청이 완료되었습니다! 이제 로그인 탭에서 로그인을 진행해 주세요.")
                else:
                    st.error("가입 처리 중 오류가 발생했습니다.")
            else:
                st.warning("모든 필수 정보를 입력해 주세요.")

# --- 대시보드 화면 ---
else:
    if st.session_state['status'] == "정상":
        st.title("📊 상장사 재무정보 대시보드")
        if st.sidebar.button("로그아웃"):
            st.session_state['auth'] = False
            st.rerun()
            
        file_path = 'data.csv'
        
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, header=0, encoding='utf-8-sig')
                df.columns = df.columns.str.strip()
                target_items = ["매출액(3개월)", "영업이익(3개월)", "OPM(3개월)", "순이익(3개월)", "자산총계", "부채총계", "자본총계"]
                df = df[df['항목'].isin(target_items)]
                
                selected_company = st.selectbox("분석할 종목을 선택하세요:", df['종목명'].unique())
                company_data = df[df['종목명'] == selected_company]
                
                id_vars = ['종목코드', '종목명', '대분류', '항목']
                date_cols = [c for c in company_data.columns if c not in id_vars]
                melted = company_data.melt(id_vars=id_vars, value_vars=date_cols, var_name='날짜_원', value_name='금액')
                melted['날짜'] = pd.to_datetime(melted['날짜_원'], format='%Y%m', errors='coerce')
                melted['금액'] = pd.to_numeric(melted['금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                
                for item in target_items:
                    item_df = melted[melted['항목'] == item].sort_values('날짜')
                    if not item_df.empty:
                        st.subheader(f"📈 {item} 추이")
                        st.plotly_chart(px.line(item_df, x='날짜', y='금액', markers=True), use_container_width=True)
            except Exception as e:
                st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        else:
            st.error(f"데이터 파일을 찾을 수 없습니다. 깃허브에 'data.csv' 파일이 있는지 확인해주세요.")
            
    else:
        st.error("🚫 이용 권한이 만료된 계정입니다. 연장 후 이용해 주세요.")
        if st.button("돌아가기"):
            st.session_state['auth'] = False
            st.rerun()
