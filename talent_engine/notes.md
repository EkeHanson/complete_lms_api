To develop the Django REST Framework (DRF) app for the recruitment module (`recruitment` app) with a focus on the job requisition feature, I’ll create a complete Django app that integrates with your existing multi-tenant setup using `django-tenants`, supports your ReactJS frontend (`RecruitmentHome`, `CreateRequisition`, `VewRequisition`, etc.), and aligns with the subscription-based access model where tenants and their users (admin and others) can access subscribed modules like recruitment. The app will handle job requisitions, including creation, viewing, updating, deletion, and listing, with proper permissions and tenant isolation.

### Requirements
Based on your application and the provided React components, the `recruitment` app should:
1. **Models**:
   - `JobRequisition`: Store job requisition details (e.g., title, status, requested_by, role, reason, etc.).
   - Link to `CustomUser` (from `users` app) for `requested_by` and `tenant` (from `core` app).
   - Support fields for qualification, experience, knowledge requirements, and reason for requisition (as in `CreateRequisition`).

2. **Permissions**:
   - Only authenticated users within a tenant can access the recruitment module if the tenant is subscribed.
   - Admin users can create, update, delete, and view requisitions.
   - Non-admin users can view requisitions but cannot create, update, or delete.

3. **API Endpoints**:
   - `POST /api/recruitment/requisitions/`: Create a job requisition.
   - `GET /api/recruitment/requisitions/`: List all requisitions for the tenant.
   - `GET /api/recruitment/requisitions/{id}/`: Retrieve a specific requisition.
   - `PUT /api/recruitment/requisitions/{id}/`: Update a requisition (admin only).
   - `DELETE /api/recruitment/requisitions/{id}/`: Delete a requisition (admin only).
   - `POST /api/recruitment/requisitions/bulk-delete/`: Delete multiple requisitions (admin only).

4. **Integration**:
   - Use `django-tenants` for schema isolation.
   - Integrate with `CustomUser` and `Tenant` models.
   - Support JWT authentication via `rest_framework_simplejwt`.
   - Align with the frontend’s data structure (e.g., `RecruitmentHome` expects `id`, `title`, `status`, etc.).
   - Handle pagination, filtering, and searching as shown in `RecruitmentHome`.

5. **Subscription Logic**:
   - Check if the tenant is subscribed to the `recruitment` module before granting access.
   - Use a `Subscription` model to manage tenant subscriptions.

6. **Frontend Compatibility**:
   - Replace mock data in `generateMockJobs` with API calls to fetch requisitions.
   - Support `CreateRequisition` form submission.
   - Ensure `VewRequisition` displays requisition details from the API.

---

### Implementation

#### Step 1: Create the Recruitment App
Run:
```bash
python manage.py startapp recruitment
```

Add to `INSTALLED_APPS` in `settings.py`:

```python
# lumina_care/settings.py (partial)
INSTALLED_APPS = [
    'corsheaders',
    'django_tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'allauth.socialaccount.providers.microsoft',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'core',
    'users',
    'talent_engine',
    'compliance',
    'training',
    'care_coordination',
    'workforce',
    'analytics',
    'integrations',
    'recruitment',  # Added
]

# Add to TENANT_APPS
TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'users',
    'recruitment',  # Added
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

---

#### Step 2: Create Models
Define the `JobRequisition` model and a `Subscription` model to manage module access.

```python
# apps/recruitment/models.py
from django.db import models
from users.models import CustomUser
from core.models import Tenant
import uuid

class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='subscriptions')
    module = models.CharField(max_length=50, choices=[('recruitment', 'Recruitment'), ('compliance', 'Compliance'), ('training', 'Training')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'module')
        db_table = 'recruitment_subscription'

    def __str__(self):
        return f"{self.tenant.name} - {self.module}"

class JobRequisition(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
    ]

    ROLE_CHOICES = [
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='requisitions')
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='requisitions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    qualification_requirement = models.TextField()
    experience_requirement = models.TextField()
    knowledge_requirement = models.TextField()
    reason = models.TextField()
    requested_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recruitment_job_requisition'

    def __str__(self):
        return f"{self.title} ({self.tenant.schema_name})"
```

**Details**:
- `Subscription`: Tracks tenant subscriptions to modules. Stored in the `public` schema (shared).
- `JobRequisition`: Stores requisition details, linked to `Tenant` and `CustomUser`. Stored in tenant schemas.
- UUID primary keys for uniqueness across tenants.
- Fields align with `CreateRequisition` (title, qualification, experience, knowledge, reason).

---

#### Step 3: Create Serializers
Define serializers for `JobRequisition` to handle API input/output.

```python
# apps/recruitment/serializers.py
from rest_framework import serializers
from .models import JobRequisition
from users.models import CustomUser
from core.models import Tenant

class JobRequisitionSerializer(serializers.ModelSerializer):
    requested_by = serializers.SlugRelatedField(
        slug_field='email',
        queryset=CustomUser.objects.all(),
        required=False
    )
    tenant = serializers.SlugRelatedField(
        slug_field='schema_name',
        queryset=Tenant.objects.all(),
        read_only=True
    )

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'tenant', 'title', 'status', 'requested_by', 'role',
            'qualification_requirement', 'experience_requirement',
            'knowledge_requirement', 'reason', 'requested_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'requested_date', 'created_at', 'updated_at']

    def validate(self, data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            data['requested_by'] = request.user
        return data
```

**Details**:
- Serializes `JobRequisition` fields.
- Uses `email` for `requested_by` and `schema_name` for `tenant`.
- Automatically sets `requested_by` to the authenticated user.
- Makes `id`, `tenant`, and timestamps read-only.

---

#### Step 4: Create Permissions
Define a custom permission to check tenant subscription and user role.

```python
# apps/recruitment/permissions.py
from rest_framework import permissions
from .models import Subscription
from core.models import Tenant
import logging

logger = logging.getLogger('recruitment')

class IsSubscribedAndAuthorized(permissions.BasePermission):
    def has_permission(self, request, view):
        try:
            tenant = request.tenant
            if not isinstance(tenant, Tenant):
                logger.error("No tenant associated with request")
                return False

            # Check if tenant is subscribed to recruitment module
            if not Subscription.objects.filter(tenant=tenant, module='recruitment', is_active=True).exists():
                logger.warning(f"Tenant {tenant.schema_name} is not subscribed to recruitment module")
                return False

            # Allow safe methods (GET, HEAD, OPTIONS) for all authenticated users
            if request.method in permissions.SAFE_METHODS:
                return request.user.is_authenticated

            # For non-safe methods (POST, PUT, DELETE), require admin role
            return request.user.is_authenticated and request.user.role == 'admin'
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False
```

**Details**:
- Checks if the tenant is subscribed to the `recruitment` module.
- Allows `GET` for all authenticated users in the tenant.
- Restricts `POST`, `PUT`, `DELETE` to users with `role='admin'`.

---

#### Step 5: Create Views
Define DRF views for job requisition CRUD operations.

```python
# apps/recruitment/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import JobRequisition
from .serializers import JobRequisitionSerializer
from .permissions import IsSubscribedAndAuthorized
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
import logging

logger = logging.getLogger('recruitment')

class JobRequisitionListCreateView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role']

    def get_queryset(self):
        return JobRequisition.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
        logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {self.request.tenant.schema_name}")

class JobRequisitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    lookup_field = 'id'

    def get_queryset(self):
        return JobRequisition.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Job requisition updated: {serializer.instance.title} for tenant {self.request.tenant.schema_name}")

    def perform_destroy(self, instance):
        logger.info(f"Job requisition deleted: {instance.title} for tenant {self.request.tenant.schema_name}")
        instance.delete()

class JobRequisitionBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            requisitions = JobRequisition.objects.filter(tenant=request.tenant, id__in=ids)
            count = requisitions.count()
            if count == 0:
                logger.warning("No requisitions found for provided IDs")
                return Response({"detail": "No requisitions found."}, status=status.HTTP_404_NOT_FOUND)

            requisitions.delete()
            logger.info(f"Bulk deleted {count} job requisitions for tenant {request.tenant.schema_name}")
            return Response({"detail": f"Deleted {count} requisition(s)."}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Bulk delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

**Details**:
- `JobRequisitionListCreateView`: Lists and creates requisitions with filtering and searching.
- `JobRequisitionDetailView`: Handles retrieve, update, and delete for a single requisition.
- `JobRequisitionBulkDeleteView`: Deletes multiple requisitions by IDs.
- Uses `IsSubscribedAndAuthorized` to enforce subscription and role checks.
- Filters by tenant to ensure schema isolation.

---

#### Step 6: Create URLs
Define API endpoints for the recruitment app.

```python
# apps/recruitment/urls.py
from django.urls import path
from .views import JobRequisitionListCreateView, JobRequisitionDetailView, JobRequisitionBulkDeleteView

urlpatterns = [
    path('requisitions/', JobRequisitionListCreateView.as_view(), name='requisition-list-create'),
    path('requisitions/<uuid:id>/', JobRequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/bulk-delete/', JobRequisitionBulkDeleteView.as_view(), name='requisition-bulk-delete'),
]
```

Update `lumina_care/urls.py`:

```python
# lumina_care/urls.py
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/tenants/', include('core.urls')),
    path('api/users/', include('users.urls')),
    path('api/recruitment/', include('recruitment.urls')),  # Added
    path('api/token/', include('rest_framework_simplejwt.urls')),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('accounts/', include('allauth.urls')),
]
```

---

#### Step 7: Create Migrations
Generate and apply migrations for the `recruitment` app.

```python
# apps/recruitment/migrations/0001_initial.py
from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('core', '0001_initial'),  # Adjust based on actual core migrations
        ('users', '0001_initial'),  # Adjust based on actual users migrations
    ]
    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('module', models.CharField(choices=[('recruitment', 'Recruitment'), ('compliance', 'Compliance'), ('training', 'Training')], max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=models.CASCADE, related_name='subscriptions', to='core.tenant')),
            ],
            options={
                'db_table': 'recruitment_subscription',
                'unique_together': {('tenant', 'module')},
            },
        ),
        migrations.CreateModel(
            name='JobRequisition',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('open', 'Open'), ('pending', 'Pending'), ('closed', 'Closed'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('role', models.CharField(choices=[('staff', 'Staff'), ('admin', 'Admin')], default='staff', max_length=20)),
                ('qualification_requirement', models.TextField()),
                ('experience_requirement', models.TextField()),
                ('knowledge_requirement', models.TextField()),
                ('reason', models.TextField()),
                ('requested_date', models.DateField(auto_now_add=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('requested_by', models.ForeignKey(null=True, on_delete=models.SET_NULL, related_name='requisitions', to='users.customuser')),
                ('tenant', models.ForeignKey(on_delete=models.CASCADE, related_name='requisitions', to='core.tenant')),
            ],
            options={
                'db_table': 'recruitment_job_requisition',
            },
        ),
    ]
```

Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate_schemas --shared  # For Subscription model
python manage.py migrate_schemas  # For JobRequisition model
```

---

#### Step 8: Update Frontend (`RecruitmentHome`)
Replace mock data with API calls using Axios.

```javascript
import React, { useState, useEffect, useRef } from 'react';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import CreateRequisition from './CreateRequisition';
import VewRequisition from './VewRequisition';
import {
  LockOpenIcon,
  XMarkIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  ClipboardDocumentListIcon,
  FolderOpenIcon,
  ClockIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
  EyeIcon,
  TrashIcon,
  AdjustmentsHorizontalIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import CountUp from 'react-countup';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import config from '../../config';

// Register Chart.js components
ChartJS.register(ArcElement, Tooltip, Legend);

const Backdrop = ({ onClick }) => (
  <motion.div
    className="fixed inset-0 bg-black bg-opacity-50 z-40"
    onClick={onClick}
    initial={{ opacity: 0 }}
    animate={{ opacity: 0.5 }}
    exit={{ opacity: 0 }}
  />
);

const Modal = ({ title, message, onConfirm, onCancel, confirmText = 'Confirm', cancelText = 'Cancel' }) => (
  <AnimatePresence>
    <Backdrop onClick={onCancel} />
    <motion.div
      className="fixed top-1/2 left-1/2 z-50 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-md bg-white p-6 shadow-lg"
      variants={{ hidden: { opacity: 0, scale: 0.75 }, visible: { opacity: 1, scale: 1 }, exit: { opacity: 0, scale: 0.75 } }}
      initial="hidden"
      animate="visible"
      exit="exit"
      role="dialog"
      aria-modal="true"
    >
      <h3 className="mb-4 text-lg font-semibold">{title}</h3>
      <p className="mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="rounded bg-gray-300 px-4 py-2 font-semibold hover:bg-gray-400"
        >
          {cancelText}
        </button>
        <button
          onClick={onConfirm}
          className="rounded bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700"
          autoFocus
        >
          {confirmText}
        </button>
      </div>
    </motion.div>
  </AnimatePresence>
);

const AlertModal = ({ title, message, onClose }) => (
  <AnimatePresence>
    <Backdrop onClick={onClose} />
    <motion.div
      className="fixed top-1/2 left-1/2 z-50 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-md bg-white p-6 shadow-lg"
      variants={{ hidden: { opacity: 0, scale: 0.75 }, visible: { opacity: 1, scale: 1 }, exit: { opacity: 0, scale: 0.75 } }}
      initial="hidden"
      animate="visible"
      exit="exit"
      role="alertdialog"
      aria-modal="true"
    >
      <h3 className="mb-4 text-lg font-semibold">{title}</h3>
      <p className="mb-6">{message}</p>
      <div className="flex justify-end">
        <button
          onClick={onClose}
          className="rounded bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700"
          autoFocus
        >
          OK
        </button>
      </div>
    </motion.div>
  </AnimatePresence>
);

const renderPieChart = (jobData) => {
  const counts = {
    Open: jobData.filter(job => job.status === 'open').length,
    Pending: jobData.filter(job => job.status === 'pending').length,
    Closed: jobData.filter(job => job.status === 'closed').length
  };

  const total = counts.Open + counts.Pending + counts.Closed;

  const percentages = {
    Open: total ? Math.round((counts.Open / total) * 100) : 0,
    Pending: total ? Math.round((counts.Pending / total) * 100) : 0,
    Closed: total ? Math.round((counts.Closed / total) * 100) : 0
  };

  const data = {
    labels: ['Open', 'Pending', 'Closed'],
    datasets: [
      {
        data: [percentages.Open, percentages.Pending, percentages.Closed],
        backgroundColor: [
          'rgba(75, 192, 192, 0.8)',  // Open
          'rgba(255, 206, 86, 0.8)',  // Pending
          'rgba(255, 99, 132, 0.8)',  // Closed
        ],
        borderColor: [
          'rgba(75, 192, 192, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(255, 99, 132, 1)',
        ],
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          font: {
            size: 9,
            family: "'Poppins', 'sans-serif'"
          },
          padding: 20,
        }
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const label = context.label || '';
            const value = context.raw || 0;
            return `${label}: ${value}% (${counts[label]})`;
          }
        }
      }
    },
    cutout: '50%',
    animation: {
      animateRotate: true,
      animateScale: true,
      duration: 1000,
    }
  };

  return (
    <div className="chart-wrapper">
      <div className="chart-container">
        <Pie data={data} options={options} />
      </div>
      <div className="chart-summary">
        <div className="summary-item">
          <div className="summary-color"><LockOpenIcon /> <span style={{ backgroundColor: 'rgba(75, 192, 192, 0.8)' }}></span></div>
          <div className="summary-text">{counts.Open} ({percentages.Open}%)</div>
        </div>
        <div className="summary-item">
          <div className="summary-color"><ClockIcon /> <span style={{ backgroundColor: 'rgba(255, 206, 86, 0.8)' }}></span></div>
          <div className="summary-text">{counts.Pending} ({percentages.Pending}%)</div>
        </div>
        <div className="summary-item">
          <div className="summary-color"><XMarkIcon /> <span style={{ backgroundColor: 'rgba(255, 99, 132, 0.8)' }}></span></div>
          <div className="summary-text">{counts.Closed} ({percentages.Closed}%)</div>
        </div>
      </div>
    </div>
  );
};

const RecruitmentHome = () => {
  const [trigger, setTrigger] = useState(0);
  const [lastUpdateTime, setLastUpdateTime] = useState(new Date());
  const [jobData, setJobData] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [showRequisition, setShowRequisition] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [roleFilter, setRoleFilter] = useState('All');
  const [isVisible, setIsVisible] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [showNoSelectionAlert, setShowNoSelectionAlert] = useState(false);
  const [showViewRequisition, setShowViewRequisition] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [totalJobs, setTotalJobs] = useState(0);
  const [openJobs, setOpenJobs] = useState(0);
  const [pendingJobs, setPendingJobs] = useState(0);
  const [closedJobs, setClosedJobs] = useState(0);

  const statuses = ['All', 'open', 'pending', 'closed', 'rejected'];
  const roles = ['All', 'staff', 'admin'];

  const fetchJobs = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.get(`${config.API_BASE_URL}/api/recruitment/requisitions/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        params: {
          page: currentPage,
          page_size: rowsPerPage,
          search: searchTerm || undefined,
          status: statusFilter !== 'All' ? statusFilter : undefined,
          role: roleFilter !== 'All' ? roleFilter : undefined,
        },
      });
      setJobData(response.data.results);
      setTotalJobs(response.data.count);
      setOpenJobs(response.data.results.filter(job => job.status === 'open').length);
      setPendingJobs(response.data.results.filter(job => job.status === 'pending').length);
      setClosedJobs(response.data.results.filter(job => job.status === 'closed').length);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => {
      setTrigger((prev) => prev + 1);
      setLastUpdateTime(new Date());
    }, 50000);
    return () => clearInterval(interval);
  }, [currentPage, rowsPerPage, searchTerm, statusFilter, roleFilter, trigger]);

  const handleCheckboxChange = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSelectAllVisible = () => {
    const allVisibleIds = jobData.map((job) => job.id);
    const areAllVisibleSelected = allVisibleIds.every((id) => selectedIds.includes(id));
    if (areAllVisibleSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allVisibleIds.includes(id)));
    } else {
      setSelectedIds((prev) => [...new Set([...prev, ...allVisibleIds])]);
    }
  };

  const handleDeleteMarked = async () => {
    if (selectedIds.length === 0) {
      setShowNoSelectionAlert(true);
      return;
    }
    setShowConfirmDelete(true);
  };

  const confirmDelete = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      await axios.post(`${config.API_BASE_URL}/api/recruitment/requisitions/bulk-delete/`, { ids: selectedIds }, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      setSelectedIds([]);
      fetchJobs();
      setShowConfirmDelete(false);
    } catch (error) {
      console.error('Error deleting requisitions:', error);
    }
  };

  const toggleSection = () => {
    setIsVisible(prev => !prev);
  };

  const handleViewClick = (job) => {
    setSelectedJob(job);
    setShowViewRequisition(true);
  };

  const handleCloseViewRequisition = () => {
    setShowViewRequisition(false);
    setSelectedJob(null);
  };

  const masterCheckboxRef = useRef(null);

  useEffect(() => {
    const allVisibleSelected = jobData.every((job) => selectedIds.includes(job.id));
    const someSelected = jobData.some((job) => selectedIds.includes(job.id));
    if (masterCheckboxRef.current) {
      masterCheckboxRef.current.indeterminate = !allVisibleSelected && someSelected;
    }
  }, [selectedIds, jobData]);

  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
  };

  const totalPages = Math.ceil(totalJobs / rowsPerPage);

  return (
    <div className="YUa-Opal-sec">
      <div className="YUa-Opal-Part-1">
        <div className="glo-Top-Cards">
          {[
            { icon: ClipboardDocumentListIcon, label: 'Total Job Requisitions', value: totalJobs },
            { icon: FolderOpenIcon, label: 'Open Requisitions', value: openJobs },
            { icon: ClockIcon, label: 'Pending Approvals', value: pendingJobs },
            { icon: CheckCircleIcon, label: 'Closed Requisitions', value: closedJobs },
          ].map((item, idx) => (
            <div key={idx} className={`glo-Top-Card card-${idx + 1} Gen-Boxshadow`}>
              <div className="ffl-TOp">
                <span><item.icon /></span>
                <p>{item.label}</p>
              </div>
              <h3>
                <ArrowTrendingUpIcon />
                <CountUp key={trigger + `-${idx}`} end={item.value} duration={2} />{' '}
                <span className='ai-check-span'>Last checked - {formatTime(lastUpdateTime)}</span>
              </h3>
              <h5>
                Last Update <span>6/9/2025</span>
              </h5>
            </div>
          ))}
        </div>

        <div className='Dash-OO-Boas Gen-Boxshadow'>
          <div className='Dash-OO-Boas-Top'>
            <div className='Dash-OO-Boas-Top-1'>
              <span onClick={toggleSection}><AdjustmentsHorizontalIcon /></span>
              <h3>Job Requisitions</h3>
            </div>
            <div className='Dash-OO-Boas-Top-2'>
              <div className='genn-Drop-Search'>
                <span><MagnifyingGlassIcon /></span>
                <input 
                  type='text' 
                  placeholder='Search requisitions...' 
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
          </div>
          <AnimatePresence>
            {isVisible && (
              <motion.div className="filter-dropdowns"
                initial={{ height: 0, opacity: 0, overflow: "hidden" }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3 }}>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="filter-select"
                >
                  {statuses.map(status => (
                    <option key={status} value={status}>
                      {status === 'All' ? 'All Statuses' : status.charAt(0).toUpperCase() + status.slice(1)}
                    </option>
                  ))}
                </select>
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="filter-select"
                >
                  {roles.map(role => (
                    <option key={role} value={role}>
                      {role === 'All' ? 'All Roles' : role.charAt(0).toUpperCase() + role.slice(1)}
                    </option>
                  ))}
                </select>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="table-container">
            <table className="Gen-Sys-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      ref={masterCheckboxRef}
                      onChange={handleSelectAllVisible}
                      checked={jobData.length > 0 && jobData.every((job) => selectedIds.includes(job.id))}
                    />
                  </th>
                  <th>Request ID</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Request Date</th>
                  <th>Requested By</th>
                  <th>Role</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobData.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '20px', fontStyle: 'italic' }}>
                      No matching job requisitions found
                    </td>
                  </tr>
                ) : (
                  jobData.map((job) => (
                    <tr key={job.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(job.id)}
                          onChange={() => handleCheckboxChange(job.id)}
                        />
                      </td>
                      <td>{job.id}</td>
                      <td>{job.title}</td>
                      <td>
                        <span className={`status ${job.status.toLowerCase()}`}>
                          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                        </span>
                      </td>
                      <td>{job.requested_date}</td>
                      <td>{job.requested_by}</td>
                      <td>
                        <span className={`role ${job.role.toLowerCase()}`}>
                          {job.role.charAt(0).toUpperCase() + job.role.slice(1)}
                        </span>
                      </td>
                      <td>
                        <div className="gen-td-btns">
                          <button 
                            className="view-btn"
                            onClick={() => handleViewClick(job)}
                          >
                            <EyeIcon className="w-4 h-4" /> View
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {jobData.length > 0 && (
            <div className="pagination-controls">
              <div className='Dash-OO-Boas-foot'>
                <div className='Dash-OO-Boas-foot-1'>
                  <div className="items-per-page">
                    <p>Number of rows:</p>
                    <select
                      className="form-select"
                      value={rowsPerPage}
                      onChange={(e) => setRowsPerPage(Number(e.target.value))}
                    >
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={50}>50</option>
                    </select>
                  </div>
                </div>

                <div className='Dash-OO-Boas-foot-2'>
                  <button onClick={handleSelectAllVisible} className='mark-all-btn'>
                    <CheckCircleIcon className='h-6 w-6' />
                    {jobData.every((job) => selectedIds.includes(job.id)) ? 'Unmark All' : 'Mark All'}
                  </button>
                  <button onClick={handleDeleteMarked} className='delete-marked-btn'>
                    <TrashIcon className='h-6 w-6' />
                    Delete Marked
                  </button>
                </div>
              </div>

              <div className="page-navigation">
                <span className="page-info">
                  Page {currentPage} of {totalPages}
                </span>
                <div className="page-navigation-Btns">
                  <button
                    className="page-button"
                    onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeftIcon className="h-5 w-5" />
                  </button>
                  <button
                    className="page-button"
                    onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                    disabled={currentPage === totalPages}
                  >
                    <ChevronRightIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {showConfirmDelete && (
          <Modal
            title="Confirm Delete"
            message={`Are you sure you want to delete ${selectedIds.length} marked requisition(s)? This action cannot be undone.`}
            onConfirm={confirmDelete}
            onCancel={() => setShowConfirmDelete(false)}
            confirmText="Delete"
            cancelText="Cancel"
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showNoSelectionAlert && (
          <AlertModal
            title="No Selection"
            message="You have not selected any requisitions to delete."
            onClose={() => setShowNoSelectionAlert(false)}
          />
        )}
      </AnimatePresence>

      <div className='YUa-Opal-Part-2'>
        <div className='Top-GHY-s'>
          <button onClick={() => setShowRequisition(true)} className='btn-primary-bg'><PlusIcon /> Create Job Requisition</button>
          <p>Last Created <span>2025-06-02 ✦ 9:21 AM</span></p>
        </div>

        <div className="chart-container">
          {renderPieChart(jobData)}
        </div>
      </div>

      <AnimatePresence>
        {showRequisition && (
          <CreateRequisition onClose={() => { setShowRequisition(false); fetchJobs(); }} />
        )}
      </AnimatePresence>

      {showViewRequisition && (
        <VewRequisition job={selectedJob} onClose={handleCloseViewRequisition} />
      )}
    </div>
  );
};

export default RecruitmentHome;
```

**Changes**:
- Replaced `generateMockJobs` with `fetchJobs` using Axios.
- Added state for `totalJobs`, `openJobs`, `pendingJobs`, `closedJobs`.
- Updated `handleDeleteMarked` and `confirmDelete` to call the bulk delete endpoint.
- Refreshed data after creating a requisition in `CreateRequisition`.

---

#### Step 9: Update `CreateRequisition`
Integrate the form with the API.

```javascript
import React, { useState, useRef, useEffect } from 'react';
import { MicrophoneIcon as MicOutline } from '@heroicons/react/24/outline';
import { MicrophoneIcon as MicSolid } from '@heroicons/react/24/solid';
import { PaperAirplaneIcon, InformationCircleIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import config from '../../config';

const MAX_HEIGHT = 150;
const MAX_WORDS = 1000;

const CreateRequisition = ({ onClose }) => {
  const [title, setTitle] = useState('');
  const [qualification, setQualification] = useState('');
  const [experience, setExperience] = useState('');
  const [knowledge, setKnowledge] = useState('');
  const [text, setText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [focusedInput, setFocusedInput] = useState(null);

  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);
  const timerRef = useRef(null);

  const handleSendRequest = async () => {
    if (!title.trim()) {
      setErrorMessage("Job title is required.");
      return;
    }
    if (!qualification.trim()) {
      setErrorMessage("Qualification requirement is required.");
      return;
    }
    if (!experience.trim()) {
      setErrorMessage("Experience requirement is required.");
      return;
    }
    if (!knowledge.trim()) {
      setErrorMessage("Knowledge requirement is required.");
      return;
    }
    if (!text.trim()) {
      setErrorMessage("Please enter something before sending the request.");
      return;
    }

    setErrorMessage('');
    setIsSending(true);

    try {
      const token = localStorage.getItem('accessToken');
      await axios.post(`${config.API_BASE_URL}/api/recruitment/requisitions/`, {
        title,
        qualification_requirement: qualification,
        experience_requirement: experience,
        knowledge_requirement: knowledge,
        reason: text,
        role: 'staff',  // Default role
      }, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      setIsSending(false);
      setShowSuccess(true);

      setTimeout(() => {
        setShowSuccess(false);
        onClose();
      }, 1000);
    } catch (error) {
      setIsSending(false);
      setErrorMessage(error.response?.data?.detail || 'Failed to create requisition.');
    }
  };

  const handleChange = (e, setter) => {
    const value = e.target.value;
    const words = value.trim().split(/\s+/);
    if (words.length > MAX_WORDS) return;
    setter(value);
  };

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, MAX_HEIGHT);
      textarea.style.height = `${newHeight}px`;
      textarea.style.overflowY = newHeight >= MAX_HEIGHT ? 'auto' : 'hidden';
    }
  }, [text]);

  const formatTime = (seconds) => {
    const m = String(Math.floor(seconds / 60)).padStart(2, '0');
    const s = String(seconds % 60).padStart(2, '0');
    return `${m}:${s}`;
  };

  const toggleRecording = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      setErrorMessage('Your browser does not support Speech Recognition');
      return;
    }

    setErrorMessage('');

    if (isRecording) {
      recognitionRef.current?.stop();
      clearInterval(timerRef.current);
      setIsRecording(false);
    } else {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.continuous = false;

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (focusedInput === 'title') {
          setTitle((prev) => {
            const newText = prev ? `${prev} ${transcript}` : transcript;
            const words = newText.trim().split(/\s+/);
            return words.length <= MAX_WORDS ? newText : prev;
          });
        } else if (focusedInput === 'qualification') {
          setQualification((prev) => {
            const newText = prev ? `${prev} ${transcript}` : transcript;
            const words = newText.trim().split(/\s+/);
            return words.length <= MAX_WORDS ? newText : prev;
          });
        } else if (focusedInput === 'experience') {
          setExperience((prev) => {
            const newText = prev ? `${prev} ${transcript}` : transcript;
            const words = newText.trim().split(/\s+/);
            return words.length <= MAX_WORDS ? newText : prev;
          });
        } else if (focusedInput === 'knowledge') {
          setKnowledge((prev) => {
            const newText = prev ? `${prev} ${transcript}` : transcript;
            const words = newText.trim().split(/\s+/);
            return words.length <= MAX_WORDS ? newText : prev;
          });
        } else {
          setText((prev) => {
            const newText = prev ? `${prev} ${transcript}` : transcript;
            const words = newText.trim().split(/\s+/);
            return words.length <= MAX_WORDS ? newText : prev;
          });
        }
      };

      recognition.onerror = (e) => {
        console.error('Recognition error:', e);
        clearInterval(timerRef.current);
        setIsRecording(false);
        setErrorMessage('Speech recognition error occurred.');
      };

      recognition.onend = () => {
        clearInterval(timerRef.current);
        setIsRecording(false);
      };

      recognition.start();
      recognitionRef.current = recognition;
      setIsRecording(true);
      setRecordingTime(0);

      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    }
  };

  return (
    <motion.div
      className='CreateRequisition'
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className='CreateRequisition-Bodddy' onClick={onClose}></div>

      <motion.div
        className='CreateRequisition-box Gen-Boxshadow'
        initial={{ y: 25, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <div className='CreateRequisition-box-Top'>
          <h3>Create Job Requisition</h3>
          <button onClick={onClose}><XMarkIcon /></button>
        </div>

        <div className='CreateRequisition-box-SubTop'>
          <p>Use the microphone icon to record your reason. Your voice will be transcribed into text automatically.</p>
        </div>

        <div className='CreateRequisition-box-Mid'>
          <input
            type='text'
            placeholder='Job Title'
            value={title}
            onChange={(e) => handleChange(e, setTitle)}
            onFocus={() => setFocusedInput('title')}
            onBlur={() => setFocusedInput(null)}
            className={errorMessage.includes('title') ? 'input-error' : ''}
          />
          <input
            type='text'
            placeholder='Qualification requirement'
            value={qualification}
            onChange={(e) => handleChange(e, setQualification)}
            onFocus={() => setFocusedInput('qualification')}
            onBlur={() => setFocusedInput(null)}
            className={errorMessage.includes('Qualification') ? 'input-error' : ''}
          />
          <input
            type='text'
            placeholder='Experience requirement'
            value={experience}
            onChange={(e) => handleChange(e, setExperience)}
            onFocus={() => setFocusedInput('experience')}
            onBlur={() => setFocusedInput(null)}
            className={errorMessage.includes('Experience') ? 'input-error' : ''}
          />
          <input
            type='text'
            placeholder='Knowledge requirement'
            value={knowledge}
            onChange={(e) => handleChange(e, setKnowledge)}
            onFocus={() => setFocusedInput('knowledge')}
            onBlur={() => setFocusedInput(null)}
            className={errorMessage.includes('Knowledge') ? 'input-error' : ''}
          />
          <textarea
            ref={textareaRef}
            placeholder='Reason for request'
            value={text}
            onChange={(e) => handleChange(e, setText)}
            onFocus={() => setFocusedInput('text')}
            onBlur={() => setFocusedInput(null)}
            style={{ maxHeight: MAX_HEIGHT, resize: 'none' }}
            className='custom-scroll-bar'
          />
          {errorMessage && (
            <p className='erro-message-Txt'>{errorMessage}</p>
          )}
        </div>

        <div className='CreateRequisition-box-Foot'>
          <div className='CreateRequisition-box-Foot-1'>
            <p><InformationCircleIcon /> Not more than 1000 words ({text.trim().split(/\s+/).filter(Boolean).length} used)</p>
          </div>

          <div className='CreateRequisition-box-Foot-2'>
            {isRecording && (
              <span className='rec-Timer'>
                {formatTime(recordingTime)}
              </span>
            )}
            <button
              onClick={toggleRecording}
              className={`mic-button ${isRecording ? 'recording' : ''}`}
              aria-label={isRecording ? "Stop Recording" : "Start Recording"}
            >
              {isRecording ? <MicSolid className="animate-pulse text-red-600" /> : <MicOutline />}
            </button>

            <button
              onClick={handleSendRequest}
              className='creat-oo-btn btn-primary-bg flex items-center justify-center gap-2'
              disabled={isSending}
              aria-live="polite"
            >
              {isSending ? (
                <div className='rreq-PPja'>
                  <motion.div
                    initial={{ rotate: 0 }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    style={{
                      width: 15,
                      height: 15,
                      borderRadius: '50%',
                      border: '3px solid #fff',
                      borderTopColor: 'transparent',
                    }}
                  />
                  <p>Sending..</p>
                </div>
              ) : (
                <>
                  Send Request
                </>
              )}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {showSuccess && (
            <motion.div
              className="success-alert"
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
              style={{
                position: 'fixed',
                top: 10,
                right: 10,
                backgroundColor: '#38a169',
                color: 'white',
                padding: '10px 20px',
                fontSize: '12px',
                borderRadius: '6px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                zIndex: 9999,
              }}
            >
              Request sent successfully!
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
};

export default CreateRequisition;
```

**Changes**:
- Replaced mock submission with a POST request to `/api/recruitment/requisitions/`.
- Mapped form fields to API fields.
- Refreshed parent list by calling `onClose` (which triggers `fetchJobs`).

---

#### Step 10: Update `VewRequisition`
Update to display API-fetched requisition details.

```javascript
import React from 'react';
import { motion } from 'framer-motion';
import {
  XMarkIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

const VewRequisition = ({ job, onClose }) => {
  return (
    <div className="VewRequisition">
      <div className="VewRequisition-Bodddy" onClick={onClose}></div>
      <button className="VewRequisition-btn" onClick={onClose}>
        <XMarkIcon />
      </button>
      <motion.div 
        initial={{ opacity: 0, x: 50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
        className="VewRequisition-Main JobDell-gab"
      >
        <div className="VewRequisition-Part">
          <div className="VewRequisition-Part-Top">
            <h3>Job Requisition Details</h3>
            <button className="close-preview-btn" onClick={onClose}>
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>

          <div className="job-preview-container">
            <div className="main-Prevs-Sec custom-scroll-bar">
              <div className="preview-section-All">
                <div className="preview-section">
                  <h3>Basic Information</h3>
                  <p><span>Request ID:</span> {job.id}</p>
                  <p><span>Job Title:</span> {job.title}</p>
                  <p><span>Status:</span> <span className={`status ${job.status.toLowerCase()}`}>{job.status.charAt(0).toUpperCase() + job.status.slice(1)}</span></p>
                  <p><span>Request Date:</span> {job.requested_date}</p>
                  <p><span>Requested By:</span> {job.requested_by}</p>
                  <p><span>Role:</span> {job.role.charAt(0).toUpperCase() + job.role.slice(1)}</p>
                </div>

                <div className="preview-section">
                  <h3>Requirements</h3>
                  <p><span>Qualification:</span> {job.qualification_requirement}</p>
                  <p><span>Experience:</span> {job.experience_requirement}</p>
                  <p><span>Knowledge/Skills:</span> {job.knowledge_requirement}</p>
                </div>

                <div className="preview-section">
                  <h3>Reason for Requisition</h3>
                  <p>{job.reason}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default VewRequisition;
```

**Changes**:
- Updated to display `JobRequisition` fields from the API.
- Removed irrelevant fields (e.g., advert banner) to focus on requisition details.
- Formatted status and role for display.

---

#### Step 11: Create a Subscription
Create a subscription for the tenant to enable access:

```python
from core.models import Tenant
from apps.recruitment.models import Subscription
tenant = Tenant.objects.get(schema_name='test_tenant')
Subscription.objects.create(tenant=tenant, module='recruitment', is_active=True)
```

---

#### Step 12: Test the API
1. **Create a Requisition**:
   ```bash
   curl -X POST http://127.0.0.1:9090/api/recruitment/requisitions/ \
     -H "Authorization: Bearer your_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Frontend Developer",
       "qualification_requirement": "Bachelor’s degree",
       "experience_requirement": "3+ years",
       "knowledge_requirement": "React, JavaScript",
       "reason": "Team expansion",
       "role": "staff"
     }'
   ```

2. **List Requisitions**:
   ```bash
   curl -X GET http://127.0.0.1:9090/api/recruitment/requisitions/?search=Frontend&status=open \
     -H "Authorization: Bearer your_jwt_token"
   ```

3. **Delete Requisitions**:
   ```bash
   curl -X POST http://127.0.0.1:9090/api/recruitment/requisitions/bulk-delete/ \
     -H "Authorization: Bearer your_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"ids": ["uuid-1", "uuid-2"]}'
   ```

---

#### Step 13: Notes
- **Job Advert (`JobDetails`, `EditRequisition`)**: These components seem related to job advertisements, which are distinct from requisitions. If you want to extend the `recruitment` app to include job adverts, please confirm, and I can add models (e.g., `JobAdvertisement`), serializers, views, and endpoints for creating/editing adverts, integrating with `EditRequisition`’s fields (job description, responsibilities, documents, compliance).
- **Speech Recognition**: The `CreateRequisition` speech feature is retained but requires browser support. Ensure HTTPS in production for secure WebRTC.
- **Pagination**: The backend uses DRF pagination, matching the frontend’s `rowsPerPage`.
- **Security**: Only admins can create/delete requisitions, enforced by `IsSubscribedAndAuthorized`.
- **Logging**: Added logging for auditing and debugging.

If you need the job advert feature or additional functionality (e.g., approval workflows, file uploads for advert banners), let me know, and I’ll extend the solution! For issues, share logs or errors, and I’ll assist promptly.