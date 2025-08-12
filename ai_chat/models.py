from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=128, default='Untitled')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'ai_chat_chatsession'  # Ensure this matches your table name

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=16)  # 'user' or 'ai' or 'system'
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_chat_chatmessage'  # Ensure this matches your table name
