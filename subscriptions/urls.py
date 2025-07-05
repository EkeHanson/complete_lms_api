# apps/subscriptions/urls.py
from django.urls import path
from .views import SubscriptionListCreateView, SubscriptionDetailView

urlpatterns = [
    path('', SubscriptionListCreateView.as_view(), name='subscription-list-create'),
    path('<uuid:id>/', SubscriptionDetailView.as_view(), name='subscription-detail'),
]