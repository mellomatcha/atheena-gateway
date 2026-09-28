"""Ledger service, admin top-ups and adjustments, member history (FR-5.x, FR-7.1, FR-7.7)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ledger import LedgerError, post_entry
from tests.conftest import ClientFactory
from tests.gateway_support import GatewayData, auth, gateway_data, openai_body

CSRF = {"X-Atheena-CSRF": "1"}


def email_of(user_id: uuid.UUID) -> str:
    return f"u-{user_id}@example.test"


@asynccontextmanager
async def as_user(
    gateway_factory: ClientFactory, user_id: uuid.UUID
) -> AsyncIterator[httpx.AsyncClient]:
    async with gateway_factory(app_env="development", dev_auth_email=email_of(user_id)) as client:
        client.headers.update(CSRF)
        yield client


async def make_admin(data: GatewayData) -> uuid.UUID:
    admin_id = await data.user(balance=0, tier="advanced")
    await data.execute("UPDATE users SET role = 'admin' WHERE id = :id", id=admin_id)
    return admin_id


async def ledger_sum(data: GatewayData, user_id: uuid.UUID) -> int:
    return int(
        await data.scalar(
            "SELECT coalesce(sum(amount_idr), 0) FROM ledger_entries WHERE user_id = :id",
            id=user_id,
        )
    )


async def test_post_entry_keeps_balance_equal_to_ledger_sum() -> None:
    async with gateway_data() as data:
        user_id = await data.user(balance=0)
        async with AsyncSession(data.engine) as session, session.begin():
            first = await post_entry(
                session, user_id=user_id, entry_type="topup", amount_idr=50_000
            )
            await post_entry(session, user_id=user_id, entry_type="usage", amount_idr=-1_250)
            await post_entry(
                session, user_id=user_id, entry_type="adjustment", amount_idr=-750, note="koreksi"
            )
            last = await post_entry(session, user_id=user_id, entry_type="refund", amount_idr=1_250)
        assert (first.balance_before_idr, first.balance_after_idr) == (0, 50_000)
        assert last.balance_after_idr == 49_250
        balance = await data.scalar("SELECT balance_idr FROM users WHERE id = :id", id=user_id)
        assert balance == 49_250 == await ledger_sum(data, user_id)


@pytest.mark.parametrize(
    ("entry_type", "amount", "note", "code"),
    [
        ("topup", 0, None, "invalid_amount"),
        ("topup", -5, None, "invalid_amount"),
        ("refund", -5, None, "invalid_amount"),
        ("usage", 5, None, "invalid_amount"),
        ("adjustment", 1_000, None, "note_required"),
        ("adjustment", 1_000, "  ", "note_required"),
        ("adjustment", 0, "x", "invalid_amount"),
        ("bonus", 1_000, None, "invalid_type"),
    ],
)
async def test_post_entry_rejects_invalid_entries(
    entry_type: str, amount: int, note: str | None, code: str
) -> None:
    async with gateway_data() as data:
        user_id = await data.user(balance=0)
        async with AsyncSession(data.engine) as session, session.begin():
            with pytest.raises(LedgerError) as excinfo:
                await post_entry(
                    session, user_id=user_id, entry_type=entry_type, amount_idr=amount, note=note
                )
        assert excinfo.value.code == code
        assert await ledger_sum(data, user_id) == 0


async def test_admin_topup_credits_balance_with_ledger_and_audit(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        admin_id = await make_admin(data)
        member_id = await data.user(balance=0)
        async with as_user(gateway_factory, admin_id) as client:
            response = await client.post(
                f"/app/api/admin/users/{member_id}/adjustments",
                json={"type": "topup", "amount_idr": 100_000, "note": "QRIS 28/09"},
                headers={"cf-connecting-ip": "203.0.113.9"},
            )
        assert response.status_code == 201
        body = response.json()
        assert (body["balance_before_idr"], body["balance_after_idr"]) == (0, 100_000)
        assert body["user"]["balance_idr"] == 100_000

        entry = (
            await data.fetch(
                "SELECT type, amount_idr, balance_after_idr, note, created_by FROM ledger_entries"
                " WHERE id = :id",
                id=body["entry_id"],
            )
        )[0]
        assert (entry.type, entry.amount_idr, entry.balance_after_idr) == (
            "topup",
            100_000,
            100_000,
        )
        assert entry.note == "QRIS 28/09"
        assert entry.created_by == admin_id  # FR-5.3: admin who added it

        audit = (
            await data.fetch(
                "SELECT actor_user_id, action, target_type, target_id, before, after, ip_hash"
                " FROM audit_logs WHERE target_id = :tid",
                tid=str(member_id),
            )
        )[0]
        assert audit.actor_user_id == admin_id
        assert audit.action == "balance.topup"
        assert audit.target_type == "user"
        assert audit.before == {"balance_idr": 0}
        assert audit.after["balance_idr"] == 100_000
        assert audit.after["amount_idr"] == 100_000
        assert audit.ip_hash is not None and "203.0.113.9" not in audit.ip_hash


async def test_admin_adjustment_requires_note_and_can_debit(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        admin_id = await make_admin(data)
        member_id = await data.user(balance=20_000)
        async with as_user(gateway_factory, admin_id) as client:
            url = f"/app/api/admin/users/{member_id}/adjustments"
            no_note = await client.post(url, json={"type": "adjustment", "amount_idr": -5_000})
            debit = await client.post(
                url,
                json={"type": "adjustment", "amount_idr": -5_000, "note": "salah input top-up"},
            )
            negative_topup = await client.post(url, json={"type": "topup", "amount_idr": -1})
            too_large = await client.post(url, json={"type": "topup", "amount_idr": 100_000_001})
            unknown_user = await client.post(
                f"/app/api/admin/users/{uuid.uuid4()}/adjustments",
                json={"type": "topup", "amount_idr": 1_000},
            )
        assert no_note.status_code == 400
        assert no_note.json()["error"]["code"] == "note_required"
        assert debit.status_code == 201
        assert debit.json()["balance_after_idr"] == 15_000
        assert negative_topup.status_code == 400
        assert too_large.status_code == 422
        assert unknown_user.status_code == 404
        assert await ledger_sum(data, member_id) == 15_000
        actions = await data.fetch(
            "SELECT action FROM audit_logs WHERE target_id = :tid", tid=str(member_id)
        )
        assert [a.action for a in actions] == ["balance.adjustment"]


async def test_members_cannot_use_admin_balance_api(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member_id = await data.user(balance=0)
        async with as_user(gateway_factory, member_id) as client:
            topup = await client.post(
                f"/app/api/admin/users/{member_id}/adjustments",
                json={"type": "topup", "amount_idr": 1_000_000},
            )
            users = await client.get("/app/api/admin/users")
            history = await client.get(f"/app/api/admin/users/{member_id}/ledger")
        assert topup.status_code == 403
        assert users.status_code == 403
        assert history.status_code == 403
        assert await ledger_sum(data, member_id) == 0


async def test_parallel_topups_and_usage_keep_balance_exact(
    gateway_factory: ClientFactory,
) -> None:
    """Admin credits and proxy debits racing on one user never lose an update."""
    async with gateway_data() as data:
        admin_id = await make_admin(data)
        member_id = await data.user(balance=10_000)
        key, _ = await data.key(member_id)
        # Rp 1.000 per request (1M input tokens at Rp 1.000 per 1M).
        model = await data.model("ok?prompt=1000000&completion=0", prices=("1000", "0", "0", "0"))
        async with as_user(gateway_factory, admin_id) as client:

            async def topup() -> int:
                response = await client.post(
                    f"/app/api/admin/users/{member_id}/adjustments",
                    json={"type": "topup", "amount_idr": 5_000},
                )
                return response.status_code

            async def usage() -> int:
                response = await client.post(
                    "/v1/chat/completions", json=openai_body(model), headers=auth(key)
                )
                return response.status_code

            statuses = await asyncio.gather(
                *(topup() if i % 2 == 0 else usage() for i in range(20))
            )
        assert statuses.count(201) == 10
        assert statuses.count(200) == 10
        expected = 10_000 + 10 * 5_000 - 10 * 1_000
        balance = await data.scalar("SELECT balance_idr FROM users WHERE id = :id", id=member_id)
        assert balance == expected == await ledger_sum(data, member_id)
        # 1 seed top-up + 10 admin top-ups + 10 usage debits.
        count = await data.scalar(
            "SELECT count(*) FROM ledger_entries WHERE user_id = :id", id=member_id
        )
        assert count == 21
        # Entry ids are monotonic UUID v7 created after the row lock is taken, so id order is
        # lock order: every balance_after must equal the previous one plus its own amount.
        chain = await data.fetch(
            "SELECT amount_idr, balance_after_idr FROM ledger_entries WHERE user_id = :id"
            " ORDER BY id",
            id=member_id,
        )
        previous = 0
        for entry in chain:
            assert entry.balance_after_idr == previous + entry.amount_idr
            previous = entry.balance_after_idr
        assert previous == expected


async def test_member_ledger_is_private_paginated_and_filterable(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        member_id = await data.user(balance=100_000)
        other_id = await data.user(balance=7_000)
        key, _ = await data.key(member_id)
        model = await data.model("ok?prompt=1000000&completion=0", prices=("100", "0", "0", "0"))
        async with as_user(gateway_factory, member_id) as client:
            for _ in range(3):
                await client.post(
                    "/v1/chat/completions", json=openai_body(model), headers=auth(key)
                )
            everything = await client.get("/app/api/ledger")
            credits = await client.get("/app/api/ledger", params={"kind": "credits"})
            page_two = await client.get("/app/api/ledger", params={"page": 2})
            info = await client.get("/app/api/topup-info")
        body = everything.json()
        assert body["total"] == 4
        assert [e["type"] for e in body["items"]] == ["usage", "usage", "usage", "topup"]
        assert body["items"][0]["amount_idr"] == -100
        assert body["items"][0]["request_id"] is not None
        assert [e["type"] for e in credits.json()["items"]] == ["topup"]
        assert page_two.json()["items"] == []
        # Only the member's own entries.
        assert all(e["amount_idr"] != 7_000 for e in body["items"])
        del other_id
        assert info.json() == {
            "whatsapp_number": "6282312202002",
            "qris_image_path": "/assets/qris.png",
        }


async def test_admin_user_search_and_history(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        admin_id = await make_admin(data)
        member_id = await data.user(balance=3_000)
        await data.execute(
            "UPDATE users SET display_name = 'Sari 100% Unik' WHERE id = :id", id=member_id
        )
        async with as_user(gateway_factory, admin_id) as client:
            by_name = await client.get("/app/api/admin/users", params={"q": "100% unik"})
            wildcard = await client.get("/app/api/admin/users", params={"q": "%"})
            history = await client.get(f"/app/api/admin/users/{member_id}/ledger")
        assert [u["id"] for u in by_name.json()] == [str(member_id)]
        # A literal "%" only matches names containing "%".
        assert all("%" in u["display_name"] or "%" in u["email"] for u in wildcard.json())
        assert history.json()["items"][0]["amount_idr"] == 3_000
