import React, { useState, useEffect } from 'react';
import { CircularProgress, Paper, Typography, Tabs, Tab, Table, TableBody, TableCell, TableHead, TableRow, Chip, Button, IconButton, Collapse, Box, Dialog, DialogTitle, DialogContent, DialogActions, TextField } from '@mui/material';
import { Download, ExpandMore, ExpandLess } from '@mui/icons-material';
import { format } from 'date-fns';
import { coursesAPI } from '../../../config';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';

const StudentAssignments = ({ courses }) => {
  const [assignments, setAssignments] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [tabValue, setTabValue] = useState(0);
  const [expandedId, setExpandedId] = useState(null);
  const [submitDialog, setSubmitDialog] = useState({ open: false, assignment: null });
  const [submissionText, setSubmissionText] = useState('');
  const [submissionFile, setSubmissionFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const fetchAllAssignmentsAndSubmissions = async () => {
      setLoading(true);
      try {
        const allAssignments = [];
        for (const course of courses) {
          const courseId = course.course?.id || course.id;
          if (!courseId) continue;
          const res = await coursesAPI.getAssignments({ course: courseId });
          const results = res.data;
          results.forEach(a => {
            a.course_name = course.course?.title || course.title;
          });
          allAssignments.push(...results);
        }
        setAssignments(allAssignments);

        // Fetch all submissions for the current user
        const submissionsRes = await coursesAPI.getAssignmentSubmissions();
        setSubmissions(submissionsRes.data); // adjust if paginated
      } catch (err) {
        setAssignments([]);
        setSubmissions([]);
      } finally {
        setLoading(false);
      }
    };
    fetchAllAssignmentsAndSubmissions();
  }, [courses]);

  const filteredAssignments = assignments.filter(() => tabValue === 0);

  // Submit assignment handler
  const handleSubmitAssignment = async () => {
    if (!submitDialog.assignment) return;
    setSubmitting(true);
    setErrorMsg('');
    try {
      const formData = new FormData();
      formData.append('assignment', submitDialog.assignment.id);
      formData.append('response_text', submissionText);
      if (submissionFile) formData.append('response_file', submissionFile);

      await coursesAPI.submitAssignment(formData);

      setSubmitDialog({ open: false, assignment: null });
      setSubmissionText('');
      setSubmissionFile(null);
      setErrorMsg('');
      // Optionally, refresh assignments or show a success message
    } catch (err) {
      // Extract error message from response
      let msg = 'Submission failed. Please try again.';
      if (err.response && err.response.data && err.response.data.detail) {
        msg = err.response.data.detail;
      } else if (err.response && err.response.data) {
        msg = JSON.stringify(err.response.data);
      }
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const getSubmissionForAssignment = (assignmentId) =>
    submissions.find(sub => sub.assignment === assignmentId);

  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3, borderRadius: 2 }}>
      <Typography variant="h5" gutterBottom>Assignments</Typography>
      <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)} sx={{ mb: 3 }}>
        <Tab label="Upcoming" />
        <Tab label="Submitted" />
        <Tab label="Graded" />
      </Tabs>
      {loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><CircularProgress /></div>
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell>Title</TableCell>
              <TableCell>Course</TableCell>
              <TableCell>Module</TableCell>
              <TableCell>Created By</TableCell>
              <TableCell>Due Date</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Grade</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAssignments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center">No assignments found</TableCell>
              </TableRow>
            ) : (
              filteredAssignments.map(assignment => (
                <React.Fragment key={assignment.id}>
                  <TableRow hover>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => setExpandedId(expandedId === assignment.id ? null : assignment.id)}
                        aria-label={expandedId === assignment.id ? 'Collapse' : 'Expand'}
                      >
                        {expandedId === assignment.id ? <ExpandLess /> : <ExpandMore />}
                      </IconButton>
                    </TableCell>
                    <TableCell>{assignment.title}</TableCell>
                    <TableCell>{assignment.course_name || ''}</TableCell>
                    <TableCell>{assignment.module_name || ''}</TableCell>
                    <TableCell>{assignment.created_by_name || ''}</TableCell>
                    <TableCell>
                      {assignment.due_date
                        ? format(new Date(assignment.due_date), 'MMM dd, yyyy')
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const submission = getSubmissionForAssignment(assignment.id);
                        if (submission) {
                          return (
                            <Chip
                              label={submission.is_graded ? 'Graded' : 'Submitted'}
                              color={submission.is_graded ? 'success' : 'info'}
                              size="small"
                            />
                          );
                        }
                        return <Chip label="Due" color="warning" size="small" />;
                      })()}
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const submission = getSubmissionForAssignment(assignment.id);
                        return submission && submission.grade != null ? `${submission.grade}%` : '-';
                      })()}
                    </TableCell>
                    <TableCell>
                      {assignment.instructions_file ? (
                        <Button
                          size="small"
                          startIcon={<Download />}
                          href={assignment.instructions_file}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Download Instructions
                        </Button>
                      ) : (
                        <span style={{ color: '#888', fontSize: '0.9em' }}>No file</span>
                      )}
                      <Button
                        size="small"
                        variant="contained"
                        sx={{ ml: 1 }}
                        onClick={() => setSubmitDialog({ open: true, assignment })}
                      >
                        Submit
                      </Button>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell colSpan={9} sx={{ p: 0, border: 0 }}>
                      <Collapse in={expandedId === assignment.id} timeout="auto" unmountOnExit>
                        <Box sx={{ p: 2, background: '#f9f9f9' }}>
                          <Typography variant="subtitle1" gutterBottom>Description</Typography>
                          <div dangerouslySetInnerHTML={{ __html: assignment.description }} />
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              ))
            )}
          </TableBody>
        </Table>
      )}

      {/* Assignment Submission Dialog */}
      <Dialog open={submitDialog.open} onClose={() => { setSubmitDialog({ open: false, assignment: null }); setErrorMsg(''); }} maxWidth="sm" fullWidth>
        <DialogTitle>Submit Assignment</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            {submitDialog.assignment?.title}
          </Typography>
          {errorMsg && (
            <Typography color="error" sx={{ mb: 2 }}>
              {errorMsg}
            </Typography>
          )}
          <ReactQuill
            value={submissionText}
            onChange={setSubmissionText}
            theme="snow"
            style={{ height: 200, marginBottom: 16 }}
          />
          <label htmlFor="assignment-file-upload">
            <input
              id="assignment-file-upload"
              type="file"
              accept=".pdf,.doc,.docx,.txt,.jpg,.png"
              style={{ display: 'none' }}
              onChange={e => setSubmissionFile(e.target.files[0])}
            />
            <Button
              variant="outlined"
              component="span"
              sx={{ mb: 2 }}
            >
              Choose File
            </Button>
            {submissionFile && (
              <Typography variant="body2" sx={{ ml: 2, display: 'inline' }}>
                {submissionFile.name}
              </Typography>
            )}
          </label>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setSubmitDialog({ open: false, assignment: null }); setErrorMsg(''); }}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSubmitAssignment}
            disabled={submitting}
          >
            {submitting ? 'Submitting...' : 'Submit'}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default StudentAssignments;