// Mark a schedule as read
  const handleMarkAsRead = async (scheduleId) => {
    try {
      await scheduleAPI.markAsRead(scheduleId);
      enqueueSnackbar('Marked as read!', { variant: 'success' });
      fetchData();
    } catch (error) {
      enqueueSnackbar('Error marking as read', { variant: 'error' });
    }
  };

  // Download an attachment
  const handleDownloadAttachment = (scheduleId) => {
    window.open(`/api/schedule/schedules/${scheduleId}/download_attachment/`, '_blank');
  };
import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, Typography, Button, Paper, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Dialog, DialogTitle, 
  DialogContent, DialogActions, TextField, MenuItem, Snackbar, 
  Tooltip, Link, Chip, useMediaQuery, IconButton, Stack, Checkbox,
  Collapse, Card, CardContent, CardActions, List, ListItem, 
  ListItemText, ListItemAvatar, Avatar, TablePagination, Grid,
  LinearProgress, CircularProgress, Badge, Divider,FormControlLabel
} from '@mui/material';
import MuiAlert from '@mui/material/Alert';
import {
  CalendarToday as CalendarIcon, Person as PersonIcon,
  Group as GroupIcon, ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon, Check as CheckIcon,
  Close as CloseIcon, Schedule as ScheduleIcon, 
  ArrowForward as ArrowForwardIcon,
  EventAvailable as EventAvailableIcon, EventBusy as EventBusyIcon,
  LocationOn as LocationIcon, Refresh as RefreshIcon,
  Videocam as VideocamIcon, Groups as TeamsIcon,Search as SearchIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { format, parseISO, isBefore } from 'date-fns';
import { useSnackbar } from 'notistack';
import { useWebSocket } from '../../../hooks/useWebSocket';
import { scheduleAPI } from '../../../config';
import { debounce } from 'lodash';

const Alert = React.forwardRef(function Alert(props, ref) {
  return <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />;
});

const responseOptions = [
  { value: 'pending', label: 'Pending', color: 'default' },
  { value: 'accepted', label: 'Accepted', color: 'success' },
  { value: 'declined', label: 'Declined', color: 'error' },
  { value: 'tentative', label: 'Tentative', color: 'warning' },
];

const StudentSchedule = () => {
  const { enqueueSnackbar } = useSnackbar();
  const isMobile = useMediaQuery('(max-width:600px)');
  
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  // State management
  const [schedules, setSchedules] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSchedule, setExpandedSchedule] = useState(null);

  // Pagination state
  const [pagination, setPagination] = useState({
    count: 0,
    next: null,
    previous: null,
    page: 1
  });
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Filters state
  const [filters, setFilters] = useState({
    search: '',
    dateFrom: null,
    dateTo: null,
    showPast: false
  });

  // WebSocket integration
  const { lastMessage, sendMessage } = useWebSocket(
    `ws://${window.location.host}/ws/schedules/`
  );

  // Helper function to generate Google Calendar link
  const generateGoogleCalendarLink = (schedule) => {
    const startTime = new Date(schedule.start_time).toISOString().replace(/-|:|\.\d\d\d/g, '');
    const endTime = new Date(schedule.end_time).toISOString().replace(/-|:|\.\d\d\d/g, '');
    
    const baseUrl = 'https://www.google.com/calendar/render?action=TEMPLATE';
    const title = `&text=${encodeURIComponent(schedule.title || '')}`;
    const dates = `&dates=${startTime}/${endTime}`;
    const details = `&details=${encodeURIComponent(schedule.description || '')}`;
    const location = `&location=${encodeURIComponent(schedule.location || '')}`;
    
    return `${baseUrl}${title}${dates}${details}${location}`;
  };

  // Helper function to truncate URLs
  const truncateUrl = (url, maxLength = 30) => {
    if (!url) return '';
    
    try {
      const urlObj = new URL(url);
      let displayUrl = urlObj.hostname.replace('www.', '');
      
      if (urlObj.hostname.includes('meet.google.com')) {
        return 'Google Meet';
      }
      if (urlObj.hostname.includes('teams.microsoft.com')) {
        return 'Microsoft Teams';
      }
      if (urlObj.hostname.includes('zoom.us')) {
        return 'Zoom Meeting';
      }
      
      if (displayUrl.length + urlObj.pathname.length <= maxLength) {
        return `${displayUrl}${urlObj.pathname}`;
      }
      
      return displayUrl;
    } catch {
      return url.length <= maxLength ? url : `${url.substring(0, maxLength - 3)}...`;
    }
  };

  // Function to get platform icon and color
  const getPlatformIcon = (url) => {
    if (!url) return <VideocamIcon fontSize="small" />;
    
    try {
      const urlObj = new URL(url);
      
      if (urlObj.hostname.includes('meet.google.com')) {
        return <VideocamIcon fontSize="small" style={{ color: '#00897B' }} />;
      }
      if (urlObj.hostname.includes('teams.microsoft.com')) {
        return <TeamsIcon fontSize="small" style={{ color: '#464EB8' }} />;
      }
      if (urlObj.hostname.includes('zoom.us')) {
        return <VideocamIcon fontSize="small" style={{ color: '#2D8CFF' }} />;
      }
    } catch {
      // If URL parsing fails, fall back to default
    }
    
    return <VideocamIcon fontSize="small" />;
  };

  // Fetch initial data
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = {
        page: pagination.page,
        page_size: rowsPerPage,
        ...(filters.search && { search: filters.search }),
        ...(filters.dateFrom && { date_from: format(filters.dateFrom, 'yyyy-MM-dd') }),
        ...(filters.dateTo && { date_to: format(filters.dateTo, 'yyyy-MM-dd') }),
        show_past: filters.showPast
      };

      const response = await scheduleAPI.getSchedules(params);
      console.log('Fetched schedules:', response.data);
      setSchedules(response.data || []);
      setPagination({
        count: response.data.count || 0,
        next: response.data.next,
        previous: response.data.previous,
        page: pagination.page
      });
    } catch (error) {
      setError(error.message);
      enqueueSnackbar('Failed to load schedules', { variant: 'error' });
    } finally {
      setIsLoading(false);
    }
  }, [pagination.page, rowsPerPage, filters, enqueueSnackbar]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data);
      if (data.type === 'new_schedule') {
        if (pagination.page === 1) {
          setSchedules(prev => [data.schedule, ...prev.slice(0, -1)]);
          setPagination(prev => ({
            ...prev,
            count: prev.count + 1
          }));
        } else {
          setPagination(prev => ({
            ...prev,
            count: prev.count + 1
          }));
        }
      } else if (data.type === 'schedule_updated') {
        setSchedules(prev => prev.map(s => 
          s.id === data.schedule.id ? data.schedule : s
        ));
      } else if (data.type === 'schedule_deleted') {
        setSchedules(prev => prev.filter(s => s.id !== data.schedule_id));
        setPagination(prev => ({
          ...prev,
          count: prev.count - 1
        }));
      } else if (data.type === 'schedule_response') {
        setSchedules(prev => prev.map(s => {
          if (s.id === data.schedule_id) {
            const updatedParticipants = s.participants.map(p => 
              p.user?.id === data.user_id ? { ...p, response_status: data.response_status } : p
            );
            return { ...s, participants: updatedParticipants };
          }
          return s;
        }));
      }
    }
  }, [lastMessage, pagination.page]);

  // Helper functions
  const formatDate = (dateString) => {
    return format(parseISO(dateString), 'MMM d, yyyy - h:mm a');
  };

  const isPastEvent = (schedule) => {
    return isBefore(parseISO(schedule.end_time), new Date());
  };

  const handleRespondToSchedule = async (scheduleId, response) => {
    try {
      await scheduleAPI.respondToSchedule(scheduleId, response);
      enqueueSnackbar(`Response "${response}" recorded!`, { variant: 'success' });
      fetchData();
    } catch (error) {
      enqueueSnackbar('Error recording response', { variant: 'error' });
      console.error('Error recording response:', error);
    }
  };

  const toggleExpandSchedule = (scheduleId) => {
    setExpandedSchedule(expandedSchedule === scheduleId ? null : scheduleId);
  };

  const handleFilterChange = (name, value) => {
    setFilters(prev => ({
      ...prev,
      [name]: value
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const resetFilters = () => {
    setFilters({
      search: '',
      dateFrom: null,
      dateTo: null,
      showPast: false
    });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const getResponseColor = (responseStatus) => {
    const option = responseOptions.find(opt => opt.value === responseStatus);
    return option ? option.color : 'default';
  };

  const handleChangePage = (event, newPage) => {
    setPagination(prev => ({ ...prev, page: newPage + 1 }));
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  // Mobile view for schedules
  const renderMobileScheduleCards = () => (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {schedules.map((schedule) => (
        <Card key={schedule.id} elevation={3}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {isPastEvent(schedule) ? (
                  <EventBusyIcon color="error" />
                ) : (
                  <EventAvailableIcon color="primary" />
                )}
                <Typography variant="subtitle1" component="div">
                  {schedule.title}
                </Typography>
              </Box>
              <IconButton onClick={() => toggleExpandSchedule(schedule.id)}>
                {expandedSchedule === schedule.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
            </Box>
            <Typography color="text.secondary" gutterBottom>
              {formatDate(schedule.start_time)} - {formatDate(schedule.end_time)}
            </Typography>
            
            <Collapse in={expandedSchedule === schedule.id}>
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-line', mb: 2 }}>
                  {schedule.description}
                </Typography>
                
                {schedule.location && (
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    {getPlatformIcon(schedule.location)}
                    <Typography variant="body2" sx={{ ml: 1 }}>
                      {truncateUrl(schedule.location)}
                    </Typography>
                    {schedule.location && (
                      <IconButton 
                        size="small" 
                        sx={{ ml: 1 }}
                        onClick={() => window.open(schedule.location, '_blank')}
                      >
                        <ArrowForwardIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                )}
                              
                <Typography variant="subtitle2" sx={{ mt: 2 }}>Participants:</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                  {schedule.participants.map((participant, i) => (
                    <Chip 
                      key={i} 
                      label={participant.user ? 
                        `${participant.user.first_name} ${participant.user.last_name}` : 
                        participant.group.name}
                      size="small" 
                      icon={participant.group ? <GroupIcon /> : <PersonIcon />}
                      color={getResponseColor(participant.response_status)}
                    />
                  ))}
                </Box>
                
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2">Your Response:</Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    {responseOptions.map((option) => (
                      <Button
                        key={option.value}
                        variant="outlined"
                        size="small"
                        color={option.color}
                        startIcon={option.value === 'accepted' ? <CheckIcon /> : 
                                  option.value === 'declined' ? <CloseIcon /> : null}
                        onClick={() => handleRespondToSchedule(schedule.id, option.value)}
                      >
                        {option.label}
                      </Button>
                    ))}
                  </Stack>
                </Box>

                {/* Mark as Read and Download Attachment buttons */}
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => handleMarkAsRead(schedule.id)}
                  >
                    Mark as Read
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => handleDownloadAttachment(schedule.id)}
                  >
                    Download Attachment
                  </Button>
                </Stack>

                {/* Add to Google Calendar button in expanded view */}
                <Button
                  variant="contained"
                  startIcon={<CalendarIcon />}
                  onClick={() => window.open(generateGoogleCalendarLink(schedule), '_blank')}
                  sx={{ mt: 2 }}
                  fullWidth
                >
                  Add to Google Calendar
                </Button>
              </Box>
            </Collapse>
          </CardContent>
          <CardActions sx={{ justifyContent: 'flex-end' }}>
            <Button 
              size="small" 
              startIcon={<CalendarIcon />}
              onClick={() => window.open(generateGoogleCalendarLink(schedule), '_blank')}
            >
              Add to Calendar
            </Button>
          </CardActions>
        </Card>
      ))}
    </Box>
  );

  // Desktop view for schedules
  const renderDesktopScheduleTable = () => (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Title</TableCell>
            <TableCell>Time</TableCell>
            <TableCell>Location</TableCell>
            <TableCell>Participants</TableCell>
            <TableCell>Your Response</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {schedules.map((schedule) => (
            <React.Fragment key={schedule.id}>
              <TableRow 
                hover 
                sx={{ 
                  '&:hover': { cursor: 'pointer' },
                  backgroundColor: expandedSchedule === schedule.id ? 'action.hover' : 'inherit'
                }}
                onClick={() => toggleExpandSchedule(schedule.id)}
              >
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {isPastEvent(schedule) ? (
                      <EventBusyIcon color="error" sx={{ mr: 1 }} />
                    ) : (
                      <EventAvailableIcon color="primary" sx={{ mr: 1 }} />
                    )}
                    <Typography sx={{ fontWeight: isPastEvent(schedule) ? 'normal' : 'bold' }}>
                      {schedule.title}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  {formatDate(schedule.start_time)} - {formatDate(schedule.end_time)}
                </TableCell>
                <TableCell>
                  {schedule.location && (
                    <Tooltip title={schedule.location || ''}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {getPlatformIcon(schedule.location)}
                        <Link 
                          href={schedule.location} 
                          target="_blank" 
                          rel="noopener" 
                          sx={{ ml: 1 }}
                        >
                          {truncateUrl(schedule.location)}
                        </Link>
                      </Box>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {schedule.participants.slice(0, 2).map((participant, i) => (
                      <Chip 
                        key={i} 
                        label={participant.user ? 
                          `${participant.user.first_name} ${participant.user.last_name}` : 
                          participant.group.name}
                        size="small" 
                        icon={participant.group ? <GroupIcon /> : <PersonIcon />}
                        color={getResponseColor(participant.response_status)}
                      />
                    ))}
                    {schedule.participants.length > 2 && (
                      <Chip label={`+${schedule.participants.length - 2}`} size="small" />
                    )}
                  </Box>
                </TableCell>
                <TableCell>
                  {schedule.participants.find(p => p.user)?.response_status || 'Not invited'}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1}>
                    <Tooltip title="Add to Google Calendar">
                      <IconButton 
                        size="small" 
                        onClick={(e) => {
                          e.stopPropagation();
                          window.open(generateGoogleCalendarLink(schedule), '_blank');
                        }}
                      >
                        <CalendarIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Mark as Read">
                      <IconButton
                        size="small"
                        onClick={e => {
                          e.stopPropagation();
                          handleMarkAsRead(schedule.id);
                        }}
                      >
                        <CheckIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Download Attachment">
                      <IconButton
                        size="small"
                        onClick={e => {
                          e.stopPropagation();
                          handleDownloadAttachment(schedule.id);
                        }}
                      >
                        <DownloadIcon />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell style={{ padding: 0 }} colSpan={6}>
                  <Collapse in={expandedSchedule === schedule.id} timeout="auto" unmountOnExit>
                    <Box sx={{ p: 3, backgroundColor: 'background.paper' }}>
                      <Typography variant="body1" sx={{ whiteSpace: 'pre-line', mb: 2 }}>
                        {schedule.description}
                      </Typography>
                      
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <LocationIcon color="action" sx={{ mr: 1 }} />
                        <Typography>{schedule.location || 'No location specified'}</Typography>
                      </Box>
                      
                      <Typography variant="subtitle2" sx={{ mt: 2 }}>Participants:</Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                        {schedule.participants.map((participant, i) => (
                          <Chip 
                            key={i} 
                            label={participant.user ? 
                              `${participant.user.first_name} ${participant.user.last_name}` : 
                              participant.group.name}
                            size="small" 
                            icon={participant.group ? <GroupIcon /> : <PersonIcon />}
                            color={getResponseColor(participant.response_status)}
                          />
                        ))}
                      </Box>
                      
                      <Typography variant="subtitle2" sx={{ mt: 2 }}>Your Response:</Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        {responseOptions.map((option) => (
                          <Button
                            key={option.value}
                            variant="outlined"
                            size="small"
                            color={option.color}
                            startIcon={option.value === 'accepted' ? <CheckIcon /> : 
                                      option.value === 'declined' ? <CloseIcon /> : null}
                            onClick={() => handleRespondToSchedule(schedule.id, option.value)}
                          >
                            {option.label}
                          </Button>
                        ))}
                      </Stack>

                      {/* Add to Google Calendar button in expanded view */}
                      <Button
                        variant="contained"
                        startIcon={<CalendarIcon />}
                        onClick={() => window.open(generateGoogleCalendarLink(schedule), '_blank')}
                        sx={{ mt: 2 }}
                      >
                        Add to Google Calendar
                      </Button>
                    </Box>
                  </Collapse>
                </TableCell>
              </TableRow>
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
        <Typography variant="h4" gutterBottom>
          My Schedule
          <Badge badgeContent={schedules.filter(s => !isPastEvent(s)).length} color="primary" sx={{ ml: 2 }}>
            <CalendarIcon />
          </Badge>
        </Typography>
      
        {/* Filters Section */}
        <Paper elevation={2} sx={{ p: 3, mb: 3, borderRadius: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                fullWidth
                variant="outlined"
                size="small"
                placeholder="Search schedules..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                InputProps={{
                  startAdornment: <SearchIcon color="action" sx={{ mr: 1 }} />
                }}
              />
            </Grid>
            <Grid item xs={6} sm={3} md={2}>
              <DatePicker
                label="From"
                value={filters.dateFrom}
                onChange={(newValue) => handleFilterChange('dateFrom', newValue)}
                renderInput={(params) => (
                  <TextField 
                    {...params} 
                    fullWidth 
                    size="small"
                  />
                )}
              />
            </Grid>
            <Grid item xs={6} sm={3} md={2}>
              <DatePicker
                label="To"
                value={filters.dateTo}
                onChange={(newValue) => handleFilterChange('dateTo', newValue)}
                renderInput={(params) => (
                  <TextField 
                    {...params} 
                    fullWidth 
                    size="small"
                  />
                )}
              />
            </Grid>
            <Grid item xs={6} sm={3} md={2}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={filters.showPast}
                    onChange={(e) => handleFilterChange('showPast', e.target.checked)}
                    color="primary"
                  />
                }
                label="Show Past Events"
              />
            </Grid>
            <Grid item xs={6} sm={3} md={2} sx={{ textAlign: 'right' }}>
              <Tooltip title="Reset Filters">
                <IconButton onClick={resetFilters}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Grid>
          </Grid>
        </Paper>

        {isLoading ? (
          <LinearProgress />
        ) : error ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : schedules.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <Typography>No schedules found</Typography>
          </Box>
        ) : isMobile ? renderMobileScheduleCards() : renderDesktopScheduleTable()}

        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component="div"
          count={pagination.count}
          rowsPerPage={rowsPerPage}
          page={pagination.page - 1}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />

        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={handleCloseSnackbar}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <MuiAlert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }} elevation={6} variant="filled">
            {snackbar.message}
          </MuiAlert>
        </Snackbar>
      </Box>
    </LocalizationProvider>
  );
};

export default StudentSchedule;