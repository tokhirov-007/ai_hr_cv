from typing import List, Dict
from app.scoring.schemas import ScoreBreakdown
from app.scoring.weight_config import get_weights
from app.answer_analysis.schemas import FullIntegrityReport
from app.interview_flow.schemas import SessionSummary
import re

class ScoreEngine:
    """
    Combines technical evaluation, integrity, and behavioral data.
    """

    def calculate_technical_scores(self, summary: SessionSummary, questions: List[Dict]) -> Dict[str, float]:
        """
        Simulate technical scoring by checking for technical keywords 
        and expected topics in answers.
        """
        q_map = {q["id"]: q for q in questions}
        
        technical_scores = []
        problem_solving_scores = []

        for answer in summary.answers:
            q_data = q_map.get(answer.question_id, {})
            expected = q_data.get("expected_topics", [])
            
            # Log zero score reason if no answer or timeout
            if not answer.answer_text or answer.is_timeout:
                print(f"[SCORE_LOG] why_score_zero=True: Question {answer.question_id} has no answer or timeout")
                technical_scores.append(0.0)
                problem_solving_scores.append(0.0)
                continue

            # 1. Knowledge Score: Topic matching
            matches = 0
            for topic in expected:
                if re.search(r'\b' + re.escape(topic.lower()) + r'\b', answer.answer_text.lower()):
                    matches += 1
            
            # Base score from topics
            knowledge_base = (matches / len(expected)) * 100 if expected else 50
            
            # Depth bonus (longer answers with technical words)
            # Added Russian/Uzbek support for keywords
            technical_keywords = [
                "implementation", "performance", "complexity", "architecture", "pattern", "logic",
                "реализация", "производительность", "сложность", "архитектура", "паттерн", "логика",
                "amalga oshirish", "unumdorlik", "murakkablik", "arxitektura", "andoza", "mantiq"
            ]
            depth_bonus = sum(5 for word in technical_keywords if word in answer.answer_text.lower())
            
            knowledge_final = min(100.0, knowledge_base + depth_bonus)
            
            if knowledge_final == 0:
                print(f"[SCORE_LOG] why_score_zero=True: Knowledge score 0 for Question {answer.question_id}. Answer: '{answer.answer_text[:50]}...'")
            
            technical_scores.append(knowledge_final)

            # 2. Problem Solving Score (heuristic for case questions)
            is_case = q_data.get("type") == "case"
            if is_case:
                # Better score if they mention "trade-offs", "strategy", "solution"
                ps_markers = [
                    "trade-off", "alternative", "depends", "strategy", "handling", "solution", "scale",
                    "компромисс", "альтернатива", "зависит", "стратегия", "обработка", "решение", "масштабирование",
                    "kelishuv", "muqobil", "bog'liq", "strategiya", "ishlov", "yechim", "miqyoslash"
                ]
                ps_matches = sum(10 for m in ps_markers if m in answer.answer_text.lower())
                ps_score = min(100.0, knowledge_base + ps_matches)
                if ps_score == 0:
                    print(f"[SCORE_LOG] why_score_zero=True: PS score 0 for case question {answer.question_id}")
                problem_solving_scores.append(ps_score)
            else:
                problem_solving_scores.append(knowledge_final * 0.8) # Non-cases don't show full PS

        avg_knowledge = sum(technical_scores) / len(technical_scores) if technical_scores else 0
        avg_ps = sum(problem_solving_scores) / len(problem_solving_scores) if problem_solving_scores else 0
        
        return {
            "knowledge": avg_knowledge,
            "problem_solving": avg_ps
        }

    def calculate_skills_match(self, cv_skills: List[str], questions: List[Dict]) -> float:
        """
        Calculates how well the interview covered the candidate's skills.
        Range: 0-100
        """
        if not cv_skills or not questions:
            return 50.0
            
        interview_skills = set()
        for q in questions:
            skill = q.get("skill", "").lower()
            if skill:
                interview_skills.add(skill)
        
        cv_skills_lower = [s.lower() for s in cv_skills]
        matches = 0
        for skill in cv_skills_lower:
            if any(skill in iskill or iskill in skill for iskill in interview_skills):
                matches += 1
                
        return min(100.0, (matches / len(cv_skills_lower)) * 100) if cv_skills_lower else 100.0

    def calculate_confidence_points(self, confidence_level: str) -> float:
        """Maps confidence enum to numerical score (0-100)"""
        mapping = {
            "high": 100.0,
            "medium": 65.0,
            "low": 30.0
        }
        return mapping.get(confidence_level.lower(), 50.0)

    def aggregate(self, 
                  summary: SessionSummary, 
                  integrity_report: FullIntegrityReport,
                  questions: List[Dict],
                  cv_skills: List[str],
                  confidence_level: str) -> ScoreBreakdown:
        """
        Aggregate all data into component scores.
        """
        tech = self.calculate_technical_scores(summary, questions)
        
        # Mapping integrity report results back to components
        honesty = integrity_report.overall_honesty_score * 100
        
        # NEW: Skills Match
        skills_match = self.calculate_skills_match(cv_skills, questions)
        
        # NEW: Confidence Points
        confidence_points = self.calculate_confidence_points(confidence_level)

        return ScoreBreakdown(
            knowledge_score=round(tech["knowledge"], 2),
            honesty_score=round(honesty, 2),
            time_behavior_score=round(skills_match, 2), # Re-using this field for skills_match in SAFE MODE if schema change is restricted
            problem_solving_score=round(confidence_points, 2) # Re-using for confidence_points
        )

    def calculate_final_weighted_score(self, breakdown: ScoreBreakdown, difficulty_mix: str) -> int:
        """
        Calculate score = skills_match + answers_quality + confidence
        Weights: 34% skills_match, 33% technical (answers_quality), 33% confidence
        """
        # In SAFE MODE, we reuse breakdown fields to avoid schema changes if possible
        skills_match = breakdown.time_behavior_score
        answers_quality = breakdown.knowledge_score
        confidence = breakdown.problem_solving_score
        
        # Formula: Each contributes ~33.3 points to max 100
        final = (
            (skills_match * 0.34) +
            (answers_quality * 0.33) +
            (confidence * 0.33)
        )
        
        return int(round(final))
