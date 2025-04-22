# urls.py
from rest_framework.routers import DefaultRouter
from .views import AdvertViewSet

router = DefaultRouter()
router.register(r'adverts', AdvertViewSet, basename='advert')

urlpatterns = router.urls