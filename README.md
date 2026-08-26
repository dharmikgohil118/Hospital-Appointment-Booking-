# Hospital Appointment Booking 

A web application for the college FastAPI assignment. The backend exposes REST APIs and the frontend consumes those APIs with vanilla JavaScript.

## Features
- Patient registration
- Doctor listing and specialization filter
- Doctor availability by date
- Appointment booking with conflict validation
- Cancel appointment
- Dashboard statistics
- JSON data storage
- CSV export
- Swagger API documentation at `/docs`

## Assignment concepts included
- FastAPI REST APIs and routing
- Pydantic request/response validation
- Dependency Injection (`Depends`)
- Middleware
- Async endpoints + `asyncio`
- Error handling
- JSON and CSV file handling
- Iterator/generator
- Decorator
- Lambda with `map`, `filter`, `reduce`
- List comprehensions
- Context manager
- `.env` configuration
- Thread-safe file access via a lock
- Pytest
- Dockerfile

## Run in VS Code / terminal

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

Open: http://127.0.0.1:8000

Swagger: http://127.0.0.1:8000/docs

## Docker

```bash
docker build -t hospital-appointment-booking .
docker run -p 8000:8000 hospital-appointment-booking
```
