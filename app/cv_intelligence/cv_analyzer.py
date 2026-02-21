from app.cv_intelligence.parser import CVParser
from app.cv_intelligence.skill_extractor import SkillExtractor
from app.cv_intelligence.skill_mapper import SkillMapper
from app.cv_intelligence.schemas import CVAnalysisResult
from app.config import settings
import re

class CVAnalyzer:
    def __init__(self):
        print("Initializing CV Analyzer components...")
        self.parser = CVParser()
        self.extractor = SkillExtractor(model=settings.SPACY_MODEL)
        self.mapper = SkillMapper(model_name=settings.TRANSFORMER_MODEL)
        print("CV Analyzer ready.")

    def _validate_resume(self, text: str) -> bool:
        """
        Validates if the provided text looks like a resume.
        Checked markers:
        - Presence of typical headings (Work experience, Skills, Education)
        - Contact information patterns (email, phone)
        - Date patterns (years)
        - Minimum content length and keyword density
        """
        if not text or len(text.strip()) < 100:
            return False

        text_lower = text.lower()
        
        # 1. Essential Resume Section Markers (RU, UZ, EN)
        resume_markers = [
            "experience", "work history", "employment", "projects", "education", "skills", "technologies", "certificates", "languages", "summary", "profile",
            "опыт работы", "образование", "навыки", "технологии", "проекты", "курсы", "сертификаты", "о себе", "контакты", "личные данные",
            "ish tajribasi", "ma'lumoti", "ko'nikmalar", "loyihalar", "kurslar", "sertifikatlar", "til", "aloqa"
        ]
        
        marker_count = sum(1 for m in resume_markers if m in text_lower)
        
        # 2. Contact Info Check
        has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        has_phone = bool(re.search(r'\+?\d{9,15}', text))
        
        # 3. Date Pattern Check (Finding potential years like 2018, 2022)
        has_years = bool(re.search(r'\b(19|20)\d{2}\b', text))

        # Scoring heuristics
        validation_score = 0
        if marker_count >= 3: validation_score += 40
        if marker_count >= 1: validation_score += 10
        if has_email: validation_score += 20
        if has_phone: validation_score += 20
        if has_years: validation_score += 20
        
        # If the score is too low, it's likely not a resume
        return validation_score >= 40

    def analyze(self, file_path: str) -> CVAnalysisResult:
        """
        Orchestrates the CV analysis process:
        1. Parse text from file
        2. Validate if it's a resume
        3. Extract explicit skills and semantic candidates
        4. Map candidates to inferred skills
        5. Return structured result
        """
        # 1. Parse Text
        print(f"Parsing file: {file_path}")
        raw_text = self.parser.parse(file_path)
        
        # 2. Validate Resume
        if not self._validate_resume(raw_text):
            print(f"[VALIDATION_FAIL] File {file_path} does not look like a resume.")
            raise ValueError("The uploaded file does not look like a professional resume. Please provide a valid CV.")

        # 3. Extract Skills
        print("Extracting skills...")
        extraction_result = self.extractor.extract(raw_text)
        explicit_skills = extraction_result["explicit"]
        candidates = extraction_result["candidates"]
        
        # 3. Map Skills (Semantic Understanding)
        print("Mapping semantic skills...")
        inferred_skills = self.mapper.map_skills(candidates)
        
        # 4. Construct Result
        return CVAnalysisResult(
            raw_text=raw_text, # Return full text as requested
            skills_detected=sorted(list(set(explicit_skills))),
            inferred_skills=sorted(list(set(inferred_skills))),
            experience_years=self._estimate_experience(raw_text),
            confidence={
                "parsing": 1.0 if raw_text else 0.0,
                "skill_extraction": 0.85 if explicit_skills else 0.1,
                "semantic_inference": 0.75 if inferred_skills else 0.0
            }
        )

    def _estimate_experience(self, text: str) -> float | None:
        # Simple heuristic to find years of experience
        # Looks for patterns like "5 years experience", "3+ years", etc.
        matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', text.lower())
        if matches:
            try:
                years = [int(m) for m in matches]
                return float(max(years)) if years else None
            except:
                return None
        return None
