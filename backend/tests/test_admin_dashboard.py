"""Admin boundaries, audit history, live key invalidation, reports and leaderboard."""

import csv
import io
from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from app.services.leaderboard import period_bounds
from app.services.usage import today_wib
from app.worker import rollup_days
from tests.conftest import ClientFactory
from tests.gateway_support import auth, gateway_data, openai_body, setting
from tests.test_portal_keys import dashboard


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/admin/users", None),
        ("POST", "/admin/users", {"email": "new@example.test", "display_name": "New"}),
        ("GET", "/admin/models", None),
        ("POST", "/admin/models/sync", None),
        ("GET", "/admin/settings", None),
        ("PATCH", "/admin/settings", {"min_balance_idr": 0}),
        ("GET", "/admin/projects", None),
        ("GET", "/admin/audit-logs", None),
        ("GET", "/admin/health", None),
        ("GET", "/admin/usage/summary", None),
        ("GET", "/admin/usage/timeseries", None),
        ("GET", "/admin/usage/requests", None),
        ("GET", "/admin/usage/export.csv", None),
        ("GET", "/admin/reports/monthly?month=2026-10", None),
        ("GET", "/admin/reports/monthly.csv?month=2026-10", None),
    ],
)
async def test_member_cannot_access_admin(
    gateway_factory: ClientFactory, method: str, path: str, body: dict[str, object] | None
) -> None:
    async with gateway_data() as data:
        user = await data.user()
        async with dashboard(gateway_factory, user) as client:
            response = await client.request(method, f"/app/api{path}", json=body)
    assert response.status_code == 403


async def test_suspend_invalidates_warm_keys_and_self_lockout_is_blocked(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        admin = await data.user()
        await data.execute("UPDATE users SET role='admin' WHERE id=:u", u=admin)
        member = await data.member()
        model = await data.model()
        async with dashboard(gateway_factory, admin) as client:
            first = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
            assert first.status_code == 200
            changed = await client.patch(
                f"/app/api/admin/users/{member.user_id}", json={"status": "suspended"}
            )
            assert changed.status_code == 200
            rejected = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
            assert rejected.status_code in (401, 403)
            for patch in ({"status": "suspended"}, {"role": "member"}):
                response = await client.patch(f"/app/api/admin/users/{admin}", json=patch)
                assert response.status_code == 400
                assert response.json()["error"]["code"] == "self_lockout"


async def test_catalog_price_audit_and_sync_does_not_activate(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        admin = await data.user()
        await data.execute("UPDATE users SET role='admin' WHERE id=:u", u=admin)
        name = f"new-{admin.hex[:12]}"
        async with dashboard(gateway_factory, admin) as client:
            payload = {
                "public_name": name,
                "upstream_id": "cbai/test",
                "provider": "test",
                "category": "experimental",
            }
            invalid = await client.post(
                "/app/api/admin/models", json={**payload, "public_name": "cbai/test"}
            )
            assert invalid.status_code == 422
            created = await client.post("/app/api/admin/models", json=payload)
            assert created.status_code == 201 and created.json()["is_active"] is False
            model_id = created.json()["id"]
            updated = await client.patch(
                f"/app/api/admin/models/{model_id}", json={"price_input_per_m": "123.45"}
            )
            assert updated.status_code == 200
            audit = (
                await client.get(
                    "/app/api/admin/audit-logs", params={"action": "model.price_update"}
                )
            ).json()
            entry = next(r for r in audit["items"] if r["target_id"] == model_id)
            assert entry["before"]["price_input_per_m"] == "0.00"
            assert entry["after"]["price_input_per_m"] == "123.45"
            before = await data.scalar("SELECT count(*) FROM models")
            with respx.mock(assert_all_called=True) as mock:
                mock.get(url__regex=r".*/v1/models$").respond(
                    200, json={"data": [{"id": "new/model", "owned_by": "new"}]}
                )
                sync = await client.post("/app/api/admin/models/sync")
            assert sync.status_code == 200
            assert sync.json()["candidates"][0]["suggested_public_name"] == "model"
            assert await data.scalar("SELECT count(*) FROM models") == before


async def test_settings_projects_and_user_changes_are_audited(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        admin = await data.user()
        await data.execute("UPDATE users SET role='admin' WHERE id=:u", u=admin)
        async with (
            setting(data, "min_balance_idr", 1000),
            dashboard(gateway_factory, admin) as client,
        ):
            changed = await client.patch("/app/api/admin/settings", json={"min_balance_idr": 2000})
            assert changed.status_code == 200
            project = await client.post(
                "/app/api/admin/projects",
                json={"slug": f"p-{admin.hex[:12]}", "name": "Project", "official_only": True},
            )
            assert project.status_code == 201
            patch = await client.patch(
                f"/app/api/admin/projects/{project.json()['id']}", json={"official_only": False}
            )
            assert patch.status_code == 200
            user = await client.post(
                "/app/api/admin/users",
                json={"email": f"new-{admin}@example.test", "display_name": "New"},
            )
            assert user.status_code == 201
            log = (await client.get("/app/api/admin/audit-logs")).json()
            actions = {r["action"] for r in log["items"]}
            assert {
                "settings.update",
                "project.create",
                "project.update",
                "user.create",
            } <= actions
            change = next(r for r in log["items"] if r["action"] == "settings.update")
            assert change["before"] == {"value": 1000}
            assert change["after"] == {"value": 2000}


async def test_global_usage_and_monthly_csv_match_requests(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        admin = await data.user()
        await data.execute("UPDATE users SET role='admin' WHERE id=:u", u=admin)
        member = await data.user()
        model = await data.model()
        now = datetime.now(UTC)
        project = f"project-{admin}"
        for cost in (100, 250):
            await data.request(
                user_id=member, model=model, started_at=now, project=project, cost_idr=cost
            )
        async with dashboard(gateway_factory, admin) as client:
            summary = await client.get("/app/api/admin/usage/summary", params={"user": str(member)})
            assert summary.status_code == 200
            assert summary.json()["totals"]["cost_idr"] == 350
            assert summary.json()["by_project"][0]["totals"]["requests"] == 2
            month = today_wib().strftime("%Y-%m")
            report = await client.get("/app/api/admin/reports/monthly", params={"month": month})
            row = next(r for r in report.json()["rows"] if r["key"] == project)
            assert row["totals"]["cost_idr"] == 350
            exported = await client.get(
                "/app/api/admin/reports/monthly.csv", params={"month": month}
            )
            rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
            assert next(r for r in rows if r["proyek"] == project)["biaya_idr"] == "350"
            for invalid in ("0000-01", "9999-12", "2026-13", "oops"):
                response = await client.get(
                    "/app/api/admin/reports/monthly", params={"month": invalid}
                )
                assert response.status_code == 400


async def test_health_handles_failed_upstream(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        admin = await data.user()
        await data.execute("UPDATE users SET role='admin' WHERE id=:u", u=admin)
        async with dashboard(gateway_factory, admin) as client:
            with respx.mock(assert_all_called=True) as mock:
                mock.get(url__regex=r".*/v1/models$").mock(
                    side_effect=httpx.ConnectError("offline")
                )
                response = await client.get("/app/api/admin/health")
            assert response.status_code == 200
            assert response.json()["upstream_ok"] is False
            assert response.json()["upstream_error"]
            assert response.json()["active_streams"] >= 0


async def test_leaderboard_privacy_and_efficiency_threshold(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        eligible = await data.user()
        small = await data.user()
        hidden = await data.user()
        suspended = await data.user(status="suspended")
        await data.execute("UPDATE users SET leaderboard_opt_out=true WHERE id=:u", u=hidden)
        model = await data.model()
        for user, count in ((eligible, 100), (small, 99), (hidden, 101), (suspended, 102)):
            await data.execute(
                "UPDATE users SET display_name=:n, username=:handle WHERE id=:u",
                u=user,
                n="Private Full Name",
                handle="u_" + user.hex[:20],
            )
            for _ in range(count):
                await data.request(
                    user_id=user, model=model, started_at=datetime.now(UTC), tokens=(50, 10, 0, 50)
                )
        async with data.engine.begin() as conn:
            await rollup_days(conn, [today_wib()])
        async with dashboard(gateway_factory, eligible) as client:
            efficient = (
                await client.get("/app/api/leaderboard", params={"metric": "efficiency"})
            ).json()
            names = {r["username"] for r in efficient["entries"]}
            assert "u_" + eligible.hex[:20] in names
            assert not {"u_" + u.hex[:20] for u in (small, hidden, suspended)} & names
            me = next(r for r in efficient["entries"] if r["is_me"])
            assert me["value"] == 0.5
            ordinary = (await client.get("/app/api/leaderboard")).json()
            assert "u_" + small.hex[:20] in {r["username"] for r in ordinary["entries"]}
            assert "Private Full Name" not in str(ordinary)
            assert "display_name" not in str(ordinary)
            assert "full_name" not in str(ordinary)
            assert "@example.test" not in str(ordinary)


def test_calendar_periods() -> None:
    assert period_bounds("week", date(2026, 10, 25)) == (date(2026, 10, 19), date(2026, 10, 25))
    assert period_bounds("week", date(2026, 10, 26)) == (date(2026, 10, 26), date(2026, 10, 26))
    assert period_bounds("month", date(2026, 10, 1)) == (date(2026, 10, 1), date(2026, 10, 1))
