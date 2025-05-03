# --- existing code unchanged above this ---

from fastapi import FastAPI, HTTPException, Body
from typing import Dict, List, Optional
from datetime import datetime
import traceback
import os

try:
    from .data_models import StudentProgressSettings, ProgressEventInput, ProgressSummaryOutput
except ImportError:
     from data_models import StudentProgressSettings, ProgressEventInput, ProgressSummaryOutput

try:
    from .processor import ProgressProcessor
except ImportError:
     from processor import ProgressProcessor

app = FastAPI(title="Progress Tracking Agent V2.2 (Refactored - Class Based)")

processor = ProgressProcessor()

@app.post("/progress/settings/{student_id}", response_model=StudentProgressSettings, status_code=201)
async def save_student_settings_endpoint(student_id: str, settings: StudentProgressSettings = Body(...)):
    try:
        saved_settings = await processor.save_settings(student_id, settings)
        return saved_settings
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] Error saving settings for {student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save settings: {e}")

@app.get("/progress/settings/{student_id}", response_model=StudentProgressSettings)
async def get_student_settings_endpoint(student_id: str):
    try:
        settings = await processor.get_settings(student_id)
        return settings
    except Exception as e:
        print(f"[API] Error getting settings for {student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not retrieve settings: {e}")

@app.post("/progress/update", status_code=200)
async def update_progress_endpoint(event: ProgressEventInput = Body(...)):
    try:
        await processor.update_topic_progress(event)
        return {"message": "Progress updated successfully."}
    except Exception as e:
        print(f"[API] Error updating progress endpoint for student {event.student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update progress: {e}")

@app.get("/progress/{student_id}", response_model=ProgressSummaryOutput)
async def get_progress_endpoint(student_id: str):
    try:
        summary = await processor.get_progress_summary(student_id)
        return summary
    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[API] Error getting progress summary endpoint for student {student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress summary: {e}")

@app.get("/")
async def read_root():
    llm_status = "OK" if processor.LLM_AVAILABLE and processor.llm else "Unavailable/Error"
    return {"message": "Progress Tracking Agent is running (Refactored).", "llm_status": llm_status}


# ✅ ADD THIS TO MAKE RAILWAY WORK
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Required for Railway to detect the port
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
