# essays/services/scoring_service.py
import logging
import math
import re
from collections import Counter

from django.db import transaction
from django.utils import timezone


from ..utils import split_paragraphs, split_sentences, split_words
from essays.services.ai_service import AIService

logger = logging.getLogger("essays")


class EssayScorer:
        # Academic vocabulary for bonus
        ACADEMIC_WORDS = {
            "personalized", "educational", "accessibility", "infrastructure", "technology",
            "implementation", "communication", "development", "interaction", "institution",
            "automation", "analytics",
        }
        ENABLE_AI_FEEDBACK = True
        ENABLE_AI_STRUCTURE = False
        # Feature flags for runtime AI
        ENABLE_AI_VOCAB = False

        TRANSITION_WORDS = {
            "however", "therefore", "moreover", "furthermore",
            "consequently", "meanwhile", "additionally", "although",
            "instead", "finally", "overall", "in conclusion",
            "in addition", "for example", "on the other hand",
        }

        STOPWORDS = {
            "the", "and", "is", "are", "was", "were", "be", "been",
            "being", "to", "of", "in", "on", "at", "for", "from",
            "with", "by", "as", "an", "a", "it", "this", "that",
            "these", "those", "or", "if", "then", "than", "but",
            "so", "because", "while", "during", "into", "through",
            "about", "after", "before", "above", "below", "under",
            "again", "further", "once", "here", "there", "when",
            "where", "why", "how", "all", "any", "both", "each",
            "few", "more", "most", "other", "some", "such", "only",
            "own", "same", "too", "very", "can", "will", "just",
        }

        def analyze_vocabulary_sophistication(self, text):
            """
            Calls AIService for vocabulary sophistication and vague language analysis.
            Returns: {"score": float, "notes": str}
            """
            try:
                # Endpoint name must match FastAPI exactly
                result = AIService.analyze_vocabulary_sophistication(text)
                logger.debug({"ai_vocab_sophistication": result})
                return result
            except Exception as e:
                logger.warning({"ai_vocab_sophistication_failed": str(e)})
                return {"score": 65.0, "notes": "AI unavailable"}

        def analyze_structure_coherence(self, text):
            """
            Calls AIService for structure coherence analysis.
            Returns: {"score": float, "strengths": list, "weaknesses": list}
            """
            try:
                # Endpoint name must match FastAPI exactly
                result = AIService.analyze_structure_coherence(text)
                logger.debug({"ai_structure_coherence": result})
                return result
            except Exception as e:
                logger.warning({"ai_structure_coherence_failed": str(e)})
                return {"score": 70.0, "strengths": [], "weaknesses": []}

        FILLER_WORDS = {
            "good", "bad", "nice", "thing", "things", "stuff",
            "many", "really", "basically", "actually", "literally",
            "very", "cool", "awesome",
        }

        COMMON_MISSPELLINGS = {
            "becuase": "because",
            "teh": "the",
            "enviroment": "environment",
            "educashun": "education",
            "recieve": "receive",
            "seperate": "separate",
            "definately": "definitely",
            "wierd": "weird",
            "goverment": "government",
        }

        def generate_feedback_summary(self, text):
            """
            Calls AIService to generate educational feedback summary.
            Returns: {"feedback": str, "strengths": str, "weaknesses": str}
            """
            try:
                # Endpoint name must match FastAPI exactly
                if self.ENABLE_AI_FEEDBACK:
                    result = AIService.generate_feedback_summary(text)
                    return result
                else:
                    return {"feedback": "AI feedback unavailable. Please review your essay for clarity, structure, and relevance.", "strengths": "", "weaknesses": ""}
            except Exception as e:
                logger.warning({"ai_feedback_failed": str(e)})
                return {
                    "feedback": "AI feedback unavailable. Please review your essay for clarity, structure, and relevance.",
                    "strengths": "",
                    "weaknesses": ""
                }
        """
        Production-ready deterministic essay scoring engine.

        PURPOSE:
        - Lightweight MVP scoring
        - Stable deterministic scoring
        - Fast execution
        - Educational feedback
        - Pre-AI baseline scorer
        """





        # ==========================================================
        # HELPERS
        # ==========================================================

        def normalize_words(self, text):
            words = split_words(text)

            cleaned = []

            for word in words:
                word = re.sub(r"[^a-zA-Z']", "", word)
                word = word.lower().strip("'")

                if not word:
                    continue

                cleaned.append(word)

            return cleaned

        def estimate_syllables(self, word):
            word = re.sub(r"[^a-z]", "", word.lower())

            if not word:
                return 1

            special_cases = {
                "education": 4,
                "teacher": 2,
                "technology": 4,
                "learning": 2,
                "artificial": 4,
                "intelligence": 4,
                "students": 2,
                "automation": 4,
            }

            if word in special_cases:
                return special_cases[word]

            vowels = "aeiouy"

            syllables = 0
            prev_vowel = False

            for char in word:
                is_vowel = char in vowels

                if is_vowel and not prev_vowel:
                    syllables += 1

                prev_vowel = is_vowel

            if word.endswith("e") and syllables > 1:
                syllables -= 1

            if word.endswith("le") and len(word) > 2:
                syllables += 1

            return max(1, syllables)

        def sentence_openings(self, sentences):
            openings = []

            for sentence in sentences:
                parts = sentence.strip().split()

                if parts:
                    openings.append(parts[0].lower())

            return openings

        # ==========================================================
        # GRAMMAR
        # ==========================================================

        def analyze_grammar(self, text):
            sentences = split_sentences(text)

            if not sentences:
                return {
                    "score": 0,
                    "issues": ["No sentences detected."],
                    "issue_count": 1,
                    "suggestions": ["Write complete sentences."],
                }

            penalties = 0
            issues = []

            openings = self.sentence_openings(sentences)

            repeated_openings = Counter(openings)

            for sentence in sentences:
                s = sentence.strip()

                if not s:
                    continue

                words = s.split()

                if not s[0].isupper():
                    penalties += 1
                    issues.append("Sentence should begin with capital letter.")

                if not re.search(r"[.!?]$", s):
                    penalties += 1
                    issues.append("Sentence missing ending punctuation.")

                if re.search(r"([.!?,])\1+", s):
                    penalties += 1
                    issues.append("Repeated punctuation detected.")

                if len(words) > 45:
                    penalties += 1.5
                    issues.append("Possible run-on sentence.")

                if len(words) < 4:
                    penalties += 0.5
                    issues.append("Very short sentence.")

            for opening, count in repeated_openings.items():
                if count >= 3:
                    penalties += count * 0.5

            sentence_count = max(1, len(sentences))

            penalty_ratio = penalties / sentence_count

            score = 100 - (penalty_ratio * 45)

            score = max(10, min(96, score))

            return {
                "score": round(score, 2),
                "issues": issues[:10],
                "issue_count": len(issues),
                "suggestions": [
                    "Vary sentence structures naturally."
                ],
            }

        # ==========================================================
        # SPELLING
        # ==========================================================

        def analyze_spelling(self, text):
            words = self.normalize_words(text)

            if not words:
                return {
                    "score": 0,
                    "misspelled_words": [],
                    "issue_count": 0,
                    "suggestions": ["Add meaningful content."],
                }

            misspelled = []

            for word in words:
                if len(word) <= 2:
                    continue

                if word in self.COMMON_MISSPELLINGS:
                    misspelled.append(word)

                if re.search(r"(.)\1\1", word):
                    misspelled.append(word)

            unique_misspelled = list(set(misspelled))

            error_ratio = len(unique_misspelled) / max(1, len(words))

            score = 100 - (error_ratio * 350)

            score = max(20, min(100, score))

            return {
                "score": round(score, 2),
                "misspelled_words": unique_misspelled[:10],
                "issue_count": len(unique_misspelled),
                "suggestions": [
                    "Review uncommon spellings carefully."
                ],
            }

        # ==========================================================
        # PUNCTUATION
        # ==========================================================

        def analyze_punctuation(self, text):
            sentences = split_sentences(text)

            penalties = 0
            issues = []

            for sentence in sentences:
                s = sentence.strip()

                if not re.search(r"[.!?]$", s):
                    penalties += 1
                    issues.append("Missing ending punctuation.")

                if re.search(r"([.!?,])\1+", s):
                    penalties += 1
                    issues.append("Repeated punctuation.")

                if re.search(r"[.!?,][A-Za-z]", s):
                    penalties += 0.5
                    issues.append("Missing space after punctuation.")

            sentence_count = max(1, len(sentences))

            score = 100 - ((penalties / sentence_count) * 35)

            score = max(15, min(97, score))

            return {
                "score": round(score, 2),
                "issues": issues[:10],
                "issue_count": len(issues),
                "suggestions": [
                    "Maintain punctuation consistency."
                ],
            }

        # ==========================================================
        # READABILITY
        # ==========================================================

        def analyze_readability(self, text):
            sentences = split_sentences(text)
            words = self.normalize_words(text)

            sentence_count = max(1, len(sentences))
            word_count = max(1, len(words))

            syllable_count = sum(
                self.estimate_syllables(word)
                for word in words
            )

            avg_sentence_length = word_count / sentence_count
            avg_syllables_per_word = syllable_count / word_count

            flesch = (
                206.835
                - 1.015 * avg_sentence_length
                - 65 * avg_syllables_per_word
            )

            readability_score = max(0, min(100, flesch))

            if readability_score >= 90:
                level = "Very Easy"
            elif readability_score >= 80:
                level = "Easy"
            elif readability_score >= 70:
                level = "Fairly Easy"
            elif readability_score >= 60:
                level = "Standard"
            elif readability_score >= 50:
                level = "Fairly Difficult"
            elif readability_score >= 30:
                level = "Difficult"
            else:
                level = "Very Difficult"

            logger.debug({
                "readability": {
                    "words": word_count,
                    "sentences": sentence_count,
                    "syllables": syllable_count,
                    "flesch": flesch,
                }
            })

            return {
                "score": round(readability_score, 2),
                "avg_sentence_length": round(avg_sentence_length, 2),
                "avg_word_length": round(
                    sum(len(w) for w in words) / word_count,
                    2,
                ),
                "readability_level": level,
                "suggestions": [
                    "Use clear sentence flow and balanced wording."
                ],
            }

        # ==========================================================
        # VOCABULARY
        # ==========================================================

        def analyze_vocabulary(self, text, topic=None):
                words = self.normalize_words(text)
                # Academic vocabulary bonus
                academic_count = sum(1 for word in words if word in self.ACADEMIC_WORDS)
                academic_bonus = min(15, academic_count * 1.5)
                if not words:
                    return {
                        "score": 0,
                        "lexical_diversity": 0,
                        "repeated_words": [],
                        "ai_notes": "",
                        "suggestions": ["Add richer vocabulary."],
                    }

                total_words = len(words)
                unique_words = set(words)
                lexical_diversity = len(unique_words) / max(1, total_words)

                # Ignore topic keywords in repetition penalty
                topic_keyword_set = set()
                if topic and getattr(topic, "semantic_keywords", None):
                    topic_keyword_set = set(self.normalize_words(topic.semantic_keywords))

                counts = Counter(words)
                repeated_words = [
                    word
                    for word, count in counts.items()
                    if count >= 5 and len(word) > 3 and word not in topic_keyword_set
                ]

                filler_count = sum(
                    1 for word in words
                    if word in self.FILLER_WORDS
                )

                # Advanced vocabulary bonus
                advanced_words = [word for word in unique_words if len(word) > 8]
                advanced_ratio = len(advanced_words) / max(1, total_words)
                advanced_bonus = min(10, advanced_ratio * 100)

                diversity_score = 60 + (lexical_diversity * 40)
                repetition_penalty = len(repeated_words) * 4
                filler_penalty = filler_count * 0.5

                ai_score = 65.0
                ai_notes = ""
                if self.ENABLE_AI_VOCAB:
                    ai_vocab = self.analyze_vocabulary_sophistication(text)
                    ai_score = ai_vocab.get("score", 65.0)
                    ai_notes = ai_vocab.get("notes", "")

                base_score = diversity_score - repetition_penalty - filler_penalty + advanced_bonus + academic_bonus
                score = (0.6 * base_score) + (0.4 * ai_score)
                score = max(15, min(95, score))

                suggestions = ["Use varied and precise vocabulary."]
                if ai_notes:
                    suggestions.append(ai_notes)

                return {
                    "score": round(score, 2),
                    "lexical_diversity": round(lexical_diversity, 2),
                    "repeated_words": repeated_words[:10],
                    "advanced_bonus": round(advanced_bonus, 2),
                    "ai_notes": ai_notes,
                    "suggestions": suggestions,
                }

            # ==========================================================
            # STRUCTURE
            # ==========================================================

        def analyze_structure(self, text, topic=None):
            paragraphs = split_paragraphs(text)
            penalties = 0
            issues = []
            n_paragraphs = len(paragraphs)
            if n_paragraphs < 3:
                penalties += 3
                issues.append("Essay needs stronger paragraph structure.")

            # Introduction detection
            has_intro = n_paragraphs > 0 and len(paragraphs[0].split()) >= 40
            if not has_intro:
                penalties += 1
                issues.append("Missing or weak introduction.")

            # Conclusion detection
            has_conclusion = False
            if n_paragraphs > 0:
                last_para = paragraphs[-1].lower()
                has_conclusion = any(
                    phrase in last_para
                    for phrase in [
                        "in conclusion",
                        "to conclude",
                        "overall",
                        "in summary",
                    ]
                )
            if not has_conclusion:
                penalties += 1
                issues.append("Missing or weak conclusion.")

            # Paragraph balance
            para_lengths = [len(p.split()) for p in paragraphs]
            if para_lengths and (max(para_lengths) - min(para_lengths) > 100):
                penalties += 1
                issues.append("Paragraphs are imbalanced in length.")

            # Paragraph richness (average length)
            avg_paragraph_length = sum(para_lengths) / max(1, n_paragraphs)
            if avg_paragraph_length < 45:
                penalties += 2
                issues.append("Paragraphs are underdeveloped.")

            # Paragraph variance
            if para_lengths and (max(para_lengths) > 2 * (sum(para_lengths) / max(1, n_paragraphs))):
                penalties += 1
                issues.append("One paragraph is much longer than others.")

            # Paragraph uniqueness ratio (semantic progression)
            paragraph_keyword_sets = [set(self.normalize_words(p)) for p in paragraphs]
            overlap_scores = []
            for i in range(1, len(paragraph_keyword_sets)):
                overlap = len(paragraph_keyword_sets[i] & paragraph_keyword_sets[i-1]) / max(1, len(paragraph_keyword_sets[i-1] | paragraph_keyword_sets[i]))
                overlap_scores.append(overlap)
            if overlap_scores and sum(overlap_scores)/len(overlap_scores) > 0.7:
                penalties += 1
                issues.append("Paragraphs are too repetitive; weak progression.")

            # Sentence complexity penalty (shallow reasoning)
            all_sentences = []
            for p in paragraphs:
                all_sentences.extend(split_sentences(p))
            avg_sentence_length = sum(len(s.split()) for s in all_sentences) / max(1, len(all_sentences))
            if avg_sentence_length < 10:
                penalties += 1
                issues.append("Sentences are too simple; weak analysis.")

            # Transition density
            transition_hits = 0
            for paragraph in paragraphs:
                lowered = paragraph.lower()
                for transition in self.TRANSITION_WORDS:
                    if transition in lowered:
                        transition_hits += 1
                        break
            if transition_hits < n_paragraphs // 2:
                penalties += 1
                issues.append("Insufficient transitions between paragraphs.")

            base_score = 100 - (penalties * 6)
            base_score = max(20, min(95, base_score))

            # Coherence bonus
            coherence_bonus = 0
            if has_intro and has_conclusion and avg_paragraph_length >= 45 and transition_hits >= n_paragraphs // 2:
                coherence_bonus = 5
            base_score += coherence_bonus

            strengths = []
            weaknesses = []
            ai_score = 70.0
            if self.ENABLE_AI_STRUCTURE:
                ai_struct = self.analyze_structure_coherence(text)
                ai_score = ai_struct.get("score", 70.0)
                strengths = ai_struct.get("strengths", [])
                weaknesses = ai_struct.get("weaknesses", [])

            # Blend: 60% deterministic, 40% AI
            score = (0.6 * base_score) + (0.4 * ai_score)
            score = max(20, min(95, score))

            suggestions = ["Organize ideas with smoother transitions."]
            if strengths:
                suggestions.append("Strengths: " + "; ".join(strengths[:2]))
            if weaknesses:
                suggestions.append("Weaknesses: " + "; ".join(weaknesses[:2]))

            return {
                "score": round(score, 2),
                "paragraph_count": n_paragraphs,
                "avg_paragraph_length": round(avg_paragraph_length, 2),
                "coherence_bonus": coherence_bonus,
                "strengths": strengths,
                "weaknesses": weaknesses,
                "issues": issues[:10],
                "suggestions": suggestions,
            }


    # ==========================================================
    # RELEVANCE
    # ==========================================================
        def analyze_relevance(self, content, topic):
            # Use pre-generated semantic keywords from topic
            topic_keywords = getattr(topic, "semantic_keywords", None) or []

            # Safe fallback if no keywords
            if not topic_keywords:
                return {
                    "score": 50.0,
                    "matched_keywords": [],
                    "topic_keywords": [],
                    "coverage_ratio": 0.0,
                }

            # Step 5: Normalize essay words
            essay_words = self.normalize_words(content)
            essay_text = " ".join(essay_words)

            # Step 6: Semantic overlap matching (phrase first, then partial)
            matched_keywords = []
            for keyword in topic_keywords:
                keyword_lower = keyword.lower().strip()
                if keyword_lower in essay_text:
                    matched_keywords.append(keyword)
                else:
                    keyword_parts = keyword_lower.split()
                    if any(part in essay_words for part in keyword_parts):
                        matched_keywords.append(keyword)

            # Step 7: Coverage ratio
            coverage_ratio = (
                len(matched_keywords) / len(topic_keywords)
            ) if topic_keywords else 0.0

            # Step 8: Nonlinear score scaling and clamping
            relevance_score = (coverage_ratio ** 1.5) * 100
            if coverage_ratio < 0.2:
                relevance_score -= 50
            elif coverage_ratio < 0.4:
                relevance_score -= 30
            relevance_score = max(5, min(100, relevance_score))

            # Step 9: Logging (no essay content)
            logger.debug({
                "topic_keywords": topic_keywords,
                "matched_keywords": matched_keywords,
                "coverage_ratio": coverage_ratio,
            })

            return {
                "score": round(relevance_score, 2),
                "matched_keywords": matched_keywords[:15],
                "topic_keywords": topic_keywords[:15],
                "coverage_ratio": coverage_ratio,
            }

        # ==========================================================
        # FINAL SCORE
        # ==========================================================

        def calculate_final_score(self, scores):
            # Final professional weights
            weights = {
                "grammar": 0.08,
                "spelling": 0.03,
                "punctuation": 0.04,
                "readability": 0.05,
                "vocabulary": 0.30,
                "structure": 0.25,
                "relevance": 0.25,
            }

            total = 0
            for category, weight in weights.items():
                total += scores.get(category, 0) * weight

            # Semantic richness bonus for excellence
            if (
                scores.get("vocabulary", 0) >= 80
                and scores.get("structure", 0) >= 80
                and scores.get("relevance", 0) >= 80
            ):
                total += 5

            return round(total, 2)

        # ==========================================================
        # MAIN PIPELINE
        # ==========================================================

        def score_essay(self, attempt):
            text = attempt.content or ""

            with transaction.atomic():
                grammar = self.analyze_grammar(text)
                spelling = self.analyze_spelling(text)
                punctuation = self.analyze_punctuation(text)
                readability = self.analyze_readability(text)
                vocabulary = self.analyze_vocabulary(text)
                structure = self.analyze_structure(text)
                relevance = self.analyze_relevance(
                    text,
                    attempt.essay_topic,
                )

                # AI feedback summary (in-memory only unless model field exists)
                feedback_summary = self.generate_feedback_summary(text)

                scores = {
                    "grammar": grammar["score"],
                    "spelling": spelling["score"],
                    "punctuation": punctuation["score"],
                    "readability": readability["score"],
                    "vocabulary": vocabulary["score"],
                    "structure": structure["score"],
                    "relevance": relevance["score"],
                }

                final_score = self.calculate_final_score(scores)

                attempt.final_score = final_score
                attempt.grammar_score = scores["grammar"]
                attempt.spelling_score = scores["spelling"]
                attempt.punctuation_score = scores["punctuation"]
                attempt.readability_score = scores["readability"]
                attempt.vocabulary_score = scores["vocabulary"]
                attempt.structure_score = scores["structure"]
                attempt.relevance_score = scores["relevance"]
                attempt.grading_status = "completed"
                attempt.graded_at = timezone.now()

                attempt.save(update_fields=[
                    "final_score",
                    "grammar_score",
                    "spelling_score",
                    "punctuation_score",
                    "readability_score",
                    "vocabulary_score",
                    "structure_score",
                    "relevance_score",
                    "grading_status",
                    "graded_at",
                    "updated_at",
                ])

            logger.info({
                "essay_scored": {
                    "attempt_id": attempt.id,
                    "final_score": final_score,
                    "scores": scores,
                }
            })

