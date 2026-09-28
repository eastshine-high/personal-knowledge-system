# Google ADK — Agent Context & Session 정리

> **한 줄 요약:** ADK에서 에이전트는 현재 메시지만이 아니라 **Context**(상태·이력·서비스 묶음)를 통해 동작한다. Context는 **Session**의 `state`(현재 스냅샷)와 `events`(이력 로그)에 접근하며, 상태 변경은 **직접 수정이 아니라 `state_delta`(이벤트에 담긴 변경분)** 로 이뤄진다.

## 1. Context란?

에이전트/툴이 실행 중 쓰는 **정보 묶음**. 상태 유지, 단계 간 데이터 전달, 서비스(아티팩트·메모리) 접근, 호출 신원(invocation) 추적을 가능하게 한다. 실행 위치에 따라 4가지 종류가 있고, **읽기/쓰기 권한이 다르다**:

| Context 종류 | 쓰이는 곳 | state | 추가 능력 |
|---|---|---|---|
| **InvocationContext** | 에이전트 코어(`_run_async_impl`) | 읽기/쓰기 | session·services(artifact/memory/session) 전체, invocation_id, user_content |
| **ReadonlyContext** | 변경 금지 지점(instruction provider 등) | **읽기 전용** | invocation_id, agent_name |
| **Context** (구 CallbackContext) | 라이프사이클/모델 콜백 | 읽기/쓰기 | `state` 수정(→ 자동으로 `state_delta` 추적), `save_artifact`/`load_artifact`, `user_content` |
| **ToolContext** | 툴 함수, 툴 콜백 | 읽기/쓰기 | Context 전부 + `search_memory(query)`, `list_artifacts()`, `actions`(EventActions), `request_credential`, `function_call_id` |

> Python/TypeScript에서는 CallbackContext와 ToolContext가 **하나의 `Context`로 통합**됨(CallbackContext는 별칭으로 유지).

## 2. Context가 주는 접근

- **Session state** — 딕셔너리형 접근. `context.state['key'] = value` 하면 그 변경이 **`EventActions.state_delta`에 자동 기록**됨.
- **Artifacts** — `save_artifact(filename, part)`(버전 반환) / `load_artifact(filename)` / (ToolContext) `list_artifacts()`.
- **Memory** — (ToolContext만) `search_memory(query)` — 과거 상호작용·외부 지식 검색.
- **Invocation 신원** — `invocation_id`, `agent_name`, (ToolContext) `function_call_id`.
- **EventActions** — (ToolContext) `actions`로 상태 변경·인증 요청 신호.

**주요 메서드**

```python
context.state.get(key, default)      # 읽기
context.state[key] = value           # 쓰기 (자동 델타 추적)
context.save_artifact(name, part)    # 아티팩트 저장
context.load_artifact(name)          # 아티팩트 로드
tool_context.search_memory(query)    # 메모리 검색 (ToolContext)
tool_context.list_artifacts()        # 아티팩트 목록 (ToolContext)
```

## 3. Session State — 스코프 prefix

`state`는 KV 딕셔너리지만 **키 prefix가 값의 수명·범위**를 결정한다(변수 스코프와 유사).

| prefix | 범위 | 지속성(DB 서비스 기준) |
|---|---|---|
| (없음) | 이 **세션** | 지속 (InMemory는 재시작 시 소멸) |
| `user:` | 이 **사용자**의 모든 세션 | 지속 |
| `app:` | **앱 전체**(모든 사용자) | 지속 |
| `temp:` | 이번 **턴(invocation)만** | **절대 미영속** — 턴 끝나면 폐기 |

```python
session.state['current_step'] = 'draft'          # 세션
session.state['user:preferred_language'] = 'ko'  # 사용자(세션 간)
session.state['app:api_endpoint'] = '...'         # 앱 공통
session.state['temp:raw_api_response'] = {...}    # 이 턴만
```

## 4. state_delta & Events (이벤트 소싱)

**규칙: state를 직접 고치지 말 것.** 모든 변경은 **이벤트에 담긴 `state_delta`**(바뀔 {키:값})로 표현하고, `session_service.append_event(session, event)`가 델타를 읽어 state에 적용한다(prefix에 따라 라우팅, `last_update_time` 갱신, 동시성 잠금).

- **events** = append-only **이력 로그**, **state** = **현재 스냅샷** (통장: 거래내역 = events, 잔액 = state)
- 이점: **감사**(어떤 이벤트가 이 값을 바꿨나) · **재현/undo**(이벤트 replay) · **영속**(DB는 append_event로만 저장) · **thread-safe**

**델타를 만드는 3가지 방법**

```python
# 1) LlmAgent output_key — 응답을 자동으로 state에 저장
LlmAgent(..., output_key="last_greeting")   # state_delta = {'last_greeting': <응답>}

# 2) 수동 EventActions.state_delta — 다중 키/스코프
actions = EventActions(state_delta={"task_status": "active", "user:login_count": 5, "temp:flag": True})
session_service.append_event(session, Event(author="system", actions=actions, ...))
# → temp:flag는 적용은 되나 영속 저장에서 제외

# 3) context.state 수정(콜백/툴 권장) — 프레임워크가 자동으로 델타에 반영
context.state["user_action_count"] = count + 1
```

> ⚠️ `session_service.get_session()`으로 받은 `session.state`를 **직접 수정 금지** — 이벤트 미생성 → 감사 상실, DB 미저장, race condition, `last_update_time` 미갱신.

## 5. 우리 PKS 노트 엔진에 적용 (활용/도입 계획)

우리는 ADK **프레임워크 전체**가 아니라 **Session의 state/events/scope/delta "개념"** 을 빌려온다(패턴만 경량 채택).

| 우리 `NoteSession` (현재) | ADK 개념 도입 시 |
|---|---|
| `context`(원문·그림) + `notes` 직접 필드 | **`state` KV** (`notes`, `source_text`, `figures`, `topic`) |
| `note.body = ...` **직접 수정** | **`state_delta` + append_event** (감사·재현) |
| `history`(얇은 기록, LLM 미사용) | **`events`**(델타 포함) → 재현·undo·**리파인 대화맥락 주입** |
| 취향 매번 재입력 | **`user:preferred_guideline`** 등으로 세션 간 기억 |
| (없음) | 나중에 DB 세션서비스 → **편집 이어하기(영속)** |

**도입 시 좋아지는 것:** 되돌리기/재현 · 변경 감사 · 세션 재개 · 개인 취향 기억 · 리파인 다중턴 맥락.

**미채택(현 단계 과함):** ToolContext·artifacts·memory·Runner/Agent 루프 — Qdrant/LangChain 질의 등 **에이전트 모듈 단계**에서 재검토.

## 참고 문서

- [ADK — Context](https://adk.dev/context/)
- [ADK — Session State (scopes & deltas)](https://adk.dev/sessions/state/)
- [ADK — Events](https://google.github.io/adk-docs/events/)
- [How ADK Agents Remember: Sessions, Events, Scoped-State (Medium)](https://medium.com/google-cloud/how-adk-agents-remember-sessions-events-and-persistent-state-742e06e9568c)
