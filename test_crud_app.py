"""
crud_app.py 회귀·안전성 테스트

격리 전략: monkeypatch로 crud_app.DB_PATH를 tmp_path 내 임시 파일로
교체하여 실제 data/contacts.json 을 오염시키지 않음.
"""

import json
import sys
import time

import pytest
from pydantic import ValidationError

import crud_app
from crud_app import (
    Contact,
    _load_records,
    _next_id,
    _save_records,
    create_contact,
    delete_contact,
    read_all,
    read_by_id,
    search_contacts,
    update_contact,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """각 테스트마다 별도의 임시 DB 파일로 격리한다."""
    db = tmp_path / "contacts.json"
    monkeypatch.setattr(crud_app, "DB_PATH", db)
    return db


# ──────────────────────────────────────────────────────────
# Safety: Pydantic 스키마 검증
# ──────────────────────────────────────────────────────────

class TestContactSchema:
    """Contact 모델의 Pydantic v2 검증 규칙이 올바르게 동작하는지 확인한다."""

    _BASE = {
        "id": 1, "name": "홍길동", "phone": "010-1234-5678",
        "email": "", "group": "기타", "memo": "",
        "created_at": "", "updated_at": "",
    }

    def _make(self, **overrides) -> dict:
        return {**self._BASE, **overrides}

    # name ────────────────────────────────────────────────

    def test_name_empty_raises(self):
        with pytest.raises(ValidationError) as exc:
            Contact.model_validate(self._make(name=""))
        assert any(e["loc"] == ("name",) for e in exc.value.errors())

    def test_name_max_length_50_ok(self):
        c = Contact.model_validate(self._make(name="가" * 50))
        assert len(c.name) == 50

    def test_name_51_chars_raises(self):
        with pytest.raises(ValidationError):
            Contact.model_validate(self._make(name="가" * 51))

    # phone ───────────────────────────────────────────────

    def test_phone_with_hyphens_ok(self):
        c = Contact.model_validate(self._make(phone="010-1234-5678"))
        assert c.phone == "010-1234-5678"

    def test_phone_with_spaces_ok(self):
        c = Contact.model_validate(self._make(phone="010 1234 5678"))
        assert c.phone == "010 1234 5678"

    def test_phone_plain_11_digits_ok(self):
        c = Contact.model_validate(self._make(phone="01012345678"))
        assert c.phone == "01012345678"

    def test_phone_boundary_9_digits_ok(self):
        c = Contact.model_validate(self._make(phone="012345678"))
        assert c.phone == "012345678"

    def test_phone_boundary_8_digits_raises(self):
        with pytest.raises(ValidationError) as exc:
            Contact.model_validate(self._make(phone="01234567"))
        assert any(e["loc"] == ("phone",) for e in exc.value.errors())

    def test_phone_non_digit_raises(self):
        with pytest.raises(ValidationError):
            Contact.model_validate(self._make(phone="abc-defg-hijk"))

    def test_phone_too_short_raises(self):
        with pytest.raises(ValidationError):
            Contact.model_validate(self._make(phone="010-123"))

    # group ───────────────────────────────────────────────

    def test_group_valid_literals(self):
        for group in ("가족", "친구", "직장", "기타"):
            c = Contact.model_validate(self._make(group=group))
            assert c.group == group

    def test_group_invalid_raises(self):
        with pytest.raises(ValidationError):
            Contact.model_validate(self._make(group="모르는그룹"))

    def test_group_default_is_other(self):
        c = Contact(id=1, name="홍길동", phone="010-1234-5678")
        assert c.group == "기타"

    # memo ────────────────────────────────────────────────

    def test_memo_200_chars_ok(self):
        c = Contact.model_validate(self._make(memo="가" * 200))
        assert len(c.memo) == 200

    def test_memo_201_chars_raises(self):
        with pytest.raises(ValidationError):
            Contact.model_validate(self._make(memo="가" * 201))

    # defaults ────────────────────────────────────────────

    def test_email_default_empty(self):
        c = Contact(id=1, name="홍길동", phone="010-1234-5678")
        assert c.email == ""

    def test_memo_default_empty(self):
        c = Contact(id=1, name="홍길동", phone="010-1234-5678")
        assert c.memo == ""


# ──────────────────────────────────────────────────────────
# Safety: _next_id 순번 생성
# ──────────────────────────────────────────────────────────

class TestNextId:
    def test_empty_list_returns_1(self):
        assert _next_id([]) == 1

    def test_returns_max_plus_one(self):
        assert _next_id([{"id": 3}, {"id": 7}, {"id": 1}]) == 8

    def test_single_record(self):
        assert _next_id([{"id": 5}]) == 6


# ──────────────────────────────────────────────────────────
# Safety: 파일 I/O
# ──────────────────────────────────────────────────────────

class TestFileIO:
    def test_load_missing_file_returns_empty(self):
        assert _load_records() == []

    def test_load_corrupt_json_returns_empty_and_warns(self, isolated_db, capsys):
        isolated_db.write_text("{ 이건 깨진 json }", encoding="utf-8")
        result = _load_records()
        assert result == []
        assert "경고" in capsys.readouterr().out

    def test_load_empty_file_returns_empty(self, isolated_db, capsys):
        isolated_db.write_text("", encoding="utf-8")
        result = _load_records()
        assert result == []

    def test_save_load_roundtrip(self, isolated_db):
        records = [{"id": 1, "name": "홍길동", "phone": "010-1234-5678",
                    "email": "", "group": "기타", "memo": "",
                    "created_at": "2024-01-01 00:00:00",
                    "updated_at": "2024-01-01 00:00:00"}]
        _save_records(records)
        assert _load_records() == records

    def test_save_utf8_no_escape(self, isolated_db):
        """ensure_ascii=False: 한글이 \\uXXXX 이스케이프 없이 저장되어야 한다."""
        records = [{"id": 1, "name": "한글이름", "phone": "010-1234-5678",
                    "email": "", "group": "가족", "memo": "한글 메모",
                    "created_at": "", "updated_at": ""}]
        _save_records(records)
        raw = isolated_db.read_text(encoding="utf-8")
        assert "한글이름" in raw
        assert "\\u" not in raw


# ──────────────────────────────────────────────────────────
# Regression: CREATE
# ──────────────────────────────────────────────────────────

class TestCreate:
    def test_basic_create(self):
        c = create_contact("홍길동", "010-1234-5678", "", "친구", "")
        assert c.id == 1
        assert c.name == "홍길동"
        assert c.group == "친구"

    def test_timestamps_set_on_create(self):
        c = create_contact("홍길동", "010-1234-5678", "", "기타", "")
        assert c.created_at != ""
        assert c.updated_at != ""
        assert c.created_at == c.updated_at

    def test_persisted_to_file(self, isolated_db):
        create_contact("홍길동", "010-1234-5678", "", "기타", "")
        records = json.loads(isolated_db.read_text(encoding="utf-8"))
        assert len(records) == 1
        assert records[0]["name"] == "홍길동"

    def test_id_increments(self):
        c1 = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        c2 = create_contact("김철수", "010-2222-2222", "", "기타", "")
        assert c1.id == 1
        assert c2.id == 2

    def test_invalid_phone_raises(self):
        with pytest.raises(ValidationError):
            create_contact("홍길동", "123", "", "기타", "")

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            create_contact("", "010-1234-5678", "", "기타", "")

    def test_invalid_group_raises(self):
        with pytest.raises(ValidationError):
            create_contact("홍길동", "010-1234-5678", "", "없는그룹", "")

    def test_korean_preserved_in_file(self, isolated_db):
        create_contact("한글이름", "010-1234-5678", "", "가족", "한글메모")
        records = json.loads(isolated_db.read_text(encoding="utf-8"))
        assert records[0]["name"] == "한글이름"
        assert records[0]["memo"] == "한글메모"

    def test_five_records_all_unique_ids(self):
        ids = [create_contact(f"이름{i}", f"010111{i:05d}", "", "기타", "").id
               for i in range(5)]
        assert len(set(ids)) == 5


# ──────────────────────────────────────────────────────────
# Regression: READ
# ──────────────────────────────────────────────────────────

class TestReadAll:
    def test_empty_db_returns_empty_list(self):
        assert read_all() == []

    def test_returns_all_records(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        create_contact("김철수", "010-2222-2222", "", "기타", "")
        assert len(read_all()) == 2

    def test_returns_contact_instances(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        assert all(isinstance(c, Contact) for c in read_all())


class TestReadById:
    def test_found(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        found = read_by_id(c.id)
        assert found is not None
        assert found.name == "홍길동"

    def test_not_found_returns_none(self):
        assert read_by_id(9999) is None

    def test_correct_record_among_multiple(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        c2 = create_contact("김철수", "010-2222-2222", "", "친구", "")
        create_contact("이영희", "010-3333-3333", "", "가족", "")
        found = read_by_id(c2.id)
        assert found.name == "김철수"
        assert found.group == "친구"


# ──────────────────────────────────────────────────────────
# Regression: SEARCH
# ──────────────────────────────────────────────────────────

class TestSearch:
    def test_by_name(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        create_contact("김철수", "010-2222-2222", "", "기타", "")
        results = search_contacts("홍길동")
        assert len(results) == 1
        assert results[0].name == "홍길동"

    def test_by_email(self):
        create_contact("홍길동", "010-1111-1111", "hong@test.com", "기타", "")
        create_contact("김철수", "010-2222-2222", "kim@other.com", "기타", "")
        results = search_contacts("hong@test")
        assert len(results) == 1
        assert results[0].name == "홍길동"

    def test_by_memo(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "파이썬 개발자")
        create_contact("김철수", "010-2222-2222", "", "기타", "디자이너")
        results = search_contacts("파이썬")
        assert len(results) == 1
        assert results[0].name == "홍길동"

    def test_case_insensitive(self):
        create_contact("홍길동", "010-1111-1111", "Hong@Test.COM", "기타", "")
        assert len(search_contacts("hong@test")) == 1

    def test_partial_match(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        assert len(search_contacts("길")) == 1

    def test_multiple_matches(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        create_contact("홍길순", "010-2222-2222", "", "기타", "")
        create_contact("김철수", "010-3333-3333", "", "기타", "")
        assert len(search_contacts("홍길")) == 2

    def test_no_match_returns_empty(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "")
        assert search_contacts("없는이름") == []

    def test_empty_db_returns_empty(self):
        assert search_contacts("아무거나") == []


# ──────────────────────────────────────────────────────────
# Regression: UPDATE
# ──────────────────────────────────────────────────────────

class TestUpdate:
    def test_update_name(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        updated = update_contact(c.id, name="홍길순")
        assert updated.name == "홍길순"

    def test_update_phone(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        updated = update_contact(c.id, phone="010-9999-9999")
        assert updated.phone == "010-9999-9999"

    def test_update_group(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        updated = update_contact(c.id, group="가족")
        assert updated.group == "가족"

    def test_unchanged_fields_preserved(self):
        c = create_contact("홍길동", "010-1111-1111", "hong@test.com", "친구", "메모")
        updated = update_contact(c.id, name="홍길순")
        assert updated.phone == "010-1111-1111"
        assert updated.email == "hong@test.com"
        assert updated.group == "친구"
        assert updated.memo == "메모"

    def test_created_at_not_changed(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        original_ts = c.created_at
        updated = update_contact(c.id, name="홍길순")
        assert updated.created_at == original_ts

    def test_not_found_returns_none(self):
        assert update_contact(9999, name="없음") is None

    def test_invalid_phone_raises(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        with pytest.raises(ValidationError):
            update_contact(c.id, phone="123")

    def test_invalid_group_raises(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        with pytest.raises(ValidationError):
            update_contact(c.id, group="없는그룹")

    def test_invalid_update_does_not_persist(self, isolated_db):
        """검증 실패 시 파일이 변경되지 않아야 한다."""
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        with pytest.raises(ValidationError):
            update_contact(c.id, phone="invalid_phone")
        unchanged = read_by_id(c.id)
        assert unchanged.phone == "010-1111-1111"

    def test_update_persisted_to_file(self, isolated_db):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        update_contact(c.id, name="홍길순")
        records = json.loads(isolated_db.read_text(encoding="utf-8"))
        assert records[0]["name"] == "홍길순"

    def test_update_correct_record_only(self):
        c1 = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        c2 = create_contact("김철수", "010-2222-2222", "", "기타", "")
        update_contact(c1.id, name="홍변경")
        assert read_by_id(c2.id).name == "김철수"


# ──────────────────────────────────────────────────────────
# Regression: DELETE
# ──────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_returns_true(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        assert delete_contact(c.id) is True

    def test_not_found_returns_false(self):
        assert delete_contact(9999) is False

    def test_record_removed_after_delete(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        delete_contact(c.id)
        assert read_by_id(c.id) is None

    def test_others_preserved_after_delete(self):
        c1 = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        c2 = create_contact("김철수", "010-2222-2222", "", "기타", "")
        delete_contact(c1.id)
        remaining = read_all()
        assert len(remaining) == 1
        assert remaining[0].id == c2.id

    def test_delete_all_results_in_empty(self):
        c1 = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        c2 = create_contact("김철수", "010-2222-2222", "", "기타", "")
        delete_contact(c1.id)
        delete_contact(c2.id)
        assert read_all() == []

    def test_delete_twice_returns_false(self):
        c = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        delete_contact(c.id)
        assert delete_contact(c.id) is False


# ──────────────────────────────────────────────────────────
# Regression: ID 재사용 방지
# ──────────────────────────────────────────────────────────

class TestIdNoReuse:
    def test_id_after_delete_is_max_plus_one(self):
        """삭제 후 생성해도 max(id)+1 방식이라 낮은 ID를 재사용하지 않는다."""
        c1 = create_contact("홍길동", "010-1111-1111", "", "기타", "")
        c2 = create_contact("김철수", "010-2222-2222", "", "기타", "")
        delete_contact(c1.id)                               # id=1 삭제
        c3 = create_contact("이영희", "010-3333-3333", "", "기타", "")
        assert c3.id == 3                                   # max(2)+1, id=1 재사용 없음

    def test_ten_creates_all_unique_ids(self):
        ids = [create_contact(f"이름{i}", f"010111{i:05d}", "", "기타", "").id
               for i in range(10)]
        assert len(set(ids)) == 10


# ──────────────────────────────────────────────────────────
# End-to-End: 통합 시나리오
# ──────────────────────────────────────────────────────────

class TestIntegration:
    def test_full_crud_lifecycle(self):
        # Create
        c = create_contact("홍길동", "010-1111-1111", "hong@test.com", "친구", "테스트")
        assert c.id == 1

        # Read
        found = read_by_id(1)
        assert found.name == "홍길동"

        # Update
        updated = update_contact(1, name="홍길순", memo="수정됨")
        assert updated.name == "홍길순"
        assert updated.memo == "수정됨"
        assert updated.email == "hong@test.com"     # 미변경 필드 보존

        # Delete
        assert delete_contact(1) is True
        assert read_by_id(1) is None
        assert read_all() == []

    def test_search_consistent_across_create_delete(self):
        create_contact("홍길동", "010-1111-1111", "", "기타", "파이썬")
        c2 = create_contact("김파이썬", "010-2222-2222", "", "기타", "")

        assert len(search_contacts("파이썬")) == 2

        delete_contact(c2.id)
        results = search_contacts("파이썬")
        assert len(results) == 1
        assert results[0].name == "홍길동"

    def test_data_integrity_after_failed_update(self):
        """잘못된 업데이트 시 원본 데이터가 보존된다."""
        c = create_contact("홍길동", "010-1111-1111", "hong@test.com", "친구", "원본메모")
        with pytest.raises(ValidationError):
            update_contact(c.id, phone="bad", group="없는그룹")
        original = read_by_id(c.id)
        assert original.phone == "010-1111-1111"
        assert original.group == "친구"
        assert original.memo == "원본메모"

    def test_multiple_contacts_independent(self):
        """여러 연락처가 서로 간섭 없이 독립적으로 동작한다."""
        contacts = [
            create_contact(f"이름{i}", f"010{i:08d}", f"user{i}@test.com", "기타", "")
            for i in range(3)
        ]
        update_contact(contacts[1].id, name="수정된이름")
        delete_contact(contacts[0].id)

        remaining = read_all()
        assert len(remaining) == 2
        names = {c.name for c in remaining}
        assert "수정된이름" in names
        assert "이름2" in names
        assert "이름0" not in names
