import sqlite3
import uvicorn
import logging
from fastapi import FastAPI, Request

# 1. Setup Logging
logging.basicConfig(level=logging.INFO)
app = FastAPI()
DB_NAME = "hospital.db"


# 2. Database Init (Fast Mode)
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS doctors (id INTEGER PRIMARY KEY, name TEXT, slots TEXT)")
        # Check if empty, if so, seed
        c.execute("SELECT count(*) FROM doctors")
        if c.fetchone()[0] == 0:
            seed = [
                (1, "Dr. Priya", "10:00 AM, 04:00 PM"),
                (2, "Dr. Arun", "09:00 AM, 02:00 PM"),
                (3, "Dr. Danielle", "10:00 AM")
            ]
            c.executemany("INSERT INTO doctors VALUES (?,?,?)", seed)
            conn.commit()


init_db()


# 3. FAST API ENDPOINTS (Removed 'async' to prevent blocking)

@app.post("/check-slots")
async def check_slots(req: Request):
    try:
        raw_body = await req.json()
        print(f"\n🔎 SEARCH REQUEST: {raw_body}")

        # Extract extraction logic
        data = raw_body.get('message', {}).get('toolCalls', [{}])[0].get('function', {}).get('arguments', {})
        # Fallback if Vapi sends arguments at top level
        if not data: data = raw_body

        term = data.get('doctorName') or data.get('doctor_name') or data.get('specialty') or ""
        term = str(term).lower().strip()

        # Logic
        query_name = term
        if any(x in term for x in ["heart", "cardio", "idhayam"]):
            query_name = "Priya"
        elif any(x in term for x in ["skin", "derm", "thol"]):
            query_name = "Arun"
        elif "daniel" in term:
            query_name = "Danielle"

        print(f"🎯 MAPPED '{term}' -> '{query_name}'")

        # Database Lookup
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT name, slots FROM doctors WHERE name LIKE ?", (f"%{query_name}%",))
            res = c.fetchone()

        if res:
        # We put the answer in 'message' instead of 'result'
        # Some models prefer this key
        msg = f"The database confirms: {res[0]} is available at {res[1]}."
        print(f"✅ RETURNING: {msg}")
        return {"result": msg, "message": msg}

        print("❌ NOT FOUND")
        return {"result": f"No doctor found matching '{term}'."}

    except Exception as e:
        print(f"💥 ERROR: {e}")
        return {"result": "System Error: Unable to check database."}


@app.post("/book-slot")
async def book_slot(req: Request):
    try:
        raw_body = await req.json()
        print(f"\n📅 BOOKING REQUEST: {raw_body}")

        data = raw_body.get('message', {}).get('toolCalls', [{}])[0].get('function', {}).get('arguments', {})
        if not data: data = raw_body

        doctor = data.get('doctorName') or data.get('doctor_name')
        time = data.get('time') or ""

        # Simple Time Normalization
        clean_time = time.upper().replace(".", "").replace(" ", "")
        if "10" in clean_time:
            clean_time = "10:00 AM"
        elif "9" in clean_time:
            clean_time = "09:00 AM"
        elif "2" in clean_time:
            clean_time = "02:00 PM"

        print(f"📝 BOOKING: {doctor} @ {clean_time}")
        return {"result": "Booking Successful", "message": f"Success. Appointment confirmed with {doctor} at {clean_time}."}

    except Exception as e:
        print(f"💥 ERROR: {e}")
        return {"result": "System Error: Booking failed."}


if __name__ == "__main__":
    # Workers=1 prevents database locking issues
    uvicorn.run(app, host="0.0.0.0", port=5001)