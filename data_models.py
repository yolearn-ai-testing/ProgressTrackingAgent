# subagents/progress_tracking_agent/data_models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union
from datetime import datetime
import uuid # Although not used in these specific models, keep if other agents need it
import statistics # Keep here as it might be used for future model methods

class StudentProgressSettings(BaseModel):
    """Settings related to progress tracking for a student"""
    student_id: str
    success_threshold: float = Field(default=80.0, ge=0, le=100, description="Student's definition of success %")
    learning_goals: List[str] = Field(default=[], description="Student's primary learning goals")

class ProgressEventInput(BaseModel):
    """Input for reporting a progress event"""
    student_id: str
    topic_id: str # Corresponds to Topic.topic_id from Learning Path Agent
    event_type: str # e.g., 'topic_completed', 'quiz_attempted', 'resource_viewed', 'session_duration_minutes'
    timestamp: datetime = Field(default_factory=datetime.now)
    score: Optional[float] = Field(default=None, ge=0, le=100) # e.g., Quiz score %
    duration_minutes: Optional[int] = Field(default=None, ge=0) # e.g., Time spent on topic/resource
    details: Optional[Dict] = Field(default=None) # e.g., {'quiz_id': 'q123', 'attempts': 1}

class TopicProgressData(BaseModel):
    """Stores aggregated progress data for a single topic"""
    topic_id: str
    status: str = Field(default="Not Started", description="e.g., Not Started, In Progress, Completed, Needs Review")
    attempts: int = 0
    scores: List[float] = Field(default=[]) # Store all scores
    average_score: Optional[float] = None
    total_time_minutes: int = 0
    last_activity_type: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now)

    def update_progress(self, event: ProgressEventInput):
        """Updates topic progress based on an incoming event."""
        self.last_updated = event.timestamp
        self.last_activity_type = event.event_type
        # Only set to In Progress if Not Started, allow Completed/Needs Review to persist
        if self.status == "Not Started":
            self.status = "In Progress"

        if event.event_type == 'quiz_attempted' and event.score is not None:
            self.attempts += event.details.get('attempts', 1) if event.details else 1
            self.scores.append(event.score)
            if self.scores:
                 # Use statistics module correctly
                 self.average_score = round(statistics.mean(self.scores), 1)
            else:
                 self.average_score = None
        elif event.event_type == 'topic_completed':
            self.status = "Completed"
        elif event.event_type == 'session_duration_minutes' and event.duration_minutes is not None:
            self.total_time_minutes += event.duration_minutes
        elif event.event_type == 'needs_review': # Could be triggered by low score logic
             self.status = "Needs Review"

class ProgressSummaryOutput(BaseModel):
    """Output structure for the GET /progress endpoint"""
    student_id: str
    overall_completion_percent: float = 0.0
    average_score_all: Optional[float] = None
    total_study_time_minutes: int = 0
    topics_progress: List[TopicProgressData] = Field(default=[])
    identified_weaknesses: List[str] = Field(default=[], description="List of topic_ids flagged as weak")
    llm_insights: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.now)