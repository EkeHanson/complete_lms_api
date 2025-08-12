import axios from 'axios';

// Dynamically set API base URL based on environment
const isLocalhost = window?.location?.hostname === 'localhost';

export const API_BASE_URL = isLocalhost
  ? 'http://127.0.0.1:9090'
  : 'https://complete-lms-api-em3w.onrender.com';
  

export const CMVP_SITE_URL = isLocalhost
  ? 'http://localhost:3000'
  : 'https://your-production-site-url.com'; // Optional: Replace with your deployed frontend URL

export const CMVP_API_URL = API_BASE_URL;

// Payment Methods Configuration
export const paymentMethods = [
  {
    name: 'Paystack',
    fields: [
      { label: 'Public Key', key: 'publicKey' },
      { label: 'Secret Key', key: 'secretKey' },
    ],
  },
  {
    name: 'Paypal',
    fields: [
      { label: 'Sandbox Client ID', key: 'sandboxClientId' },
      { label: 'Sandbox Secret Key', key: 'sandboxSecretKey' },
    ],
  },
  {
    name: 'Remita',
    fields: [
      { label: 'Public Key', key: 'publicKey' },
      { label: 'Secret Key', key: 'secretKey' },
    ],
  },
  {
    name: 'Stripe',
    fields: [
      { label: 'Publishable Key', key: 'publishableKey' },
      { label: 'Secret Key', key: 'secretKey' },
    ],
  },
  {
    name: 'Flutterwave',
    fields: [
      { label: 'Public Key', key: 'publicKey' },
      { label: 'Secret Key', key: 'secretKey' },
    ],
  },
];

// Supported Currencies
export const currencies = ['USD', 'NGN', 'EUR', 'GBP', 'KES', 'GHS'];

// Create base axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    //'Content-Type': 'application/json',
    //'Accept': 'application/json',
  },
});

// Example for axios config
const tenantId = localStorage.getItem('tenant_id');
const tenantSchema = localStorage.getItem('tenant_schema');
axios.defaults.headers.common['X-Tenant-ID'] = tenantId || '';
axios.defaults.headers.common['X-Tenant-Schema'] = tenantSchema

export const isSuperAdmin = async () => {
  try {
    const response = await api.get('/api/token/validate/');
    return response.data.user.role === 'super_admin';
  } catch (error) {
    console.error('Error checking super admin status:', error);
    return false;
  }
};

// Helper function to get CSRF token
const getCSRFToken = () => {
  const cookieValue = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
};

// In config.jsx, update the request interceptor
api.interceptors.request.use(
  (config) => {
    const accessToken = localStorage.getItem('access_token');
    const tenantId = localStorage.getItem('tenant_id');
    if (!accessToken) {
      console.warn('No access token found in localStorage');
    }
    if (!tenantId) {
      console.warn('No tenant ID found in localStorage');
    }
    if (accessToken) {
      config.headers['Authorization'] = `Bearer ${accessToken}`;
    }
    if (tenantId) {
      config.headers['X-Tenant-ID'] = tenantId;
    }
    const csrfToken = getCSRFToken();
    if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
      config.headers['X-CSRFToken'] = csrfToken;
    }
    return config;
  },
  (error) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);


// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      originalRequest.url.includes('/api/token/') ||
      originalRequest.url.includes('/api/logout/') ||
      window.location.pathname === '/login'
    ) {
      return Promise.reject(error);
    }
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }
        const refreshResponse = await api.post('/api/token/refresh/', { refresh: refreshToken });
        localStorage.setItem('access_token', refreshResponse.data.access);
        if (refreshResponse.data.refresh) {
          localStorage.setItem('refresh_token', refreshResponse.data.refresh);
        }
        return api(originalRequest);
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError.response?.data || refreshError.message);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('tenant_id');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login?session_expired=1';
        }
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (credentials) => api.post('/api/token/', credentials),
  logout: () => api.post('/api/logout/', {}, { headers: { 'X-CSRFToken': getCSRFToken() } }),
  refreshToken: () => api.post('/api/token/refresh/', { refresh: localStorage.getItem('refresh_token') }),
  getCurrentUser: () => api.get('/api/token/validate/'),
  register: (userData) => api.post('/users/api/register/', userData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  verifyToken: () => api.get('/api/token/validate/'),
  changePassword: (data) => api.post('/users/api/change-password/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  resetPassword: (email) => api.post('/users/api/reset-password/', { email }, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  confirmResetPassword: (data) => api.post('/users/api/reset-password/confirm/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
};

// User API
export const userAPI = {

    // Example: custom PATCH to a user sub-endpoint
  updateUserPassword: (id, data) => api.post(`/api/users/users/${id}/change_password/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' }
  }),
  impersonateUser: (id) => api.post(`/api/users/users/${id}/impersonate/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),

  getUsers: (params = {}) => api.get('/api/users/users/', { params }),
  getUser: (id) => api.get(`/api/users/user/${id}/`),
  uploadProfilePicture: (id, formData) => api.patch(`/api/users/user/${id}/profile_picture/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),

  getCurrentUser: (id) => api.get(id === 'me' ? '/api/users/user/me/' : `/api/users/users/${id}/`),
  createUser: (userData) => api.post('/api/users/register/', userData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  // updateUser: (id, userData) => {
  //   // If userData is FormData, don't set Content-Type (let Axios handle it)
  //   if (userData instanceof FormData) {
  //     return api.patch(`/api/users/users/${id}/`, userData, {
  //       headers: { 'X-CSRFToken': getCSRFToken() }
  //     });
  //   }
  //   // Otherwise, send as JSON
  //   return api.patch(`/api/users/users/${id}/`, userData, {
  //     headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' }
  //   });
  // },

  updateUser: (id, userData) => {
    if (userData instanceof FormData) {
      return api.patch(`/api/users/users/${id}/`, userData, {
        headers: { 'X-CSRFToken': getCSRFToken() }
        // Do NOT set Content-Type here!
      });
    }
    return api.patch(`/api/users/users/${id}/`, userData, {
      headers: {
        'X-CSRFToken': getCSRFToken(),
        'Content-Type': 'application/json'
      }
    });
  },



  deleteUser: (id) => api.delete(`/api/users/users/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  lockUser: (id) => api.post(`/api/users/users/${id}/lock/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  unlockUser: (id) => api.post(`/api/users/users/${id}/unlock/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  fetchRoleStats: (params = {}) => api.get('/api/users/users/role_stats/', { params }),
  getUserActivities: (params = {}) => api.get('/api/users/user-activities/', { params }),
  getUserStats: () => api.get('/api/users/stats/'),
  bulkUpload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/users/users/bulk_upload/', formData, {
      headers: {
        'X-CSRFToken': getCSRFToken(),
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

// Roles API
export const rolesAPI = {
  getRoles: (params = {}) => api.get('/api/groups/roles/', { params }),
  getRole: (id) => api.get(`/api/groups/roles/${id}/`),
  createRole: (data) => api.post('/api/groups/roles/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateRole: (id, data) => api.patch(`/api/groups/roles/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteRole: (id) => api.delete(`/api/groups/roles/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  setDefaultRole: (id) => api.post(`/api/groups/roles/${id}/set_default/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getRolePermissions: (id) => api.get(`/api/groups/roles/${id}/permissions/`),
  updateRolePermissions: (id, permissions) => api.put(`/api/groups/roles/${id}/permissions/`, { permissions }, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  validateRole: (data) => api.post('/api/groups/roles/validate/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
};

// In config.jsx, update the groupsAPI object
export const groupsAPI = {
  getGroups: (params = {}) => api.get('/api/groups/groups/', { params }),
  getGroup: (id) => api.get(`/api/groups/groups/${id}/`),
  createGroup: (data) => api.post('/api/groups/groups/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateGroup: (id, data) => api.patch(`/api/groups/groups/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteGroup: (id) => api.delete(`/api/groups/groups/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getGroupMembers: (groupId) => api.get(`/api/groups/groups/${groupId}/members/`),
  getGroupMembersByName: (name) => api.get(`/api/groups/groups/by-name/${name}/members/`),
  addGroupMember: (groupId, userId) => api.post(`/api/groups/groups/${groupId}/add_member/`, { user_id: userId }, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  removeGroupMember: (groupId, userId) => api.delete(`/api/groups/groups/${groupId}/members/${userId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  updateGroupMembers: (groupId, data) => {
    const numericMemberIds = (data.members || []).map(id => Number(id));
    return api.post(`/api/groups/groups/${groupId}/update_members/`, { members: numericMemberIds }, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    });
  },
};

// Activity API
export const activityAPI = {
  getActivities: (params = {}) => api.get('/api/activitylog/activity-logs/', { params }),
  getActivity: (id) => api.get(`/api/activitylog/activity-logs/${id}/`),
  getUserActivities: (userId) => api.get(`/api/activitylog/activity-logs/user-activities/${userId}/`),
};

// Messaging API
export const messagingAPI = {
  getMessages: (params = {}) => api.get('/api/messaging/messages/', { params }),
  getMessage: (id) => api.get(`/api/messaging/messages/${id}/`),
  createMessage: (data) => api.post('/api/messaging/messages/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateMessage: (id, data) => api.patch(`/api/messaging/messages/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteMessage: (id) => api.delete(`/api/messaging/messages/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),

  deleteForUser: (id) => api.patch(`/api/messaging/messages/${id}/delete_for_user/`, {}, {
  headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
}),
  markAsRead: (id) => api.patch(`/api/messaging/messages/${id}/mark_as_read/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  forwardMessage: (id, data) => api.post(`/api/messaging/messages/${id}/forward/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  replyToMessage: (id, data) => api.post(`/api/messaging/messages/${id}/reply/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getMessageTypes: () => api.get('/api/messaging/message-types/'),
  createMessageType: (data) => api.post('/api/messaging/message-types/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateMessageType: (id, data) => api.patch(`/api/messaging/message-types/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteMessageType: (id) => api.delete(`/api/messaging/message-types/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  setDefaultMessageType: (id) => api.post(`/api/messaging/message-types/${id}/set_default/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getTotalMessages: () => api.get('/api/messaging/messages/stats/'),
  getUnreadCount: () => api.get('/api/messaging/messages/unread_count/'),
  uploadAttachment: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/attachments/', formData, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
    });
  },
  deleteAttachment: (id) => api.delete(`/attachments/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
};

// Schedule API
export const scheduleAPI = {
  getSchedules: (params) => api.get('/api/schedule/schedules/all', { params }),
  getSchedule: (id) => api.get(`/schedule/api/schedules/${id}/`),
  createSchedule: (data) => api.post('/api/schedule/schedules/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateSchedule: (id, data) => api.put(`/api/schedule/schedules/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteSchedule: (id) => api.delete(`/api/schedule/schedules/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  respondToSchedule: (id, response) => api.post(`/api/schedule/schedules/${id}/respond/`, { response_status: response }, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getTotalSchedules: () => api.get('/api/schedule/schedules/stats/'),
  getUpcomingSchedules: () => api.get('/api/schedule/schedules/upcoming/'),
};

// Advert API
export const advertAPI = {
  createAdvertWithImage: (formData) => {
    return api.post('/adverts/api/adverts/', formData, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
    });
  },
  createAdvert: (advertData) => {
    return api.post('/adverts/api/adverts/', advertData, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    });
  },
  updateAdvert: (id, advertData, isFormData = false) => {
    return api.put(`/adverts/api/adverts/${id}/`, advertData, {
      headers: {
        'X-CSRFToken': getCSRFToken(),
        'Content-Type': isFormData ? 'multipart/form-data' : 'application/json',
      },
    });
  },
  deleteAdvert: (id) => api.delete(`/adverts/api/adverts/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  toggleAdvertStatus: (id, status) => api.patch(`/adverts/api/adverts/${id}/`, { status }, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getAdvertStats: () => api.get('/adverts/api/adverts/stats/'),
  getAdverts: () => api.get('/adverts/api/adverts/'),
  getTargetStats: () => api.get('/adverts/api/adverts/target_stats/'),
};

// Courses API
export const coursesAPI = {
  getCategories: (params = {}) => api.get('/api/courses/categories/', { params }),
  getCategory: (id) => api.get(`/api/courses/categories/${id}/`),
  createCategory: (data) => api.post('/api/courses/categories/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateCategory: (id, data) => api.patch(`/api/courses/categories/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteCategory: (id) => api.delete(`/api/courses/categories/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getCourses: (params = {}) => api.get('/api/courses/courses/', { params }),
  getCourse: (id) => api.get(`/api/courses/courses/${id}/`),
  createCourse: (formData) => api.post('/api/courses/courses/', formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  updateCourse: (id, formData) => api.patch(`/api/courses/courses/${id}/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  deleteCourse: (id) => api.delete(`/api/courses/courses/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  
  getMostPopularCourses: () => api.get('/api/courses/courses/most_popular/'),
  getLeastPopularCourses: () => api.get('/api/courses/courses/least_popular/'),
  getModules: (courseId, params = {}) => api.get(`/api/courses/courses/${courseId}/modules/`, { params }),
  getModule: (courseId, moduleId) => api.get(`/api/courses/courses/${courseId}/modules/${moduleId}/`),
  createModule: (courseId, data) => api.post(`/api/courses/courses/${courseId}/modules/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateModule: (courseId, moduleId, data) => api.patch(`/api/courses/courses/${courseId}/modules/${moduleId}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteModule: (courseId, moduleId) => api.delete(`/api/courses/courses/${courseId}/modules/${moduleId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getLessons: (courseId, moduleId, params = {}) => api.get(`/api/courses/courses/${courseId}/modules/${moduleId}/lessons/`, { params }),
  getLesson: (courseId, moduleId, lessonId) => api.get(`/api/courses/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/`),
  createLesson: (courseId, moduleId, formData) => api.post(`/api/courses/courses/${courseId}/modules/${moduleId}/lessons/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  updateLesson: (courseId, moduleId, lessonId, formData) => api.patch(`/api/courses/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  deleteLesson: (courseId, moduleId, lessonId) => api.delete(`/api/courses/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getResources: (courseId, params = {}) => api.get(`/api/courses/courses/${courseId}/resources/`, { params }),
  createResource: (courseId, formData) => api.post(`/api/courses/courses/${courseId}/resources/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  updateResource: (courseId, resourceId, formData) => api.patch(`/api/courses/courses/${courseId}/resources/${resourceId}/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  deleteResource: (courseId, resourceId) => api.delete(`/api/courses/courses/${courseId}/resources/${resourceId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getBadges: () => api.get('/api/courses/badges/'),
  createBadge: (formData) => api.post('/api/courses/badges/', formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  updateBadge: (id, formData) => api.patch(`/api/courses/badges/${id}/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  deleteBadge: (id) => api.delete(`/api/courses/badges/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getLeaderboard: (courseId) =>
    api.get(`/api/courses/user-points/leaderboard/${courseId ? `?course_id=${courseId}` : ''}`),
  updatePointsConfig: (courseId, config) => api.post(`/api/courses/courses/${courseId}/points-config/`, config, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  adminSingleEnroll: (courseId, data) => api.post(`/api/courses/enrollments/course/${courseId}/enroll/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  adminBulkEnrollCourse: (courseId, data) => api.post(`/api/courses/enrollments/course/${courseId}/bulk/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  adminBulkEnroll: (enrollmentsData) => api.post('/api/courses/enrollments/admin_bulk_enroll/', enrollmentsData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getAllEnrollments: () => api.get('/api/courses/enrollments/all/'),
  selfEnroll: (courseId) => api.post(`/api/courses/enrollments/self-enroll/${courseId}/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getEnrollments: (courseId = null) => {
    const url = courseId ? `/api/courses/enrollments/course/${courseId}/` : '/api/courses/enrollments/';
    return api.get(url);
  },
  getAllMyEnrollments: () => {
    const url =  `/api/courses/enrollments/my-courses/`;
    return api.get(url);
  },
  getUserEnrollments: (userId = null) => {
    console.log("User ID", userId);
    const url = userId ? `/api/courses/enrollments/user/${userId}/` : '/api/courses/enrollments/user/';
    console.log("These are the kist of my enroolled course")
    return api.get(url);
},
  getCourseEnrollmentsAdmin: (courseId) => api.get(`/api/courses/enrollments/course/${courseId}/`),
  deleteEnrollment: (id) => api.delete(`/api/courses/enrollments/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),


  // Fetch course progress for a user and course
  getCourseProgress: ({ user, course }) =>
    api.get('/api/courses/enrollments/for/user/progress/', {
      params: { user, course },
    }),

  // Create course progress record for a user and course
  createCourseProgress: ({ user, course }) =>
    api.post(
      '/api/courses/enrollments/for/user/progress/',
      { user, course },
      {
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'Content-Type': 'application/json',
        },
      }
    ),

  // Mark a lesson as completed for a user
  completeLesson: ({ user, lesson }) =>
    api.post(
      '/api/courses/enrollments/for/user/lesson-completion/',
      { user, lesson },
      {
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'Content-Type': 'application/json',
        },
      }
    ),

  // Update/recalculate course progress for a user and course
  updateCourseProgress: ({ user, course }) =>
    api.patch(
      '/api/courses/enrollments/for/user/progress/update/',
      { user, course },
      {
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'Content-Type': 'application/json',
        },
      }
    ),
  
  getRatings: (courseId = null) => {
    const url = courseId ? `/api/courses/ratings/course/${courseId}/` : '/api/courses/ratings/';
    return api.get(url);
  },
  submitRating: (courseId, data) => api.post(`/api/courses/ratings/course/${courseId}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getLearningPaths: (params = {}) => api.get('/api/courses/learning-paths/', { params }),
  getLearningPath: (id) => api.get(`/api/courses/learning-paths/${id}/`),
  createLearningPath: (data) => api.post('/api/courses/learning-paths/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateLearningPath: (id, data) => api.patch(`/api/courses/learning-paths/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteLearningPath: (id) => api.delete(`/api/courses/learning-paths/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),

  
  getCertificates: (courseId) => api.get(`/api/courses/certificates/course/${courseId}/template/`),
  createCertificate: (courseId, formData) => api.post(`/api/courses/certificates/course/${courseId}/template/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  updateCertificate: (courseId, formData) => api.patch(`/api/courses/certificates/course/${courseId}/template/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  deleteCertificate: (courseId) => api.delete(`/api/courses/certificates/course/${courseId}/template/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),

  getFAQStats: () => api.get('/api/courses/faqs/stats/'),
  getFAQs: (courseId, params = {}) => api.get(`/api/courses/courses/${courseId}/faqs/`, { params }),
  createFAQ: (courseId, data) => api.post(`/api/courses/courses/${courseId}/faqs/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateFAQ: (courseId, faqId, data) => api.patch(`/api/courses/courses/${courseId}/faqs/${faqId}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteFAQ: (courseId, faqId) => api.delete(`/api/courses/courses/${courseId}/faqs/${faqId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  reorderFAQs: (courseId, data) => api.post(`/api/courses/courses/${courseId}/faqs/reorder/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getSCORMSettings: (courseId) => api.get(`/api/courses/scorm/${courseId}/`),
  updateSCORMSettings: (courseId, formData) => api.patch(`/api/courses/scorm/${courseId}/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  uploadSCORMPackage: (courseId, formData) => api.post(`/api/courses/scorm/${courseId}/upload/`, formData, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'multipart/form-data' },
  }),
  deleteSCORMSettings: (courseId) => api.delete(`/api/courses/scorm/${courseId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  // Instructor assignment endpoints
  assignInstructor: (courseId, data) => api.post(`/api/courses/courses/${courseId}/assign_instructor/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateInstructorAssignment: (courseId, instructorId, data) => api.put(`/api/courses/courses/${courseId}/instructors/${instructorId}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteInstructorAssignment: (courseId, instructorId) =>
  api.delete(`/api/courses/courses/${courseId}/instructors/${instructorId}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),



    getAssignments: (params = {}) => api.get('/api/courses/assignments/', { params }),
    createAssignment: (data) => api.post('/api/courses/assignments/', data, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    }),
    updateAssignment: (id, data) => api.patch(`/api/courses/assignments/${id}/`, data, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    }),
    deleteAssignment: (id) => api.delete(`/api/courses/assignments/${id}/`, {
      headers: { 'X-CSRFToken': getCSRFToken() },
    }),


      submitAssignment: (formData) =>
        api.post('/api/courses/assignment-submissions/', formData, {
          headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'multipart/form-data',
          },
        }),
      getAssignmentSubmissions: (params = {}) =>
      api.get('/api/courses/assignment-submissions/', { params }),


    getFeedback: (params = {}) => api.get('/api/courses/feedback/', { params }),
    createFeedback: (data) => api.post('/api/courses/feedback/', data, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    }),


    getCart: (params = {}) => api.get('/api/courses/cart/', { params }),
    addToCart: (data) => api.post('/api/courses/cart/', data, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    }),
    removeFromCart: (id) => api.delete(`/api/courses/cart/${id}/`, {
      headers: { 'X-CSRFToken': getCSRFToken() },
    }),
    getWishlist: (params = {}) => api.get('/api/courses/wishlist/', { params }),
    addToWishlist: (data) => api.post('/api/courses/wishlist/', data, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    }),
    removeFromWishlist: (id) => api.delete(`/api/courses/wishlist/${id}/`, {
      headers: { 'X-CSRFToken': getCSRFToken() },
    }),
    getGrades: (params = {}) => api.get('/api/courses/grades/', { params }),
    getAnalytics: (params = {}) => api.get('/api/courses/analytics/', { params }),

  
};



// Payment API

export const paymentAPI = {
  getPaymentConfig: () => api.get('/api/payments/site-currency'),
  createPaymentConfig: (data) => api.post('/api/payments/site-currency', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updatePaymentConfig: (data) => api.patch('/api/payments/site-currency/update', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deletePaymentConfig: () => api.delete('/api/payments/site-currency/delete', {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getSiteConfig: () => api.get('/api/payments/site-currency'),
  createSiteConfig: (data) => api.post('/api/payments/site-currency', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateSiteConfig: (data) => api.patch('/api/payments/site-currency/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getAllGateways: () => api.get('/api/payments/payment-gateways/'),
  updateGateway: (id, data) => api.patch(`/api/payments/payment-gateways/${id}/`, data),
  updateGatewayConfig: (id, data) => api.patch(`/api/payments/payment-gateways/${id}/config/`, data),
};

// Forum API
export const forumAPI = {
  getForums: (params) => api.get('/api/forums/forums/', { params }),
  createForum: (data) => api.post('/api/forums/forums/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateForum: (id, data) => api.patch(`/api/forums/forums/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteForum: (id) => api.delete(`/api/forums/forums/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getForumStats: () => api.get('/api/forums/forums/stats/'),
};

// Moderation API
export const moderationAPI = {
  getModerationQueue: (params) => api.get('/api/forums/queue/', { params }),
  moderateItem: (id, data) => api.patch(`/api/forums/queue/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getPendingCount: () => api.get('/api/forums/queue/pending_count/'),
};

// Quality API
export const qualityAPI = {
  getQualifications: (params = {}) => api.get('/quality/api/qualifications/', { params }),
  createQualification: (data) => api.post('/quality/api/qualifications/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateQualification: (id, data) => api.patch(`/quality/api/qualifications/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteQualification: (id) => api.delete(`/quality/api/qualifications/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getAssessors: (params = {}) => api.get('/quality/api/assessors/', { params }),
  createAssessor: (data) => api.post('/quality/api/assessors/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateAssessor: (id, data) => api.patch(`/quality/api/assessors/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteAssessor: (id) => api.delete(`/quality/api/assessors/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getIQAs: (params = {}) => api.get('/quality/api/iqas/', { params }),
  createIQA: (data) => api.post('/quality/api/iqas/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateIQA: (id, data) => api.patch(`/quality/api/iqas/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteIQA: (id) => api.delete(`/quality/api/iqas/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getEQAs: (params = {}) => api.get('/quality/api/eqas/', { params }),
  createEQA: (data) => api.post('/quality/api/eqas/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateEQA: (id, data) => api.patch(`/quality/api/eqas/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteEQA: (id) => api.delete(`/quality/api/eqas/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getLearners: (params = {}) => api.get('/quality/api/learners/', { params }),
  createLearner: (data) => api.post('/quality/api/learners/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateLearner: (id, data) => api.patch(`/quality/api/learners/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteLearner: (id) => api.delete(`/quality/api/learners/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getAssessments: (params = {}) => api.get('/quality/api/assessments/', { params }),
  getAssessment: (id) => api.get(`/quality/api/assessments/${id}/`),
  createAssessment: (data) => api.post('/quality/api/assessments/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateAssessment: (id, data) => api.patch(`/quality/api/assessments/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteAssessment: (id) => api.delete(`/quality/api/assessments/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getIQASamples: (params = {}) => api.get('/quality/api/iqasamples/', { params }),
  createIQASample: (data) => api.post('/quality/api/iqasamples/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateIQASample: (id, data) => api.patch(`/quality/api/iqasamples/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteIQASample: (id) => api.delete(`/quality/api/iqasamples/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getIQASamplingPlans: (params = {}) => api.get('/quality/api/iqasamplingplans/', { params }),
  createIQASamplingPlan: (data) => api.post('/quality/api/iqasamplingplans/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateIQASamplingPlan: (id, data) => api.patch(`/quality/api/iqasamplingplans/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteIQASamplingPlan: (id) => api.delete(`/quality/api/iqasamplingplans/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getEQAVisits: (params = {}) => api.get('/quality/api/eqavisits/', { params }),
  createEQAVisit: (data) => api.post('/quality/api/eqavisits/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateEQAVisit: (id, data) => api.patch(`/quality/api/eqavisits/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteEQAVisit: (id) => api.delete(`/quality/api/eqavisits/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getEQASamples: (params = {}) => api.get('/quality/api/eqasamples/', { params }),
  createEQASample: (data) => api.post('/quality/api/eqasamples/', data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  updateEQASample: (id, data) => api.patch(`/quality/api/eqasamples/${id}/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  deleteEQASample: (id) => api.delete(`/quality/api/eqasamples/${id}/`, {
    headers: { 'X-CSRFToken': getCSRFToken() },
  }),
  getQualityDashboard: () => api.get('/quality/api/dashboard/'),
};

// Security Compliance API
export const securityComplianceAPI = {
  // Failed Logins
  getFailedLogins: (params = {}) => api.get('/api/users/failed-logins/', { params }),
  blockIP: (ip) => api.post('/api/users/blocked-ips/', {
      ip_address: ip,
      action: 'manual-block',
      reason: 'Blocked due to multiple failed login attempts'
    }, {
      headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
    }),
  getFailedLoginDetails: (id) => api.get(`/api/users/failed-logins/${id}/`),

  // Blocked IPs
  getBlockedIPs: (params = {}) => api.get('/api/users/blocked-ips/', { params }),
  unblockIP: (ip) => api.post('/api/users/blocked-ips/unblock/', { ip }, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getBlockedIPDetails: (id) => api.get(`/api/users/blocked-ips/${id}/`),

  // Audit Logs
  getAuditLogs: (params = {}) => api.get('/api/users/user-activities/', { params }),
  getAuditLogDetails: (id) => api.get(`/api/users/audit-logs/${id}/`),

  // Vulnerability Alerts
  getVulnerabilityAlerts: (params = {}) => api.get('/api/users/vulnerability-alerts/', { params }),
  resolveVulnerabilityAlert: (id) => api.patch(`/api/users/vulnerability-alerts/${id}/resolve/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  getVulnerabilityAlertDetails: (id) => api.get(`/api/users/vulnerability-alerts/${id}/`),

  // Compliance Reports
  getComplianceReports: (params = {}) => api.get('/api/users/compliance-reports/', { params }),
  generateComplianceReport: (id) => api.post(`/api/users/compliance-reports/${id}/generate/`, {}, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),
  scheduleComplianceAudit: (id, data) => api.post(`/api/users/compliance-reports/${id}/schedule-audit/`, data, {
    headers: { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' },
  }),

  // Recent Security Events
  getRecentSecurityEvents: (params = {}) => api.get('/api/users/recent-events/', { params }),

  // Dashboard Statistics
  getSecurityDashboardStats: () => api.get('/api/users/dashboard/stats/'),
};

// Utility functions
// Utility functions
export const setAuthTokens = (accessToken, refreshToken, tenantId) => {
  localStorage.setItem('access_token', accessToken);
  if (refreshToken) localStorage.setItem('refresh_token', refreshToken);
  if (tenantId) localStorage.setItem('tenant_id', tenantId);
};

export const clearAuthTokens = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('tenant_id');
};

export const getAuthHeader = () => {
  const token = localStorage.getItem('access_token');
  const tenantId = localStorage.getItem('tenant_id');
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(tenantId ? { 'X-Tenant-ID': tenantId } : {}),
  };
};

export const instructorAPI = {
  // Fetch instructor dashboard data for the logged-in instructor
  getDashboardData: () =>
    api.get('/api/courses/instructors/me/', {
      headers: {
        'X-CSRFToken': getCSRFToken(),
        'Content-Type': 'application/json',
      },
    }),
  // ...add other instructor API methods here as needed...
};


export default {
  API_BASE_URL,
  CMVP_SITE_URL,
  CMVP_API_URL,
  paymentMethods,
  currencies,
  api,
  userAPI,
  authAPI,
  rolesAPI,
  groupsAPI,
  activityAPI,
  messagingAPI,
  scheduleAPI,
  advertAPI,
  coursesAPI,
  paymentAPI,
  forumAPI,
  moderationAPI,
  qualityAPI,
  securityComplianceAPI,
  instructorAPI,
  setAuthTokens,
  clearAuthTokens,
  getAuthHeader,
};



