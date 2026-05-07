# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Python으로 JSON 파싱, 파일 저장, Pydantic v2 스키마 검증을 학습하기 위한 POC 프로젝트.

## 실행 방법

```powershell
# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# POC 실행
python json_poc.py
```

## 의존성 설치

```powershell
python -m pip install pydantic
```

현재 설치된 버전: pydantic 2.13.4 (Python 3.13, Windows)

## 코드 구조

`json_poc.py` 단일 파일에 12개의 데모 함수가 순서대로 정의되어 있으며, `if __name__ == "__main__"` 블록에서 전부 실행된다.

| 함수 | 내용 |
|------|------|
| `demo_parse_string` | `json.loads()` 문자열 파싱 |
| `demo_serialize` | `json.dumps()` 직렬화 (indent, ensure_ascii=False) |
| `demo_save_file` | `json.dump()` 파일 저장 |
| `demo_load_file` | `json.load()` 파일 읽기 |
| `demo_list_json` | 배열 JSON 처리 및 필터링 |
| `demo_error_handling` | `json.JSONDecodeError` 처리 |
| `demo_nested` | 중첩 구조 접근 |
| `demo_pydantic_basic` | `BaseModel`, `model_validate_json()`, `ValidationError` |
| `demo_pydantic_fields` | `Field(gt=, ge=, pattern=)`, `Literal` |
| `demo_pydantic_validators` | `@field_validator`, `@model_validator` (크로스 필드 규칙) |
| `demo_pydantic_file_io` | `model_dump()` → 파일 저장 → `model_validate()` 왕복 |
| `demo_json_schema_export` | `model_json_schema()`로 JSON Schema 내보내기 |

실행 후 생성되는 파일:
- `data/output.json` — 단일 객체
- `data/users.json` — 배열
- `data/pydantic_users.json` — Pydantic 모델 직렬화 결과
- `data/user_schema.json` — User 모델의 JSON Schema

## 주요 패턴

```python
# JSON 문자열 → Pydantic 모델 (파싱 + 검증 동시)
obj = MyModel.model_validate_json(raw_str)

# dict → Pydantic 모델 (json.load() 결과 복원 시)
obj = MyModel.model_validate(loaded_dict)

# Pydantic 모델 → dict (json.dump() 전 직렬화)
payload = obj.model_dump()

# 파일 저장 시 필수 옵션
json.dump(data, f, indent=2, ensure_ascii=False)   # 한글 유지
open(path, encoding="utf-8")                        # Windows 인코딩 명시

# Windows 터미널 한글 출력
sys.stdout.reconfigure(encoding="utf-8")
```

## Windows 주의사항

- 파일 읽기/쓰기 시 항상 `encoding="utf-8"` 명시 (기본 cp949로 한글 깨짐)
- 스크립트 상단에 `sys.stdout.reconfigure(encoding="utf-8")` 추가 필요
- em dash(`—`) 등 cp949 미지원 문자는 터미널 출력에서 오류 발생

---

## CRUD 콘솔 애플리케이션 (crud_app.py)

### 개요

`json_poc.py`의 JSON / Pydantic v2 패턴을 기반으로 구현한 **연락처 관리 콘솔 앱**.
데이터는 `data/contacts.json`에 JSON으로 영속 저장된다.

### 실행 방법

```powershell
python crud_app.py
```

### 기능 구조

| 메뉴 | 동작 |
|------|------|
| 1 - Create | 이름·전화번호·이메일·그룹·메모 입력 → 신규 연락처 저장 |
| 2 - Read   | 전체 목록 / ID 검색 / 이름 검색 |
| 3 - Update | ID 지정 후 변경 필드만 수정 |
| 4 - Delete | ID 지정 후 확인 절차 거쳐 삭제 |
| 0 - 종료   | 프로그램 종료 |

### 모델 스키마 (Contact)

```python
class Contact(BaseModel):
    id: int                          # 자동 증가 (저장 시 부여)
    name: str                        # 1~50자
    phone: str                       # 숫자 9자리 이상, 하이픈 허용
    email: str                       # 선택 (빈 문자열 허용)
    group: Literal["가족","친구","직장","기타"]  # 기본 "기타"
    memo: str                        # 최대 200자, 선택
    created_at: str                  # YYYY-MM-DD HH:MM:SS
    updated_at: str
```

### 핵심 함수

| 함수 | 역할 |
|------|------|
| `create_contact(...)` | `model_validate()` 검증 후 append → `json.dump()` 저장 |
| `read_all()` | 전체 레코드 → `Contact` 리스트 반환 |
| `read_by_id(id)` | ID 단건 조회, 없으면 `None` |
| `search_contacts(keyword)` | 이름·이메일·메모 대상 키워드 부분 일치 검색 |
| `update_contact(id, **fields)` | 변경 필드만 dict update → `model_validate()` 재검증 후 저장 |
| `delete_contact(id)` | 필터링 후 저장, 성공 여부 `bool` 반환 |

### PoC 코드 구조 대응

| PoC 함수 | crud_app.py 적용 위치 |
|---|---|
| `demo_save_file` / `demo_load_file` | `_save_records()` / `_load_records()` |
| `demo_error_handling` (JSONDecodeError) | `_load_records()` 내 `try/except json.JSONDecodeError` |
| `demo_pydantic_basic` (ValidationError) | `ui_create` / `ui_update` 의 `except ValidationError` |
| `demo_pydantic_file_io` (model_validate/model_dump) | `create_contact()`, `update_contact()`, `read_all()` |

### 저장 파일

- `data/contacts.json` — 연락처 레코드 배열
