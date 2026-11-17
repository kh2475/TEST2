import json
import os
import re
import secrets
import threading
import uuid
from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")  # 경로 조작 방지를 위해 토큰 형식을 엄격히 검증
MAX_LEN = 50  # 아이템 이름 최대 길이


# ---------- 저장/불러오기 (링크별 개인 목록, 파일이 단일 진실 공급원) ----------
@st.cache_resource
def get_lock() -> threading.Lock:
    """같은 서버 안의 여러 세션이 동시에 쓰지 않도록 하는 락"""
    return threading.Lock()


def get_token() -> str:
    """URL의 ?u=토큰으로 방문자를 구분. 없거나 형식이 잘못됐으면 새로 발급"""
    token = st.query_params.get("u", "")
    if not TOKEN_RE.fullmatch(token):
        token = secrets.token_urlsafe(12)
        st.query_params["u"] = token
    return token


def data_file() -> Path:
    return DATA_DIR / f"{st.session_state.token}.json"


def load_items() -> list:
    """내 목록 파일 로드. 파일이 없거나 깨졌으면 빈 목록"""
    try:
        data = json.loads(data_file().read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [
            {"id": str(d["id"]), "name": str(d["name"]), "checked": bool(d.get("checked", False))}
            for d in data
            if isinstance(d, dict) and "id" in d and "name" in d
        ]
    except (OSError, ValueError):
        return []


def save_items(items: list):
    """임시 파일에 쓴 뒤 교체(원자적 저장). 실패해도 앱은 계속 동작"""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        tmp = data_file().with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, data_file())
    except OSError:
        st.session_state.save_failed = True


def update(change):
    """최신 파일을 읽고 → 변경 → 저장을 락 안에서 수행 (다른 탭의 변경을 덮어쓰지 않음)"""
    with get_lock():
        items = load_items()
        change(items)
        save_items(items)


# ---------- 상태 ----------
def init_page():
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")


def init_state():
    """editing_id = 수정 중인 항목 id (한 번에 하나만)"""
    st.session_state.token = get_token()
    st.session_state.setdefault("editing_id", None)
    st.session_state.setdefault("edit_error", False)


# ---------- 콜백 (상태 변경) ----------
def add_item(name: str) -> bool:
    name = name.strip()[:MAX_LEN]
    if not name:
        return False
    update(lambda items: items.append({"id": str(uuid.uuid4()), "name": name, "checked": False}))
    return True


def toggle_item(item_id: str):
    checked = st.session_state[f"chk_{item_id}"]

    def change(items):
        for i in items:
            if i["id"] == item_id:
                i["checked"] = checked

    update(change)


def delete_item(item_id: str):
    update(lambda items: items.__setitem__(slice(None), [i for i in items if i["id"] != item_id]))


def clear_checked():
    update(lambda items: items.__setitem__(slice(None), [i for i in items if not i["checked"]]))


def start_edit(item_id: str):
    item = next((i for i in load_items() if i["id"] == item_id), None)
    if item:
        st.session_state.editing_id = item_id
        st.session_state[f"edit_{item_id}"] = item["name"]
        st.session_state.edit_error = False


def cancel_edit():
    st.session_state.editing_id = None
    st.session_state.edit_error = False


def save_edit(item_id: str):
    new_name = st.session_state.get(f"edit_{item_id}", "").strip()[:MAX_LEN]
    if not new_name:
        st.session_state.edit_error = True
        return

    def change(items):
        for i in items:
            if i["id"] == item_id:
                i["name"] = new_name

    update(change)
    cancel_edit()


# ---------- 화면 ----------
CSS = """
<style>
/* 모바일에서도 컬럼이 세로로 쌓이지 않고 한 줄 유지 */
div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center; gap: 0.5rem; }
div[data-testid="stColumn"] { min-width: 0 !important; }
div[data-testid="stColumn"] button { padding: 0.25rem 0.5rem; white-space: nowrap; }
/* 항목 행/입력 행: 첫 컬럼이 남는 폭을 쓰고, 버튼 컬럼은 내용 크기로 오른쪽 정렬 */
[class*="st-key-row_"] div[data-testid="stColumn"]:first-child,
.st-key-addrow div[data-testid="stColumn"]:first-child { flex: 1 1 0 !important; width: auto !important; }
[class*="st-key-row_"] div[data-testid="stColumn"]:not(:first-child),
.st-key-addrow div[data-testid="stColumn"]:not(:first-child) { flex: 0 0 auto !important; width: auto !important; }
/* 긴 이름은 잘리지 않고 줄바꿈 */
div[data-testid="stCheckbox"] p { white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; overflow-wrap: anywhere; }
</style>
"""

ZWSP = "​"


def md_escape(text: str) -> str:
    """사용자 입력이 마크다운/HTML 엔티티/자동 링크로 해석되지 않도록 처리 (표시용)"""
    text = re.sub(r"(?<=//)|(?<=[wW]{3})(?=\.)|(?=@)", ZWSP, text)  # URL·이메일 자동 링크 방지
    return re.sub(r"[\\`*_\[\]~$:<>#|&]", lambda m: "\\" + m.group(0), text)


def render_header():
    st.markdown(CSS, unsafe_allow_html=True)  # 고정 CSS만 사용 (사용자 입력 없음)
    st.title("🛒 쇼핑 리스트")
    st.caption("살 물건을 담고, 샀으면 체크하세요. 🔗 이 페이지 주소가 내 목록이에요. 북마크해 두세요!")


def render_add_form():
    with st.container(key="addrow"):
        with st.form("add_form", clear_on_submit=True, border=False):
            col_input, col_btn = st.columns([5, 1])
            name = col_input.text_input(
                "아이템", placeholder="사야 할 물건을 입력하세요",
                max_chars=MAX_LEN, label_visibility="collapsed",
            )
            submitted = col_btn.form_submit_button("추가", type="primary")
    if submitted and not add_item(name):
        st.warning("아이템 이름을 입력해주세요.")


def render_summary(items: list):
    """진행 현황(진행 바) + 완료 항목 일괄 삭제"""
    done = sum(1 for i in items if i["checked"])
    st.progress(done / len(items), text=f"완료 {done} / 전체 {len(items)}")
    st.button("완료 항목 삭제", on_click=clear_checked, disabled=done == 0, icon="🧹")


def render_item(item: dict):
    item_id = item["id"]
    with st.container(border=True, key=f"row_{item_id}"):
        if st.session_state.editing_id == item_id:
            # 폼이라 Enter로도 저장됨
            with st.form(f"editform_{item_id}", border=False):
                col_input, col_save, col_cancel = st.columns([5, 1, 1])
                col_input.text_input(
                    "이름 수정", key=f"edit_{item_id}", max_chars=MAX_LEN, label_visibility="collapsed"
                )
                col_save.form_submit_button("저장", on_click=save_edit, args=(item_id,), type="primary")
                col_cancel.form_submit_button("취소", on_click=cancel_edit)
            if st.session_state.edit_error:
                st.warning("이름을 입력해주세요.")
            return

        col_chk, col_edit, col_del = st.columns([6, 1, 1])
        name = md_escape(item["name"])
        label = f":gray[~~{name}~~]" if item["checked"] else name
        st.session_state[f"chk_{item_id}"] = item["checked"]  # 다른 탭의 변경을 반영
        col_chk.checkbox(label, key=f"chk_{item_id}", on_change=toggle_item, args=(item_id,))
        col_edit.button("✏️", key=f"edit_btn_{item_id}", on_click=start_edit, args=(item_id,), help="수정")
        col_del.button("🗑️", key=f"del_{item_id}", on_click=delete_item, args=(item_id,), help="삭제")


def render_list():
    if st.session_state.get("save_failed"):
        st.warning("목록을 파일에 저장하지 못했습니다. 새로고침하면 사라질 수 있어요.")
    items = load_items()
    editing = st.session_state.editing_id
    if editing and not any(i["id"] == editing for i in items):
        st.session_state.editing_id = None  # 다른 탭에서 삭제된 항목
    if not items:
        st.info("아직 담은 물건이 없어요. 위에서 첫 물건을 추가해보세요! 🛍️")
        return
    render_summary(items)
    # 미완료 항목을 위에, 완료 항목을 아래에 (저장 순서는 유지, sorted는 안정 정렬)
    for item in sorted(items, key=lambda i: i["checked"]):
        render_item(item)


def main():
    init_page()
    init_state()
    render_header()
    render_add_form()
    render_list()


main()
