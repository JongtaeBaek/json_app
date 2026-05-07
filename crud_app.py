"""
JSON 기반 연락처 CRUD 콘솔 애플리케이션
PoC 코드 구조 유지 (json_poc.py 패턴 기반)
저장소  : data/contacts.json
스키마  : pydantic v2
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH  = DATA_DIR / "contacts.json"

GROUPS: list[str] = ["가족", "친구", "직장", "기타"]
Group = Literal["가족", "친구", "직장", "기타"]


# ══════════════════════════════════════════
# 스키마 정의 (Pydantic v2)
# ══════════════════════════════════════════

class Contact(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=50)
    phone: str
    email: str = Field(default="")
    group: Group = "기타"
    memo: str = Field(default="", max_length=200)
    created_at: str = ""
    updated_at: str = ""

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = v.replace("-", "").replace(" ", "")
        if not digits.isdigit() or len(digits) < 9:
            raise ValueError("숫자 9자리 이상이어야 합니다 (하이픈 허용)")
        return v


# ══════════════════════════════════════════
# 저장소 I/O
# (json_poc.py: demo_save_file / demo_load_file / demo_error_handling 패턴)
# ══════════════════════════════════════════

def _load_records() -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"  [경고] 데이터 파일 손상: {e.msg} (line {e.lineno}, col {e.colno})")
        return []


def _save_records(records: list[dict]) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def _next_id(records: list[dict]) -> int:
    return max((r["id"] for r in records), default=0) + 1


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════
# CRUD 핵심 함수
# ══════════════════════════════════════════

# ──────────────────────────────────────────
# 1. CREATE  — 검증 후 JSON 파일에 추가 저장
# ──────────────────────────────────────────
def create_contact(name: str, phone: str, email: str,
                   group: str, memo: str) -> Contact:
    records = _load_records()
    ts = _now()
    # model_validate(): dict → Pydantic 모델 (json_poc.py: demo_pydantic_file_io 패턴)
    contact = Contact.model_validate({
        "id": _next_id(records),
        "name": name, "phone": phone,
        "email": email, "group": group, "memo": memo,
        "created_at": ts, "updated_at": ts,
    })
    records.append(contact.model_dump())
    _save_records(records)
    return contact


# ──────────────────────────────────────────
# 2. READ  — 전체 목록 / ID 단건 / 키워드 검색
# ──────────────────────────────────────────
def read_all() -> list[Contact]:
    return [Contact.model_validate(r) for r in _load_records()]


def read_by_id(contact_id: int) -> Optional[Contact]:
    for r in _load_records():
        if r["id"] == contact_id:
            return Contact.model_validate(r)
    return None


def search_contacts(keyword: str) -> list[Contact]:
    """이름·이메일·메모 대상 부분 일치 검색"""
    keyword_lower = keyword.lower()
    results = []
    for r in _load_records():
        searchable = (
            r.get("name", "") + r.get("email", "") + r.get("memo", "")
        ).lower()
        if keyword_lower in searchable:
            results.append(Contact.model_validate(r))
    return results


# ──────────────────────────────────────────
# 3. UPDATE  — ID 지정 후 변경 필드만 수정, Pydantic 재검증
# ──────────────────────────────────────────
def update_contact(contact_id: int, **fields) -> Optional[Contact]:
    records = _load_records()
    for i, r in enumerate(records):
        if r["id"] == contact_id:
            r.update(fields)
            r["updated_at"] = _now()
            updated = Contact.model_validate(r)   # 검증 실패 시 ValidationError 상위 전파
            records[i] = updated.model_dump()
            _save_records(records)
            return updated
    return None


# ──────────────────────────────────────────
# 4. DELETE  — ID 지정 삭제, 성공 여부 반환
# ──────────────────────────────────────────
def delete_contact(contact_id: int) -> bool:
    records = _load_records()
    filtered = [r for r in records if r["id"] != contact_id]
    if len(filtered) == len(records):
        return False
    _save_records(filtered)
    return True


# ══════════════════════════════════════════
# 콘솔 UI 헬퍼
# ══════════════════════════════════════════

def _sep(ch: str = "─", w: int = 55) -> None:
    print(ch * w)


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {prompt}{suffix}: ").strip()
    return val if val else default


def _pick_group() -> str:
    opts = "  ".join(f"{i + 1}.{g}" for i, g in enumerate(GROUPS))
    print(f"  그룹: {opts}")
    while True:
        sel = (input("  선택(1-4, 기본 4): ").strip() or "4")
        if sel.isdigit() and 1 <= int(sel) <= 4:
            return GROUPS[int(sel) - 1]
        print("  1~4 사이 숫자를 입력하세요.")


def _print_row(c: Contact) -> None:
    print(f"  [{c.id:>3}] {c.name:<12} {c.group:<6} {c.phone:<16} {c.email}")
    if c.memo:
        print(f"       메모: {c.memo}")


def _print_errors(e: ValidationError) -> None:
    print("  [검증 오류]")
    for err in e.errors():
        loc = " > ".join(str(l) for l in err["loc"])
        print(f"    [{loc}] {err['msg']}")


# ══════════════════════════════════════════
# UI: CRUD 메뉴 핸들러
# ══════════════════════════════════════════

# ──────────────────────────────────────────
# UI-1. CREATE
# ──────────────────────────────────────────
def ui_create() -> None:
    _sep("═")
    print("[CREATE] 연락처 추가")
    _sep("═")

    name = _ask("이름 (필수)")
    if not name:
        print("  이름은 필수입니다."); return

    phone = _ask("전화번호 (예: 010-1234-5678)")
    if not phone:
        print("  전화번호는 필수입니다."); return

    email = _ask("이메일 (선택)")
    group = _pick_group()
    memo  = _ask("메모 (선택)")

    try:
        c = create_contact(name, phone, email, group, memo)
        print(f"\n  저장 완료 → ID={c.id}  이름={c.name}  그룹={c.group}")
    except ValidationError as e:
        _print_errors(e)


# ──────────────────────────────────────────
# UI-2. READ
# ──────────────────────────────────────────
def ui_read() -> None:
    _sep("═")
    print("[READ] 연락처 조회")
    _sep("═")
    print("  1.전체 목록  2.ID 검색  3.키워드 검색")
    choice = input("  선택: ").strip()

    if choice == "1":
        contacts = read_all()
        if not contacts:
            print("  저장된 연락처가 없습니다."); return
        _sep()
        print(f"  {'ID':>4}  {'이름':<12} {'그룹':<6} {'전화번호':<16} 이메일")
        _sep()
        for c in contacts:
            _print_row(c)
        print(f"\n  총 {len(contacts)}건")

    elif choice == "2":
        raw = input("  ID: ").strip()
        if not raw.isdigit():
            print("  숫자를 입력하세요."); return
        c = read_by_id(int(raw))
        if c:
            _sep()
            _print_row(c)
            print(f"  생성: {c.created_at}  수정: {c.updated_at}")
        else:
            print(f"  ID={raw} 연락처를 찾을 수 없습니다.")

    elif choice == "3":
        kw = input("  검색어 (이름 / 이메일 / 메모): ").strip()
        if not kw:
            print("  검색어를 입력하세요."); return
        results = search_contacts(kw)
        if not results:
            print("  검색 결과가 없습니다.")
        else:
            _sep()
            for c in results:
                _print_row(c)
            print(f"\n  {len(results)}건 검색됨")
    else:
        print("  올바른 번호를 선택하세요.")


# ──────────────────────────────────────────
# UI-3. UPDATE
# ──────────────────────────────────────────
def ui_update() -> None:
    _sep("═")
    print("[UPDATE] 연락처 수정")
    _sep("═")

    raw = input("  수정할 ID: ").strip()
    if not raw.isdigit():
        print("  숫자를 입력하세요."); return

    c = read_by_id(int(raw))
    if not c:
        print(f"  ID={raw} 연락처를 찾을 수 없습니다."); return

    print(f"  현재: {c.name} | {c.phone} | {c.email} | {c.group}")
    print("  변경할 값을 입력하세요 (엔터 = 유지).")

    updates: dict = {}
    for field, label, current in [
        ("name",  "이름",     c.name),
        ("phone", "전화번호", c.phone),
        ("email", "이메일",   c.email),
        ("memo",  "메모",     c.memo),
    ]:
        val = _ask(label, current)
        if val != current:
            updates[field] = val

    if input("  그룹 변경? (y/N): ").strip().lower() == "y":
        updates["group"] = _pick_group()

    if not updates:
        print("  변경 사항 없음."); return

    try:
        updated = update_contact(int(raw), **updates)
        if updated:
            print(f"  수정 완료 → {updated.name}  (수정: {updated.updated_at})")
    except ValidationError as e:
        _print_errors(e)


# ──────────────────────────────────────────
# UI-4. DELETE
# ──────────────────────────────────────────
def ui_delete() -> None:
    _sep("═")
    print("[DELETE] 연락처 삭제")
    _sep("═")

    raw = input("  삭제할 ID: ").strip()
    if not raw.isdigit():
        print("  숫자를 입력하세요."); return

    c = read_by_id(int(raw))
    if not c:
        print(f"  ID={raw} 연락처를 찾을 수 없습니다."); return

    print(f"  대상: [{c.id}] {c.name} / {c.phone} / {c.group}")
    if input("  정말 삭제하시겠습니까? (y/N): ").strip().lower() != "y":
        print("  취소되었습니다."); return

    if delete_contact(int(raw)):
        print(f"  ID={raw} [{c.name}] 삭제 완료.")
    else:
        print("  삭제 실패.")


# ══════════════════════════════════════════
# 메인 루프
# ══════════════════════════════════════════

MENU: dict[str, tuple[str, Optional[object]]] = {
    "1": ("[C] 추가",  ui_create),
    "2": ("[R] 조회",  ui_read),
    "3": ("[U] 수정",  ui_update),
    "4": ("[D] 삭제",  ui_delete),
    "0": ("종료",      None),
}


def main() -> None:
    print("=" * 55)
    print("  연락처 CRUD 애플리케이션 (JSON + Pydantic v2)")
    print("=" * 55)

    while True:
        _sep()
        print("  " + "  |  ".join(f"{k}.{v[0]}" for k, v in MENU.items()))
        _sep()
        sel = input("  선택: ").strip()

        if sel == "0":
            print("  종료합니다."); break
        if sel in MENU and MENU[sel][1]:
            MENU[sel][1]()
        else:
            print("  올바른 메뉴 번호를 선택하세요.")


if __name__ == "__main__":  # pragma: no cover
    main()
