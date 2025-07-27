from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, ModuleListView, TenantConfigView, BranchListCreateView, BranchDetailView

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('modules/', ModuleListView.as_view(), name='module_list'),
    path('config/', TenantConfigView.as_view(), name='tenant_config'),
    path('branches/', BranchListCreateView.as_view(), name='branch-list-create'),
    path('branches/<int:id>/', BranchDetailView.as_view(), name='branch-detail'),
    path('tenants/create_with_domains/', TenantViewSet.as_view({'post': 'create_with_domains'}), name='tenant-create-with-domains'),
]