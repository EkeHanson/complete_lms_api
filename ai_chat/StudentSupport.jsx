import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Paper, Typography, Button, List, ListItem, Box, TextField, IconButton, CircularProgress, Snackbar, Alert
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import './StudentSupport.css';
import { API_BASE_URL, chatAPI } from '../../../config';

const formatCourseDetails = (course) => {
  if (!course) return null;
  const {
    title,
    description,
    learning_outcomes,
    discount_price,
    price
  } = course;

  // Format description to first 10 words
  const descPreview = description
    ? description.split(' ').slice(0, 10).join(' ') + '...'
    : '';

  // Format learning outcomes
  let outcomes = '';
  if (Array.isArray(learning_outcomes)) {
    outcomes = learning_outcomes.join(', ');
  } else if (typeof learning_outcomes === 'string') {
    try {
      const parsed = JSON.parse(learning_outcomes);
      outcomes = Array.isArray(parsed) ? parsed.join(', ') : parsed;
    } catch {
      outcomes = learning_outcomes;
    }
  }

  return (
    <Box sx={{ mb: 2, p: 2, border: '1px solid #e0e0e0', borderRadius: 2, background: '#f9f9f9' }}>
      <Typography variant="h6" color="primary">{title}</Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        <strong>Description:</strong> {descPreview}
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        <strong>Learning Outcomes:</strong> {outcomes}
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        <strong>Price:</strong> {price ? `₦${price}` : 'N/A'}
      </Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        <strong>Discount Price:</strong> {discount_price ? `₦${discount_price}` : 'N/A'}
      </Typography>
    </Box>
  );
};

const StudentSupport = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [wsError, setWsError] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [sending, setSending] = useState(false);
  const [waitingForAI, setWaitingForAI] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState('error');
  const [courseDetails, setCourseDetails] = useState([]);
  const [editingIndex, setEditingIndex] = useState(null);
  const [editValue, setEditValue] = useState('');
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);

  const tenantId = localStorage.getItem('tenant_id');
  const tenantSchema = localStorage.getItem('tenant_schema');
  const accessToken = localStorage.getItem('access_token');

  // Show error snackbar
  const showError = (message) => {
    setSnackbarMessage(message);
    setSnackbarSeverity('error');
    setSnackbarOpen(true);
  };

  // Create new session with proper error handling
  const handleNewSession = useCallback(async () => {
    try {
      setSessionReady(false);
      const res = await chatAPI.createSession(tenantId);
      if (res.data?.session) {
        setSelectedSession(res.data.session);
        setSessions(prev => [res.data.session, ...prev]);
        setMessages([]);
        setSessionReady(true);
        return res.data.session;
      }
      throw new Error('Session creation failed');
    } catch (error) {
      console.error('Session creation error:', error);
      showError('Failed to create new session. Please try again.');
      setSessionReady(false);
      return null;
    }
  }, [tenantId]);

  // Load sessions and handle initial session creation
  useEffect(() => {
    let isMounted = true;
    
    const loadSessions = async () => {
      try {
        setLoadingSessions(true);
        const res = await chatAPI.getSessions(tenantId);
        if (!isMounted) return;
        
        const sessionList = res.data.sessions || [];
        setSessions(sessionList);
        
        if (sessionList.length > 0) {
          setSelectedSession(sessionList[0]);
          setSessionReady(true);
        } else {
          const newSession = await handleNewSession();
          if (newSession) {
            setSelectedSession(newSession);
          }
        }
      } catch (error) {
        console.error('Session load error:', error);
        showError('Failed to load sessions. Please refresh the page.');
      } finally {
        if (isMounted) setLoadingSessions(false);
      }
    };

    if (tenantId) {
      loadSessions();
    } else {
      showError('Missing tenant information');
    }
    
    return () => {
      isMounted = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [tenantId, handleNewSession]);

  // Load messages for selected session
  useEffect(() => {
    if (selectedSession && sessionReady) {
      chatAPI.getSession(selectedSession.id, tenantId)
        .then(res => setMessages(res.data.messages || []))
        .catch(error => {
          console.error('Message load error:', error);
          showError('Failed to load messages');
        });
    }
  }, [selectedSession, tenantId, sessionReady]);

  // WebSocket connection management
  useEffect(() => {
    if (!tenantId || !tenantSchema || !accessToken || !selectedSession || !sessionReady) return;
    
    const connectWebSocket = () => {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const backendUrl = new URL(API_BASE_URL);
      const wsHost = backendUrl.host;

      const wsUrl = `${wsProtocol}//${wsHost}/ws/ai-chat/?tenant_id=${encodeURIComponent(tenantId)}&token=${encodeURIComponent(accessToken)}&session_id=${selectedSession.id}`;
      
      setConnecting(true);
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setWsError(null);
        setConnecting(false);
      };

      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'auth_required') return;

        setWaitingForAI(false); // <-- Always stop loader when a message arrives

        if (data.error) {
          setMessages(prev => [...prev, { text: `Error: ${data.error}`, sender: 'system' }]);
          showError(data.error);
        } else if (data.courses && Array.isArray(data.courses)) {
          setCourseDetails(data.courses);
          if (typeof data.message === 'string') {
            setMessages(prev => [...prev, { text: data.message, sender: 'ai' }]);
          } else {
            setMessages(prev => [...prev, { text: 'Here are some recommended courses:', sender: 'ai' }]);
          }
        } else if (typeof data.message === 'string') {
          setMessages(prev => [...prev, { text: data.message, sender: 'ai' }]);
        }
      };

      wsRef.current.onclose = (event) => {
        setConnecting(false);
        if (!event.wasClean) {
          showError('Connection lost. Reconnecting...');
          setTimeout(() => {
            if (tenantId && tenantSchema && selectedSession && sessionReady) {
              connectWebSocket();
            }
          }, 3000);
        }
      };

      wsRef.current.onerror = (error) => {
        setConnecting(false);
        showError('Connection error. Please try again.');
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
    };
  }, [tenantId, tenantSchema, accessToken, selectedSession, sessionReady]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, courseDetails]);

  // Handle sending messages
  const handleSendMessage = () => {
    if (!input.trim()) return;
    
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      const errorMsg = 'Cannot send message: Connection not ready';
      setMessages(prev => [...prev, { text: errorMsg, sender: 'system' }]);
      showError(errorMsg);
      return;
    }

    try {
      setSending(true);
      setMessages(prev => [...prev, { text: input, sender: 'user' }]);
      wsRef.current.send(JSON.stringify({ message: input }));
      setInput('');
      setWaitingForAI(true);
      setCourseDetails([]); // Clear previous course details on new query
    } catch (error) {
      console.error('Message send error:', error);
      showError('Failed to send message');
      setSending(false);
    }
  };

  // Reset sending state when AI responds
  useEffect(() => {
    if (messages.length > 0 && messages[messages.length - 1].sender === 'ai') {
      setSending(false);
      setWaitingForAI(false);
    }
  }, [messages]);

  // Handle Enter key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Delete session handler
  const handleDeleteSession = (sessionId) => {
    chatAPI.deleteSession(sessionId)
      .then(() => {
        setSessions(prev => prev.filter(s => s.id !== sessionId));
        if (selectedSession?.id === sessionId) {
          setSelectedSession(null);
          setSessionReady(false);
          // Create a new session if we're deleting the current one
          handleNewSession();
        }
      })
      .catch(error => {
        console.error('Session deletion error:', error);
        showError('Failed to delete session');
      });
  };

  // Handle session selection
  const handleSelectSession = (session) => {
    // Close existing connection before switching
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      wsRef.current.close();
    }
    setSelectedSession(session);
    setSessionReady(true);
  };

  // Edit message handler
  const handleEditMessage = (index) => {
    setEditingIndex(index);
    setEditValue(messages[index].text);
  };

  const handleSaveEdit = () => {
    if (!editValue.trim()) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Remove all messages below the edited one
      setMessages(prev => [
        ...prev.slice(0, editingIndex),
        { text: editValue, sender: 'user' }
      ]);
      setEditingIndex(null);
      setEditValue('');
      setWaitingForAI(true); // Show loader
      setCourseDetails([]);  // Clear course details

      wsRef.current.send(JSON.stringify({ message: editValue }));
    }
  };

  return (
    <div className="support-container">
      <Paper elevation={3} className="support-paper">
        <Typography variant="h5" gutterBottom>
          AI Support Chat
        </Typography>
        
        {/* Connection status indicators */}
        {connecting && (
          <Typography color="textSecondary">
            <CircularProgress size={14} sx={{ mr: 1 }} />
            Connecting to chat server...
          </Typography>
        )}
        {!sessionReady && !wsError && (
          <Box display="flex" justifyContent="center" my={2}>
            <CircularProgress size={20} />
            <Typography variant="body2" ml={2}>Initializing session...</Typography>
          </Box>
        )}
        
        <Box className="support-session-list" mb={2}>
          <Typography variant="subtitle1" gutterBottom>
            Your Chat Sessions
          </Typography>
          <Typography variant="body2" color="textSecondary" gutterBottom>
            Select a session to continue or start a new chat.
          </Typography>
          <Button
            variant="outlined"
            onClick={handleNewSession}
            className="support-new-chat-button"
            sx={{ mb: 1 }}
            disabled={!sessionReady || connecting}
          >
            New Chat
          </Button>
          
          {loadingSessions ? (
            <Box display="flex" justifyContent="center">
              <CircularProgress size={24} />
            </Box>
          ) : sessions.length === 0 ? (
            <Typography variant="body2" color="textSecondary">
              No chat sessions found
            </Typography>
          ) : (
            <List>
              {sessions.map(session => (
                <ListItem
                  key={session.id}
                  selected={selectedSession?.id === session.id}
                  button
                  onClick={() => handleSelectSession(session)}
                  className="support-session-item"
                  disabled={!sessionReady || connecting}
                  secondaryAction={
                    <IconButton 
                      edge="end" 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(session.id);
                      }}
                      disabled={connecting}
                    >
                      <DeleteIcon />
                    </IconButton>
                  }
                >
                  <Typography variant="body2" noWrap>
                    {session.title || 'Untitled'} • {new Date(session.created_at).toLocaleDateString()}
                  </Typography>
                </ListItem>
              ))}
            </List>
          )}
        </Box>
        
        <Box className="support-chat-box">
          <List>
            {messages.length === 0 && !waitingForAI ? (
              <ListItem className="support-list-item-system">
                <Box className="support-message-box system">
                  <Typography variant="body2">
                    {sessionReady ? "Send a message to start the conversation" : "Initializing chat session..."}
                  </Typography>
                </Box>
              </ListItem>
            ) : (
              messages.map((msg, index) => (
                <ListItem
                  key={index}
                  className={
                    msg.sender === 'user'
                      ? 'support-list-item-user'
                      : msg.sender === 'system'
                      ? 'support-list-item-system'
                      : 'support-list-item-ai'
                  }
                  style={{
                    justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                    display: 'flex'
                  }}
                >
                  <Box
                    className={`support-message-box ${msg.sender}`}
                    sx={{
                      background: msg.sender === 'ai'
                        ? '#e3f2fd'
                        : msg.sender === 'user'
                          ? '#f5f5f5'
                          : '#fff3e0',
                      color: msg.sender === 'ai'
                        ? '#1976d2'
                        : msg.sender === 'user'
                          ? '#333'
                          : '#f57c00',
                      borderRadius: msg.sender === 'ai'
                        ? '16px 0 16px 16px'
                        : msg.sender === 'user'
                          ? '0 16px 16px 16px'
                          : '16px',
                      maxWidth: '70%',
                      textAlign: msg.sender === 'user' ? 'right' : 'left',
                      alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                      marginLeft: msg.sender === 'user' ? 'auto' : 0,
                      marginRight: msg.sender === 'ai' ? 'auto' : 0,
                    }}
                  >
                    {editingIndex === index ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TextField
                          value={editValue}
                          onChange={e => setEditValue(e.target.value)}
                          size="small"
                          sx={{ minWidth: 120 }}
                        />
                        <Button onClick={handleSaveEdit} size="small" variant="contained">Send</Button>
                        <Button onClick={() => setEditingIndex(null)} size="small">Cancel</Button>
                      </Box>
                    ) : (
                      <>
                        <Typography variant="body2">{msg.text}</Typography>
                        {msg.sender === 'user' && (
                          <IconButton
                            size="small"
                            sx={{ ml: 1 }}
                            onClick={() => handleEditMessage(index)}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        )}
                      </>
                    )}
                  </Box>
                </ListItem>
              ))
            )}
            
            {/* Display formatted course details if available */}
            {courseDetails.length > 0 && (
              <ListItem>
                <Box sx={{ width: '100%' }}>
                  {courseDetails.map((course, idx) => (
                    <React.Fragment key={idx}>
                      {formatCourseDetails(course)}
                    </React.Fragment>
                  ))}
                </Box>
              </ListItem>
            )}
            
            {/* AI typing indicator */}
            {waitingForAI && (
              <ListItem
                className="support-list-item-ai"
                style={{ justifyContent: 'flex-end', display: 'flex' }}
              >
                <Box
                  className="support-message-box ai"
                  sx={{
                    background: '#e3f2fd',
                    color: '#1976d2',
                    borderRadius: '16px 0 16px 16px',
                    maxWidth: '70%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    padding: '8px 16px',
                    textAlign: 'right',
                    alignSelf: 'flex-end',
                    marginLeft: 'auto'
                  }}
                >
                  <CircularProgress size={18} />
                  <Typography variant="body2">AI is typing...</Typography>
                </Box>
              </ListItem>
            )}
            <div ref={messagesEndRef} />
          </List>
        </Box>
        
        <Box className="support-input-box" mt={2}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Type your question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            className="support-textfield"
            disabled={!sessionReady || connecting || sending}
            InputProps={{
              endAdornment: (
                <IconButton
                  onClick={handleSendMessage}
                  disabled={!input.trim() || sending || !sessionReady || connecting}
                  className="support-send-button"
                >
                  {sending ? (
                    <CircularProgress size={24} />
                  ) : (
                    <SendIcon />
                  )}
                </IconButton>
              ),
            }}
          />
        </Box>
      </Paper>

      {/* Error Snackbar */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setSnackbarOpen(false)}
          severity={snackbarSeverity}
          sx={{ width: '100%' }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </div>
  );
};

export default StudentSupport;