# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 문서

- `PRD.md`: 요구사항(F1~F8)과 배포 계획. 기능 범위의 기준 문서.
- `PROMPTS.md`: 4단계 개발 프롬프트 (1 뼈대 → 2 기능 → 3 UI → 4 Playwright 검토). 4단계 검토 후 지적 사항은 모두 반영된 상태다.

## 명령어

```
pip install -r requirements.txt
streamlit run app.py                          # 로컬 실행 (http://localhost:8501)
streamlit run app.py --server.headless true   # Playwright 검토용
```

테스트 프레임워크와 린터는 없다. 로직은 `streamlit.testing.v1.AppTest`(`at.query_params["u"]`로 토큰 지정)로, 화면은 Playwright MCP로 검증했다.

## 아키텍처

단일 파일 `app.py`, 의존성은 streamlit뿐이다.

- **링크별 개인 목록**: URL의 `?u=<토큰>`이 방문자 식별자이고, 없거나 `TOKEN_RE` 형식이 아니면 새로 발급해 URL에 넣는다. 목록은 `data/<토큰>.json`에 저장한다. 토큰을 파일 경로에 쓰므로 형식 검증을 빼지 말 것.
- **파일이 단일 진실 공급원**: 세션에 목록을 캐시하지 않는다. 매 실행마다 `load_items()`로 읽고, 모든 변경은 `update(change)`(락 안에서 읽기 → 변경 → 원자적 저장)를 거친다. 같은 링크를 여러 탭에서 열어도 서로의 변경을 덮어쓰지 않는다.
- 세션 상태는 `token`, `editing_id`(한 번에 하나만 수정), `edit_error`뿐이다. 체크박스 값은 렌더링 때 파일 값으로 `st.session_state["chk_<id>"]`를 덮어써 다른 탭 변경을 반영한다.
- `st.session_state.items`는 dict 메서드와 충돌하므로 쓰지 말 것.
- 위젯 key는 항목 id 기반(`chk_`, `edit_`, `del_`...)이다. 항목 행은 `st.container(key=f"row_{id}")`이고, 레이아웃 CSS(`CSS` 상수)가 이 key 클래스(`st-key-row_*`, `st-key-addrow`)를 선택자로 쓴다.
- 이름은 `MAX_LEN`(50)자로 자르고, 표시할 때 `md_escape`로 마크다운·`&` 엔티티·URL/이메일 자동 링크를 막는다. `unsafe_allow_html`은 고정 CSS에만 쓴다.
- 수정 UI는 `st.form`이라 Enter로 저장되고, 저장/취소는 `form_submit_button`의 `on_click` 콜백이다.

## 배포 시 주의

- Streamlit Community Cloud 재시작 시 `data/`가 초기화될 수 있다(파일 저장의 한계). 완전한 영구 보존이 필요하면 외부 DB(Supabase 등)로 `load_items`/`save_items`를 교체한다.
- `data/`는 `.gitignore`에 있다. 링크(토큰)를 아는 사람은 누구나 그 목록을 편집할 수 있다.
- UI 문구와 코드 주석은 한국어로 쓴다.
