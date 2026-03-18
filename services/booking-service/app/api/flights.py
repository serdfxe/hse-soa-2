"""Flight proxy endpoints — delegate to Flight Service via gRPC."""

from fastapi import APIRouter, Query

from app.core.dependencies import DBSession
from app.services import booking_service

router = APIRouter(prefix="/flights", tags=["Flights"])


@router.get("")
async def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: str = Query(default="", description="YYYY-MM-DD"),
) -> list[dict]:
    return await booking_service.search_flights(origin=origin, destination=destination, date=date)


@router.get("/{flight_id}")
async def get_flight(flight_id: str) -> dict:
    return await booking_service.get_flight(flight_id)
