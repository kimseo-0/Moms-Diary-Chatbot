# Refactor Plan — Moms-Diary-Chatbot

목표: 중복 최소화, 복잡성 제거, import-time 사이드이펙트 제거, LLM 접근 중앙화.
우선순위: P0 (긴급) → P1 (높음) → P2 (중간)

요약 작업 목록

P0 (긴급)
- dependencies: 모든 모듈-레벨 초기화(heavy imports, 네트워크/IO, API key checks)를 제거하여 호출 시에만 초기화되도록 변경한다. (완료)
- pydantic 직렬화 통일: `app/core/pydantic_utils.py::safe_model_dump`로 모든 응답/저장 포인트를 통일한다. (완료)

P1 (우선순위)
- LLM 접근 중앙화: `app/core/tooling.py`의 `get_llm`/`get_llm_with_tools` 사용으로 통일. 노드별로 툴 바인딩 필요 여부에 따라 적절한 함수 사용. (진행/완료)
- OpenAIAdapter 안전성: 생성자에서 예외를 발생시키지 않고, 호출 시 `_ensure_api_key()`로 체크하도록 유지. (점검 완료)
- 그래프 컴파일 지연: `compile_app_graph()`를 import-time에서 startup 또는 최초 호출 시점으로 변경. (완료)

P2 (중간)
- DB 마이그레이션 유틸 구현: `app/utils/migrations.py`를 만들고 startup 훅에서 마이그레이션을 수행하도록 이전. (계획)
- 프롬프트/툴 정리: 프롬프트 상수와 툴 정의를 별도 디렉토리로 분리하고 테스트 추가. (계획)
- CI 구성: GitHub Actions로 lint + pytest(삭제 테스트 제외 또는 격리) 구성. (계획)

파일별 변경 요약 (이미 변경된 항목)
- `app/core/dependencies.py` — langchain heavy import을 함수 내부로 지연 이동, lru_cache getter 유지.
- `app/api/http.py` — `_graph`를 지연 생성 `get_app_graph()`로 변경.
- `app/core/pydantic_utils.py` — 추가 (safe_model_dump)
- `app/core/tooling.py` — 중앙 LLM 접근기.
- `app/nodes/*`, `app/graphs/*` — `get_llm`/`get_llm_with_tools`로 통일 적용.

다음 단계
1. (권장) `app/utils/migrations.py` 초안 작성 및 간단한 실행기 추가.
2. (권장) 자동화된 검색으로 남은 import-time 초기화 포인트(예: 다른 서드파티 모듈) 재검사.
3. (옵션) `app/graphs/router.py` 제거(이미 deprecated로 교체 가능).
4. 테스트: 비파괴성 테스트 자동 실행(데이터 삭제 테스트는 제외).

안전 가이드
- `OPENAI_API_KEY`가 없으면 LLM 호출 시점에 예외가 뜹니다. 로컬 개발에서는 mocking 또는 환경변수 설정 필요.
- DB 변경은 마이그레이션 스크립트를 통해 운영환경에서 단계적으로 적용하세요.

간단한 체크리스트
- [x] dependencies lazy-getters 적용
- [x] safe_model_dump 적용
- [x] tooling: get_llm 통일
- [x] graph compile 지연
- [ ] migrations 유틸 추가
- [ ] CI + 테스트 격리

문제가 발생하면 변경 전 상태로 롤백 가능하도록 커밋/PR을 만들 것을 권장합니다.
