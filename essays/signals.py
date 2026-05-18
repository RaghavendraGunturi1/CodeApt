# essays/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import EssayTopic
from .services.ai_service import AIService
import logging

logger = logging.getLogger("essays")

@receiver(pre_save, sender=EssayTopic)
def generate_semantic_keywords(sender, instance, **kwargs):
	# Only generate if new or if title/instructions changed
	if not instance.pk:
		should_generate = True
	else:
		try:
			old = EssayTopic.objects.get(pk=instance.pk)
			should_generate = (
				old.title != instance.title or
				old.instructions != instance.instructions
			)
		except EssayTopic.DoesNotExist:
			should_generate = True

	if should_generate:
		topic_text = instance.title
		if getattr(instance, "instructions", None):
			topic_text += "\n" + instance.instructions
		try:
			keywords = AIService.extract_keywords(topic_text)
			if not isinstance(keywords, list):
				keywords = []
			instance.semantic_keywords = keywords
			logger.info({"semantic_keywords_created": True, "topic_id": getattr(instance, 'id', None)})
		except Exception as e:
			instance.semantic_keywords = []
			logger.warning({"semantic_keyword_generation_failed": str(e), "topic_id": getattr(instance, 'id', None)})
