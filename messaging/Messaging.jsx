import { useWebSocket } from '../../../hooks/useWebSocket';
import { messagingAPI, groupsAPI, userAPI } from '../../../config';
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon,
  Send as SendIcon, Email as EmailIcon, Person as PersonIcon,
  Group as GroupIcon, MoreVert as MoreIcon, ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon, MarkEmailRead as ReadIcon,
  MarkEmailUnread as UnreadIcon, Reply as ReplyIcon,
  Forward as ForwardIcon, Attachment as AttachmentIcon,
  Search as SearchIcon, FilterList as FilterIcon, Refresh as RefreshIcon,
  Close as CloseIcon, Check as CheckIcon
} from '@mui/icons-material';
import { TablePagination, Chip } from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { format, parseISO } from 'date-fns';
import { useSnackbar } from 'notistack';

import MessageTypeManager from './MessageTypeManager';
import { debounce } from 'lodash';
import './Messaging.jsx';

const Messaging = () => {
  const { enqueueSnackbar } = useSnackbar();
  const [messageTypeDialogOpen, setMessageTypeDialogOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [messageTypes, setMessageTypes] = useState([]);
  const [messageTypesLoading, setMessageTypesLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [openDialog, setOpenDialog] = useState(false);
  const [currentMessage, setCurrentMessage] = useState(null);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [expandedMessage, setExpandedMessage] = useState(null);
  const [replyMode, setReplyMode] = useState(false);
  const [forwardMode, setForwardMode] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const fileInputRef = useRef(null);
  const [pagination, setPagination] = useState({
    count: 0,
    next: null,
    previous: null,
    page: 1
  });
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    search: '',
    type: 'all',
    status: 'all',
    dateFrom: null,
    dateTo: null,
    readStatus: 'all'
  });
  const [sending, setSending] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const { lastMessage, sendMessage } = useWebSocket(
    `ws://${window.location.host}/ws/messages/`
  );

  const fetchUsers = useCallback(async (searchQuery = '') => {
    try {
      const params = {
        search: searchQuery,
        page_size: 50,
      };
      const usersRes = await userAPI.getUsers(params);
      setUsers(usersRes.data.results || []);
    } catch (error) {
      enqueueSnackbar('Failed to load users', { variant: 'error' });
      console.error('Error fetching users:', error);
    }
  }, [enqueueSnackbar]);

  const debouncedFetchUsers = useCallback(
    debounce((query) => {
      fetchUsers(query);
    }, 300),
    [fetchUsers]
  );

  const handleUserSearch = (event, value) => {
    setUserSearchQuery(value);
    debouncedFetchUsers(value);
  };

  const fetchMessageTypes = async () => {
    try {
      setMessageTypesLoading(true);
      const response = await messagingAPI.getMessageTypes();
      //console.log("fetchMessageTypes full response:", response);
      if (response.status === 200) {
        const types = Array.isArray(response.data.results) ? response.data.results : 
                     Array.isArray(response.data) ? response.data : [];
        //console.log("Parsed messageTypes:", types);
        setMessageTypes(types);
      } else {
        console.error("Unexpected response status:", response.status);
        setMessageTypes([]);
      }
    } catch (error) {
      console.error("Error fetching message types:", error.response ? error.response.data : error.message);
      enqueueSnackbar('Failed to load message types', { variant: 'error' });
      setMessageTypes([]);
    } finally {
      setMessageTypesLoading(false);
    }
  };

  useEffect(() => {
    fetchMessageTypes();
  }, []);

  useEffect(() => {
    //console.log("messageTypes updated:", messageTypes);
  }, [messageTypes, messageTypesLoading]); // Removed currentMessage from dependencies

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = {
        page: pagination.page,
        page_size: rowsPerPage,
        ...(filters.search && { search: filters.search }),
        ...(filters.type !== 'all' && { type: filters.type }),
        ...(filters.status !== 'all' && { status: filters.status }),
        ...(filters.readStatus !== 'all' && { read_status: filters.readStatus }),
        ...(filters.dateFrom && { date_from: format(filters.dateFrom, 'yyyy-MM-dd') }),
        ...(filters.dateTo && { date_to: format(filters.dateTo, 'yyyy-MM-dd') })
      };
      const [messagesRes, groupsRes, unreadRes] = await Promise.all([
        messagingAPI.getMessages(params),
        groupsAPI.getGroups(),
        messagingAPI.getUnreadCount(),
      ]);
      setMessages(messagesRes.data || []);

      //console.log("Messages fetched:", messagesRes.data);
      setGroups(groupsRes.data.results || []);
      setUnreadCount(unreadRes.data.count || 0);
      setPagination({
        count: messagesRes.data.count || 0,
        next: messagesRes.data.next,
        previous: messagesRes.data.previous,
        page: pagination.page
      });
      await fetchUsers();
    } catch (error) {
      setError(error.message);
      enqueueSnackbar('Failed to load data', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [pagination.page, rowsPerPage, filters]);

  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data);
      if (data.type === 'new_message') {
        if (pagination.page === 1) {
          setMessages(prev => [data.message, ...prev.slice(0, -1)]);
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
        if (!data.message.is_read) {
          setUnreadCount(prev => prev + 1);
        }
      } else if (data.type === 'message_read') {
        setMessages(prev => prev.map(m => 
          m.id === data.message_id ? { ...m, is_read: true } : m
        ));
      }
    }
  }, [lastMessage, pagination.page]);

  const formatDate = (dateString) => {
    return format(parseISO(dateString), 'MMM d, yyyy - h:mm a');
  };

  const handleOpenDialog = (message = null, reply = false, forward = false) => {
    if (messageTypesLoading) return; // Prevent opening until messageTypes are loaded
    console.log("Opening dialog, messageTypes:", messageTypes);
    const defaultMessage = { 
      subject: '', 
      message_type: messageTypes.length > 0 ? messageTypes[0].id : null, 
      content: '',
      status: 'draft',
      attachments: []
    };
    if (message) {
      if (reply) {
        setCurrentMessage({
          ...defaultMessage,
          subject: `Re: ${message.subject}`,
          content: `\n\n---------- Original Message ----------\nFrom: ${message.sender}\nDate: ${formatDate(message.sent_at)}\nSubject: ${message.subject}\n\n${message.content}`,
          parent_message: message.id
        });
        const senderUser = users.find(u => u.email === message.sender);
        setSelectedUsers(senderUser ? [senderUser] : [{ email: message.sender }]);
        setReplyMode(true);
      } else if (forward) {
        setCurrentMessage({
          ...defaultMessage,
          subject: `Fwd: ${message.subject}`,
          content: `\n\n---------- Forwarded Message ----------\nFrom: ${message.sender.first_name} ${message.sender.last_name}\nDate: ${formatDate(message.sent_at)}\nSubject: ${message.subject}\n\n${message.content}`,
          parent_message: message.id,
          is_forward: true
        });
        setForwardMode(true);
      } else {
        setCurrentMessage({
          ...message,
          message_type: messageTypes.find(t => t.id === message.message_type || t.value === message.message_type)?.id || message.message_type
        });
        setSelectedUsers(message.recipients.filter(r => r.recipient).map(r => ({
          id: r.recipient.id,
          email: r.recipient.email,
          first_name: r.recipient.first_name,
          last_name: r.recipient.last_name
        })));
        setSelectedGroups(message.recipients.filter(r => r.recipient_group).map(r => ({
          id: r.recipient_group.id,
          name: r.recipient_group.name
        })));
        setAttachments(message.attachments);
      }
    } else {
      setCurrentMessage(defaultMessage); // Set default message_type here
      setSelectedUsers([]);
      setSelectedGroups([]);
      setAttachments([]);
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setReplyMode(false);
    setForwardMode(false);
    setCurrentMessage(null);
    setSelectedUsers([]);
    setSelectedGroups([]);
    setAttachments([]);
  };


const handleSendMessage = async () => {
  setSending(true);
  try {
    const payload = {
      subject: currentMessage.subject,
      content: currentMessage.content,
      message_type: currentMessage.message_type,
      status: 'sent',
      parent_message: currentMessage.parent_message || null,
      is_forward: !!currentMessage.is_forward,
      recipient_users: selectedUsers.map(u => u.id),
      recipient_groups: selectedGroups.map(g => g.id),
      // If you have attachments, handle them separately
    };
    const response = currentMessage.id 
      ? await messagingAPI.updateMessage(currentMessage.id, payload)
      : await messagingAPI.createMessage(payload);

    enqueueSnackbar(
      replyMode ? 'Reply sent successfully!' : 
      forwardMode ? 'Message forwarded successfully!' : 
      'Message sent successfully!',
      { variant: 'success' }
    );
    fetchData();
    handleCloseDialog();
  } catch (error) {
    enqueueSnackbar(
      error.message || 'Error sending message. Please check your input and try again. If the issue persists, contact support.',
      { variant: 'error' }
    );
    console.error('Error sending message:', error.response?.data || error.message);
  } finally {
    setSending(false);
  }
};

  const handleSaveDraft = async () => {
    try {
      const formData = new FormData();
      formData.append('subject', currentMessage.subject);
      formData.append('content', currentMessage.content);
      formData.append('message_type', currentMessage.message_type);
      formData.append('status', 'draft');
      selectedUsers.forEach(user => 
        formData.append('recipient_users', user.id)
      );
      selectedGroups.forEach(group => 
        formData.append('recipient_groups', group.id)
      );
      const response = currentMessage.id 
        ? await messagingAPI.updateMessage(currentMessage.id, formData)
        : await messagingAPI.createMessage(formData);
      enqueueSnackbar('Draft saved successfully!', { variant: 'success' });
      fetchData();
      handleCloseDialog();
    } catch (error) {
      enqueueSnackbar('Error saving draft', { variant: 'error' });
      console.error('Error saving draft:', error);
    }
  };

  const handleDeleteForUser = async (messageId) => {
    setDeletingId(messageId);
    try {
      await messagingAPI.deleteForUser(messageId);
      enqueueSnackbar('Message deleted from your dashboard.', { variant: 'success' });
      setMessages(prev => prev.filter(msg => msg.id !== messageId));
    } catch (error) {
      enqueueSnackbar('Failed to delete message.', { variant: 'error' });
      console.error('Delete error:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const handleMarkAsRead = async (id) => {
    try {
      await messagingAPI.markAsRead(id);
      setMessages(prev => prev.map(m => 
        m.id === id ? { ...m, is_read: true } : m
      ));
      setUnreadCount(prev => prev - 1);
      sendMessage(JSON.stringify({
        type: 'mark_as_read',
        message_id: id
      }));
    } catch (error) {
      console.error('Error marking as read:', error);
    }
  };

  const handleRemoveRecipient = (recipientToRemove) => {
    if (recipientToRemove.email) {
      setSelectedUsers(selectedUsers.filter(user => user.id !== recipientToRemove.id));
    } else {
      setSelectedGroups(selectedGroups.filter(group => group.id !== recipientToRemove.id));
    }
  };

  const toggleExpandMessage = (messageId) => {
    setExpandedMessage(expandedMessage === messageId ? null : messageId);
    if (expandedMessage !== messageId) {
      const message = messages.find(m => m.id === messageId);
      if (message && !message.is_read) {
        handleMarkAsRead(messageId);
      }
    }
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
      type: 'all',
      status: 'all',
      dateFrom: null,
      dateTo: null,
      readStatus: 'all'
    });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handleAddAttachment = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setIsUploading(true);
    try {
      const newAttachments = [];
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        newAttachments.push({
          file,
          original_filename: file.name,
          id: `temp-${Date.now()}-${i}`,
          uploaded_at: new Date().toISOString()
        });
      }
      setAttachments(prev => [...prev, ...newAttachments]);
    } catch (error) {
      enqueueSnackbar('Error adding attachments', { variant: 'error' });
      console.error('Error adding attachments:', error);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleRemoveAttachment = (attachmentId) => {
    setAttachments(prev => prev.filter(a => a.id !== attachmentId));
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'sent':
        return '#7226FF';
      case 'draft':
        return '#6251a4';
      default:
        return '#6251a4';
    }
  };

  const handleChangePage = (event, newPage) => {
    setPagination(prev => ({ ...prev, page: newPage + 1 }));
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const renderMobileMessageCards = () => (
    <div className="msg-card-list">
      {messages.map((message) => (
        <div key={message.id} className="msg-card">
          <div className="msg-card-header">
            <div className="msg-card-title">
              {message.is_read ? <ReadIcon /> : <UnreadIcon />}
              <span className={message.is_read ? '' : 'unread'}>{message.subject}</span>
              {message.is_read && (
                <span style={{ marginLeft: 8 }}>
                  <Chip label="Read" size="small" color="success" />
                </span>
              )}
            </div>
            <button
              className="msg-expand-btn"
              onClick={() => toggleExpandMessage(message.id)}
            >
              {expandedMessage === message.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </button>
          </div>
          <div className="msg-card-meta">
            <span>From: {message.sender.email}</span>
            <span>{formatDate(message.sent_at)}</span>
          </div>
          <div className={`msg-card-content ${expandedMessage === message.id ? 'expanded' : ''}`}>
            <div className="msg-card-body">
              <p>{message.content}</p>
              {message.attachments.length > 0 && (
                <div className="msg-attachments">
                  <h4>Attachments:</h4>
                  {message.attachments.map((attachment, index) => (
                    <div key={index} className="msg-attachment-item">
                      <AttachmentIcon />
                      <a href={attachment.file} target="_blank" rel="noopener noreferrer">
                        {attachment.original_filename}
                      </a>
                    </div>
                  ))}
                </div>
              )}
              <h4>Recipients:</h4>
              <div className="msg-chip-container">
                {message.recipients.map((recipient, i) => (
                  <span key={i} className="msg-chip">
                    {recipient.recipient ? 
                      `${recipient.recipient}` : 
                      recipient.recipient_group}
                    {recipient.recipient_group ? <GroupIcon /> : <PersonIcon />}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="msg-card-actions">
            <div className="msg-action-group">
              <button
                className="msg-btn msg-btn-secondary"
                onClick={() => handleOpenDialog(message, true)}
              >
                <ReplyIcon /> Reply
              </button>
              <button
                className="msg-btn msg-btn-secondary"
                onClick={() => handleOpenDialog(message, false, true)}
              >
                <ForwardIcon /> Forward
              </button>
            </div>
            <div className="msg-action-group">
              {message.status === 'draft' && (
                <button
                  className="msg-btn msg-btn-edit"
                  onClick={() => handleOpenDialog(message)}
                >
                  <EditIcon /> Edit
                </button>
              )}
              <button
                className="msg-btn msg-btn-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteForUser(message.id);
                }}
                disabled={deletingId === message.id}
                title="Delete for me"
              >
                {deletingId === message.id ? <div className="msg-spinner-small"></div> : <DeleteIcon />}
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  const renderDesktopMessageTable = () => (
    <div className="msg-table-container">
      <table className="msg-table">
        <thead>
          <tr>
            <th style={{ width: '40px' }}></th>
            <th><span>Subject</span></th>
            <th><span>Type</span></th>
            <th><span>From</span></th>
            <th><span>Date</span></th>
            <th><span>Recipients</span></th>
            <th><span>Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {messages.map((message) => (
            <React.Fragment key={message.id}>
              <tr
                className={expandedMessage === message.id ? 'expanded' : ''}
                onClick={() => toggleExpandMessage(message.id)}
              >
                <td>
                  {message.is_read ? <ReadIcon /> : <UnreadIcon />}
                </td>
                <td>
                  <span className={message.is_read ? '' : 'unread'}>{message.subject}</span>
                  {message.is_read && (
                    <span style={{ marginLeft: 8 }}>
                      <Chip label="Read" size="small" color="success" />
                    </span>
                  )}
                </td>
                <td>
                  <span
                    className="msg-chip"
                    style={{ backgroundColor: getStatusColor(message.status) }}
                  >
                    {messageTypes.find(t => t.id === message.message_type)?.label || message.message_type_display}
                  </span>
                </td>
                <td>
                  <span>{message.sender}</span>
                </td>
                <td>
                  <span>{formatDate(message.sent_at)}</span>
                </td>
                <td>
                  <div className="msg-chip-container">
                    {message.recipients.slice(0, 2).map((recipient, i) => (
                      <span key={i} className="msg-chip">
                        {recipient.recipient 
                          ? recipient.recipient 
                          : recipient.recipient_group}
                        {recipient.recipient_group ? <GroupIcon /> : <PersonIcon />}
                      </span>
                    ))}
                    {message.recipients.length > 2 && (
                      <span className="msg-chip">+{message.recipients.length - 2}</span>
                    )}
                  </div>
                </td>
                <td>
                  <div className="msg-action-btns">
                    <button
                      className="msg-btn msg-btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDialog(message, true);
                      }}
                      title="Reply"
                    >
                      <ReplyIcon />
                    </button>
                    <button
                      className="msg-btn msg-btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDialog(message, false, true);
                      }}
                      title="Forward"
                    >
                      <ForwardIcon />
                    </button>
                    {message.status === 'draft' && (
                      <button
                        className="msg-btn msg-btn-edit"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDialog(message);
                        }}
                        title="Edit"
                      >
                        <EditIcon />
                      </button>
                    )}
                    <button
                      className="msg-btn msg-btn-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteForUser(message.id);
                      }}
                      disabled={deletingId === message.id}
                      title="Delete for me"
                    >
                      {deletingId === message.id ? <div className="msg-spinner-small"></div> : <DeleteIcon />}
                    </button>
                  </div>
                </td>
              </tr>
              <tr>
                <td colSpan="7" className="msg-expand-content">
                  <div className={`msg-expand-body ${expandedMessage === message.id ? 'expanded' : ''}`}>
                    <p>{message.content}</p>
                    {message.attachments.length > 0 && (
                      <div className="msg-attachments">
                        <h4>Attachments:</h4>
                        {message.attachments.map((attachment, index) => (
                          <div key={index} className="msg-attachment-item">
                            <AttachmentIcon />
                            <a href={attachment.file} target="_blank" rel="noopener noreferrer">
                              {attachment.original_filename}
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                    <h4>Recipients:</h4>
                    <div className="msg-chip-container">
                      {message.recipients.map((recipient, i) => (
                        <span key={i} className="msg-chip">
                          {recipient.recipient ? 
                            `${recipient.recipient.first_name} ${recipient.recipient.last_name}` : 
                            recipient.recipient_group.name}
                          {recipient.recipient_group ? <GroupIcon /> : <PersonIcon />}
                        </span>
                      ))}
                    </div>
                  </div>
                </td>
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderUserAutocomplete = () => (
    <div className="msg-form-field msg-form-field-full">
      <label>Select Users</label>
      <div className="msg-autocomplete">
        <input
          type="text"
          placeholder="Search users"
          value={userSearchQuery}
          onChange={(e) => handleUserSearch(e, e.target.value)}
        />
        <div className="msg-autocomplete-options">
          {users.map(user => (
            <div
              key={user.id}
              className={`msg-autocomplete-option ${selectedUsers.some(u => u.id === user.id) ? 'selected' : ''}`}
              onClick={() => {
                if (selectedUsers.some(u => u.id === user.id)) {
                  setSelectedUsers(selectedUsers.filter(u => u.id !== user.id));
                } else {
                  setSelectedUsers([...selectedUsers, user]);
                }
              }}
            >
              <span>{`${user.first_name} ${user.last_name} (${user.email})`}</span>
              {selectedUsers.some(u => u.id === user.id) && <CheckIcon />}
            </div>
          ))}
        </div>
      </div>
      <div className="msg-chip-container">
        {selectedUsers.map(user => (
          <span key={user.id} className="msg-chip">
            {`${user.first_name} ${user.last_name}`}
            <button onClick={() => handleRemoveRecipient(user)}>
              <CloseIcon />
            </button>
          </span>
        ))}
      </div>
    </div>
  );

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        const response = await groupsAPI.getGroups();
        setGroups(response.data.results || response.data); // Adjust based on API response shape
      } catch (error) {
        enqueueSnackbar('Failed to fetch groups', { variant: 'error' });
      }
    };
    fetchGroups();
  }, []);

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <div className="msg-container">
        <div className="msg-header">
          <h1>
            Messaging Center
            <span className="msg-unread-count">{unreadCount}</span>
            <EmailIcon />
          </h1>
          <div className="msg-header-actions">
            <button
              className="msg-btn msg-btn-primary"
              onClick={() => handleOpenDialog()}
              disabled={messageTypesLoading}
            >
              <SendIcon /> New Message
            </button>
            <button
              className="msg-btn msg-btn-outline"
              onClick={() => setMessageTypeDialogOpen(true)}
              disabled={messageTypesLoading}
            >
              <EditIcon /> Manage Message Types
            </button>
          </div>
        </div>

        <div className="msg-filters">
          <div className="msg-filter-item">
            <div className="msg-search-input">
              <SearchIcon />
              <input
                type="text"
                placeholder="Search messages..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
              />
            </div>
          </div>
          <div className="msg-filter-item">
            <label>Message Type</label>
            <select
              value={filters.type}
              onChange={(e) => handleFilterChange('type', e.target.value)}
              disabled={messageTypes.length === 0}
            >
              <option value="all">All Types</option>
              {messageTypes.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>
          <div className="msg-filter-item">
            <label>Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
            >
              <option value="all">All Statuses</option>
              <option value="sent">Sent</option>
              <option value="draft">Draft</option>
            </select>
          </div>
          <div className="msg-filter-item">
            <label>Read Status</label>
            <select
              value={filters.readStatus}
              onChange={(e) => handleFilterChange('readStatus', e.target.value)}
            >
              <option value="all">All</option>
              <option value="read">Read</option>
              <option value="unread">Unread</option>
            </select>
          </div>
          <div className="msg-filter-item">
            <label>From</label>
            <DatePicker
              value={filters.dateFrom}
              onChange={(newValue) => handleFilterChange('dateFrom', newValue)}
              renderInput={(params) => (
                <input
                  {...params.inputProps}
                  className="msg-date-input"
                  placeholder="Select date"
                />
              )}
            />
          </div>
          <div className="msg-filter-item">
            <label>To</label>
            <DatePicker
              value={filters.dateTo}
              onChange={(newValue) => handleFilterChange('dateTo', newValue)}
              renderInput={(params) => (
                <input
                  {...params.inputProps}
                  className="msg-date-input"
                  placeholder="Select date"
                />
              )}
            />
          </div>
          <div className="msg-filter-actions">
            <button className="msg-btn msg-btn-icon" onClick={resetFilters} title="Reset Filters">
              <RefreshIcon />
            </button>
            <button className="msg-btn msg-btn-icon" title="Filter Options">
              <FilterIcon />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="msg-loading">
            <div className="msg-spinner"></div>
          </div>
        ) : error ? (
          <div className="msg-error">{error}</div>
        ) : messages.length === 0 ? (
          <div className="msg-no-data">No messages found</div>
        ) : window.innerWidth <= 600 ? renderMobileMessageCards() : renderDesktopMessageTable()}

        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component="div"
          count={pagination.count}
          rowsPerPage={rowsPerPage}
          page={pagination.page - 1}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />

        <div className="msg-dialog" style={{ display: openDialog ? 'block' : 'none' }}>
          <div className="msg-dialog-backdrop" onClick={handleCloseDialog}></div>
          <div className="msg-dialog-content">
            <div className="msg-dialog-header">
              <h3>
                {replyMode ? 'Reply to Message' : forwardMode ? 'Forward Message' : currentMessage?.id ? 'Edit Message' : 'Compose New Message'}
              </h3>
              <button className="msg-dialog-close" onClick={handleCloseDialog}>
                <CloseIcon />
              </button>
            </div>
            <div className="msg-dialog-body">
              <div className="msg-form-field">
                <label>Subject</label>
                <input
                  type="text"
                  value={currentMessage?.subject || ''}
                  onChange={(e) => setCurrentMessage({...currentMessage, subject: e.target.value})}
                />
              </div>
              <div className="msg-form-field">
                <label>Message Type</label>
                <select
                  value={currentMessage?.message_type || ''}
                  onChange={(e) => setCurrentMessage({...currentMessage, message_type: e.target.value})}
                  disabled={messageTypes.length === 0}
                >
                  <option value="" disabled>Select a type</option>
                  {messageTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="msg-form-field msg-form-field-full">
                <label>Recipients</label>
                <div className="msg-recipients">
                  {renderUserAutocomplete()}
                  <div className="msg-form-field">
                    <label>Select Groups</label>
                    <div className="msg-autocomplete">
                      <input
                        type="text"
                        placeholder="Search groups"
                        onChange={(e) => {
                          // Placeholder for group search if needed
                        }}
                      />
                      <div className="msg-autocomplete-options">
                        {groups.map(group => (
                          <div
                            key={group.id}
                            className={`msg-autocomplete-option ${selectedGroups.some(g => g.id === group.id) ? 'selected' : ''}`}
                            onClick={() => {
                              if (selectedGroups.some(g => g.id === group.id)) {
                                setSelectedGroups(selectedGroups.filter(g => g.id !== group.id));
                              } else {
                                setSelectedGroups([...selectedGroups, group]);
                              }
                            }}
                          >
                            <span>{group.name}</span>
                            {selectedGroups.some(g => g.id === group.id) && <CheckIcon />}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="msg-chip-container">
                      {selectedGroups.map(group => (
                        <span key={group.id} className="msg-chip">
                          {group.name}
                          <button onClick={() => handleRemoveRecipient(group)}>
                            <CloseIcon />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div className="msg-form-field msg-form-field-full">
                <label>Message Content</label>
                <textarea
                  rows="8"
                  value={currentMessage?.content || ''}
                  onChange={(e) => setCurrentMessage({...currentMessage, content: e.target.value})}
                ></textarea>
              </div>
              <div className="msg-form-field msg-form-field-full">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleAddAttachment}
                  style={{ display: 'none' }}
                  multiple
                />
                <button
                  className="msg-btn msg-btn-outline"
                  onClick={() => fileInputRef.current.click()}
                  disabled={isUploading}
                >
                  <AttachmentIcon /> Add Attachment
                  {isUploading && <div className="msg-spinner-small"></div>}
                </button>
                {attachments.length > 0 && (
                  <div className="msg-attachments">
                    <h4>Attachments:</h4>
                    {attachments.map((attachment) => (
                      <div key={attachment.id} className="msg-attachment-item">
                        <AttachmentIcon />
                        <span>{attachment.original_filename}</span>
                        {attachment.file_url && (
                          <a href={attachment.file_url} target="_blank" rel="noopener noreferrer">
                            Download
                          </a>
                        )}
                        <button
                          className="msg-btn-icon"
                          onClick={() => handleRemoveAttachment(attachment.id)}
                        >
                          <CloseIcon />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="msg-dialog-actions">
              {!replyMode && !forwardMode && currentMessage?.status === 'draft' && (
                <button
                  className="msg-btn msg-btn-outline"
                  onClick={handleSaveDraft}
                  disabled={isUploading}
                >
                  Save Draft
                </button>
              )}
              <button
                className="msg-btn msg-btn-cancel"
                onClick={handleCloseDialog}
                disabled={isUploading}
              >
                Cancel
              </button>
              <button
                className="msg-btn msg-btn-confirm"
                onClick={handleSendMessage}
                disabled={
                  sending ||
                  !currentMessage?.subject || 
                  !currentMessage?.content || 
                  !currentMessage?.message_type ||
                  (selectedUsers.length === 0 && selectedGroups.length === 0) ||
                  isUploading
                }
              >
                <SendIcon /> {sending ? <div className="msg-spinner-small" style={{ display: 'inline-block', verticalAlign: 'middle' }}></div> : (replyMode ? 'Send Reply' : forwardMode ? 'Forward' : 'Send Message')}
              </button>
            </div>
          </div>
        </div>
        <MessageTypeManager
          open={messageTypeDialogOpen}
          onClose={() => setMessageTypeDialogOpen(false)}
          onUpdate={fetchMessageTypes}
          messageTypes={messageTypes}
          loading={messageTypesLoading}
        />
      </div>
    </LocalizationProvider>
  );
};

export default Messaging;