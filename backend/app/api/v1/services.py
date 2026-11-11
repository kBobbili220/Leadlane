from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.app.api.dependencies import CurrentBusinessID, DatabaseSession
from backend.app.schemas import ServiceCreate, ServiceRead, ServiceUpdate
from backend.app.services import services

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate, session: DatabaseSession, business_id: CurrentBusinessID
) -> ServiceRead:
    service = services.create_service(session, business_id, payload)
    result = ServiceRead.model_validate(service)
    session.commit()
    return result


@router.get("", response_model=list[ServiceRead])
def list_services(
    session: DatabaseSession,
    business_id: CurrentBusinessID,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ServiceRead]:
    return [
        ServiceRead.model_validate(service)
        for service in services.list_services(
            session, business_id, include_archived=include_archived, limit=limit, offset=offset
        )
    ]


@router.get("/{id}", response_model=ServiceRead)
def get_service(id: UUID, session: DatabaseSession, business_id: CurrentBusinessID) -> ServiceRead:
    service = services.get_service(session, business_id, id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return ServiceRead.model_validate(service)


@router.patch("/{id}", response_model=ServiceRead)
def update_service(
    id: UUID, payload: ServiceUpdate, session: DatabaseSession, business_id: CurrentBusinessID
) -> ServiceRead:
    service = services.get_service(session, business_id, id, for_update=True)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    services.update_service(session, service, payload)
    result = ServiceRead.model_validate(service)
    session.commit()
    return result


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_service(id: UUID, session: DatabaseSession, business_id: CurrentBusinessID) -> Response:
    service = services.get_service(session, business_id, id, for_update=True)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    services.archive_service(session, service)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
