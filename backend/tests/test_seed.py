from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.gateway.settings_store import DEFAULT_SETTINGS
from app.seed import SEED_MEMBER_EMAIL, SEED_MODELS, seed


async def test_seed_creates_admin_member_project_and_settings(db: AsyncConnection) -> None:
    await seed(db, "Admin@Example.Test")

    users = {
        row.email: row
        for row in await db.execute(text("SELECT email, role, tier, status FROM users"))
    }
    assert users["admin@example.test"].role == "admin"
    assert users["admin@example.test"].status == "active"
    assert users[SEED_MEMBER_EMAIL].role == "member"
    assert users[SEED_MEMBER_EMAIL].tier == "basic"

    official_only = await db.scalar(
        text("SELECT official_only FROM projects WHERE slug = 'helios'")
    )
    assert official_only is True

    stored = {
        row.key: row.value for row in await db.execute(text("SELECT key, value FROM settings"))
    }
    assert stored == DEFAULT_SETTINGS
    assert stored["min_balance_idr"] == 1_000
    assert stored["rate_limit_per_key_per_minute"] == 60
    assert stored["rate_limit_per_user_per_minute"] == 120


async def _counts(db: AsyncConnection) -> dict[str, int]:
    # Other tests commit their own rows to the test database, so compare deltas.
    queries = {
        "users": "SELECT count(*) FROM users",
        "projects": "SELECT count(*) FROM projects",
        "models": "SELECT count(*) FROM models",
        "settings": "SELECT count(*) FROM settings",
    }
    return {name: int(await db.scalar(text(sql)) or 0) for name, sql in queries.items()}


async def test_seed_is_idempotent_and_keeps_admin_changes(db: AsyncConnection) -> None:
    before = await _counts(db)
    await seed(db, "admin@example.test")
    after_first = await _counts(db)
    await db.execute(
        text("UPDATE settings SET value = '5000'::jsonb WHERE key = 'min_balance_idr'")
    )
    await seed(db, "admin@example.test")

    assert await _counts(db) == after_first
    assert after_first["users"] - before["users"] == 2
    assert after_first["models"] - before["models"] == len(SEED_MODELS)
    assert await db.scalar(text("SELECT count(*) FROM projects WHERE slug = 'helios'")) == 1
    assert await db.scalar(text("SELECT value FROM settings WHERE key = 'min_balance_idr'")) == 5000


async def test_seed_creates_starter_catalog(db: AsyncConnection) -> None:
    await seed(db, "admin@example.test")

    rows = await db.execute(
        text(
            "SELECT public_name, upstream_id, api_format, provider, category, min_tier, is_active,"
            " price_input_per_m, price_output_per_m, price_cache_write_per_m,"
            " price_cache_read_per_m FROM models WHERE public_name = ANY(:names)"
            " ORDER BY public_name"
        ),
        {"names": [m.public_name for m in SEED_MODELS]},
    )
    catalog = {row.public_name: row for row in rows}
    assert set(catalog) == {"claude-haiku-4.5-exp", "gemini-3.1-flash-lite", "glm-4.6"}
    assert catalog["claude-haiku-4.5-exp"].upstream_id == "cb/claude-haiku-4.5"
    for row in catalog.values():
        assert row.api_format == "both"
        assert row.provider == "codebuddy"
        assert row.category == "experimental"
        assert row.min_tier == "basic"
        assert row.is_active is True
        assert row.price_input_per_m == row.price_output_per_m == 0
        assert row.price_cache_write_per_m == row.price_cache_read_per_m == 0


def test_seed_models_follow_catalog_rules() -> None:
    # TASK-000: 2-3 cheap models as the starting catalog.
    assert 2 <= len(SEED_MODELS) <= 3
    for model in SEED_MODELS:
        # Q2: Opus-class models are never available to the basic tier.
        assert "opus" not in model.upstream_id.lower() or model.min_tier == "advanced"
        # FR-4.0: public names never carry the upstream routing prefix (anthropic/, cb/, ...).
        assert "/" not in model.public_name
        assert model.public_name != model.upstream_id
        # Q1: all prices start at Rp 0.
        assert model.price_input_per_m == model.price_output_per_m == 0
        assert model.price_cache_write_per_m == model.price_cache_read_per_m == 0
