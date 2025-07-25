from rest_framework.test import APITestCase
from django_tenants.test.cases import TenantTestCase
from users.models import CustomUser
from .models import Course, CertificateTemplate
from .serializers import CertificateTemplateSerializer

class CertificateTemplateViewTest(TenantTestCase):
    def setUp(self):
        self.tenant = self.setup_tenant()
        self.client = self.get_tenant_client(self.tenant)
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(title='Test Course', slug='test-course', code='TC001', description='Test')

    def test_get_template(self):
        response = self.client.get(f'/api/courses/certificates/course/{self.course.id}/template/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['is_active'], True)

    def test_patch_create_template(self):
        data = {'is_active': True, 'template': 'custom', 'custom_text': 'Test Certificate'}
        response = self.client.patch(f'/api/courses/certificates/course/{self.course.id}/template/', data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CertificateTemplate.objects.count(), 1)

    def test_patch_update_template(self):
        template = CertificateTemplate.objects.create(course=self.course, is_active=True)
        data = {'is_active': False}
        response = self.client.patch(f'/api/courses/certificates/course/{self.course.id}/template/', data, format='multipart')
        self.assertEqual(response.status_code, 200)
        template.refresh_from_db()
        self.assertFalse(template.is_active)