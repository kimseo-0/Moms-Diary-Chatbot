import streamlit as st
import requests
from PIL import Image
from pathlib import Path
import uuid
import io

# --- (!!!) 중요 설정 (!!!) ---
# ComfyUI의 'input' 폴더 경로를 정확하게 지정해야 합니다.
# FastAPI/ComfyUI 서버와 Streamlit 앱이 같은 컴퓨터에서 실행되어야 합니다.
COMFYUI_INPUT_PATH = Path(r"c:\Potenup\ComfyUI-Study\ComfyUI\input") 

# FastAPI 서버 주소 (프로젝트의 FastAPI에 연결)
# 기본값: 로컬 FastAPI가 8000에서 /api 접두어로 라우터를 포함하므로 아래가 기본입니다.
API_URL = "http://127.0.0.1:9000/generate"
# ------------------------------

st.set_page_config(layout="wide")
st.title("얼굴 합치기")

# ComfyUI input 폴더가 존재하는지 확인
if not COMFYUI_INPUT_PATH.exists():
    st.error(f"설정 오류: ComfyUI input 폴더를 찾을 수 없습니다.\n경로: {COMFYUI_INPUT_PATH}\n`st_app.py` 코드 상단의 `COMFYUI_INPUT_PATH` 변수를 수정하세요.")
    st.stop()


def save_uploaded_image(uploaded_file):
    """
    업로드된 파일을 ComfyUI input 폴더에 저장하고 파일명을 반환합니다.
    """
    try:
        # 고유한 파일명 생성 (png로 통일)
        filename = f"st_upload_{uuid.uuid4()}.png"
        save_path = COMFYUI_INPUT_PATH / filename
        
        # 이미지로 열어서 PNG로 저장 (포맷 통일)
        image = Image.open(uploaded_file)
        image.save(save_path, "PNG")
        
        return filename
    except Exception as e:
        st.error(f"이미지 저장 실패: {e}")
        return None

# --- UI 레이아웃 ---

col1, col2 = st.columns(2)

with col1:
    st.header("엄마 얼굴")
    img1_file = st.file_uploader("얼굴이 잘 보이는 이미지를 업로드하세요.", type=["jpg", "jpeg", "png"], key="img1")
    if img1_file:
        st.image(img1_file, use_column_width=True)

with col2:
    st.header("아빠 얼굴")
    img2_file = st.file_uploader("참고할 포즈나 스타일 이미지를 업로드하세요.", type=["jpg", "jpeg", "png"], key="img2")
    if img2_file:
        st.image(img2_file, use_column_width=True)

st.divider()

gender = st.radio("성별", ("남자", "여자"))

st.header("프롬프트")
if gender == "남자":
    pos_prompt = st.text_area("Positive Prompt (긍정 프롬프트)", "a boy 1 months olds, handsome")
else:
    pos_prompt = st.text_area("Positive Prompt (긍정 프롬프트)", "a girl 1 months olds, beautiful")

neg_prompt = st.text_area("Negative Prompt (부정 프롬프트)", "(worst quality, low quality, 2k), blurry, ugly, watermark, text")

st.divider()

if st.button("이미지 생성하기", use_container_width=True, type="primary"):
    if img1_file and img2_file and pos_prompt:
        with st.spinner("이미지를 생성 중입니다... (1~2분 소요) 🏃‍♂️"):
            # 1. 업로드된 이미지를 ComfyUI input 폴더에 저장
            filename1 = save_uploaded_image(img1_file)
            filename2 = save_uploaded_image(img2_file)
            
            if filename1 and filename2:
                st.info(f"이미지 저장 완료:\n1. {filename1}\n2. {filename2}")
                
                # 2. FastAPI 백엔드에 요청
                payload = {
                    "positive_prompt": pos_prompt,
                    "negative_prompt": neg_prompt,
                    "image1_filename": filename1,
                    "image2_filename": filename2
                }
                
                try:
                    response = requests.post(API_URL, json=payload, timeout=300) # 5분 타임아웃

                    if response.status_code == 200:
                        st.header("🎉 생성 완료!")
                        # response.content is raw PNG bytes
                        st.image(response.content, caption="생성된 이미지", use_column_width=True)
                        st.success("이미지 생성에 성공했습니다!")
                    else:
                        st.error(f"백엔드 오류 (Status code: {response.status_code})")
                        try:
                            st.json(response.json())
                        except:
                            st.text(response.text)

                except requests.exceptions.ConnectionError:
                    st.error(f"연결 실패: FastAPI 서버({API_URL})가 실행 중인지 확인하세요.")
                except requests.exceptions.ReadTimeout:
                    st.error("오류: 이미지 생성 시간이 5분을 초과했습니다. (Timeout)")
                except Exception as e:
                    st.error(f"알 수 없는 오류 발생: {e}")
                    
    elif not img1_file or not img2_file:
        st.warning("두 개의 이미지를 모두 업로드해야 합니다.")
    else:
        st.warning("긍정 프롬프트를 입력해야 합니다.")