import React, { useState, useEffect } from 'react';
import {
  Paper, Typography, TextField, FormControl, InputLabel, Select, MenuItem,
  Button, Grid, CircularProgress, InputAdornment, IconButton, Box
} from '@mui/material';
import { Search as SearchIcon, BookmarkBorder, Bookmark } from '@mui/icons-material';
import { coursesAPI } from '../../../config';
import { useSnackbar } from 'notistack'; // ✅ CORRECT
import './StudentSearch.css';

const levels = [
  { value: '', label: 'All' },
  { value: 'Beginner', label: 'Beginner' },
  { value: 'Intermediate', label: 'Intermediate' },
  { value: 'Advanced', label: 'Advanced' }
];

const StudentSearch = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [level, setLevel] = useState('');
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(false);

  // For category filter
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');

  // Bookmarked course IDs
  const [bookmarked, setBookmarked] = useState(() => {
    const saved = localStorage.getItem('bookmarkedCourses');
    return saved ? JSON.parse(saved) : [];
  });

  // Wishlist and cart state
  const [wishlist, setWishlist] = useState([]);
  const [cart, setCart] = useState([]);
  const { enqueueSnackbar } = useSnackbar(); // Optional

  // Fetch courses and extract unique categories from course.category.name
  useEffect(() => {
    setLoading(true);
    coursesAPI.getCourses({
      search: searchQuery,
      level
    })
      .then(res => {
        const courseList = res.data.results || [];
        setCourses(courseList);

        // Extract unique categories from courses (by category.name)
        const cats = [];
        const seen = new Set();
        courseList.forEach(course => {
          if (course.category && course.category.name && !seen.has(course.category.name)) {
            cats.push({ value: course.category.name, label: course.category.name });
            seen.add(course.category.name);
          }
        });
        setCategoryOptions([{ value: '', label: 'All' }, ...cats]);
      })
      .catch(() => {
        setCourses([]);
        setCategoryOptions([{ value: '', label: 'All' }]);
      })
      .finally(() => setLoading(false));
  }, [searchQuery, level]);

  // Fetch wishlist and cart from backend on mount
  useEffect(() => {
    coursesAPI.getWishlist().then(res => {
      const data = res.data?.results || res.data || [];
      setWishlist(Array.isArray(data) ? data : []);
    });
    coursesAPI.getCart().then(res => {
      const data = res.data?.results || res.data || [];
      setCart(Array.isArray(data) ? data : []);
    });
  }, []);

  // Log wishlist and cart state
  console.log('Wishlist:', wishlist);
  console.log('Cart:', cart);

  // Filter courses based on selected category name
  const filteredCourses = selectedCategory
    ? courses.filter(course => course.category && course.category.name === selectedCategory)
    : courses;

  // Helper: always extract course ID for comparison
  const getCourseId = (item) => typeof item.course === 'object' ? item.course.id : item.course;

  // Helper: check if course is in wishlist/cart
  const isWishlisted = (courseId) =>
    Array.isArray(wishlist) && wishlist.some(item => getCourseId(item) === courseId);

  const isInCart = (courseId) =>
    Array.isArray(cart) && cart.some(item => getCourseId(item) === courseId);

  // Add/remove wishlist (bookmark)
  const handleBookmark = async (courseId) => {
    try {
      if (isWishlisted(courseId)) {
        // Remove from wishlist
        const item = wishlist.find(w => getCourseId(w) === courseId);
        await coursesAPI.removeFromWishlist(item.id);
        setWishlist(wishlist.filter(w => getCourseId(w) !== courseId));
        enqueueSnackbar && enqueueSnackbar('Removed from wishlist', { variant: 'info' });
      } else {
        const res = await coursesAPI.addToWishlist({ course_id: courseId });
        setWishlist([...wishlist, res.data]);
        enqueueSnackbar && enqueueSnackbar('Added to wishlist', { variant: 'success' });
      }
    } catch (error) {
      // Catch and display error message from backend
      let msg = 'An error occurred. Please try again.';
      if (error?.response?.data?.detail) {
        msg = error.response.data.detail;
      } else if (error?.message) {
        msg = error.message;
      }
      enqueueSnackbar && enqueueSnackbar(msg, { variant: 'error' });
    }
  };

  // Add to cart
  const handleAddToCart = async (courseId) => {
    if (isInCart(courseId)) {
      enqueueSnackbar && enqueueSnackbar('Already in cart', { variant: 'warning' });
      return;
    }
    try {
      const res = await coursesAPI.addToCart({ course_id: courseId });
      setCart([...cart, res.data]);
      enqueueSnackbar && enqueueSnackbar('Added to cart', { variant: 'success' });
    } catch (error) {
      // Catch and display error message from backend
      let msg = 'An error occurred. Please try again.';
      if (error?.response?.data?.detail) {
        msg = error.response.data.detail;
      } else if (error?.message) {
        msg = error.message;
      }
      enqueueSnackbar && enqueueSnackbar(msg, { variant: 'error' });
    }
  };

  // Helper to get price display
  const renderPrice = (course) => {
    const price = course.price || course.current_price;
    const discount = course.discount_price && course.discount_price !== price;
    if (discount) {
      return (
        <Box>
          <span style={{
            color: '#ff6600',
            fontWeight: 700,
            fontSize: '1.1rem',
            marginRight: 8,
          }}>
            ₦{course.discount_price}
          </span>
          <span style={{
            textDecoration: 'line-through',
            color: '#888',
            fontWeight: 500,
            fontSize: '0.98rem'
          }}>
            ₦{price}
          </span>
        </Box>
      );
    }
    return (
      <span className="student-search-card-price">
        {price ? `₦${price}` : 'Free'}
      </span>
    );
  };

  return (
    <Paper elevation={3} className="student-search-root">
      <Typography variant="h4" className="student-search-title">Find Your Next Course</Typography>
      <form className="student-search-form" autoComplete="off" onSubmit={e => e.preventDefault()}>
        <TextField
          className="student-search-input"
          label="Search by title or category"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="primary" />
              </InputAdornment>
            ),
          }}
          variant="outlined"
        />
        <FormControl className="student-search-select">
          <InputLabel>Category</InputLabel>
          <Select
            value={selectedCategory}
            onChange={e => setSelectedCategory(e.target.value)}
            label="Category"
          >
            {categoryOptions.map(opt => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl className="student-search-select">
          <InputLabel>Level</InputLabel>
          <Select value={level} onChange={e => setLevel(e.target.value)} label="Level">
            {levels.map(opt => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="contained"
          color="primary"
          className="student-search-btn"
          type="submit"
        >
          Search
        </Button>
      </form>
      <Grid container spacing={3} className="student-search-grid" sx={{ minHeight: '320px' }}>
        {loading ? (
          <Grid item xs={12}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: { xs: '220px', sm: '320px' },
                width: '100%',
                py: { xs: 4, sm: 8 },
                background: 'linear-gradient(135deg, #e3f2fd 0%, #fce4ec 100%)',
                borderRadius: 3,
                boxShadow: 2,
              }}
            >
              <CircularProgress
                size={60}
                thickness={4.5}
                sx={{
                  color: '#1976d2',
                  mb: 2,
                  animationDuration: '1.2s'
                }}
              />
              <Typography
                variant="h6"
                align="center"
                sx={{
                  color: '#1976d2',
                  fontWeight: 600,
                  letterSpacing: 0.5,
                  mt: 1
                }}
              >
                Loading courses...
              </Typography>
              <Typography
                variant="body2"
                align="center"
                sx={{
                  color: '#888',
                  mt: 0.5,
                  maxWidth: 320
                }}
              >
                Please wait while we fetch the best courses for you.
              </Typography>
            </Box>
          </Grid>
        ) : filteredCourses.length === 0 ? (
          <Grid item xs={12}>
            <Typography color="textSecondary" align="center" sx={{ mt: 4 }}>
              No courses found. Try adjusting your search.
            </Typography>
          </Grid>
        ) : (
          filteredCourses.map(course => (
            <Grid item xs={12} sm={6} md={3} key={course.id}>
              <div className="student-search-card">
                {course.status === 'New' && (
                  <span className="student-search-card-badge">New</span>
                )}
                <IconButton
                  className="student-search-bookmark-btn"
                  onClick={() => handleBookmark(course.id)}
                  aria-label={isWishlisted(course.id) ? 'Remove Bookmark' : 'Bookmark'}
                >
                  {isWishlisted(course.id) ? (
                    <Bookmark color="primary" />
                  ) : (
                    <BookmarkBorder color="action" />
                  )}
                </IconButton>
                <img
                  src={course.thumbnail}
                  alt={course.title}
                  className="student-search-card-media uniform-img"
                />
                <div className="student-search-card-body">
                  <div className="student-search-card-title">{course.title}</div>
                  <div className="student-search-card-price">
                    {renderPrice(course)}
                  </div>
                  <button
                    className="student-search-enroll-btn"
                    onClick={() => handleAddToCart(course.id)}
                    disabled={isInCart(course.id)}
                  >
                    {isInCart(course.id) ? 'In Cart' : 'Add to Cart'}
                  </button>
                </div>
              </div>
            </Grid>
          ))
        )}
      </Grid>
    </Paper>
  );
};

export default StudentSearch;