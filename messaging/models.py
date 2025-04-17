# messaging/models.py
from django.db import models
from users.models import User
from groups.models import UserGroup

class Message(models.Model):
    MESSAGE_TYPES = (
        ('announcement', 'Announcement'),
        ('notification', 'Notification'),
        ('reminder', 'Reminder'),
        ('personal', 'Personal Message'),
    )
    
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('draft', 'Draft'),
    )
    
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    subject = models.CharField(max_length=200)
    content = models.TextField()
    message_type = models.CharField(
        max_length=20, 
        choices=MESSAGE_TYPES, 
        default='personal'
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='sent'
    )
    parent_message = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replies'
    )
    is_forward = models.BooleanField(default=False)

    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.sender.email}: {self.subject}"

class MessageRecipient(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    recipient = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    recipient_group = models.ForeignKey(
        UserGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='group_messages'
    )
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['message', 'recipient'], ['message', 'recipient_group']]
    
    def __str__(self):
        recipient = self.recipient.email if self.recipient else self.recipient_group.name
        return f"Recipient: {recipient} for {self.message}"

class MessageAttachment(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='message_attachments/')
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment for {self.message.subject}"