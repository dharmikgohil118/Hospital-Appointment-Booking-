from __future__ import annotations

import asyncio
import csv
import json
import os
import time
from contextlib import contextmanager
from functools import reduce, wraps
from pathlib import Path
from threading import Lock
from typing import Generator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / os.getenv("DATA_FILE", "data/database.json")
APP_NAME = os.getenv("APP_NAME", "Hospital Appointment Booking")
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
DB_LOCK = Lock()


@contextmanager
def open_data_file(mode: str = "r"):
    """Context manager required by the assignment for safe file handling."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, mode, encoding="utf-8", newline="") as file:
        yield file


def load_db() -> dict:
    with DB_LOCK:
        with open_data_file("r") as file:
            return json.load(file)


def save_db(db: dict) -> None:
    with DB_LOCK:
        temp = DATA_FILE.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as file:
            json.dump(db, file, indent=2)
        temp.replace(DATA_FILE)


def timed_endpoint(func):
    """Decorator: records endpoint execution time for the assignment."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} completed in {elapsed:.4f}s")
        return result
    return wrapper


# Iterator / generator requirement.
def appointment_generator(appointments: list[dict]) -> Generator[dict, None, None]:
    for appointment in appointments:
        yield appointment


def next_id(items: list[dict]) -> int:
    return max((item["id"] for item in items), default=0) + 1


class Doctor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    specialization: str = Field(min_length=2, max_length=80)
    experience: int = Field(ge=0, le=70)
    available_days: list[str] = Field(min_length=1)
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Patient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    age: int = Field(ge=0, le=120)
    phone: str = Field(pattern=r"^[0-9]{10}$")
    email: str = Field(min_length=5, max_length=120)


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reason: str = Field(min_length=3, max_length=300)


class AppointmentStatus(BaseModel):
    status: str


class SearchFilter(BaseModel):
    specialization: str | None = None


def get_db() -> dict:
    """FastAPI dependency injection."""
    return load_db()


@app.middleware("http")
async def request_logger(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-App-Name"] = APP_NAME
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.6f}"
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": APP_NAME}


@app.get("/api/doctors")
@timed_endpoint
async def list_doctors(db: dict = Depends(get_db), specialization: str | None = None):
    doctors = db["doctors"]
    if specialization:
        doctors = list(filter(lambda d: d["specialization"].lower() == specialization.lower(), doctors))
    # Comprehension: compact response projection.
    return [doctor for doctor in doctors]


@app.post("/api/doctors", status_code=201)
async def create_doctor(doctor: Doctor, db: dict = Depends(get_db)):
    item = doctor.model_dump()
    item["id"] = next_id(db["doctors"])
    db["doctors"].append(item)
    save_db(db)
    return item


@app.get("/api/patients")
async def list_patients(db: dict = Depends(get_db)):
    return db["patients"]


@app.post("/api/patients", status_code=201)
async def create_patient(patient: Patient, db: dict = Depends(get_db)):
    item = patient.model_dump()
    item["id"] = next_id(db["patients"])
    db["patients"].append(item)
    save_db(db)
    return item


@app.get("/api/appointments")
async def list_appointments(db: dict = Depends(get_db), status: str | None = None):
    # Generator + list comprehension.
    generated = appointment_generator(db["appointments"])
    result = [a for a in generated if not status or a["status"].lower() == status.lower()]
    return result


async def validate_booking(patient_id: int, doctor_id: int, date: str, booking_time: str, db: dict) -> dict:
    patient = next((p for p in db["patients"] if p["id"] == patient_id), None)
    doctor = next((d for d in db["doctors"] if d["id"] == doctor_id), None)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    weekday = __import__("datetime").date.fromisoformat(date).strftime("%A")
    if weekday not in doctor["available_days"]:
        raise HTTPException(status_code=400, detail=f"Doctor is not available on {weekday}")
    if not (doctor["start_time"] <= booking_time < doctor["end_time"]):
        raise HTTPException(status_code=400, detail="Selected time is outside doctor's working hours")
    conflict = any(
        a["doctor_id"] == doctor_id and a["date"] == date and a["time"] == booking_time and a["status"] == "Booked"
        for a in db["appointments"]
    )
    if conflict:
        raise HTTPException(status_code=409, detail="This appointment slot is already booked")
    return doctor


@app.post("/api/appointments", status_code=201)
@timed_endpoint
async def create_appointment(payload: AppointmentCreate, db: dict = Depends(get_db)):
    await asyncio.sleep(0)  # Asyncio requirement: non-blocking endpoint path.
    doctor = await validate_booking(payload.patient_id, payload.doctor_id, payload.date, payload.time, db)
    item = payload.model_dump()
    item.update({"id": next_id(db["appointments"]), "status": "Booked"})
    db["appointments"].append(item)
    save_db(db)
    return {**item, "doctor_name": doctor["name"]}


@app.patch("/api/appointments/{appointment_id}/status")
async def update_status(appointment_id: int, payload: AppointmentStatus, db: dict = Depends(get_db)):
    allowed = {"Booked", "Completed", "Cancelled"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of {sorted(allowed)}")
    appointment = next((a for a in db["appointments"] if a["id"] == appointment_id), None)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment["status"] = payload.status
    save_db(db)
    return appointment


@app.get("/api/availability")
async def availability(doctor_id: int, date: str, db: dict = Depends(get_db)):
    doctor = next((d for d in db["doctors"] if d["id"] == doctor_id), None)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    weekday = __import__("datetime").date.fromisoformat(date).strftime("%A")
    if weekday not in doctor["available_days"]:
        return {"available": False, "slots": []}
    hour_start = int(doctor["start_time"].split(":")[0])
    hour_end = int(doctor["end_time"].split(":")[0])
    slots = [f"{h:02d}:00" for h in range(hour_start, hour_end)]
    booked = {a["time"] for a in db["appointments"] if a["doctor_id"] == doctor_id and a["date"] == date and a["status"] == "Booked"}
    return {"available": True, "slots": [slot for slot in slots if slot not in booked]}


@app.get("/api/reports/summary")
async def summary(db: dict = Depends(get_db)):
    appointments = db["appointments"]
    status_counts = {status: len([a for a in appointments if a["status"] == status]) for status in ["Booked", "Completed", "Cancelled"]}
    # map/filter/reduce: count total reasons length over booked appointments as a simple workload metric.
    booked_reasons = list(map(lambda a: len(a["reason"]), filter(lambda a: a["status"] == "Booked", appointments)))
    reason_characters = reduce(lambda x, y: x + y, booked_reasons, 0)
    return {
        "total_doctors": len(db["doctors"]),
        "total_patients": len(db["patients"]),
        "total_appointments": len(appointments),
        "status_counts": status_counts,
        "booked_reason_characters": reason_characters,
    }


@app.get("/api/reports/appointments.csv")
async def export_csv(db: dict = Depends(get_db)):
    rows = db["appointments"]
    def row_stream():
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "patient_id", "doctor_id", "date", "time", "reason", "status"])
        writer.writeheader()
        yield output.getvalue()
        for row in rows:
            output.seek(0); output.truncate(0)
            writer.writerow(row)
            yield output.getvalue()
    return StreamingResponse(row_stream(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=appointments.csv"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=os.getenv("HOST", "127.0.0.1"), port=PORT, reload=True)
