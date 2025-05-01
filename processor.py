# subagents/progress_tracking_agent/processor.py

import os
import json
import uuid
from typing import List, Optional, Dict, Union
from datetime import datetime, date
from collections import defaultdict
import statistics # Need this import
from dotenv import load_dotenv
import traceback
import asyncio

# --- Check and Import LLM Libraries ---
LANGCHAIN_AVAILABLE_FLAG = False
llm_client_class = None
prompt_template_class = None
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.prompts import PromptTemplate
    llm_client_class = ChatGoogleGenerativeAI
    prompt_template_class = PromptTemplate
    LANGCHAIN_AVAILABLE_FLAG = True
except ImportError:
    print("WARNING: Langchain or Google GenAI not installed. LLM features will be disabled.")

# --- Relative Import for Models ---
try:
    from .data_models import (
        StudentProgressSettings, ProgressEventInput, TopicProgressData, ProgressSummaryOutput
    )
except ImportError:
     from data_models import ( # Fallback
        StudentProgressSettings, ProgressEventInput, TopicProgressData, ProgressSummaryOutput
    )

# --- Load Environment Variables ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class ProgressProcessor:
    """Encapsulates logic and data storage for the Progress Tracking Agent."""

    def __init__(self):
        """Initializes storage and the LLM client if configured."""
        # --- In-memory storage (Managed by this processor instance) ---
        self.progress_db: Dict[str, Dict[str, TopicProgressData]] = defaultdict(lambda: {})
        self.student_settings_db: Dict[str, StudentProgressSettings] = {}

        # --- LLM Setup ---
        self.llm: Optional[ChatGoogleGenerativeAI] = None
        self.insight_prompt_template: Optional[PromptTemplate] = None
        self.LLM_AVAILABLE: bool = False

        if LANGCHAIN_AVAILABLE_FLAG and GOOGLE_API_KEY and llm_client_class and prompt_template_class:
            try:
                self.llm = llm_client_class(
                    model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.7
                )
                self.insight_prompt_template = prompt_template_class(
                    template="""
You are an encouraging AI learning assistant (YoBuddy). Analyze the student's progress data provided below and generate a brief (2-4 sentences), positive, and insightful summary for the student.

Student ID: {student_id}
Student's Learning Goals: {learning_goals}
Student's Success Threshold: {success_threshold}%

Progress Summary Metrics:
- Overall Completion: {overall_completion_percent:.1f}%
- Overall Average Score: {average_score_all_str}
- Total Study Time (Tracked): {total_study_time_minutes} minutes

Topic Breakdown:
{topic_breakdown_str}

Instructions for your summary:
- Start with a positive reinforcement or acknowledgement of effort.
- Mention progress towards their stated learning goals.
- Highlight 1-2 areas of strength (topics well above threshold or completed quickly).
- Gently point out 1-2 areas identified as weaknesses (topics below threshold or needing review), suggesting focus or encouragement.
- Keep the tone supportive and motivational. Do not just list stats. Address the student using "you".

Example Tone: "Great job focusing on your goal to master Physics! You've really nailed 'Kinematics' with an average score of 92%, exceeding your 80% target. Keep an eye on 'Newton's Laws' (68%) – maybe try reviewing the key concepts there this week. You're making good progress overall!"

Generate the summary now:
""",
                    input_variables=[
                        "student_id", "learning_goals", "success_threshold",
                        "overall_completion_percent", "average_score_all_str",
                        "total_study_time_minutes", "topic_breakdown_str"
                    ]
                )
                self.LLM_AVAILABLE = True
                print("ProgressProcessor: LLM Initialized successfully.")
            except Exception as e:
                print(f"ProgressProcessor ERROR: Failed LLM init: {e}")
                self.LLM_AVAILABLE = False
                self.llm = None
        else:
            if not LANGCHAIN_AVAILABLE_FLAG: print("ProgressProcessor WARNING: LLM libraries not installed.")
            if not GOOGLE_API_KEY: print("ProgressProcessor WARNING: GOOGLE_API_KEY missing.")
            self.LLM_AVAILABLE = False
            print("ProgressProcessor WARNING: LLM features disabled.")

    # --- Logic Methods (Async where needed) ---
    async def save_settings(self, student_id: str, settings: StudentProgressSettings) -> StudentProgressSettings:
        """Saves student settings."""
        if student_id != settings.student_id:
            # Use ValueError for internal logic errors, let endpoint handle HTTP Exception
            raise ValueError("Student ID in path does not match payload.")
        # Replace with async DB write later
        self.student_settings_db[student_id] = settings
        print(f"[Processor] Settings saved for student: {student_id}")
        return settings

    async def get_settings(self, student_id: str) -> StudentProgressSettings:
        """Gets student settings or returns defaults."""
        # Replace with async DB read later
        if student_id in self.student_settings_db:
            return self.student_settings_db[student_id]
        else:
            print(f"[Processor] No settings found for {student_id}, returning defaults.")
            # Create and return default settings, but don't save them automatically
            return StudentProgressSettings(student_id=student_id)

    # This method only updates in-memory dicts based on input, no async I/O needed *yet*
    # Making it async allows easier integration if DB calls are added later
    async def update_topic_progress(self, event: ProgressEventInput):
        """Handles incoming progress events, updates storage, checks thresholds."""
        student_id = event.student_id
        topic_id = event.topic_id
        print(f"[Processor] Updating progress for {student_id}, topic {topic_id}, event {event.event_type}")

        # Access internal storage
        student_data = self.progress_db[student_id]
        if topic_id not in student_data:
            student_data[topic_id] = TopicProgressData(topic_id=topic_id)

        topic_progress = student_data[topic_id]
        topic_progress.update_progress(event) # Update the topic data object

        # Check threshold
        settings = self.student_settings_db.get(student_id, StudentProgressSettings(student_id=student_id))
        threshold = settings.success_threshold
        needs_review = False
        score_for_trigger = None

        if event.event_type == 'quiz_attempted' and event.score is not None:
            score_for_trigger = event.score
            if event.score < threshold:
                needs_review = True
                topic_progress.status = "Needs Review" # Update status

        # Persist update (in memory for now)
        self.progress_db[student_id][topic_id] = topic_progress

        # Simulate Trigger (remains sync print)
        if needs_review:
            print(f"---!!! TRIGGER (SIMULATED for {student_id}) !!!---")
            reason = f"Score {score_for_trigger:.1f}% < Threshold {threshold:.1f}%." if score_for_trigger is not None else "Status requires review."
            print(f"  >> Path Agent: Adjustment needed for topic '{topic_id}'. Reason: {reason}")
            print(f"---!!! END TRIGGER !!!---")

    async def get_progress_summary(self, student_id: str) -> ProgressSummaryOutput:
        """Calculates progress summary and generates LLM insights (Async)."""
        print(f"[Processor] Calculating progress summary for {student_id}")
        # Access internal storage
        student_topic_data = self.progress_db.get(student_id, {})
        settings = self.student_settings_db.get(student_id, StudentProgressSettings(student_id=student_id))

        if not student_topic_data and student_id not in self.student_settings_db:
             # If neither exists, raise error for endpoint to catch
             raise ValueError(f"No progress data or settings found for student {student_id}.")

        # Calculate Metrics (Sync part)
        topics_progress_list = list(student_topic_data.values())
        identified_weaknesses = []; total_topics = len(topics_progress_list)
        completed_topics = 0; all_scores = []; total_study_time = 0
        for topic in topics_progress_list:
            if topic.status == "Completed": completed_topics += 1
            if topic.scores: all_scores.extend(topic.scores)
            total_study_time += topic.total_time_minutes
            if topic.status == "Needs Review" or (topic.average_score is not None and topic.average_score < settings.success_threshold):
                identified_weaknesses.append(topic.topic_id)
        overall_completion = (completed_topics / total_topics * 100) if total_topics > 0 else 0.0
        overall_avg_score = round(statistics.mean(all_scores), 1) if all_scores else None

        # Generate LLM Insight (Async part)
        llm_insight_text = None
        if self.LLM_AVAILABLE and self.llm and self.insight_prompt_template:
            print(f"[Processor] Attempting LLM insights for {student_id}")
            topic_breakdown = [f"- {t.topic_id}: Status='{t.status}', Avg Score={t.average_score:.1f}%, Attempts={t.attempts}" if t.average_score is not None else f"- {t.topic_id}: Status='{t.status}', Attempts={t.attempts}" for t in topics_progress_list]
            topic_breakdown_str = "\n".join(topic_breakdown) if topic_breakdown else "No topic data yet."
            try:
                prompt_filled = self.insight_prompt_template.format(
                    student_id=student_id, learning_goals=", ".join(settings.learning_goals) or "Not specified",
                    success_threshold=settings.success_threshold, overall_completion_percent=overall_completion,
                    average_score_all_str=f"{overall_avg_score:.1f}%" if overall_avg_score is not None else "N/A",
                    total_study_time_minutes=total_study_time, topic_breakdown_str=topic_breakdown_str
                )
                # *** Use await self.llm.ainvoke ***
                response = await self.llm.ainvoke(prompt_filled)
                llm_insight_text = response.content.strip()
                print(f"[Processor] LLM Insight Generated: {llm_insight_text}")
            except Exception as e:
                print(f"ERROR generating LLM insight for {student_id}: {e}")
                llm_insight_text = "Could not generate insights at this time due to an error." # Fallback text
        else:
            llm_insight_text = "LLM insights feature not available." # Fallback text

        return ProgressSummaryOutput(
            student_id=student_id, overall_completion_percent=round(overall_completion, 1),
            average_score_all=overall_avg_score, total_study_time_minutes=total_study_time,
            topics_progress=topics_progress_list, identified_weaknesses=list(set(identified_weaknesses)),
            llm_insights=llm_insight_text
        )

# --- Notes for Future ---
# (Keep relevant notes here)
# 1. Database Integration: Replace dicts with async DB operations.
# ... (rest of notes) ...
