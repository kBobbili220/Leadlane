from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Service
from backend.app.schemas import ServiceCreate, ServiceUpdate


def create_service(session: Session, business_id: UUID, payload: ServiceCreate) -> Service:
    service = Service(business_id=business_id, **payload.model_dump())
    session.add(service)
    session.flush()
    return service


def list_services(
    session: Session, business_id: UUID, *, include_archived: bool, limit: int, offset: int
) -> list[Service]:
    statement = select(Service).where(Service.business_id == business_id)
    if not include_archived:
        statement = statement.where(Service.is_active.is_(True))
    statement = statement.order_by(Service.sort_order, Service.id).limit(limit).offset(offset)
    return list(session.scalars(statement))


def get_service(
    session: Session, business_id: UUID, service_id: UUID, *, for_update: bool = False
) -> Service | None:
    statement = select(Service).where(Service.business_id == business_id, Service.id == service_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def update_service(session: Session, service: Service, payload: ServiceUpdate) -> Service:
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, name, value)
    session.flush()
    return service


def archive_service(session: Session, service: Service) -> None:
    service.is_active = False
    session.flush()
