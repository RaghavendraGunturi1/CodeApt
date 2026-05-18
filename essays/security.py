from django.utils import timezone

def validate_timer(attempt):
	if attempt.is_timed and attempt.is_time_expired():
		return False
	return True

def validate_attempt_access(user, attempt):
	return attempt.user_id == user.id

def calculate_risk_level(risk_score):
	if risk_score >= 80:
		return 'HIGH'
	elif risk_score >= 50:
		return 'MEDIUM'
	else:
		return 'LOW'
# essays/security.py
