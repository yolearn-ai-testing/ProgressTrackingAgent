# subagents/progress_tracking_agent/main.py

from fastapi import FastAPI, HTTPException, Body
from typing import Dict, List, Optional
from datetime import datetime
import traceback

# --- Relative imports ---
try:
    from .data_models import StudentProgressSettings, ProgressEventInput, ProgressSummaryOutput
except ImportError:
     from data_models import StudentProgressSettings, ProgressEventInput, ProgressSummaryOutput # Fallback
try:
    from .processor import ProgressProcessor
except ImportError:
     from processor import ProgressProcessor # Fallback

# Create the FastAPI application instance
app = FastAPI(title="Progress Tracking Agent V2.2 (Refactored - Class Based)")

# --- Instantiate Processor ---
processor = ProgressProcessor()

# ---------------------------
# API Endpoints (Async)
# ---------------------------
@app.post("/progress/settings/{student_id}", response_model=StudentProgressSettings, status_code=201, summary="Save Student Progress Settings")
async def save_student_settings_endpoint(student_id: str, settings: StudentProgressSettings = Body(...)):
    """Saves or updates progress settings (threshold, goals) for a student."""
    try:
        # Call processor method
        saved_settings = await processor.save_settings(student_id, settings)
        return saved_settings
    except ValueError as e: # Catch validation errors from processor
         raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] Error saving settings for {student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save settings: {e}")

@app.get("/progress/settings/{student_id}", response_model=StudentProgressSettings, summary="Get Student Progress Settings")
async def get_student_settings_endpoint(student_id: str):
    """Retrieves progress settings for a student, returning defaults if not found."""
    try:
        # Call processor method
        settings = await processor.get_settings(student_id)
        return settings
    except Exception as e:
        print(f"[API] Error getting settings for {student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not retrieve settings: {e}")

@app.post("/progress/update", status_code=200, summary="Update Progress with Event")
async def update_progress_endpoint(event: ProgressEventInput = Body(...)):
    """Receives a progress event, updates record via processor, checks threshold, simulates trigger."""
    try:
        # Call processor method
        await processor.update_topic_progress(event)
        return {"message": "Progress updated successfully."}
    except Exception as e:
        print(f"[API] Error updating progress endpoint for student {event.student_id}: {e}")
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update progress: {e}")

@app.get("/progress/{student_id}", response_model=ProgressSummaryOutput, summary="Get Progress Summary with Insights")
async def get_progress_endpoint(student_id: str):
    """Retrieves the progress summary via processor, including metrics and LLM insights."""
    try:
        # Call processor method
        summary = await processor.get_progress_summary(student_id)
        return summary
    except HTTPException as e: raise e # Re-raise 404 etc.
    except ValueError as e: # Catch specific logic errors like 'not found'
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[API] Error getting progress summary endpoint for student {student_id}: {e}")
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get progress summary: {e}")

@app.get("/", summary="Health Check")
async def read_root():
    """Basic health check endpoint."""
    # Access LLM status via processor instance attribute
    llm_status = "OK" if processor.LLM_AVAILABLE and processor.llm else "Unavailable/Error"
    return {"message": "Progress Tracking Agent is running (Refactored).", "llm_status": llm_status}

# --- Notes for Future --- now mainly in processor.py or README ---