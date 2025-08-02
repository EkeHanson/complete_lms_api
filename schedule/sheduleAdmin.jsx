import React, { useState, useEffect, useCallback } from 'react';
import {
  Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon,
  CalendarToday as CalendarIcon, Person as PersonIcon,
  Group as GroupIcon, Close as CloseIcon, Search as SearchIcon,
  Check as CheckIcon, Refresh as RefreshIcon,
  EventAvailable as EventAvailableIcon, EventBusy as EventBusyIcon,
  ArrowForward as ArrowForwardIcon, Videocam as VideocamIcon
} from '@mui/icons-material';
import { DatePicker, DateTimePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, parseISO, isBefore } from 'date-fns';
import { TablePagination } from '@mui/material';
import { useSnackbar } from 'notistack';
import { debounce } from 'lodash';
import TextField from '@mui/material/TextField';
import './Schedule.css';

// Dummy API imports for context
import { scheduleAPI, groupsAPI, userAPI } from '../../../config';

const responseOptions = [
  { value: 'pending', label: 'Pending', color: '#6251a4' },

  { value: 'declined', label: 'Declined', color: '#991b1b' },
  { value: 'tentative', label: 'Tentative', color: '#d97706' },
];

const ScheduleManagement = () => {
  const { enqueueSnackbar } = useSnackbar();
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [schedules, setSchedules] = useState([]);
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [filteredGroups, setFilteredGroups] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState(null);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [expandedSchedule, setExpandedSchedule] = useState(null);
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [groupSearchQuery, setGroupSearchQuery] = useState('');
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null, page: 1 });
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [filters, setFilters] = useState({
    search: '',
    dateFrom: null,
    dateTo: null,
    showPast: false
  });
  const [userPagination, setUserPagination] = useState({ page: 1, pageSize: 10, count: 0 });
  const [groupPagination, setGroupPagination] = useState({ page: 1, pageSize: 10, count: 0 });
  const [userSearch, setUserSearch] = useState('');
  const [groupSearch, setGroupSearch] = useState('');

  // Fetch schedules, users, and groups from API
  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      scheduleAPI.getSchedules(), // Replace with your actual schedule fetch
      userAPI.getUsers({ page: 1, page_size: 1000 }), // Adjust params as needed
      groupsAPI.getGroups()
    ])
      .then(([schedulesRes, usersRes, groupsRes]) => {
        setSchedules(schedulesRes.data || []);
        setUsers(usersRes.data?.results || []);
        setGroups(groupsRes.data || []);
        setFilteredGroups(groupsRes.data || []);
        setPagination(prev => ({
          ...prev,
          count: (schedulesRes.data?.length || 0)
        }));
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.response?.data?.message || err.message || 'Failed to fetch data');
        setIsLoading(false);
      });
  }, []);

  // Fetch users
  useEffect(() => {
    userAPI.getUsers({
      page: userPagination.page,
      page_size: userPagination.pageSize,
      search: userSearch
    }).then(res => {
      setUsers(res.data?.results || []);
      setUserPagination(prev => ({
        ...prev,
        count: res.data?.count || 0
      }));
    });
  }, [userPagination.page, userPagination.pageSize, userSearch]);

  // Fetch groups
  useEffect(() => {
    groupsAPI.getGroups({
      page: groupPagination.page,
      page_size: groupPagination.pageSize,
      search: groupSearch
    }).then(res => {
      setGroups(res.data?.results || []);
      setFilteredGroups(res.data?.results || []);
      setGroupPagination(prev => ({
        ...prev,
        count: res.data?.count || 0
      }));
    });
  }, [groupPagination.page, groupPagination.pageSize, groupSearch]);

  // Search filter
  useEffect(() => {
    // Add search filter logic if needed
  }, [filters.search, schedules]);

  // Handlers
  const handleOpenDialog = (schedule = null) => {
    const defaultSchedule = {
      title: '',
      description: '',
      start_time: new Date(),
      end_time: new Date(Date.now() + 3600000),
      location: '',
      is_all_day: false
    };
    if (schedule) {
      setCurrentSchedule({
        ...schedule,
        start_time: parseISO(schedule.start_time),
        end_time: parseISO(schedule.end_time)
      });
      setSelectedUsers(schedule.participants.filter(p => p.user).map(p => p.user));
      setSelectedGroups(schedule.participants.filter(p => p.group).map(p => p.group));
    } else {
      setCurrentSchedule(defaultSchedule);
      setSelectedUsers([]);
      setSelectedGroups([]);
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setCurrentSchedule(null);
    setSelectedUsers([]);
    setSelectedGroups([]);
  };

  const handleSaveSchedule = async () => {
    if (!currentSchedule.title || !currentSchedule.start_time || !currentSchedule.end_time) {
      setSnackbar({ open: true, message: 'Title and time required.', severity: 'error' });
      return;
    }

    // Prepare user and group IDs for the backend
    const participant_users = selectedUsers.map(user => user.id);
    const participant_groups = selectedGroups.map(group => group.id);

    const payload = {
      ...currentSchedule,
      participant_users,
      participant_groups,
      // Ensure ISO string for datetime fields
      start_time: currentSchedule.start_time instanceof Date
        ? currentSchedule.start_time.toISOString()
        : currentSchedule.start_time,
      end_time: currentSchedule.end_time instanceof Date
        ? currentSchedule.end_time.toISOString()
        : currentSchedule.end_time,
      // location is already included from currentSchedule
    };

    try {
      if (currentSchedule.id) {
        await scheduleAPI.updateSchedule(currentSchedule.id, payload);
        setSnackbar({ open: true, message: 'Schedule updated.', severity: 'success' });
      } else {
        await scheduleAPI.createSchedule(payload);
        setSnackbar({ open: true, message: 'Schedule created.', severity: 'success' });
      }
      setOpenDialog(false);
      // Refresh the schedules list
      const schedulesRes = await scheduleAPI.getSchedules();
      setSchedules(schedulesRes.data || []);
    } catch (error) {
      setSnackbar({
        open: true,
        message: error.response?.data?.detail || error.message || 'Failed to save schedule',
        severity: 'error'
      });
    }
  };

  const handleDeleteSchedule = (id) => {
    setSchedules(schedules.filter(s => s.id !== id));
    setSnackbar({ open: true, message: 'Schedule deleted.', severity: 'success' });
  };

  const handleRespondToSchedule = (scheduleId, response) => {
    setSnackbar({ open: true, message: `Response "${response}" recorded!`, severity: 'success' });
  };

  const handleRemoveParticipant = (participantToRemove) => {
    if (participantToRemove.email) {
      setSelectedUsers(selectedUsers.filter(user => user.id !== participantToRemove.id));
    } else {
      setSelectedGroups(selectedGroups.filter(group => group.id !== participantToRemove.id));
    }
  };

  const toggleExpandSchedule = (scheduleId) => {
    setExpandedSchedule(expandedSchedule === scheduleId ? null : scheduleId);
  };

  const handleFilterChange = (name, value) => {
    setFilters(prev => ({ ...prev, [name]: value }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const resetFilters = () => {
    setFilters({ search: '', dateFrom: null, dateTo: null, showPast: false });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const getResponseColor = (responseStatus) => {
    const option = responseOptions.find(opt => opt.value === responseStatus);
    return option ? option.color : '#6251a4';
  };

  const handleChangePage = (event, newPage) => {
    setPagination(prev => ({ ...prev, page: newPage + 1 }));
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const formatDate = (dateString) => {
    return format(parseISO(dateString), 'MMM d, yyyy - h:mm a');
  };

  const isPastEvent = (schedule) => {
    return isBefore(parseISO(schedule.end_time), new Date());
  };

  const getPlatformIcon = (url) => {
    if (!url) return null;
    try {
      const urlObj = new URL(url);
      if (urlObj.hostname.includes('meet.google.com')) {
        return <VideocamIcon className="sch-icon sch-icon-google" />;
      }
      if (urlObj.hostname.includes('teams.microsoft.com')) {
        return <VideocamIcon className="sch-icon sch-icon-teams" />;
      }
      if (urlObj.hostname.includes('zoom.us')) {
        return <VideocamIcon className="sch-icon sch-icon-zoom" />;
      }
    } catch {
      // Fallback
    }
    return null;
  };

  const truncateUrl = (url, maxLength = 30) => {
    if (!url) return '';
    try {
      const urlObj = new URL(url);
      let displayUrl = urlObj.hostname.replace('www.', '');
      if (urlObj.hostname.includes('meet.google.com')) return 'Google Meet';
      if (urlObj.hostname.includes('teams.microsoft.com')) return 'Microsoft Teams';
      if (urlObj.hostname.includes('zoom.us')) return 'Zoom Meeting';
      if (displayUrl.length + urlObj.pathname.length <= maxLength) {
        return `${displayUrl}${urlObj.pathname}`;
      }
      return displayUrl;
    } catch {
      return url.length <= maxLength ? url : `${url.substring(0, maxLength - 3)}...`;
    }
  };

  // Autocomplete renderers
  const renderUserAutocomplete = () => (
    <div className="sch-form-field sch-form-field-full">
      <label>Select Users</label>
      <div className="sch-autocomplete">
        <div className="sch-search-input">
          <SearchIcon />
          <input
            type="text"
            placeholder="Search users"
            value={userSearch}
            onChange={e => {
              setUserSearch(e.target.value);
              setUserPagination(prev => ({ ...prev, page: 1 }));
            }}
          />
        </div>
        <div className="sch-autocomplete-options">
          {users.map(option => (
            <div
              key={option.id}
              className={`sch-autocomplete-option ${selectedUsers.some(u => u.id === option.id) ? 'selected' : ''}`}
              onClick={() => {
                if (selectedUsers.some(u => u.id === option.id)) {
                  handleRemoveParticipant(option);
                } else {
                  setSelectedUsers([...selectedUsers, option]);
                }
              }}
            >
              <div>{`${option.first_name} ${option.last_name} (${option.email})`}</div>
              {selectedUsers.some(u => u.id === option.id) && <CheckIcon />}
            </div>
          ))}
        </div>
        <div className="sch-autocomplete-pagination">
          <button
            className="sch-btn sch-btn-secondary"
            disabled={userPagination.page === 1}
            onClick={() => setUserPagination(prev => ({ ...prev, page: prev.page - 1 }))
            }>Prev</button>
          <span>
            Page {userPagination.page} of {Math.ceil(userPagination.count / userPagination.pageSize) || 1}
          </span>
          <button
            className="sch-btn sch-btn-secondary"
            disabled={userPagination.page >= Math.ceil(userPagination.count / userPagination.pageSize)}
            onClick={() => setUserPagination(prev => ({ ...prev, page: prev.page + 1 }))
            }>Next</button>
        </div>
        <div className="sch-chip-container">
          {selectedUsers.map(option => (
            <span key={option.id} className="sch-chip">
              <PersonIcon />
              {`${option.first_name} ${option.last_name}`}
              <button onClick={() => handleRemoveParticipant(option)}>
                <CloseIcon />
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );

  const renderGroupAutocomplete = () => (
    <div className="sch-form-field sch-form-field-full">
      <label>Select Groups</label>
      <div className="sch-autocomplete">
        <div className="sch-search-input">
          <SearchIcon />
          <input
            type="text"
            placeholder="Search groups"
            value={groupSearch}
            onChange={e => {
              setGroupSearch(e.target.value);
              setGroupPagination(prev => ({ ...prev, page: 1 }));
            }}
          />
        </div>
        <div className="sch-autocomplete-options">
          {groups.map(option => (
            <div
              key={option.id}
              className={`sch-autocomplete-option ${selectedGroups.some(g => g.id === option.id) ? 'selected' : ''}`}
              onClick={() => {
                if (selectedGroups.some(g => g.id === option.id)) {
                  handleRemoveParticipant(option);
                } else {
                  setSelectedGroups([...selectedGroups, option]);
                }
              }}
            >
              <div>{option.name}</div>
              {selectedGroups.some(g => g.id === option.id) && <CheckIcon />}
            </div>
          ))}
        </div>
        <div className="sch-autocomplete-pagination">
          <button
            className="sch-btn sch-btn-secondary"
            disabled={groupPagination.page === 1}
            onClick={() => setGroupPagination(prev => ({ ...prev, page: prev.page - 1 }))
            }>Prev</button>
          <span>
            Page {groupPagination.page} of {Math.ceil(groupPagination.count / groupPagination.pageSize) || 1}
          </span>
          <button
            className="sch-btn sch-btn-secondary"
            disabled={groupPagination.page >= Math.ceil(groupPagination.count / groupPagination.pageSize)}
            onClick={() => setGroupPagination(prev => ({ ...prev, page: prev.page + 1 }))
            }>Next</button>
        </div>
        <div className="sch-chip-container">
          {selectedGroups.map(option => (
            <span key={option.id} className="sch-chip">
              <GroupIcon />
              {option.name}
              <button onClick={() => handleRemoveParticipant(option)}>
                <CloseIcon />
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );

  // Table rendering
  const renderDesktopScheduleTable = () => (
    <div className="sch-table-container">
      <table className="sch-table">
        <thead>
          <tr>
            <th><span>Title</span></th>
            <th><span>Time</span></th>
            <th><span>Location</span></th>
            <th><span>Participants</span></th>
            <th><span>Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {schedules.map((schedule) => (
            <React.Fragment key={schedule.id}>
              <tr
                className={expandedSchedule === schedule.id ? 'expanded' : ''}
                onClick={() => toggleExpandSchedule(schedule.id)}
              >
                <td>
                  <div className="sch-table-cell">
                    {isPastEvent(schedule) ? (
                      <EventBusyIcon className="sch-icon sch-icon-error" />
                    ) : (
                      <EventAvailableIcon className="sch-icon sch-icon-primary" />
                    )}
                    <span style={{ fontWeight: isPastEvent(schedule) ? 'normal' : '600' }}>
                      {schedule.title}
                    </span>
                  </div>
                </td>
                <td>
                  <span className="sch-text-secondary">
                    {formatDate(schedule.start_time)} - {formatDate(schedule.end_time)}
                  </span>
                </td>
                <td>
                  {schedule.location && (
                    <div className="sch-table-cell">
                      {getPlatformIcon(schedule.location)}
                      <a href={schedule.location} target="_blank" rel="noopener">
                        {truncateUrl(schedule.location)}
                      </a>
                    </div>
                  )}
                </td>
                <td>
                  <div className="sch-chip-container">
                    {schedule.participants.slice(0, 2).map((participant, i) => (
                      <span
                        key={i}
                        className="sch-chip"
                        style={{ backgroundColor: `${getResponseColor(participant.response_status)}20` }}
                      >
                        {participant.group ? <GroupIcon /> : <PersonIcon />}
                        {participant.user
                          ? `${participant.user.first_name} ${participant.user.last_name}`
                          : participant.group.name}
                      </span>
                    ))}
                    {schedule.participants.length > 2 && (
                      <span className="sch-chip">+{schedule.participants.length - 2}</span>
                    )}
                  </div>
                </td>
                <td>
                  <div className="sch-action-btns">
                    <button
                      className="sch-btn sch-btn-icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(schedule.location, '_blank');
                      }}
                    >
                      <ArrowForwardIcon />
                    </button>
                    <button
                      className="sch-btn sch-btn-icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDialog(schedule);
                      }}
                    >
                      <EditIcon />
                    </button>
                    <button
                      className="sch-btn sch-btn-icon sch-btn-error"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSchedule(schedule.id);
                      }}
                    >
                      <DeleteIcon />
                    </button>
                  </div>
                </td>
              </tr>
              {expandedSchedule === schedule.id && (
                <tr>
                  <td colSpan="5">
                    <div className="sch-table-expanded">
                      <p>{schedule.description}</p>
                      <div className="sch-location">
                        <span>{schedule.location || 'No location specified'}</span>
                      </div>
                      <div className="sch-participants">
                        <span>Participants:</span>
                        <div className="sch-chip-container">
                          {schedule.participants.map((participant, i) => {
                            const response = responseOptions.find(opt => opt.value === participant.response_status);
                            return (
                              <span
                                key={i}
                                className="sch-chip"
                                style={{ backgroundColor: `${getResponseColor(participant.response_status)}20` }}
                                title={response ? response.label : participant.response_status}
                              >
                                {participant.group ? <GroupIcon /> : <PersonIcon />}
                                {participant.user
                                  ? `${participant.user.first_name} ${participant.user.last_name}`
                                  : participant.group.name}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                      <div className="sch-response">
                        <span>Your Response:</span>
                        <div className="sch-response-btns">
                          {responseOptions.map((option) => (
                            <button
                              key={option.value}
                              className="sch-btn sch-btn-response"
                              style={{ borderColor: option.color, color: option.color }}
                              onClick={() => handleRespondToSchedule(schedule.id, option.value)}
                            >
                              {option.value === 'accepted' && <CheckIcon />}
                              {option.value === 'declined' && <CloseIcon />}
                              {option.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <button
                        className="sch-btn sch-btn-primary"
                        onClick={() => window.open(schedule.location, '_blank')}
                      >
                        <CalendarIcon />
                        Open Meeting Link
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <div className="sch-container">
        {snackbar.open && (
          <div className={`sch-alert sch-alert-${snackbar.severity}`}>
            <span>{snackbar.message}</span>
            <button onClick={() => setSnackbar(prev => ({ ...prev, open: false }))} className="sch-alert-close">
              <CloseIcon />
            </button>
          </div>
        )}
        <div className="sch-header">
          <h1>
            Schedule Manager
            <span className="sch-badge">
              {schedules.length}
              <CalendarIcon />
            </span>
          </h1>
          <div className="sch-header-btns">
            <button className="sch-btn sch-btn-primary" onClick={() => handleOpenDialog()}>
              <AddIcon />
              New Schedule
            </button>
            <button
              className="sch-btn sch-btn-secondary"
              onClick={() => {
                schedules.forEach(schedule => {
                  window.open(schedule.location, '_blank');
                });
              }}
              disabled={schedules.length === 0}
            >
              <CalendarIcon />
              Export All Links
            </button>
          </div>
        </div>
        <div className="sch-filters">
          <div className="sch-search">
            <div className="sch-search-input">
              <SearchIcon />
              <input
                type="text"
                placeholder="Search schedules..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
              />
            </div>
          </div>
          <div className="sch-date-picker">
            <label>From</label>
            <DatePicker
              value={filters.dateFrom}
              onChange={(newValue) => handleFilterChange('dateFrom', newValue)}
              renderInput={({ inputProps, ...params }) => (
                <input {...inputProps} {...params} />
              )}
            />
          </div>
          <div className="sch-date-picker">
            <label>To</label>
            <DatePicker
              value={filters.dateTo}
              onChange={(newValue) => handleFilterChange('dateTo', newValue)}
              renderInput={({ inputProps, ...params }) => (
                <input {...inputProps} {...params} />
              )}
            />
          </div>
          <div className="sch-checkbox">
            <input
              type="checkbox"
              checked={filters.showPast}
              onChange={(e) => handleFilterChange('showPast', e.target.checked)}
            />
            <span>Show Past Events</span>
          </div>
          <button className="sch-btn sch-btn-icon" onClick={resetFilters}>
            <RefreshIcon />
          </button>
        </div>
        {isLoading ? (
          <div className="sch-loading">
            <div className="sch-progress"></div>
          </div>
        ) : error ? (
          <div className="sch-no-data sch-error">{error}</div>
        ) : schedules.length === 0 ? (
          <div className="sch-no-data">No schedules found</div>
        ) : renderDesktopScheduleTable()}
        <div className="sch-pagination">
          <TablePagination
            rowsPerPageOptions={[5, 10, 25]}
            component="div"
            count={pagination.count}
            rowsPerPage={rowsPerPage}
            page={pagination.page - 1}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        </div>
        {/* Modal */}
        {openDialog && (
          <div className="sch-dialog">
            <div className="sch-dialog-backdrop" onClick={handleCloseDialog}></div>
            <div className="sch-dialog-content sch-dialog-compact">
              <div className="sch-dialog-header">
                <h3>{currentSchedule?.id ? 'Edit Schedule' : 'Create New Schedule'}</h3>
                <button className="sch-dialog-close" onClick={handleCloseDialog}>
                  <CloseIcon />
                </button>
              </div>
              <div className="sch-dialog-body">
                <div className="sch-form-field">
                  <label>Title</label>
                  <input
                    type="text"
                    value={currentSchedule?.title || ''}
                    onChange={(e) => setCurrentSchedule({ ...currentSchedule, title: e.target.value })}
                  />
                </div>
                <div className="sch-form-field sch-form-field-full">
                  <label>Description</label>
                  <textarea
                    rows="4"
                    value={currentSchedule?.description || ''}
                    onChange={(e) => setCurrentSchedule({ ...currentSchedule, description: e.target.value })}
                  ></textarea>
                </div>
                <div className="sch-form-grid">
                  <div className="sch-form-field">
                    <label>Start Time</label>
                    <DateTimePicker
                      label="Start Time"
                      value={currentSchedule?.start_time}
                      onChange={(newValue) => setCurrentSchedule({ ...currentSchedule, start_time: newValue })}
                      renderInput={(params) => <TextField fullWidth size="small" {...params} />}
                    />
                  </div>
                  <div className="sch-form-field">
                    <label>End Time</label>
                    <DateTimePicker
                      label="End Time"
                      value={currentSchedule?.end_time}
                      onChange={(newValue) => setCurrentSchedule({ ...currentSchedule, end_time: newValue })}
                      minDateTime={currentSchedule?.start_time}
                      renderInput={(params) => <TextField fullWidth size="small" {...params} />}
                    />
                  </div>
                </div>
                <div className="sch-form-field">
                  <label>Location</label>
                  <input
                    type="text"
                    value={currentSchedule?.location || ''}
                    onChange={(e) => setCurrentSchedule({ ...currentSchedule, location: e.target.value })}
                  />
                </div>
                <div className="sch-form-field">
                  <label className="sch-checkbox">
                    <input
                      type="checkbox"
                      checked={currentSchedule?.is_all_day || false}
                      onChange={(e) => setCurrentSchedule({ ...currentSchedule, is_all_day: e.target.checked })}
                    />
                    <span>All Day Event</span>
                  </label>
                </div>
                <div className="sch-form-field sch-form-field-full">
                  <h4>Participants</h4>
                  {renderUserAutocomplete()}
                  {renderGroupAutocomplete()}
                </div>
              </div>
              <div className="sch-dialog-actions">
                <button className="sch-btn sch-btn-cancel" onClick={handleCloseDialog}>
                  Cancel
                </button>
                <button
                  className="sch-btn sch-btn-confirm"
                  onClick={handleSaveSchedule}
                  disabled={!currentSchedule?.title || !currentSchedule?.start_time || !currentSchedule?.end_time}
                >
                  {currentSchedule?.id ? 'Update Schedule' : 'Create Schedule'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </LocalizationProvider>
  );
};

export default ScheduleManagement;