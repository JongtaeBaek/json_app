"""
JSON 기반 CRUD 콘솔 애플리케이션
저장소 : data/contacts.json
스키마 검증: pydantic v2
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "contacts.json"

Group = Literal["가족", "친구", "직장", "기타"]


# ──────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────
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
            raise ValueError("전화번호는 숫자 9자리 이상이어야 합니다 (하이픈 허용)")
        return v


# ──────────────────────────────────────────
# 저장소 (JSON 파일 읽기/쓰기)
# ──────────────────────────────────────────
def _load() -> list[dict]:
    if not DB_PATH.exists():
        return []
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(records: list[dict]) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def _next_id(records: list[dict]) -> int:
    return max((r["id"] for r in records), default=0) + 1


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ──────────────────────────────────────────
# CRUD 함수
# ──────────────────────────────────────────
def create_contact(name: str, phone: str, email: str, group: Group, memo: str) -> Contact:
    records = _load()
    ts = _now()
    contact = Contact(
        id=_next_id(records),
        name=name,
        phone=phone,
        email=email,
        group=group,
        memo=memo,
        created_at=ts,
        updated_at=ts,
    )
    records.append(contact.model_dump())
    _save(records)
    return contact


def read_all() -> list[Contact]:
    return [Contact.model_validate(r) for r in _load()]


def read_by_id(contact_id: int) -> Optional[Contact]:
    for r in _load():
        if r["id"] == contact_id:
            return Contact.model_validate(r)
    return None


def search_by_name(keyword: str) -> list[Contact]:
    return [Contact.model_validate(r) for r in _load() if keyword in r["name"]]


def update_contact(contact_id: int, **kwargs) -> Optional[Contact]:
    records = _load()
    for i, r in enumerate(records):
        if r["id"] == contact_id:
            r.update(kwargs)
            r["updated_at"] = _now()
            try:
                updated = Contact.model_validate(r)
            except ValidationError:
                raise
            records[i] = updated.model_dump()
            _save(records)
            return updated
    return None


def delete_contact(contact_id: int) -> bool:
    records = _load()
    filtered = [r for r in records if r["id"] != contact_id]
    if len(filtered) == len(records):
        return False
    _save(filtered)
    return True


# ──────────────────────────────────────────
# UI 헬퍼
# ──────────────────────────────────────────
def _sep(char: str = "-", width: int = 55) -> None:
    print(char * width)


def _print_contact(c: Contact) -> None:
    print(f"  [{c.id:>3}] {c.name:<12} {c.group:<6} {c.phone:<15} {c.email}")
    if c.memo:
        print(f"       메모: {c.memo}")


def _input_group() -> Group:
    groups: list[Group] = ["가족", "친구", "직장", "기타"]
    print("  그룹:", " / ".join(f"{i+1}.{g}" for i, g in enumerate(groups)))
    while True:
        raw = input("  선택(1-4, 기본 4): ").strip() or "4"
        if raw.isdigit() and 1 <= int(raw) <= 4:
            return groups[int(raw) - 1]
        print("  1~4 사이 숫자를 입력하세요.")


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {prompt}{suffix}: ").strip()
    return val if val else default


# ──────────────────────────────────────────
# 메뉴 핸들러
# ──────────────────────────────────────────
def handle_create() -> None:
    _sep()
    print("[C] 연락처 추가")
    _sep()
    name = _ask("이름 (필수)")
    if not name:
        print("  이름은 필수입니다.")
        return
    phone = _ask("전화번호 (필수, 예: 010-1234-5678)")
    if not phone:
        print("  전화번호는 필수입니다.")
        return
    email = _ask("이메일 (선택)")
    group = _input_group()
    memo = _ask("메모 (선택)")

    try:
        contact = create_contact(name, phone, email, group, memo)
        print(f"\n  저장 완료 → ID={contact.id}, 이름={contact.name}")
    except ValidationError as e:
        print("  검증 오류:")
        for err in e.errors():
            loc = " > ".join(str(l) for l in err["loc"])
            print(f"    [{loc}] {err['msg']}")


def handle_read() -> None:
    _sep()
    print("[R] 연락처 조회")
    _sep()
    print("  1. 전체 목록  2. ID 검색  3. 이름 검색")
    choice = input("  선택: ").strip()

    if choice == "1":
        contacts = read_all()
        if not contacts:
            print("  저장된 연락처가 없습니다.")
            return
        _sep("·")
        print(f"  {'ID':>4}  {'이름':<12} {'그룹':<6} {'전화번호':<15} 이메일")
        _sep("·")
        for c in contacts:
            _print_contact(c)
        print(f"\n  총 {len(contacts)}건")

    elif choice == "2":
        raw = input("  ID 입력: ").strip()
        if not raw.isdigit():
            print("  숫자를 입력하세요.")
            return
        c = read_by_id(int(raw))
        if c:
            _sep("·")
            _print_contact(c)
            print(f"  생성: {c.created_at}  수정: {c.updated_at}")
        else:
            print(f"  ID={raw} 연락처를 찾을 수 없습니다.")

    elif choice == "3":
        keyword = input("  검색어: ").strip()
        results = search_by_name(keyword)
        if not results:
            print("  검색 결과가 없습니다.")
        else:
            for c in results:
                _print_contact(c)
            print(f"\n  {len(results)}건 검색됨")
    else:
        print("  잘못된 선택입니다.")


def handle_update() -> None:
    _sep()
    print("[U] 연락처 수정")
    _sep()
    raw = input("  수정할 ID: ").strip()
    if not raw.isdigit():
        print("  숫자를 입력하세요.")
        return

    contact_id = int(raw)
    c = read_by_id(contact_id)
    if not c:
        print(f"  ID={contact_id} 연락처를 찾을 수 없습니다.")
        return

    print(f"  현재 정보: {c.name} / {c.phone} / {c.email} / {c.group}")
    print("  변경할 값을 입력하세요 (엔터 = 유지).")

    updates: dict = {}
    name = _ask("이름", c.name)
    if name != c.name:
        updates["name"] = name
    phone = _ask("전화번호", c.phone)
    if phone != c.phone:
        updates["phone"] = phone
    email = _ask("이메일", c.email)
    if email != c.email:
        updates["email"] = email
    print("  그룹 변경? (엔터 = 유지)")
    change_group = input("  변경하려면 y 입력: ").strip().lower()
    if change_group == "y":
        updates["group"] = _input_group()
    memo = _ask("메모", c.memo)
    if memo != c.memo:
        updates["memo"] = memo

    if not updates:
        print("  변경 사항 없음.")
        return

    try:
        updated = update_contact(contact_id, **updates)
        if updated:
            print(f"  수정 완료 → {updated.name} ({updated.updated_at})")
    except ValidationError as e:
        print("  검증 오류:")
        for err in e.errors():
            loc = " > ".join(str(l) for l in err["loc"])
            print(f"    [{loc}] {err['msg']}")


def handle_delete() -> None:
    _sep()
    print("[D] 연락처 삭제")
    _sep()
    raw = input("  삭제할 ID: ").strip()
    if not raw.isdigit():
        print("  숫자를 입력하세요.")
        return

    contact_id = int(raw)
    c = read_by_id(contact_id)
    if not c:
        print(f"  ID={contact_id} 연락처를 찾을 수 없습니다.")
        return

    confirm = input(f"  [{c.name}]을(를) 삭제하시겠습니까? (y/N): ").strip().lower()
    if confirm != "y":
        print("  취소되었습니다.")
        return

    if delete_contact(contact_id):
        print(f"  ID={contact_id} [{c.name}] 삭제 완료.")
    else:
        print("  삭제 실패.")


# ──────────────────────────────────────────
# 메인 루프
# ──────────────────────────────────────────
def main() -> None:
    print("=" * 55)
    print("  연락처 관리 애플리케이션 (JSON + Pydantic v2)")
    print("=" * 55)

    menu = {
        "1": ("C - 추가", handle_create),
        "2": ("R - 조회", handle_read),
        "3": ("U - 수정", handle_update),
        "4": ("D - 삭제", handle_delete),
        "0": ("종료", None),
    }

    while True:
        _sep()
        print("  메뉴: ", " | ".join(f"{k}.{v[0]}" for k, v in menu.items()))
        _sep()
        choice = input("  선택: ").strip()

        if choice == "0":
            print("  프로그램을 종료합니다.")
            break
        if choice in menu and menu[choice][1]:
            menu[choice][1]()
        else:
            print("  올바른 메뉴 번호를 입력하세요.")


if __name__ == "__main__":
    main()
