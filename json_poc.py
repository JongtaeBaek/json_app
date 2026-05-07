"""
JSON 파싱 & 파일 저장 POC
표준 라이브러리: json, pathlib
스키마 검증   : pydantic v2
"""

import json
import sys
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator, model_validator

# Windows 터미널 UTF-8 출력
sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────
# 1. 문자열 → Python 객체 파싱
# ──────────────────────────────────────────
def demo_parse_string():
    raw = '{"name": "홍길동", "age": 30, "skills": ["Python", "JSON"]}'
    obj = json.loads(raw)

    print("[1] 문자열 파싱")
    print(f"  name  : {obj['name']}")
    print(f"  age   : {obj['age']}")
    print(f"  skills: {obj['skills']}")
    print()


# ──────────────────────────────────────────
# 2. Python 객체 → JSON 문자열 직렬화
# ──────────────────────────────────────────
def demo_serialize():
    data = {
        "id": 1,
        "title": "JSON POC",
        "tags": ["python", "json"],
        "meta": {"created": "2026-05-07", "version": 1},
    }
    # indent: 들여쓰기, ensure_ascii=False: 한글 유지
    serialized = json.dumps(data, indent=2, ensure_ascii=False)

    print("[2] 직렬화 (dumps)")
    print(serialized)
    print()
    return data


# ──────────────────────────────────────────
# 3. JSON 파일로 저장
# ──────────────────────────────────────────
def demo_save_file(data: dict):
    path = DATA_DIR / "output.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[3] 파일 저장 → {path}")
    print()
    return path


# ──────────────────────────────────────────
# 4. JSON 파일 읽기
# ──────────────────────────────────────────
def demo_load_file(path: Path):
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)

    print("[4] 파일 읽기")
    print(f"  title : {loaded['title']}")
    print(f"  tags  : {loaded['tags']}")
    print(f"  meta  : {loaded['meta']}")
    print()
    return loaded


# ──────────────────────────────────────────
# 5. 리스트(배열) JSON 처리
# ──────────────────────────────────────────
def demo_list_json():
    users = [
        {"id": 1, "name": "Alice", "active": True},
        {"id": 2, "name": "Bob",   "active": False},
        {"id": 3, "name": "Carol", "active": True},
    ]

    path = DATA_DIR / "users.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

    with open(path, encoding="utf-8") as f:
        loaded_users = json.load(f)

    active = [u["name"] for u in loaded_users if u["active"]]
    print("[5] 리스트 JSON - 활성 사용자 필터링")
    print(f"  active users: {active}")
    print()


# ──────────────────────────────────────────
# 6. 에러 처리
# ──────────────────────────────────────────
def demo_error_handling():
    bad_json = '{"name": "broken", "age": }'  # 잘못된 JSON

    print("[6] 에러 처리")
    try:
        json.loads(bad_json)
    except json.JSONDecodeError as e:
        print(f"  JSONDecodeError: {e.msg} (line {e.lineno}, col {e.colno})")
    print()


# ──────────────────────────────────────────
# 7. 중첩 구조 접근
# ──────────────────────────────────────────
def demo_nested():
    raw = """
    {
        "company": "ACME",
        "departments": [
            {"name": "Engineering", "headcount": 20},
            {"name": "Design",      "headcount": 5}
        ],
        "address": {
            "city": "Seoul",
            "zip": "04524"
        }
    }
    """
    obj = json.loads(raw)

    print("[7] 중첩 구조 접근")
    print(f"  company    : {obj['company']}")
    print(f"  city       : {obj['address']['city']}")
    print(f"  departments: {[d['name'] for d in obj['departments']]}")
    print(f"  total staff: {sum(d['headcount'] for d in obj['departments'])}")
    print()


# ══════════════════════════════════════════
# Pydantic v2 JSON 스키마 검증 데모
# ══════════════════════════════════════════

# ──────────────────────────────────────────
# 8. 기본 모델 정의 & 검증
# ──────────────────────────────────────────
class Address(BaseModel):
    city: str
    zip: str = Field(pattern=r"^\d{5}$")  # 5자리 숫자만 허용


class User(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=150)
    email: str
    active: bool = True
    address: Address


def demo_pydantic_basic():
    print("[8] 기본 모델 검증")

    valid_json = """{
        "id": 1,
        "name": "홍길동",
        "age": 30,
        "email": "hong@example.com",
        "address": {"city": "Seoul", "zip": "04524"}
    }"""
    user = User.model_validate_json(valid_json)
    print(f"  OK  name={user.name}, age={user.age}, city={user.address.city}")

    invalid_json = """{
        "id": 2,
        "name": "",
        "age": 200,
        "email": "not-an-email",
        "address": {"city": "Busan", "zip": "ABCDE"}
    }"""
    try:
        User.model_validate_json(invalid_json)
    except ValidationError as e:
        print(f"  ERR {e.error_count()}개 오류 발생:")
        for err in e.errors():
            loc = " > ".join(str(l) for l in err["loc"])
            print(f"       [{loc}] {err['msg']}")
    print()


# ──────────────────────────────────────────
# 9. Field 제약 조건
# ──────────────────────────────────────────
class Product(BaseModel):
    sku: str = Field(pattern=r"^[A-Z]{2}-\d{4}$")   # 예: AB-1234
    name: str
    price: float = Field(gt=0)
    stock: int = Field(ge=0, default=0)
    category: Literal["electronics", "clothing", "food"]
    tags: list[str] = Field(default_factory=list, max_length=10)


def demo_pydantic_fields():
    print("[9] Field 제약 조건")

    cases = [
        ("정상", '{"sku":"AB-1234","name":"노트북","price":999.99,"category":"electronics"}'),
        ("음수 가격", '{"sku":"AB-1234","name":"노트북","price":-1,"category":"electronics"}'),
        ("잘못된 SKU", '{"sku":"abc","name":"노트북","price":10,"category":"electronics"}'),
        ("없는 카테고리", '{"sku":"AB-1234","name":"노트북","price":10,"category":"furniture"}'),
    ]

    for label, raw in cases:
        try:
            p = Product.model_validate_json(raw)
            print(f"  OK  [{label}] sku={p.sku}, price={p.price}")
        except ValidationError as e:
            first = e.errors()[0]
            loc = " > ".join(str(l) for l in first["loc"])
            print(f"  ERR [{label}] [{loc}] {first['msg']}")
    print()


# ──────────────────────────────────────────
# 10. 커스텀 validator
# ──────────────────────────────────────────
class DateRange(BaseModel):
    start: date
    end: date
    label: str

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start")
        if start and v <= start:
            raise ValueError("end는 start보다 이후여야 합니다")
        return v

    @model_validator(mode="after")
    def max_90_days(self):
        delta = (self.end - self.start).days
        if delta > 90:
            raise ValueError(f"기간은 90일 이하여야 합니다 (현재 {delta}일)")
        return self


def demo_pydantic_validators():
    print("[10] 커스텀 validator")

    cases = [
        ("정상(30일)", '{"start":"2026-01-01","end":"2026-01-31","label":"Q1 sprint"}'),
        ("end < start", '{"start":"2026-05-01","end":"2026-04-01","label":"잘못된 범위"}'),
        ("91일 초과", '{"start":"2026-01-01","end":"2026-04-02","label":"너무 긴 범위"}'),
    ]

    for label, raw in cases:
        try:
            r = DateRange.model_validate_json(raw)
            days = (r.end - r.start).days
            print(f"  OK  [{label}] {r.start} ~ {r.end} ({days}일)")
        except ValidationError as e:
            first = e.errors()[0]
            print(f"  ERR [{label}] {first['msg']}")
    print()


# ──────────────────────────────────────────
# 11. JSON 파일 저장 / 로드 (pydantic 통합)
# ──────────────────────────────────────────
def demo_pydantic_file_io():
    print("[11] Pydantic 모델 파일 저장 / 로드")

    users = [
        User(id=1, name="Alice", age=25, email="alice@example.com",
             address=Address(city="Seoul", zip="04524")),
        User(id=2, name="Bob",   age=32, email="bob@example.com",
             address=Address(city="Busan", zip="47999")),
    ]

    path = DATA_DIR / "pydantic_users.json"
    # model_dump(): pydantic 객체 → dict, date 등 직렬화 포함
    payload = [u.model_dump() for u in users]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"  저장 → {path}")

    # 파일에서 읽어 다시 모델로 복원
    with open(path, encoding="utf-8") as f:
        raw_list = json.load(f)

    restored = [User.model_validate(item) for item in raw_list]
    for u in restored:
        print(f"  로드  id={u.id}, name={u.name}, city={u.address.city}")
    print()


# ──────────────────────────────────────────
# 12. JSON Schema 내보내기
# ──────────────────────────────────────────
def demo_json_schema_export():
    print("[12] JSON Schema 내보내기 (User 모델)")
    schema = User.model_json_schema()
    print(json.dumps(schema, indent=2, ensure_ascii=False))

    schema_path = DATA_DIR / "user_schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"\n  스키마 저장 → {schema_path}")
    print()


if __name__ == "__main__":
    demo_parse_string()
    data = demo_serialize()
    path = demo_save_file(data)
    demo_load_file(path)
    demo_list_json()
    demo_error_handling()
    demo_nested()

    print("=" * 50)
    print("Pydantic v2 스키마 검증")
    print("=" * 50)
    print()

    demo_pydantic_basic()
    demo_pydantic_fields()
    demo_pydantic_validators()
    demo_pydantic_file_io()
    demo_json_schema_export()

    print("생성된 파일:")
    for f in sorted(DATA_DIR.iterdir()):
        print(f"  {f}")
