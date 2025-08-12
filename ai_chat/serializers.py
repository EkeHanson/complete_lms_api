from rest_framework import serializers
from .models import ChatSession, ChatMessage

# ---------------------------------------------------------------------------
#  Serializers
# ---------------------------------------------------------------------------

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "text", "timestamp"]

class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ["id", "title", "created_at", "messages"]

