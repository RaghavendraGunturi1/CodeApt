import logging
import requests
from typing import List, Dict, Any, Union

# Configure logger
logger = logging.getLogger("essays")

class AIService:
    # It is often better to use an environment variable or a config file for URLs
    AI_SERVICE_URL = "http://32.194.25.0:8000"
    TIMEOUT = 45

    @classmethod
    def _make_request(cls, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to handle common POST request logic."""
        url = f"{cls.AI_SERVICE_URL}/{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=cls.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning({f"ai_{endpoint.replace('-', '_')}_failed": str(e)})
            return {}
        except ValueError as e:
            logger.warning({f"ai_{endpoint.replace('-', '_')}_json_error": str(e)})
            return {}

    @staticmethod
    def extract_keywords(topic: str) -> List[str]:
        data = AIService._make_request("extract-keywords", {"topic": topic})
        keywords = data.get("keywords", [])
        
        if not isinstance(keywords, list):
            return []
            
        return [
            keyword.lower().strip()
            for keyword in keywords
            if isinstance(keyword, str) and keyword.strip()
        ]

    @staticmethod
    def analyze_vocabulary_sophistication(text: str) -> Dict[str, Union[float, str]]:
        """Returns: {"score": float (0-100), "notes": str}"""
        data = AIService._make_request("analyze-vocabulary-sophistication", {"text": text})
        
        try:
            score = float(data.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
            
        return {
            "score": max(0.0, min(100.0, score)),
            "notes": data.get("notes", "AI unavailable" if not data else "")
        }

    @staticmethod
    def analyze_structure_coherence(text: str) -> Dict[str, Any]:
        """Returns: {"score": float (0-100), "strengths": list, "weaknesses": list}"""
        data = AIService._make_request("analyze-structure-coherence", {"text": text})
        
        try:
            score = float(data.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0

        return {
            "score": max(0.0, min(100.0, score)),
            "strengths": data.get("strengths", []) if isinstance(data.get("strengths"), list) else [],
            "weaknesses": data.get("weaknesses", []) if isinstance(data.get("weaknesses"), list) else [],
        }

    @staticmethod
    def generate_feedback_summary(text: str) -> Dict[str, str]:
        """Returns: {"feedback": str, "strengths": str, "weaknesses": str}"""
        data = AIService._make_request("generate-feedback-summary", {"text": text})
        
        return {
            "feedback": data.get("feedback", "AI feedback unavailable."),
            "strengths": data.get("strengths", ""),
            "weaknesses": data.get("weaknesses", ""),
        }