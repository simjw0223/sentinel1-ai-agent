import os
from datetime import datetime, timedelta, timezone
import requests
from pystac_client import Client
import streamlit as st
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# ==============================
# 0. 환경 변수(.env) 로드
# ==============================
load_dotenv()  # .env에서 OPENAI_API_KEY 불러오기

# Sentinel-1 저장 경로 (환경변수로 설정 가능, 기본값: ./downloads)
SAVE_DIR = os.getenv("SAVE_DIR", "./downloads")

# ==============================
# 1. Sentinel-1 다운로드 함수
# ==============================
def download_sentinel1_grd(
    lon: float,
    lat: float,
    date_str: str,
    save_dir: str = "downloads",
    days_margin: int = 10,
):
    """
    특정 위치(lon, lat)에서 기준 날짜(date_str)에 가장 가까운 Sentinel-1 GRD 장면을 자동으로 찾고 다운로드.
    - Dual-pol(VV/VH)인 경우: VV, VH 두 파일 모두 저장
    - Single-pol(VV 또는 VH)인 경우: 존재하는 편파만 저장

    Parameters
    ----------
    lon : float
        경도 (longitude)
    lat : float
        위도 (latitude)
    date_str : str
        기준 날짜 (YYYY-MM-DD)
    save_dir : str
        저장 디렉터리
    days_margin : int
        기준 날짜 ± days_margin 일 범위에서 검색
    """
    os.makedirs(save_dir, exist_ok=True)

    # 기준 날짜 (UTC 기준 aware datetime)
    center_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )

    # 검색 날짜 범위 (± days_margin)
    start_date = (center_date - timedelta(days=days_margin)).strftime(
        "%Y-%m-%dT00:00:00Z"
    )
    end_date = (center_date + timedelta(days=days_margin)).strftime(
        "%Y-%m-%dT23:59:59Z"
    )

    # STAC 연결
    catalog_url = "https://earth-search.aws.element84.com/v1"
    catalog = Client.open(catalog_url)

    # bbox (±0.2도 박스: 대략 20km 정도)
    delta = 0.2
    bbox = [lon - delta, lat - delta, lon + delta, lat + delta]

    # 검색
    search = catalog.search(
        collections=["sentinel-1-grd"],
        bbox=bbox,
        datetime=f"{start_date}/{end_date}",
        limit=50,
    )
    items = list(search.get_items())
    print(f"검색된 Sentinel-1 GRD 개수: {len(items)}")

    if not items:
        return (
            f"±{days_margin}일 범위에서도 Sentinel-1 GRD 영상을 찾지 못했습니다.\n"
            f"기준 날짜: {date_str}, 좌표(lon={lon}, lat={lat})"
        )

    # (1) 기준 날짜와 가장 가까운 item 선택
    def get_time_diff(item):
        item_datetime_str = item.properties.get("datetime")
        if item_datetime_str is None:
            return float("inf")
        # 예: '2023-06-01T09:12:34.123Z' → UTC aware datetime
        item_datetime = datetime.fromisoformat(
            item_datetime_str.replace("Z", "+00:00")
        )
        return abs((item_datetime - center_date).total_seconds())

    items.sort(key=get_time_diff)
    item = items[0]  # 가장 가까운 시간 차이
    selected_time = item.properties.get("datetime")
    print(f"선택된 item ID: {item.id}")
    print(f"촬영 시각: {selected_time}")

    # (2) VV, VH asset 가져오기
    assets = item.assets
    vv_asset = assets.get("vv")
    vh_asset = assets.get("vh")
    print("사용 가능한 편파 asset keys:", list(assets.keys()))

    def s3_to_http(href: str) -> str:
        """s3:// URL을 https:// URL로 변환"""
        if href.startswith("s3://"):
            no_scheme = href[len("s3://"):]  # 'bucket/path...'
            bucket, key = no_scheme.split("/", 1)
            return f"https://{bucket}.s3.amazonaws.com/{key}"
        else:
            return href

    downloaded_paths = {}

    # (3) VV 다운로드 (있으면)
    if vv_asset is not None:
        vv_href = vv_asset.href
        vv_url = s3_to_http(vv_href)
        print(f"VV 원본 href: {vv_href}")
        print(f"VV 다운로드 URL: {vv_url}")
        vv_filename = os.path.join(save_dir, f"{item.id}_vv.tif")

        resp = requests.get(vv_url, stream=True)
        if resp.status_code == 200:
            with open(vv_filename, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            downloaded_paths["VV"] = vv_filename
        else:
            print(f"VV 다운로드 실패 (status code: {resp.status_code})")
            downloaded_paths["VV"] = f"다운로드 실패 (status code: {resp.status_code})"
    else:
        downloaded_paths["VV"] = "해당 장면에 VV 편파 없음"

    # (4) VH 다운로드 (있으면)
    if vh_asset is not None:
        vh_href = vh_asset.href
        vh_url = s3_to_http(vh_href)
        print(f"VH 원본 href: {vh_href}")
        print(f"VH 다운로드 URL: {vh_url}")
        vh_filename = os.path.join(save_dir, f"{item.id}_vh.tif")

        resp = requests.get(vh_url, stream=True)
        if resp.status_code == 200:
            with open(vh_filename, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            downloaded_paths["VH"] = vh_filename
        else:
            print(f"VH 다운로드 실패 (status code: {resp.status_code})")
            downloaded_paths["VH"] = f"다운로드 실패 (status code: {resp.status_code})"
    else:
        downloaded_paths["VH"] = "해당 장면에 VH 편파 없음"

    # (5) 결과 문자열 반환
    result_msg = [
        "다운로드 결과:",
        f" VV: {downloaded_paths['VV']}",
        f" VH: {downloaded_paths['VH']}",
        f"촬영 시각: {selected_time}",
    ]
    return "\n".join(result_msg)


# ==============================
# 2. LangChain Tool 래핑
# ==============================
@tool
def sentinel1_download_tool(lon: float, lat: float, date_str: str) -> str:
    """
    지정한 경도(lon), 위도(lat), 날짜(date_str)에 대해
    해당 위치를 포함하는 ±10일 이내의 Sentinel-1 GRD 장면을 검색하고
    VV/VH 영상을 SAVE_DIR에 다운로드합니다.

    date_str 형식: 'YYYY-MM-DD'
    """
    return download_sentinel1_grd(
        lon=lon,
        lat=lat,
        date_str=date_str,
        save_dir=SAVE_DIR,
        days_margin=10,
    )


tools = [sentinel1_download_tool]


# ==============================
# 3. LLM + Tools 세팅
# ==============================
def get_llm_with_tools():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )
    return llm.bind_tools(tools)


# ==============================
# 4. Streamlit UI
# ==============================
st.set_page_config(page_title="Sentinel-1 Agent", page_icon="🛰️")
st.title("🛰️ Sentinel-1 다운로드 에이전트")
st.caption(
    "위·경도와 날짜를 기준으로 Sentinel-1 GRD(VV/VH)를 "
    f"자동 검색·다운로드하는 에이전트입니다.\n"
    f"다운로드 경로: {SAVE_DIR}"
)

tab_chat, tab_form = st.tabs(["🧠 Chat Agent", "🛰️ Direct Download"])

# ===== 공통: 상태 초기화 =====
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        SystemMessage(
            content=(
                "You are a helpful Sentinel-1 satellite data assistant. "
                "You can have casual conversations with users AND help them download Sentinel-1 data.\n\n"
                "When users request Sentinel-1 data (keywords: 'sentinel', '다운로드', '내려줘', etc.), "
                "extract location (lat, lon) and date, then IMMEDIATELY call sentinel1_download_tool. "
                "Do NOT ask for confirmation - just download it directly.\n\n"
                "If location is ambiguous, use Busan (lat=35.1796, lon=129.075) as default. "
                "If date is ambiguous, use a reasonable past date like 2023-06-01.\n\n"
                "After calling the tool, explain the download result in Korean in a friendly way.\n\n"
                "For general conversations (greetings, questions, chitchat), respond naturally in Korean without using tools."
            )
        )
    ]

# ========== 탭 1: Chat Agent ==========
with tab_chat:
    st.markdown("### 💬 자연어로 Sentinel-1 요청 및 대화")

    # 기존 대화 출력
    for msg in st.session_state["messages"]:
        if isinstance(msg, SystemMessage):
            continue
        elif isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage):
            # content가 있는 경우만 출력
            if msg.content:
                with st.chat_message("assistant"):
                    st.markdown(msg.content)
        elif isinstance(msg, ToolMessage):
            # ToolMessage는 내부용이니 출력 생략
            continue

    user_input = st.chat_input("예) 서울 근처 2024년 5월 28일 Sentinel-1 내려줘")

    if user_input:
        # 사용자 메시지 추가
        st.session_state["messages"].append(HumanMessage(content=user_input))
        
        with st.chat_message("user"):
            st.markdown(user_input)

        llm_with_tools = get_llm_with_tools()
        
        # LLM 호출
        with st.spinner("처리 중..."):
            response = llm_with_tools.invoke(st.session_state["messages"])

        # Tool calls가 있는 경우 - 바로 실행
        if getattr(response, "tool_calls", None):
            st.session_state["messages"].append(response)
            
            # 모든 tool call 실행
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                args = tool_call["args"]
                
                if tool_name == "sentinel1_download_tool":
                    with st.chat_message("assistant"):
                        st.markdown(
                            f"🛰️ Sentinel-1 다운로드를 시작합니다...\n\n"
                            f"- 위도: {args['lat']}\n"
                            f"- 경도: {args['lon']}\n"
                            f"- 날짜: {args['date_str']}\n"
                            f"- 검색 범위: ±10일"
                        )
                    
                    with st.spinner("Sentinel-1 GRD 검색 및 다운로드 중..."):
                        result_text = download_sentinel1_grd(
                            lon=args["lon"],
                            lat=args["lat"],
                            date_str=args["date_str"],
                            save_dir=SAVE_DIR,
                            days_margin=10,
                        )
                    
                    # Tool 실행 결과를 메시지에 추가
                    tool_message = ToolMessage(
                        content=result_text,
                        tool_call_id=tool_call["id"]
                    )
                    st.session_state["messages"].append(tool_message)
            
            # Tool 실행 후 최종 응답 생성
            with st.spinner("결과 정리 중..."):
                final_response = llm_with_tools.invoke(st.session_state["messages"])
            
            if final_response.content:
                with st.chat_message("assistant"):
                    st.markdown(final_response.content)
                    st.code(result_text, language="text")
                
                st.session_state["messages"].append(final_response)

        # Tool calls 없이 일반 응답만 온 경우 (일반 대화)
        else:
            if response.content:
                with st.chat_message("assistant"):
                    st.markdown(response.content)
                st.session_state["messages"].append(response)

        st.rerun()

# ========== 탭 2: Direct Download ==========
with tab_form:
    st.markdown("### 🛰️ 직접 위·경도 / 날짜를 입력해서 다운로드")

    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("위도 (lat)", value=35.1796, format="%.6f")
    with col2:
        lon = st.number_input("경도 (lon)", value=129.0750, format="%.6f")

    date_input = st.date_input("기준 날짜 (YYYY-MM-DD)", value=datetime(2023, 6, 2))
    days_margin = st.slider(
        "±일 범위 (days_margin)",
        min_value=1,
        max_value=30,
        value=10,
    )

    if st.button("Sentinel-1 GRD 다운로드 실행"):
        date_str = date_input.strftime("%Y-%m-%d")
        with st.spinner("Sentinel-1 GRD 검색 및 다운로드 중..."):
            result_text = download_sentinel1_grd(
                lon=lon,
                lat=lat,
                date_str=date_str,
                save_dir=SAVE_DIR,
                days_margin=days_margin,
            )
        st.success("다운로드 완료!")
        st.code(result_text, language="text")
