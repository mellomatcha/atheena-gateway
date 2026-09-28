from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.seed import DEFAULT_SETTINGS, SEED_MEMBER_EMAIL, SEED_MODELS, seed


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


async def test_seed_is_idempotent_and_keeps_admin_changes(db: AsyncConnection) -> None:
    await seed(db, "admin@example.test")
    await db.execute(
        text("UPDATE settings SET value = '5000'::jsonb WHERE key = 'min_balance_idr'")
    )
    await seed(db, "admin@example.test")

    assert await db.scalar(text("SELECT count(*) FROM users")) == 2
    assert await db.scalar(text("SELECT count(*) FROM projects")) == 1
    assert await db.scalar(text("SELECT count(*) FROM models")) == len(SEED_MODELS)
    assert await db.scalar(text("SELECT value FROM settings WHERE key = 'min_balance_idr'")) == 5000


def test_seed_models_follow_catalog_rules() -> None:
    for model in SEED_MODELS:
        # FR-4.0: public names never carry the upstream routing prefix (anthropic/, cb/, ...).
        assert "/" not in model.public_name
        assert model.public_name != model.upstream_id
        # Q1: all prices start at Rp 0.
        assert model.price_input_per_m == model.price_output_per_m == 0
        assert model.price_cache_write_per_m == model.price_cache_read_per_m == 0
