import React, { useState, useEffect, useCallback } from 'react';
import CircularProgress from '@mui/material/CircularProgress';
import {
  AppBar, Toolbar, Typography, IconButton, Drawer, List, ListItem, ListItemIcon, ListItemText,
  Box, Avatar, Badge, Menu, MenuItem as MenuItemMUI, Chip, Divider, Fab, Snackbar, Alert, Button
} from '@mui/material';
import {
  Menu as MenuIcon, Dashboard, School, Assignment, Message, Schedule, Feedback, Logout,
  Notifications, Search, Star, Book, ShoppingCart, Help
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import {
  userAPI, coursesAPI, messagingAPI, scheduleAPI, activityAPI, paymentAPI, authAPI, getAuthHeader
} from '../../../config';
import { useAuth } from '../../../contexts/AuthContext';
import StudentOverview from './StudentOverview';
import StudentCourseList from './StudentCourseList';
import StudentAssignments from './StudentAssignments';
import StudentMessages from './StudentMessages';
import StudentSchedule from './StudentSchedule';
import StudentFeedback from './StudentFeedback';
import StudentProfile from './StudentProfile';
import StudentCartWishlist from './StudentCartWishlist';
import StudentSearch from './StudentSearch';
import StudentSupport from './StudentSupport';
import StudentGamification from './StudentGamification';
import ErrorBoundary from './ErrorBoundary';
import AITutor from './AITutor';




const fetchDashboardData = async (userId) => {
  const defaultData = {
    student: null,
    metrics: {
      enrolledCourses: 0,
      completedCourses: 0,
      assignmentsDue: 0,
      averageGrade: 0,
      learningHours: 0,
      strongestModule: 'Unknown',
      weakestModule: 'Unknown',
    },
    enrolledCourses: [],
    assignments: [],
    messages: [],
    schedules: [],
    feedbackHistory: [],
    cart: [],
    wishlist: [],
    paymentHistory: [],
    certificates: [],
    gamification: { points: 0, badges: [], leaderboardRank: 0 },
    activities: [],
    analytics: { timeSpent: { total: '0h', weekly: '0h' }, strengths: [], weaknesses: [] },
  };

  if (!userId) {
    console.warn('User ID not available, returning default data');
    return defaultData;
  }

  const headers = getAuthHeader();

  // Fetch student profile
  let student = defaultData.student;
  try {
    const profileResponse = await userAPI.getUser('me');
    student = {
      id: profileResponse.data.id || 0,
      name: `${profileResponse.data.first_name || ''} ${profileResponse.data.last_name || ''}`.trim() || 'Unknown User',
      email: profileResponse.data.email || 'No email available',
      bio: profileResponse.data.bio || 'No bio available',
      avatar: profileResponse.data.profile_picture || 'https://randomuser.me/api/portraits/men/32.jpg',
      department: profileResponse.data.department || 'Not specified',
      lastLogin: profileResponse.data.last_login || new Date().toISOString(),
      enrollmentDate: profileResponse.data.signup_date || new Date().toISOString(),
      interests: profileResponse.data.interests || [],
      learningTrack: profileResponse.data.learning_track || 'Intermediate',
      points: profileResponse.data.points || 0,
      badges: profileResponse.data.badges || [],
      language: profileResponse.data.language || 'en',
    };
  } catch (error) {
    console.warn('Error fetching student profile:', error);
  }

  // Fetch enrolled courses with full course data
  let enrolledCourses = defaultData.enrolledCourses;
  try {
    const enrollmentsResponse = await coursesAPI.getAllMyEnrollments();
    
    console.log("enrollmentsResponse")
    console.log(enrollmentsResponse.data)
    console.log("enrollmentsResponse")

    enrolledCourses = (enrollmentsResponse.data || []).map((enrollment) => ({
      id: enrollment.id || 0,
      course: {
        id: enrollment.course?.id || 0,
        title: enrollment?.title || 'Untitled Course',
        description: enrollment?.description || 'No description available',
        thumbnail: enrollment?.thumbnail || 'https://source.unsplash.com/random/300x200?course',
        category: enrollment?.category?.name || 'Uncategorized',
        resources: (enrollment?.resources || []).map((r) => ({
          id: r.id || 0,
          title: r.title || 'Untitled Resource',
          type: r.resource_type || 'Unknown',
          url: r.url || null,
          order: r.order || 0,
          file: r.file || null,
        })),
        modules: (enrollment?.modules || []).map((m) => ({
          id: m.id || 0,
          title: m.title || 'Untitled Module',
          order: m.order || 0,
          lessons: (m.lessons || []).map((l) => ({
            id: l.id || 0,
            title: l.title || 'Untitled Lesson',
            type: l.lesson_type || 'Unknown',
            duration: l.duration || 'Unknown',
            order: l.order || 0,
            is_published: l.is_published || false,
            content_url: l.content_url || null,
            content_file: l.content_file || null,
          })),
        })),
        instructors: (enrollment?.instructors || []).map((i) => ({
          id: i.id || 0,
          name: i.name || 'Unknown Instructor',
          bio: i.bio || 'No bio available',
        })),
      },
      progress: enrollment.progress || 0,
      enrolled_at: enrollment.enrolled_at || new Date().toISOString(),
      completed_at: enrollment.completed_at || null,
      assignmentsDue: enrollment.assignments_due || 0,
      price: enrollment?.price || 0,
      rating: enrollment?.rating || 0,
      bookmarked: enrollment.bookmarked || false,
    }));
  } catch (error) {
    console.warn('Error fetching enrolled courses:', error);
  }

  // Fetch user activities
  let activities = defaultData.activities;
  try {
    const activitiesResponse = await activityAPI.getUserActivities(userId);
    const activitiesData = activitiesResponse.data.results || activitiesResponse.data;
    activities = (Array.isArray(activitiesData) ? activitiesData : []).map((activity) => ({
      id: activity.id || 0,
      action: activity.details || 'No details available',
      date: activity.timestamp || new Date().toISOString(),
      course: activity.course?.title || null,
      type: activity.activity_type || 'unknown',
    }));
    //console.log('Activities response:', activitiesResponse);
  } catch (error) {
    console.warn('Error fetching user activities:', error);
  }

  // Fetch certificates
  let certificates = defaultData.certificates;
  try {
    const certificatesResponse = await coursesAPI.getCertificates();
    certificates = (certificatesResponse.data || []).map((cert) => ({
      id: cert.id || 0,
      course: cert.enrollment?.course?.title || 'Unknown Course',
      date: cert.issued_at || new Date().toISOString(),
      code: cert.certificate_code || 'N/A',
    }));
  } catch (error) {
    console.warn('Error fetching certificates:', error);
  }

  // Fetch gamification data
  let gamification = defaultData.gamification;
  try {
    const pointsResponse = await coursesAPI.getLeaderboard();
    const badgesResponse = await coursesAPI.getBadges();
    gamification = {
      points: pointsResponse.data.results?.find((entry) => entry.user_id === student?.id)?.points || 0,
      badges: badgesResponse.data?.filter((badge) => badge.user_id === student?.id).map((badge) => badge.title || 'Unknown') || [],
      leaderboardRank: pointsResponse.data.results?.find((entry) => entry.user_id === student?.id)?.rank || 15,
    };
  } catch (error) {
    console.warn('Error fetching gamification data:', error);
  }

  // Fetch messages
  let messages = defaultData.messages;
  try {
    const messagesResponse = await messagingAPI.getMessages();
    messages = (messagesResponse.data.results || []).map((msg) => ({
      id: msg.id || 0,
      sender: msg.sender?.email || 'Unknown Sender',
      content: msg.content || 'No content',
      date: msg.date || new Date().toISOString(),
      read: msg.read || false,
      important: msg.important || false,
      course: msg.course?.title || null,
    }));
  } catch (error) {
    console.warn('Error fetching messages:', error);
  }

  // Fetch schedules
  let schedules = defaultData.schedules;
  try {
    const schedulesResponse = await scheduleAPI.getSchedules();
    schedules = (schedulesResponse.data.results || []).map((schedule) => ({
      id: schedule.id || 0,
      title: schedule.title || 'Untitled Schedule',
      date: schedule.start_time || new Date().toISOString(),
      time: schedule.start_time || new Date().toISOString(),
      instructor: schedule.instructor?.name || 'TBD',
      status: schedule.response_status || 'Pending',
      course: schedule.course?.title || null,
    }));
  } catch (error) {
    console.warn('Error fetching schedules:', error);
  }

  // Fetch assignments
  let assignments = defaultData.assignments;
  try {
    const assignmentsResponse = await coursesAPI.getAssignments();
    assignments = (assignmentsResponse.data.results || []).map((assignment) => ({
      id: assignment.id || 0,
      title: assignment.title || 'Untitled Assignment',
      course: assignment.course || 'Unknown Course',
      dueDate: assignment.due_date || new Date().toISOString(),
      status: assignment.status || 'Pending',
      grade: assignment.grade || null,
      feedback: assignment.feedback || null,
      type: assignment.type || 'Unknown',
    }));
  } catch (error) {
    console.warn('Error fetching assignments:', error);
  }

  // Fetch feedback history
  let feedbackHistory = defaultData.feedbackHistory;
  try {
    const feedbackResponse = await coursesAPI.getFeedback();
    feedbackHistory = (feedbackResponse.data.results || []).map((feedback) => ({
      id: feedback.id || 0,
      course: feedback.course || 'Unknown Course',
      type: feedback.type || 'Unknown',
      content: feedback.content || 'No content',
      rating: feedback.rating || 0,
      date: feedback.created_at || new Date().toISOString(),
    }));
  } catch (error) {
    console.warn('Error fetching feedback history:', error);
  }

  // Fetch cart
  let cart = defaultData.cart;
  try {
    const cartResponse = await coursesAPI.getCart();
    cart = (cartResponse.data.results || []).map((item) => ({
      id: item.id || 0,
      course: item.course || 'Unknown Course',
      addedAt: item.added_at || new Date().toISOString(),
    }));
  } catch (error) {
    console.warn('Error fetching cart:', error);
  }

  // Fetch wishlist
  let wishlist = defaultData.wishlist;
  try {
    const wishlistResponse = await coursesAPI.getWishlist();
    wishlist = (wishlistResponse.data.results || []).map((item) => ({
      id: item.id || 0,
      course: item.course || 'Unknown Course',
      addedAt: item.added_at || new Date().toISOString(),
    }));
  } catch (error) {
    console.warn('Error fetching wishlist:', error);
  }

  // Fetch grades
  let grades = [];
  try {
    const gradesResponse = await coursesAPI.getGrades();
    grades = (gradesResponse.data.results || []).map((grade) => ({
      id: grade.id || 0,
      course: grade.course || 'Unknown Course',
      assignment: grade.assignment || 'Unknown Assignment',
      score: grade.score || 0,
      date: grade.created_at || new Date().toISOString(),
    }));
  } catch (error) {
    console.warn('Error fetching grades:', error);
  }

  // Fetch analytics
  let analytics = defaultData.analytics;
  try {
    const analyticsResponse = await coursesAPI.getAnalytics();
    analytics = (analyticsResponse.data.results || []).reduce(
      (acc, curr) => ({
        timeSpent: {
          total: `${Math.floor(curr.total_time_spent / 60) || 0}h`,
          weekly: `${Math.floor(curr.weekly_time_spent / 60) || 0}h`,
        },
        strengths: curr.strengths || acc.strengths || ['Unknown'],
        weaknesses: curr.weaknesses || acc.weaknesses || ['Unknown'],
      }),
      { timeSpent: { total: '0h', weekly: '0h' }, strengths: ['Unknown'], weaknesses: ['Unknown'] }
    );
  } catch (error) {
    console.warn('Error fetching analytics:', error);
  }

  // Fetch payment history
  let paymentHistory = defaultData.paymentHistory;
  try {
    const paymentHistoryResponse = await paymentAPI.getSiteConfig();
    paymentHistory = (paymentHistoryResponse.data.transactions || []).map((txn) => ({
      id: txn.id || 0,
      course: txn.course?.title || 'N/A',
      amount: txn.amount || 0,
      currency: txn.currency || 'USD',
      date: txn.date || new Date().toISOString(),
      paymentMethod: txn.payment_method || 'Unknown',
      status: txn.status || 'Unknown',
    }));
  } catch (error) {
    console.warn('Error fetching payment history:', error);
  }

  // Calculate metrics
  const metrics = {
    enrolledCourses: enrolledCourses.length || 0,
    completedCourses: enrolledCourses.filter((course) => course.completed_at).length || 0,
    assignmentsDue: assignments.filter((a) => a.status !== 'submitted').length || 0,
    averageGrade: grades.length > 0 ? grades.reduce((sum, g) => sum + (g.score || 0), 0) / grades.length : 0,
    learningHours: analytics.timeSpent.total ? parseInt(analytics.timeSpent.total) : 0,
    strongestModule: analytics.strengths[0] || 'Unknown',
    weakestModule: analytics.weaknesses[0] || 'Unknown',
  };

  return {
    student,
    metrics,
    enrolledCourses,
    assignments,
    messages,
    schedules,
    feedbackHistory,
    cart,
    wishlist,
    paymentHistory,
    certificates,
    gamification,
    activities,
    analytics,
  };
};



const StudentDashboard = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { user, loading: authLoading } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeSection, setActiveSection] = useState('overview');
  const [profileOpen, setProfileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState('lms');
  const [feedbackTarget, setFeedbackTarget] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCourseList, setShowCourseList] = useState(false);

  const unreadCount = Array.isArray(dashboardData?.messages) ? dashboardData.messages.filter((msg) => !msg.read).length : 0;

  const navigationItems = [
    { id: 'overview', label: 'Overview', icon: <Dashboard /> },
    { id: 'courses', label: 'My Courses', icon: <School /> },
    { id: 'assignments', label: 'Assignments', icon: <Assignment /> },
    { id: 'messages', label: 'Messages', icon: <Message /> },
    { id: 'schedule', label: 'Schedule', icon: <Schedule /> },
    { id: 'feedback', label: 'Feedback', icon: <Feedback /> },
    { id: 'cart-wishlist', label: 'Cart & Wishlist', icon: <ShoppingCart /> },
    { id: 'search', label: 'Search Courses', icon: <Search /> },
    { id: 'support', label: 'Support', icon: <Help /> },
    { id: 'gamification', label: 'Achievements', icon: <Star /> },
    { id: 'ai-tutor', label: 'AI Tutor', icon: <Book /> },
  ];

  useEffect(() => {
    const loadData = async () => {
      if (authLoading || !user) {
        return; // Wait for user to be loaded
      }
      setLoading(true);
      try {
        const data = await fetchDashboardData(user.id);
        //console.log('Dashboard data:', data); // Debugging log
        setDashboardData(data);
      } catch (err) {
        console.warn('Unexpected error in fetchDashboardData:', err);
        setDashboardData({
          student: null,
          metrics: {
            enrolledCourses: 0,
            completedCourses: 0,
            assignmentsDue: 0,
            averageGrade: 0,
            learningHours: 0,
            strongestModule: 'Unknown',
            weakestModule: 'Unknown',
          },
          enrolledCourses: [],
          assignments: [],
          messages: [],
          schedules: [],
          feedbackHistory: [],
          cart: [],
          wishlist: [],
          paymentHistory: [],
          certificates: [],
          gamification: { points: 0, badges: [], leaderboardRank: 0 },
          activities: [],
          analytics: { timeSpent: { total: '0h', weekly: '0h' }, strengths: [], weaknesses: [] },
        });
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [user, authLoading]);

  const handleFeedbackClick = (target, type) => {
    setFeedbackTarget(target || { title: 'Learning Management System' });
    setFeedbackType(type || 'lms');
    setFeedbackOpen(true);
  };

  const showSnackbar = (message, severity) => {
    setSnackbar({ open: true, message, severity });
  };

  const handleProfileOpen = () => {
    if (dashboardData?.student) {
      setProfileOpen(true);
    } else {
      showSnackbar('Profile data not loaded yet. Please wait.', 'warning');
    }
  };

  // Move these utilities **inside** the StudentDashboard component so they have access to `user` from useAuth()
  // Utility to ensure course progress is tracked when a user starts a course
  const ensureCourseProgress = async (userId, courseId) => {
    try {
      // Try to get existing progress
      const response = await coursesAPI.getCourseProgress({ user: userId, course: courseId });
      console.log('getCourseProgress response:', response); // Log response
      if (Array.isArray(response.data) && response.data.length > 0) {
        return response.data[0]; // Already exists
      }
      // If not exists, create it
      const createResponse = await coursesAPI.createCourseProgress({ user: userId, course: courseId });
      console.log('createCourseProgress response:', createResponse); // Log response
      return createResponse.data;
    } catch (err) {
      console.warn('Error ensuring course progress:', err);
      return null;
    }
  };

  // Track course progress when a course is opened
  const handleCourseOpen = useCallback(async (courseId) => {
    if (!user?.id || !courseId) return;
    console.log("Course Started: ", courseId);
    const progress = await ensureCourseProgress(user.id, courseId);
    console.log('Progress after ensureCourseProgress:', progress); // Log progress
    alert('Progress after ensureCourseProgress:'); // Log progress

    if (progress && progress.started_at) {
      showSnackbar('Course started! Your progress will now be tracked.', 'success');
    }

    const data = await fetchDashboardData(user.id);
    setDashboardData(data);
  }, [user]);

  // Utility to mark lesson as completed and update course progress
  const completeLesson = async (userId, courseId, lessonId) => {
    try {
      const completeResponse = await coursesAPI.completeLesson({ user: userId, lesson: lessonId });
      console.log('completeLesson response:', completeResponse); // Log response
      const updateResponse = await coursesAPI.updateCourseProgress({ user: userId, course: courseId });
      console.log('updateCourseProgress response:', updateResponse); // Log response
    } catch (err) {
      console.warn('Error completing lesson:', err);ensureCourseProgress
    }
  };

  // Mark lesson as completed and update progress
  const handleLessonComplete = useCallback(async (courseId, lessonId) => {
    if (!user?.id || !courseId || !lessonId) return;
    await completeLesson(user.id, courseId, lessonId);
    // Optionally, refresh dashboard data to show updated progress
    const data = await fetchDashboardData(user.id);
    setDashboardData(data);
  }, [user]);

  const renderContent = () => {
    if (loading || authLoading) {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
          <CircularProgress color="primary" size={48} thickness={4} />
          <Typography sx={{ mt: 2 }} color="text.secondary">Loading your dashboard...</Typography>
        </Box>
      );
    }
    if (!dashboardData) {
      return (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography>No data available. Please try again later.</Typography>
          <Button
            variant="contained"
            onClick={() => {
              setLoading(true);
              fetchDashboardData(user?.id).then((data) => {
                setDashboardData(data);
              }).finally(() => setLoading(false));
            }}
            sx={{ mt: 2 }}
          >
            Retry
          </Button>
        </Box>
      );
    }

    if (showCourseList) {
      return (
        <StudentCourseList
          courses={dashboardData.enrolledCourses || []}
          onBack={() => setShowCourseList(false)}
        />
      );
    }

    switch (activeSection) {
      case 'overview':
        return (
          <StudentOverview
            student={dashboardData.student}
            metrics={dashboardData.metrics}
            activities={dashboardData.activities}
            analytics={dashboardData.analytics}
            onEnrolledCoursesClick={() => setShowCourseList(true)}
          />
        );
      case 'courses':
        return (
          <>
            <StudentCourseList
              courses={dashboardData.enrolledCourses || []}
              onFeedback={handleFeedbackClick}
              onCourseOpen={handleCourseOpen}
              onLessonComplete={handleLessonComplete}
            />
            <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="h5" gutterBottom align="center">My Enrolled Courses</Typography>
              {(dashboardData?.enrolledCourses?.length > 0) ? (
                <Box sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    sm: '1fr 1fr',
                    md: '1fr 1fr 1fr'
                  },
                  gap: { xs: 2, sm: 2, md: 3 },
                  justifyContent: 'center',
                  alignItems: 'center',
                  width: '100%',
                  maxWidth: 1200,
                  mx: 'auto',
                }}>
                  {dashboardData.enrolledCourses.map((course) => {
                    const modules = course.course?.modules || [];
                    const lessons = modules.reduce((acc, m) => acc + (m.lessons?.length || 0), 0);
                    const resources = course.course?.resources?.length || 0;
                    const instructors = course.course?.instructors?.map(i => i.name).join(', ') || '';

                    // Add a handler to open the course and track progress
                    const handleOpenCourse = async () => {
                      await handleCourseOpen(course.course?.id);
                      // Optionally, navigate to course details page here
                    };

                    return (
                      <Box
                        key={course.id}
                        sx={{
                          p: { xs: 2, sm: 2, md: 2 },
                          bgcolor: '#fff',
                          borderRadius: 2,
                          boxShadow: 1,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 1,
                          minWidth: 0,
                          maxWidth: 370,
                          mx: 'auto',
                          cursor: 'pointer',
                          transition: 'box-shadow 0.2s',
                          '&:hover': { boxShadow: 3 },
                        }}
                        onClick={handleOpenCourse}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Avatar src={course.course?.thumbnail} variant="rounded" sx={{ width: 48, height: 36, mr: 1 }} />
                          <Box sx={{ minWidth: 0 }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: { xs: '1rem', md: '1.1rem' }, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{course.course?.title || 'Untitled Course'}</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontSize: { xs: '0.9rem', md: '1rem' }, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 180 }}>{course.course?.description || 'No description available'}</Typography>
                          </Box>
                          <Chip label={course.progress ? `${Math.round(course.progress)}%` : '0%'} color="primary" sx={{ ml: 'auto', fontWeight: 600, fontSize: { xs: '0.8rem', md: '0.95rem' } }} />
                        </Box>
                        <Divider sx={{ my: 1 }} />
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
                          <Chip label={`Modules: ${modules.length}`} color="info" sx={{ fontSize: { xs: '0.8rem', md: '0.95rem' } }} />
                          <Chip label={`Lessons: ${lessons}`} color="success" sx={{ fontSize: { xs: '0.8rem', md: '0.95rem' } }} />
                          <Chip label={`Resources: ${resources}`} color="warning" sx={{ fontSize: { xs: '0.8rem', md: '0.95rem' } }} />
                        </Box>
                        <Typography variant="body2" sx={{ color: '#1976d2', fontWeight: 500, fontSize: { xs: '0.9rem', md: '1rem' }, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          Instructor(s): {instructors}
                        </Typography>
                        {/* Show started date if available */}
                        {course.enrolled_at && (
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                            Started: {new Date(course.enrolled_at).toLocaleDateString()}
                          </Typography>
                        )}
                      </Box>
                    );
                  })}
                </Box>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 180 }}>
                  <Typography align="center" color="text.secondary" sx={{ fontSize: '1.1rem', fontWeight: 500 }}>No enrolled courses found.</Typography>
                </Box>
              )}
            </Box>
          </>
        );
      case 'assignments':
        return <StudentAssignments courses={dashboardData.enrolledCourses || []} />;
      case 'messages':
        return <StudentMessages messages={dashboardData.messages || []} />;
      case 'schedule':
        return <StudentSchedule schedules={dashboardData.schedules || []} />;
      case 'feedback':
        return <StudentFeedback feedback={dashboardData.feedbackHistory || []} onFeedback={handleFeedbackClick} />;
      case 'cart-wishlist':
        return (
          <StudentCartWishlist
            cart={dashboardData.cart || []}
            wishlist={dashboardData.wishlist || []}
            paymentHistory={dashboardData.paymentHistory || []}
          />
        );
      case 'search':
        return <StudentSearch />;
      case 'support':
        return <StudentSupport />;
      case 'gamification':
        return <StudentGamification gamification={dashboardData.gamification || { points: 0, badges: [], leaderboardRank: 0 }} />;
      case 'ai-tutor':
        return <AITutor />;
      default:
        return <Typography>Section not found.</Typography>;
    }
  };

  return (
    <ErrorBoundary>
      <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#f5f5f5' }}>
        {/* Sidebar */}
        <Drawer
          variant={isMobile ? 'temporary' : 'permanent'}
          open={isMobile ? drawerOpen : true}
          onClose={() => setDrawerOpen(false)}
          sx={{
            width: isMobile ? '100%' : 240,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: isMobile ? '100%' : 240,
              boxSizing: 'border-box',
              bgcolor: theme.palette.primary.main,
              color: '#fff',
              borderRight: 'none',
            },
          }}
        >
          <Toolbar sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
            <School sx={{ fontSize: 32, mr: 1 }} />
            <Typography variant="h6" noWrap component="div">
              EduConnect
            </Typography>
          </Toolbar>
          <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />
          <List>
            {navigationItems.map((item) => (
              <ListItem
                button
                key={item.id}
                onClick={() => {
                  setActiveSection(item.id);
                  if (isMobile) setDrawerOpen(false);
                }}
                sx={{
                  bgcolor: activeSection === item.id ? 'rgba(255,255,255,0.2)' : 'transparent',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                  mb: 0.5,
                }}
              >
                <ListItemIcon sx={{ color: '#fff', minWidth: '40px' }}>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
                {item.id === 'messages' && unreadCount > 0 && (
                  <Chip label={unreadCount} size="small" color="error" sx={{ ml: 1 }} />
                )}
              </ListItem>
            ))}
          </List>
          <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />
          <Box sx={{ p: 2, mt: 'auto' }}>
            <Button
              variant="outlined"
              fullWidth
              startIcon={<Logout />}
              sx={{
                color: '#fff',
                borderColor: 'rgba(255,255,255,0.2)',
                '&:hover': { borderColor: 'rgba(255,255,255,0.4)' },
              }}
              onClick={async () => {
                try {
                  await authAPI.logout();
                  // Clear all user-related state and local/session storage
                  setDashboardData(null);
                  setProfileOpen(false);
                  setActiveSection('overview');
                  setFeedbackOpen(false);
                  setFeedbackTarget(null);
                  setSnackbar({ open: false, message: '', severity: 'info' });
                  // Optionally clear localStorage/sessionStorage if you store user info there
                  localStorage.clear();
                  sessionStorage.clear();
                  showSnackbar('Logged out successfully', 'success');
                  // Optionally redirect to login page
                  window.location.href = '/login';
                } catch (error) {
                  showSnackbar('Error logging out', 'error');
                }
              }}
            >
              Logout
            </Button>
          </Box>
        </Drawer>

        {/* Main Content */}
        <Box flexGrow={1}>
          {/* Top Navigation Bar */}
          <AppBar
            position="fixed"
            sx={{ bgcolor: '#fff', color: '#000', boxShadow: 1, zIndex: theme.zIndex.drawer + 1 }}
          >
            <Toolbar>
              {isMobile && (
                <IconButton edge="start" onClick={() => setDrawerOpen(true)} sx={{ mr: 2 }}>
                  <MenuIcon />
                </IconButton>
              )}
              <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
                Student Dashboard
              </Typography>
              <Box sx={{ display: { xs: 'none', md: 'flex' } }}>
                <IconButton
                  size="large"
                  color="inherit"
                  onClick={(e) => setAnchorEl(e.currentTarget)}
                  sx={{ mr: 1 }}
                >
                  <Badge badgeContent={unreadCount} color="error">
                    <Notifications />
                  </Badge>
                </IconButton>
                <IconButton
                  size="large"
                  edge="end"
                  onClick={handleProfileOpen}
                >
                  <Avatar src={dashboardData?.student?.avatar || 'https://randomuser.me/api/portraits/men/32.jpg'} sx={{ width: 32, height: 32 }} />
                </IconButton>
              </Box>
              <Box sx={{ display: { xs: 'flex', md: 'none' } }}>
                <IconButton
                  size="large"
                  color="inherit"
                  onClick={(e) => setAnchorEl(e.currentTarget)}
                >
                  <Badge badgeContent={unreadCount} color="error">
                    <Notifications />
                  </Badge>
                </IconButton>
              </Box>
            </Toolbar>
          </AppBar>

          {/* Notifications Menu */}
          <Menu
            anchorEl={anchorEl}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            keepMounted
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
          >
            <MenuItemMUI dense disabled>
              <Typography variant="subtitle1">Notifications</Typography>
            </MenuItemMUI>
            {(dashboardData?.messages || []).slice(0, 3).map((msg) => (
              <MenuItemMUI
                key={msg.id}
                onClick={() => {
                  setActiveSection('messages');
                  setAnchorEl(null);
                }}
                sx={{
                  borderLeft: msg.important ? '3px solid' + theme.palette.error.main : 'none',
                  bgcolor: !msg.read ? theme.palette.action.selected : 'inherit',
                }}
              >
                <ListItemIcon>
                  <Message color={!msg.read ? 'primary' : 'action'} />
                </ListItemIcon>
                <ListItemText
                  primary={msg.sender || 'Unknown Sender'}
                  secondary={
                    <Typography
                      variant="body2"
                      sx={{
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '300px',
                      }}
                    >
                      {msg.content || 'No content'}
                    </Typography>
                  }
                />
              </MenuItemMUI>
            ))}
            <MenuItemMUI
              onClick={() => {
                setActiveSection('messages');
                setAnchorEl(null);
              }}
              sx={{ justifyContent: 'center' }}
            >
              <Typography color="primary">View All Notifications</Typography>
            </MenuItemMUI>
          </Menu>

          {/* Content Area */}
          <Box
            sx={{
              p: isMobile ? 2 : 4,
              maxWidth: '1400px',
              mx: 'auto',
              mt: '64px',
              pb: { xs: 10, md: 12 }, // Add padding-bottom for FAB/snackbar
            }}
          >
            {renderContent()}
          </Box>

          {/* Profile Modal */}
          {dashboardData?.student && (
            <StudentProfile
              open={profileOpen}
              onClose={() => setProfileOpen(false)}
              student={dashboardData.student}
              onSave={() => {
                showSnackbar('Profile updated successfully', 'success');
                fetchDashboardData(user?.id).then((data) => {
                  setDashboardData(data);
                });
              }}
            />
          )}

          {/* Floating Feedback Button */}
          <Fab
            color="primary"
            aria-label="feedback"
            sx={{
              position: 'fixed',
              bottom: 32,
              right: 32,
              display: { xs: 'none', md: 'flex' },
            }}
            onClick={() => handleFeedbackClick(null, 'lms')}
          >
            <Feedback />
          </Fab>

          {/* Snackbar */}
          <Snackbar
            open={snackbar.open}
            autoHideDuration={6000}
            onClose={() => setSnackbar({ ...snackbar, open: false })}
          >
            <Alert
              onClose={() => setSnackbar({ ...snackbar, open: false })}
              severity={snackbar.severity}
            >
              {snackbar.message}
            </Alert>
          </Snackbar>
        </Box>
      </Box>
    </ErrorBoundary>
  );
};

export default StudentDashboard;