# serializers.py
from rest_framework import serializers
from .models import Advert
from users.models import UserActivity
import logging
logger = logging.getLogger(__name__)
from django.http import QueryDict
from datetime import datetime


class AdvertSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True, allow_empty_file=True)

    creator = serializers.StringRelatedField()
    
    class Meta:
        model = Advert
        fields = [
            'id', 'title', 'content', 'link', 'image', 'start_date', 'end_date',
            'status', 'priority', 'target', 'creator', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'start_date': {'required': True},
            'end_date': {'required': True},
        }
    
    def validate(self, data):
        logger.debug(f"Validation data: {data}")
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        return data
    
    def to_internal_value(self, data):
        logger.debug(f"Raw incoming data: {data}")
        # Handle both form data and JSON data
        if isinstance(data, QueryDict):  # form data
            data = data.dict()
        
        # Convert date strings to datetime objects if needed
        if 'start_date' in data and isinstance(data['start_date'], str):
            try:
                data['start_date'] = datetime.fromisoformat(data['start_date'])
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing start_date: {e}")
                pass
                
        if 'end_date' in data and isinstance(data['end_date'], str):
            try:
                data['end_date'] = datetime.fromisoformat(data['end_date'])
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing end_date: {e}")
                pass
                
        logger.debug(f"Processed data before super(): {data}")
        result = super().to_internal_value(data)
        logger.debug(f"Result from super().to_internal_value(): {result}")
        return result
