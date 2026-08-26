import httpx
import json
from datetime import date, timedelta

# Configuration
BASE_URL = "http://127.0.0.1:8000"

def print_section(title):
    print("\n" + "=" * 60)
    print(f" {title} ")
    print("=" * 60)

def print_response(response):
    req = response.request
    print(f"--> Outgoing Request: {req.method} {req.url}")
    if req.content:
        print("    Request Body:")
        try:
            body_text = req.content.decode("utf-8")
            body_json = json.loads(body_text)
            print(f"      {json.dumps(body_json, indent=6)}")
        except Exception:
            print(f"      {req.content}")
    print(f"<-- Incoming Response: Status Code {response.status_code}")
    try:
        print("    Response Body:")
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print("    Response Body (Text):")
        print(response.text[:200] + "..." if len(response.text) > 200 else response.text)


def main():
    print("Hospital Appointment Booking API Client Demonstration (GPT Workspace)")
    
    # 1. Health Check
    print_section("1. GET /api/health - Health Check")
    r = httpx.get(f"{BASE_URL}/api/health")
    print_response(r)
    
    # 2. Get Doctors (Initial)
    print_section("2. GET /api/doctors - List Doctors")
    r = httpx.get(f"{BASE_URL}/api/doctors")
    print_response(r)
    
    # 3. Create a Doctor
    print_section("3. POST /api/doctors - Create New Doctor")
    new_doctor = {
        "name": "Dr. Ananya Sharma",
        "specialization": "Cardiologist",
        "experience": 12,
        "available_days": ["Monday", "Wednesday", "Friday"],
        "start_time": "09:00",
        "end_time": "17:00"
    }
    r = httpx.post(f"{BASE_URL}/api/doctors", json=new_doctor)
    print_response(r)
    doctor_id = r.json().get("id") if r.status_code == 201 else 1

    # 4. Create a Patient
    print_section("4. POST /api/patients - Create New Patient")
    new_patient = {
        "name": "Aarav Kumar",
        "age": 30,
        "phone": "9876543210",
        "email": "aarav.kumar@example.com"
    }
    r = httpx.post(f"{BASE_URL}/api/patients", json=new_patient)
    print_response(r)
    patient_id = r.json().get("id") if r.status_code == 201 else 1

    # Calculate a valid date (next Monday)
    today = date.today()
    days_ahead = 0 - today.weekday() + 7  # Next Monday
    booking_date = (today + timedelta(days=days_ahead)).isoformat()
    booking_time = "10:00"

    # 5. Check Doctor Availability
    print_section(f"5. GET /api/availability - Availability for Doctor {doctor_id} on {booking_date}")
    r = httpx.get(f"{BASE_URL}/api/availability", params={"doctor_id": doctor_id, "date": booking_date})
    print_response(r)

    # 6. Book an Appointment
    print_section("6. POST /api/appointments - Book Appointment")
    appointment_payload = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "date": booking_date,
        "time": booking_time,
        "reason": "Regular cardiology health checkup"
    }
    r = httpx.post(f"{BASE_URL}/api/appointments", json=appointment_payload)
    print_response(r)
    appointment_id = r.json().get("id") if r.status_code == 201 else None

    # 7. Attempt Duplicate Booking (Conflict)
    print_section("7. POST /api/appointments - Attempt Duplicate Booking")
    r = httpx.post(f"{BASE_URL}/api/appointments", json=appointment_payload)
    print_response(r)

    # 8. List Appointments
    print_section("8. GET /api/appointments - List All Appointments")
    r = httpx.get(f"{BASE_URL}/api/appointments")
    print_response(r)

    if appointment_id:
        # 9. Update Appointment Status
        print_section(f"9. PATCH /api/appointments/{appointment_id}/status - Update Status")
        r = httpx.patch(f"{BASE_URL}/api/appointments/{appointment_id}/status", json={"status": "Completed"})
        print_response(r)

    # 10. Summary Report
    print_section("10. GET /api/reports/summary - Summary Report")
    r = httpx.get(f"{BASE_URL}/api/reports/summary")
    print_response(r)

    # 11. Export Appointments CSV
    print_section("11. GET /api/reports/appointments.csv - Export Appointments to CSV")
    r = httpx.get(f"{BASE_URL}/api/reports/appointments.csv")
    print_response(r)

if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print("\n[ERROR] Connection error. Please make sure the FastAPI server is running on http://127.0.0.1:8000 first!")
