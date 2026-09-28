"""Runtime settings and projects (FR-7.6, PRD §15). Every change is audited (FR-7.7)."""

import re
import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.gateway.settings_store import load_settings
from app.ids import new_id
from app.models import Project, Setting
from app.net import client_ip_hash
from app.portal.deps import AdminUser, PortalError, SessionDep
from app.services.audit import record_audit

router = APIRouter()


class SettingsOut(BaseModel):
    min_balance_idr: int
    default_user_daily_cap_idr: int | None
    rate_limit_per_key_per_minute: int
    rate_limit_per_user_per_minute: int
    max_concurrent_streams_per_user: int
    max_body_bytes: int
    max_active_keys_per_user: int
    default_low_balance_threshold_idr: int


class SettingsPatch(BaseModel):
    min_balance_idr: int | None = Field(default=None, ge=0, le=100_000_000)
    # Explicit null turns the default daily cap off.
    default_user_daily_cap_idr: int | None = Field(default=None, gt=0, le=1_000_000_000)
    rate_limit_per_key_per_minute: int | None = Field(default=None, ge=1, le=100_000)
    rate_limit_per_user_per_minute: int | None = Field(default=None, ge=1, le=100_000)
    max_concurrent_streams_per_user: int | None = Field(default=None, ge=1, le=1_000)
    max_body_bytes: int | None = Field(default=None, ge=1024, le=200 * 1024 * 1024)
    max_active_keys_per_user: int | None = Field(default=None, ge=1, le=100)
    default_low_balance_threshold_idr: int | None = Field(default=None, ge=0, le=100_000_000)


def _settings_out(values: dict[str, Any]) -> SettingsOut:
    return SettingsOut.model_validate({key: values[key] for key in SettingsOut.model_fields})


@router.get("/settings")
async def get_settings(admin: AdminUser, session: SessionDep) -> SettingsOut:
    return _settings_out(await load_settings(session))


@router.patch("/settings")
async def patch_settings(
    body: SettingsPatch, request: Request, admin: AdminUser, session: SessionDep
) -> SettingsOut:
    current = await load_settings(session)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is None and key != "default_user_daily_cap_idr":
            continue
        if current.get(key) == value:
            continue
        statement = insert(Setting).values(id=new_id(), key=key, value=value)
        await session.execute(
            statement.on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await record_audit(
            session,
            actor_user_id=admin.id,
            action="settings.update",
            target_type="setting",
            target_id=key,
            before={"value": current.get(key)},
            after={"value": value},
            ip_hash=client_ip_hash(request),
        )
    await session.commit()
    return _settings_out(await load_settings(session))


SLUG = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,63}$")


class ProjectOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    official_only: bool


class ProjectCreate(BaseModel):
    slug: str
    name: str = Field(min_length=1, max_length=80)
    official_only: bool = False

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, value: str) -> str:
        value = value.strip().lower()
        if not SLUG.match(value):
            raise ValueError("slug hanya huruf kecil, angka, strip, dan garis bawah")
        return value


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    official_only: bool | None = None


@router.get("/projects")
async def list_projects(admin: AdminUser, session: SessionDep) -> list[ProjectOut]:
    rows = (await session.scalars(select(Project).order_by(Project.slug))).all()
    return [ProjectOut.model_validate(p, from_attributes=True) for p in rows]


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectCreate, request: Request, admin: AdminUser, session: SessionDep
) -> ProjectOut:
    if await session.scalar(select(Project.id).where(Project.slug == body.slug)):
        raise PortalError(409, "slug_taken", "Slug proyek ini sudah ada.")
    project = Project(id=new_id(), **body.model_dump())
    session.add(project)
    await session.flush()
    await record_audit(
        session,
        actor_user_id=admin.id,
        action="project.create",
        target_type="project",
        target_id=str(project.id),
        after=body.model_dump(),
        ip_hash=client_ip_hash(request),
    )
    await session.commit()
    return ProjectOut.model_validate(project, from_attributes=True)


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    body: ProjectPatch,
    request: Request,
    admin: AdminUser,
    session: SessionDep,
) -> ProjectOut:
    project = await session.get(Project, project_id, with_for_update=True)
    if project is None:
        raise PortalError(404, "project_not_found", "Proyek tidak ditemukan.")
    before = {"name": project.name, "official_only": project.official_only}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(project, field, value)
    after = {"name": project.name, "official_only": project.official_only}
    if before != after:
        await record_audit(
            session,
            actor_user_id=admin.id,
            action="project.update",
            target_type="project",
            target_id=str(project.id),
            before={k: v for k, v in before.items() if after[k] != v},
            after={k: v for k, v in after.items() if before[k] != v},
            ip_hash=client_ip_hash(request),
        )
    await session.commit()
    return ProjectOut.model_validate(project, from_attributes=True)
