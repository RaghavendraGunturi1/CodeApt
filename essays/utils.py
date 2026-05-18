def detect_suspicious_activity(analytics, attempt):
	reasons = []
	suspicious = False
	risk = 0
	# Heuristics
	total_events = analytics.typing_events + analytics.paste_events + analytics.copy_events + analytics.delete_events
	paste_ratio = analytics.paste_events / (analytics.typing_events + 1)
	if paste_ratio > 0.5 and analytics.paste_events > 3:
		suspicious = True
		reasons.append("High paste ratio")
		risk += 0.3
	if analytics.longest_pause_seconds > 120:
		suspicious = True
		reasons.append("Long inactivity detected")
		risk += 0.2
	if analytics.focus_loss_count > 5:
		suspicious = True
		reasons.append("Excessive focus loss")
		risk += 0.2
	if analytics.typing_events < 10 and attempt.word_count > 100:
		suspicious = True
		reasons.append("Low typing, high word count")
		risk += 0.3
	# Abnormal word growth
	if analytics.paste_events > 0 and attempt.word_count > 0:
		avg_words_per_paste = attempt.word_count / (analytics.paste_events or 1)
		if avg_words_per_paste > 50:
			suspicious = True
			reasons.append("Abnormal word growth per paste")
			risk += 0.2
	risk_score = min(1.0, risk)
	return {
		"suspicious": suspicious,
		"risk_score": round(risk_score * 100, 2),
		"reasons": reasons
	}
import re
def split_sentences(text):
	if not text:
		return []
	# Split on . ! ? followed by space or end
	return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

def split_words(text):
	if not text:
		return []
	# Split on word boundaries
	return re.findall(r'\b\w+\b', text)

def split_paragraphs(text):
	if not text:
		return []
	# Split by blank lines
	return [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

def estimate_syllables(word):
	# Simple heuristic: count vowel groups
	word = word.lower()
	return max(1, len(re.findall(r'[aeiouy]+', word)))

import re

def calculate_word_count(text):
	if not text:
		return 0
	# Split by any whitespace, ignore empty
	return len([w for w in re.split(r'\s+', text.strip()) if w])

def calculate_character_count(text):
	if not text:
		return 0
	return len(text.strip())

def calculate_paragraph_count(text):
	if not text:
		return 0
	# Paragraphs are non-empty lines separated by blank lines
	paras = [p for p in re.split(r'\n+', text) if p.strip()]
	return len(paras)

def validate_essay_content(content, topic):
	errors = []
	warnings = []
	valid = True
	word_count = calculate_word_count(content)
	if not content or not content.strip():
		errors.append('Essay content is empty.')
		valid = False
	if word_count < topic.min_words:
		errors.append(f'Essay is below minimum word count ({word_count} < {topic.min_words}).')
		valid = False
	if word_count > topic.max_words:
		warnings.append(f'Essay exceeds maximum word count ({word_count} > {topic.max_words}).')
	return {
		"valid": valid,
		"errors": errors,
		"warnings": warnings
	}
