from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from groups.models import Group
from django.db.models import Q
from .models import Message, MessageRecipient, MessageAttachment, MessageType
from .serializers import (MessageSerializer, MessageAttachmentSerializer,MessageTypeSerializer,
    # ForwardMessageSerializer, ReplyMessageSerializer
)
from users.models import UserActivity

class MessageTypeViewSet(viewsets.ModelViewSet):
    queryset = MessageType.objects.all()
    serializer_class = MessageTypeSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):

       
        serializer.save()
    
    def perform_update(self, serializer):
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        message_type = self.get_object()
        # Logic to set as default message type
        return Response({'status': 'default set'})

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
        
    def get_queryset(self):
        user = self.request.user
        print("Checking recipient groups for user:", user)

        queryset = Message.objects.filter(
            Q(sender=user) | 
            Q(recipients__recipient=user) |
            Q(recipients__recipient_group__memberships__user=user)  # Corrected line
        ).distinct().order_by('-sent_at')

        # Rest of your filtering logic remains the same
        message_type = self.request.query_params.get('type', None)
        status_filter = self.request.query_params.get('status', None)
        search = self.request.query_params.get('search', None)
        read_status = self.request.query_params.get('read_status', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if message_type and message_type != 'all':
            queryset = queryset.filter(message_type=message_type)
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search) |
                Q(content__icontains=search) |
                Q(sender__email__icontains=search) |
                Q(sender__first_name__icontains=search) |
                Q(sender__last_name__icontains=search)
            )
        if read_status and read_status != 'all':
            if read_status == 'read':
                queryset = queryset.filter(
                    recipients__read=True,
                    recipients__recipient=user
                )
            else:
                queryset = queryset.filter(
                    Q(recipients__read=False) &
                    (Q(recipients__recipient=user) | 
                    Q(recipients__recipient_group__memberships__user=user))  # Corrected line
                )
        if date_from:
            queryset = queryset.filter(sent_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(sent_at__lte=date_to)
            
        return queryset
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        user = request.user
        count = MessageRecipient.objects.filter(
            Q(read=False) & (
                Q(recipient=user) |
                Q(recipient_group__memberships__user=user)
            )
        ).distinct().count()
        
        return Response({'count': count}, status=status.HTTP_200_OK)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

        # print(self.request.data)
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='message_sent',
            details=f'{self.request.user} Sent message {self.request.data["subject"]}',
            status='success'
        )
    
    @action(detail=True, methods=['post'])
    def forward(self, request, pk=None):
        message = self.get_object()
        serializer = ForwardMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            forwarded_msg = Message.objects.create(
                sender=request.user,
                subject=serializer.validated_data['subject'],
                content=serializer.validated_data['content'],
                message_type=message.message_type,
                parent_message=message,
                is_forward=True
            )
            
            # Add recipients
            for user in serializer.validated_data['recipient_users']:
                MessageRecipient.objects.create(
                    message=forwarded_msg,
                    recipient=user
                )
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='message_forwarded',
                    details=f'Forwarded message "{message.subject}" to {user.email}',
                    status='success'
                )
            
            for group in serializer.validated_data.get('recipient_groups', []):
                MessageRecipient.objects.create(
                    message=forwarded_msg,
                    recipient_group=group
                )
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='message_forwarded',
                    details=f'Forwarded message "{message.subject}" to group {group.name}',
                    status='success'
                )
            
            # Copy attachments
            for attachment in message.attachments.all():
                MessageAttachment.objects.create(
                    message=forwarded_msg,
                    file=attachment.file,
                    original_filename=attachment.original_filename
                )
            
            return Response(
                self.get_serializer(forwarded_msg).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        message = self.get_object()
        serializer = ReplyMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            reply_msg = Message.objects.create(
                sender=request.user,
                subject=f"Re: {message.subject}",
                content=serializer.validated_data['content'],
                message_type='personal',
                parent_message=message
            )
            
            # Add original sender as recipient
            MessageRecipient.objects.create(
                message=reply_msg,
                recipient=message.sender
            )
                        # Log reply activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='message_replied',
                details=f'Replied to message "{message.subject}"',
                status='success'
            )
            
            return Response(
                self.get_serializer(reply_msg).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def mark_as_read(self, request, pk=None):
        message = self.get_object()
        user = request.user
        
        # Mark as read for individual recipients
        recipient = message.recipients.filter(recipient=user).first()
        if recipient:
            recipient.read = True
            if not recipient.read_at:
                recipient.read_at = timezone.now()
            recipient.save()
        
        # Mark as read for group recipients
        group_recipients = message.recipients.filter(
            recipient_group__memberships__user=user  # Corrected line
        )
        for recipient in group_recipients:
            recipient.read = True
            if not recipient.read_at:
                recipient.read_at = timezone.now()
            recipient.save()

        UserActivity.objects.create(
            user=user,
            activity_type='message_read',
            details=f'Marked message "{message.subject}" as read',
            status='success'
        )
        
        
        return Response(
            {'status': 'message marked as read'},
            status=status.HTTP_200_OK
        )

class MessageAttachmentViewSet(viewsets.ModelViewSet):
    queryset = MessageAttachment.objects.all()
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        serializer.save(
            original_filename=file.name,
            uploaded_by=self.request.user
        )