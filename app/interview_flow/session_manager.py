from app.interview_flow.schemas import (
    InterviewSession,
    SessionStatus,
    QuestionProgress,
    Answer,
    SessionSummary
)
from app.interview_flow.timer import Timer
from app.interview_flow.answer_handler import AnswerHandler
from app.question_engine.schemas import QuestionSet
from datetime import datetime
from typing import Dict, List, Optional
import uuid
import json
from app.notifications.dispatcher import NotificationDispatcher
from app.notifications.logger import NotificationLogger
from app.database import SessionLocal
from app.models import Candidate, SessionModel

class SessionManager:
    """
    Manages interview sessions from start to finish.
    Orchestrates question flow, timing, and answer collection.
    """
    
    def __init__(self):
        # Store active sessions in memory
        # In production, this would be a database
        self.sessions: Dict[str, InterviewSession] = {}
        self.timers: Dict[str, Timer] = {}
        self.answer_handlers: Dict[str, AnswerHandler] = {}
        self.notification_dispatcher = NotificationDispatcher()
        self.audit_logger = NotificationLogger()
    
    def create_session(
        self,
        candidate_id: str,
        candidate_name: str,
        candidate_phone: str,
        candidate_email: str,
        question_set: QuestionSet,
        candidate_lang: str = "en",
        cv_path: str = ""
    ) -> InterviewSession:
        """
        Create a new interview session.
        
        Args:
            candidate_id: Unique candidate identifier
            candidate_name: Candidate name
            question_set: Set of questions from question engine
            candidate_lang: Preferred language
        
        Returns:
            InterviewSession object
        """
        session_id = str(uuid.uuid4())
        
        # Convert questions to dict format
        # Prepare questions for JSON storage (serialize datetimes)
        questions_dicts = [json.loads(q.json()) for q in question_set.questions]
        
        # Create session Pydantic object
        session = InterviewSession(
            session_id=session_id,
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
            candidate_lang=candidate_lang,
            start_time=datetime.now(),
            status=SessionStatus.ACTIVE,
            status_internal="PENDING",
            status_public="UNDER_REVIEW",
            total_questions=len(questions_dicts),
            current_question_index=0,
            questions=questions_dicts,
            answers=[],
            current_question=None
        )
        
        # Database Persistence
        db = SessionLocal()
        try:
            # 1. Find or create candidate
            db_candidate = db.query(Candidate).filter(Candidate.email == candidate_email).first()
            if not db_candidate:
                db_candidate = Candidate(
                    name=candidate_name,
                    email=candidate_email,
                    phone=candidate_phone,
                    cv_path=cv_path,
                    language=candidate_lang
                )
                db.add(db_candidate)
            else:
                # Update existing candidate details
                db_candidate.name = candidate_name
                db_candidate.phone = candidate_phone
                db_candidate.cv_path = cv_path
                db_candidate.language = candidate_lang
            
            db.flush() # Get ID / Commit updates
            
            # 2. Create DB Session
            db_session = SessionModel(
                id=session_id,
                candidate_id=db_candidate.id,
                # SNAPSHOT: Save candidate details at this moment
                candidate_name=candidate_name,
                candidate_phone=candidate_phone,
                candidate_email=candidate_email,
                
                status=SessionStatus.ACTIVE.value,
                status_internal="PENDING",
                status_public="UNDER_REVIEW",
                total_questions=len(questions_dicts),
                current_question_index=0,
                questions=questions_dicts,
                answers=[]
            )
            db.add(db_session)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"DB Error while creating session: {e}")
        finally:
            db.close()

        # Store session in memory for active tracking (optional, but keep for compatibility)
        self.sessions[session_id] = session
        self.answer_handlers[session_id] = AnswerHandler()
        
        # Start first question
        self._start_next_question(session_id)
        
        return session
    
    def get_current_question(self, session_id: str) -> Optional[QuestionProgress]:
        """
        Get the current question for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            QuestionProgress or None
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.status != SessionStatus.ACTIVE:
            return None
        
        # Update time remaining
        if session.current_question and session_id in self.timers:
            timer = self.timers[session_id]
            session.current_question.time_remaining = timer.get_time_remaining()
        
        return session.current_question
    
    def submit_answer(
        self,
        session_id: str,
        answer_text: str
    ) -> Answer:
        """
        Submit answer for current question and move to next.
        
        Args:
            session_id: Session ID
            answer_text: Candidate's answer
        
        Returns:
            Answer object
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.status != SessionStatus.ACTIVE:
            raise ValueError(f"Session {session_id} is not active")
        
        if not session.current_question:
            raise ValueError("No active question")
        
        # Stop timer
        timer = self.timers.get(session_id)
        if not timer:
            raise ValueError("Timer not found")
        
        time_spent = timer.stop()
        is_timeout = timer.is_timeout()
        
        # Submit answer
        answer_handler = self.answer_handlers[session_id]
        answer = answer_handler.submit_answer(
            question_id=session.current_question.question_id,
            answer_text=answer_text,
            time_spent=time_spent,
            is_timeout=is_timeout
        )
        
        # Add to session
        session.answers.append(answer)
        
        # Database Persistence
        db = SessionLocal()
        try:
            db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if db_session:
                # Append answer to JSON field (serialize datetime)
                current_answers = list(db_session.answers) if db_session.answers else []
                answer_dict = json.loads(answer.json())
                current_answers.append(answer_dict)
                db_session.answers = current_answers
                db_session.current_question_index += 1
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"DB Error while submitting answer: {e}")
        finally:
            db.close()

        # Move to next question in memory
        session.current_question_index += 1
        
        if session.current_question_index >= session.total_questions:
            # Interview finished
            self._finish_session(session_id)
        else:
            # Start next question
            self._start_next_question(session_id)
        
        return answer
    
    def get_session_status(self, session_id: str) -> InterviewSession:
        """
        Get current session status.
        
        Args:
            session_id: Session ID
        
        Returns:
            InterviewSession object
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Update current question time if active
        if session.status == SessionStatus.ACTIVE and session.current_question:
            timer = self.timers.get(session_id)
            if timer:
                session.current_question.time_remaining = timer.get_time_remaining()
        
        return session
    
    def get_session_summary(self, session_id: str) -> SessionSummary:
        """
        Get summary of completed session.
        
        Args:
            session_id: Session ID
        
        Returns:
            SessionSummary object
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        answer_handler = self.answer_handlers.get(session_id)
        total_time = answer_handler.get_total_time_spent() if answer_handler else 0
        
        return SessionSummary(
            session_id=session.session_id,
            candidate_name=session.candidate_name,
            total_questions=session.total_questions,
            answered_questions=len(session.answers),
            total_time_spent=total_time,
            status=session.status,
            answers=session.answers
        )
    
    def _start_next_question(self, session_id: str):
        """Start the next question in the session"""
        session = self.sessions[session_id]
        
        if session.current_question_index >= len(session.questions):
            return
        
        # Get next question
        question_data = session.questions[session.current_question_index]
        
        # Create question progress
        question_progress = QuestionProgress(
            question_id=question_data["id"],
            question_text=question_data["question"],
            skill=question_data["skill"],
            difficulty=question_data["difficulty"],
            time_limit=Timer.get_time_limit(question_data["difficulty"]),
            started_at=datetime.now()
        )
        
        # Start timer
        timer = Timer(question_data["difficulty"])
        timer.start()
        self.timers[session_id] = timer
        
        # Update session
        session.current_question = question_progress
    
    def _finish_session(self, session_id: str):
        """Mark session as finished"""
        session = self.sessions[session_id]
        session.status = SessionStatus.FINISHED
        session.end_time = datetime.now()
        session.current_question = None
        
        # Database Persistence
        db = SessionLocal()
        try:
            db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if db_session:
                db_session.status = SessionStatus.FINISHED.value
                db_session.end_time = session.end_time
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"DB Error while finishing session: {e}")
        finally:
            db.close()

        # Clean up timer
        if session_id in self.timers:
            del self.timers[session_id]

    async def update_status(self, session_id: str, new_internal: str, new_public: Optional[str] = None, actor: str = "HR_SYSTEM"):
        """
        Update internal and/or public status.
        If public status changes, trigger notification.
        """
        session = self.sessions.get(session_id)
        db = SessionLocal()
        try:
            db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if not session and not db_session:
                raise ValueError(f"Session {session_id} not found")

            # Capture old states
            old_internal = session.status_internal if session else db_session.status_internal
            old_public = session.status_public if session else db_session.status_public

            # Update DB
            if db_session:
                db_session.status_internal = new_internal
                if new_public:
                    db_session.status_public = new_public
                db.commit()
            
            # Update memory
            if session:
                session.status_internal = new_internal
                if new_public:
                    session.status_public = new_public

            # Log internal change
            self.audit_logger.log_status_change(session_id, old_internal, new_internal, actor)

            # Handle public notification
            if new_public and new_public != old_public:
                self.audit_logger.log_status_change(session_id, old_public, new_public, f"{actor}_PUBLIC")
                
                # Get candidate details for notification
                name, email, phone, lang = "", "", "", "en"
                if session:
                    name, email, phone, lang = session.candidate_name, session.candidate_email, session.candidate_phone, session.candidate_lang
                elif db_session and db_session.candidate:
                    name, email, phone, lang = db_session.candidate.name, db_session.candidate.email, db_session.candidate.phone, db_session.candidate.language

                await self.notification_dispatcher.send_final_decision(
                    candidate_id=session_id,
                    name=name,
                    email=email,
                    phone=phone,
                    status_public=new_public,
                    lang=lang
                )
            else:
                print(f"DEBUG: Notification skipped. new_public({new_public}) == old_public({old_public})")
        except Exception as e:
            db.rollback()
            print(f"Error in update_status: {e}")
            raise
        finally:
            db.close()
