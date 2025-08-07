import React, { useState, useEffect, useCallback, memo } from 'react';
import { throttle } from 'lodash';
import { API_BASE_URL } from '../../../config';
import './StudentCourseList.css';

import {
  PlayCircle, Bookmark, BookmarkBorder, Search, RateReview, VideoLibrary,
  PictureAsPdf, Description, InsertDriveFile, FilterList, Sort, Star,
  StarBorder, PlayArrow, Pause, VolumeUp, VolumeOff, Fullscreen,
  FullscreenExit, ExpandMore, ExpandLess, Link, Close, HourglassEmpty, CheckCircle,
  CheckCircleOutline, ArrowBack, Menu as MenuIcon
} from '@mui/icons-material';
import { Tooltip, Typography } from '@mui/material';
import YouTube from 'react-youtube';

// Memoized Course Card Component
const CourseCard = memo(({ course, bookmarked, onBookmark, onOpen, onFeedback }) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  return (
    <div className="course-card" aria-label={`Course: ${course.title}`}>
      <div className="course-card-image">
        {!imageLoaded && <div className="skeleton-image" />}
        <img
          src={imageError ? 'https://crm-frontend-react.vercel.app/assets/global-banner-BNdpuw-A.png' : course.thumbnail}
          alt={course.title}
          className="course-image"
          onLoad={() => setImageLoaded(true)}
          onError={() => {
            setImageError(true);
            setImageLoaded(true);
          }}
          loading="lazy"
        />
      </div>
      <div className="course-card-content">
        <h3 className="course-title">{course.title}</h3>
        <p className="course-instructor">
          {course.instructors.length > 0 ? `By ${course.instructors[0].name}` : ''}
        </p>
        <div className="course-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${course.progress}%` }}></div>
          </div>
          <span className="progress-text">{Math.round(course.progress)}%</span>
        </div>
        <span className={`course-status ${course.status}`}>
          {course.status.replace('_', ' ')}
        </span>
      </div>
      <div className="course-card-actions">
        <button className="action-button primary" onClick={() => onOpen(course)}>
          <PlayCircle />
          {course.progress > 0 ? 'Continue' : 'Start'}
        </button>
        <div className="secondary-actions">
          <Tooltip title={bookmarked ? 'Remove bookmark' : 'Add bookmark'}>
            <button
              className="icon-button"
              onClick={onBookmark}
              aria-label={bookmarked ? 'Remove bookmark' : 'Add bookmark'}
            >
              {bookmarked ? <Bookmark /> : <BookmarkBorder />}
            </button>
          </Tooltip>
          <Tooltip title="Provide feedback">
            <button className="action-button" onClick={() => onFeedback(course, 'course')}>
              <RateReview />
              Feedback
            </button>
          </Tooltip>
        </div>
      </div>
    </div>
  );
});

// Empty State
const EmptyState = () => (
  <div className="empty-state">
    <h3>No Enrolled Courses</h3>
    <p>You haven't enrolled in any courses yet.</p>
    <a href="/courses" className="action-button primary">
      <Search />
      Browse Courses
    </a>
  </div>
);

// Media Player Component
const MediaPlayer = ({ open, onClose, media, onEnded }) => {
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(80);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [completed, setCompleted] = useState(false);
  const videoRef = React.useRef(null);

  const handlePlayPause = () => {
    if (videoRef.current) {
      if (playing) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setPlaying(!playing);
    }
  };

  const handleVolumeChange = (e) => {
    const newValue = parseInt(e.target.value);
    setVolume(newValue);
    if (videoRef.current) {
      videoRef.current.volume = newValue / 100;
      setMuted(newValue === 0);
    }
  };

  const handleProgressChange = (e) => {
    const newValue = parseInt(e.target.value);
    setProgress(newValue);
    if (videoRef.current) {
      videoRef.current.currentTime = (newValue / 100) * duration;
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const currentTime = videoRef.current.currentTime;
      const newProgress = (currentTime / duration) * 100;
      setProgress(newProgress);
      if (duration > 0 && currentTime >= duration - 1 && !completed) {
        setCompleted(true);
      }
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      videoRef.current.volume = volume / 100;
    }
  };

  const handlePlaybackRateChange = (rate) => {
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
  };

  const handleFullscreen = () => {
    if (!fullscreen) {
      if (videoRef.current.requestFullscreen) {
        videoRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setFullscreen(!fullscreen);
  };

  const handleKeyDown = (e) => {
    if (e.key === ' ') {
      e.preventDefault();
      handlePlayPause();
    } else if (e.key === 'ArrowRight') {
      if (videoRef.current) {
        videoRef.current.currentTime += 5;
      }
    } else if (e.key === 'ArrowLeft') {
      if (videoRef.current) {
        videoRef.current.currentTime -= 5;
      }
    } else if (e.key === 'm') {
      setMuted(!muted);
    } else if (e.key === 'f') {
      handleFullscreen();
    }
  };

  useEffect(() => {
    if (open && videoRef.current) {
      videoRef.current.currentTime = 0;
      setPlaying(false);
      setProgress(0);
      setCompleted(false);
    }
  }, [open]);

  return (
    <div className={`media-player ${open ? 'open' : ''}`} onKeyDown={handleKeyDown} tabIndex={0}>
      <div className="media-player-content">
        <div className="media-container">
          {media.type === 'youtube' ? (
            <div className="responsive-iframe-container">
              <iframe
                src={`https://www.youtube.com/embed/${media.url.split('v=')[1]?.split('&')[0]}`}
                className="media-iframe"
                title={media.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            </div>
          ) : media.type === 'video' ? (
            <video
              ref={videoRef}
              src={media.url}
              className="media-video"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={() => {
                setPlaying(false);
                setCompleted(true);
                onEnded && onEnded(); // Call onEnded prop if provided
              }}
              onClick={handlePlayPause}
              muted={muted}
            />
          ) : (
            <iframe
              src={media.url}
              className="media-iframe"
              title={media.title}
              allowFullScreen
            />
          )}
          {media.type === 'video' && (
            <div className="media-controls">
              <input
                type="range"
                min="0"
                max="100"
                value={progress}
                onChange={handleProgressChange}
                className="progress-slider"
              />
              <div className="controls-bar">
                <div className="controls-left">
                  <button className="icon-button" onClick={handlePlayPause}>
                    {playing ? <Pause /> : <PlayArrow />}
                  </button>
                  <button className="icon-button" onClick={() => setMuted(!muted)}>
                    {muted ? <VolumeOff /> : <VolumeUp />}
                  </button>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={muted ? 0 : volume}
                    onChange={handleVolumeChange}
                    className="volume-slider"
                  />
                  <span className="time-display">
                    {formatTime((progress / 100) * duration)} / {formatTime(duration)}
                  </span>
                </div>
                <div className="controls-right">
                  <select
                    value={playbackRate}
                    onChange={(e) => handlePlaybackRateChange(parseFloat(e.target.value))}
                    className="playback-rate"
                  >
                    {[0.5, 0.75, 1, 1.25, 1.5, 2].map(rate => (
                      <option key={rate} value={rate}>{rate}x</option>
                    ))}
                  </select>
                  <button className="icon-button" onClick={handleFullscreen}>
                    {fullscreen ? <FullscreenExit /> : <Fullscreen />}
                  </button>
                </div>
              </div>
            </div>
          )}
          {completed && (
            <div className="completion-overlay">
              <CheckCircle className="completion-icon" />
              <h3>Lesson Completed</h3>
              <button
                className="action-button primary"
                onClick={() => {
                  if (videoRef.current) {
                    videoRef.current.currentTime = 0;
                    setPlaying(false);
                    setProgress(0);
                    setCompleted(false);
                  }
                }}
              >
                Replay
              </button>
            </div>
          )}
        </div>
        <div className="media-info">
          <div className="media-header">
            <h3>{media.title}</h3>
            <button className="icon-button" onClick={onClose}>
              <Close />
            </button>
          </div>
          <p>{media.description || 'No description available'}</p>
        </div>
      </div>
    </div>
  );
};

// Document Viewer Component
const DocumentViewer = ({ open, onClose, document }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);

  useEffect(() => {
    if (!open || !document || !document.url || !document.type) {
      console.log('DocumentViewer: Invalid document prop', document);
      setError('Invalid document data');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    // Check for YouTube links
    if (document.url.includes('youtube.com') || document.url.includes('youtu.be')) {
      setError('YouTube links should be viewed in the media player.');
      setLoading(false);
      return;
    }

    // Handle supported document types
    if (document.type === 'pdf') {
      setFileUrl(document.url);
      setLoading(false);
    } else if (['doc', 'docx', 'ppt', 'pptx'].includes(document.type)) {
      setFileUrl(`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(document.url)}`);
      setLoading(false);
    } else {
      // Gracefully handle unsupported external links (CORS)
      setError('This file type cannot be loaded directly. Please use the provided link to view the resource in a new tab.');
      setLoading(false);
    }

    return () => {
      if (fileUrl) {
        URL.revokeObjectURL(fileUrl);
      }
    };
  }, [open, document, fileUrl]);

  const renderViewer = () => {
    if (!document || !document.url || !document.type) {
      return (
        <div className="viewer-error">
          <Typography color="error">Invalid document data</Typography>
          <button className="action-button" onClick={onClose}>
            Close
          </button>
        </div>
      );
    }

    if (loading) {
      return (
        <div className="viewer-loading">
          <HourglassEmpty />
          <Typography>Loading document...</Typography>
        </div>
      );
    }

    if (error) {
      return (
        <div className="viewer-error">
          <Typography color="error">{error}</Typography>
          <a
            href={document.url}
            target="_blank"
            rel="noopener noreferrer"
            className="action-button"
          >
            Open Resource
          </a>
          <button className="action-button" onClick={onClose}>
            Close
          </button>
        </div>
      );
    }

    if (document.type === 'pdf' || ['doc', 'docx', 'ppt', 'pptx'].includes(document.type)) {
      return (
        <iframe
          src={fileUrl}
          className="document-iframe"
          title={document.title || 'Document'}
        />
      );
    }

    return (
      <div className="viewer-error">
        <Typography>This file type cannot be displayed in the browser.</Typography>
        <a
          href={document.url}
          target="_blank"
          rel="noopener noreferrer"
          className="action-button primary"
        >
          Download File
        </a>
        <button className="action-button" onClick={onClose}>
          Close
        </button>
      </div>
    );
  };

  return (
    <div className={`document-viewer ${open ? 'open' : ''}`}>
      <div className="document-viewer-content">
        <div className="viewer-header">
          <h3>{document?.title || 'Document Viewer'}</h3>
          <button className="icon-button" onClick={onClose}>
            <Close />
          </button>
        </div>
        <div className="viewer-body">{renderViewer()}</div>
        {document?.url && (
          <div className="viewer-footer">
            <a
              href={document.url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-button primary"
            >
              <InsertDriveFile />
              Open Original File
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

const CourseDialog = ({ open, onClose, course, activeTab, setActiveTab, onFeedback, onCourseProgressUpdate }) => {
  const [selectedLesson, setSelectedLesson] = useState(null);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [expandedModules, setExpandedModules] = useState({});
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [courseProgress, setCourseProgress] = useState(course.progress || 0);
  const userId = course.user || course.user_id;

  const toggleModule = (moduleId) => {
    setExpandedModules(prev => ({
      ...prev,
      [moduleId]: !prev[moduleId]
    }));
  };

  // Helper to infer lesson type from file/url if type is null/unknown
  const inferLessonType = (lesson) => {
    const url = lesson.content_url || lesson.content_file || '';
    if (!url) return 'unknown';
    const ext = url.split('.').pop().split('?')[0].toLowerCase();
    if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
    if (ext === 'pdf') return 'pdf';
    if (ext === 'ppt' || ext === 'pptx') return 'ppt';
    if (ext === 'doc' || ext === 'docx') return 'doc';
    if (lesson.type && lesson.type !== 'Unknown' && lesson.type !== 'unknown' && lesson.type !== null) return lesson.type;
    if (url.startsWith('http')) return 'link';
    return 'unknown';
  };

  const handleLessonSelect = (lesson) => {
    const detectedType = inferLessonType(lesson);
    const lessonWithType = { ...lesson, detectedType };
    setSelectedLesson(lessonWithType);
    setSelectedMedia(null);
    setSelectedDocument(null);
    if (detectedType === 'video' || detectedType === 'youtube') {
      setSelectedMedia({
        url: lesson.content_url || lesson.content_file,
        title: lesson.title || 'Lesson Media',
        description: lesson.description || '',
        type: detectedType
      });
    } else if (detectedType === 'link') {
      window.open(lesson.content_url || lesson.content_file, '_blank', 'noopener,noreferrer');
    } else if (detectedType === 'pdf' || detectedType === 'ppt' || detectedType === 'doc') {
      setSelectedDocument({
        url: lesson.content_url || lesson.content_file,
        title: lesson.title || 'Lesson Document',
        type: detectedType
      });
    }
  };

  const handleResourceSelect = (resource) => {
    if (resource.type === 'video' || resource.content_url?.includes('youtube.com') || resource.content_url?.includes('youtu.be')) {
      setSelectedMedia({
        url: resource.content_url || resource.content_file,
        title: resource.title || 'Resource Media',
        description: resource.description || '',
        type: resource.content_url?.includes('youtube.com') || resource.content_url?.includes('youtu.be') ? 'youtube' : 'video'
      });
      setSelectedDocument(null);
    } else if (resource.type === 'link') {
      window.open(resource.content_url, '_blank', 'noopener,noreferrer');
    } else {
      setSelectedDocument({
        url: resource.content_url || resource.content_file,
        title: resource.title || 'Resource Document',
        type: resource.type
      });
      setSelectedMedia(null);
    }
  };

  const handleDialogClose = () => {
    setSelectedLesson(null);
    setSelectedMedia(null);
    setSelectedDocument(null);
    setExpandedModules({});
    setIsSidebarOpen(true);
    setActiveTab(0);
    onClose();
  };

  const renderFileIcon = (type) => {
    switch (type) {
      case 'video':
      case 'youtube':
        return <VideoLibrary className="resource-icon" />;
      case 'pdf':
        return <PictureAsPdf className="resource-icon" />;
      case 'doc':
      case 'docx':
        return <Description className="resource-icon" />;
      case 'link':
        return <Link className="resource-icon" />;
      default:
        return <InsertDriveFile className="resource-icon" />;
    }
  };

  const calculateModuleProgress = (module) => {
    if (!module.lessons || module.lessons.length === 0) return 0;
    const completedLessons = module.lessons.filter(lesson => lesson.is_completed).length;
    return Math.round((completedLessons / module.lessons.length) * 100);
  };

  // Call this when a lesson is completed
  const handleLessonComplete = async (lesson) => {
    try {
      await coursesAPI.completeLesson({ user: userId, lesson: lesson.id });
      const progressRes = await coursesAPI.getCourseProgress({ user: userId, course: course.courseId });
      const newProgress = progressRes.data.progress;
      setCourseProgress(newProgress);

      // Update course object and notify parent
      let newStatus = course.status;
      let completedAt = course.completed_at;
      let startedAt = course.started_at;
      if (newProgress === 100) {
        newStatus = 'completed';
        completedAt = new Date().toISOString();
      } else if (newProgress > 0 && !course.started_at) {
        newStatus = 'in_progress';
        startedAt = new Date().toISOString();
      }
      onCourseProgressUpdate(course.courseId, newProgress, newStatus, startedAt, completedAt);
    } catch (error) {
      console.error('Error completing lesson or fetching progress:', error);
    }
  };

  // For document lessons, mark as completed when iframe loads
  useEffect(() => {
    if (selectedLesson && ['pdf', 'ppt', 'doc'].includes(selectedLesson.detectedType)) {
      handleLessonComplete(selectedLesson);
    }
    // For links, you may want to mark as completed when opened
    if (selectedLesson && selectedLesson.detectedType === 'link') {
      handleLessonComplete(selectedLesson);
    }
    // eslint-disable-next-line
  }, [selectedLesson]);

  return (
    <>
      {open && (
        <div className="course-dialog-overlay">
          <div className={`course-dialog-modal ${open ? 'open' : ''}`}> 
            <div className="course-dialog-content">
              <div className="dialog-header">
                <h2>{course?.course?.title || 'Course'}</h2>
               {/* Show number of modules in the course */}
               <div style={{ fontSize: '1rem', color: '#888', marginTop: 4 }}>
                 Modules: {course?.course?.modules?.length || 0}
               </div>
                <button className="close-button" onClick={handleDialogClose}>
                  <Close />
                </button>
              </div>
              <div className="dialog-main">
                {activeTab === 0 && (
                  <div className="lesson-content-area">
                    {selectedLesson ? (
                      <>
                        <Typography variant="h6" gutterBottom>
                          {selectedLesson.title}
                        </Typography>
                        {selectedLesson.description && (
                          <Typography variant="body2" color="textSecondary" paragraph>
                            {selectedLesson.description}
                          </Typography>
                        )}
                        {/* Rich text content */}
                        {selectedLesson.content && (
                          <div
                            className="lesson-content"
                            dangerouslySetInnerHTML={{ __html: selectedLesson.content }}
                          />
                        )}
                        {/* Inline YouTube embed for YouTube lessons */}
                        {selectedLesson?.detectedType === 'youtube' && selectedMedia && selectedMedia.type === 'youtube' && (
                          <YouTubePlayer
                            videoId={
                              selectedMedia.url.split('v=')[1]?.split('&')[0] ||
                              selectedMedia.url.split('/').pop()
                            }
                            onComplete={() => handleLessonComplete(selectedLesson)}
                          />
                        )}
                        {/* Non-YouTube videos still use modal */}
                        {(selectedLesson.detectedType === 'video' && selectedMedia && selectedMedia.type !== 'youtube') && (
                          <MediaPlayer
                            open={!!selectedMedia}
                            onClose={() => setSelectedMedia(null)}
                            media={selectedMedia}
                            onEnded={() => handleLessonComplete(selectedLesson)}
                          />
                        )}
                        {/* Inline PDF display */}
                        {(selectedLesson.detectedType === 'pdf' && (selectedLesson.content_url || selectedLesson.content_file)) && (
                          <div className="lesson-document">
                            <iframe
                              src={selectedLesson.content_url || selectedLesson.content_file}
                              className="lesson-document"
                              title={selectedLesson.title || 'Lesson PDF'}
                            />
                          </div>
                        )}
                        {/* Inline PowerPoint display */}
                        {(selectedLesson.detectedType === 'ppt' && (selectedLesson.content_url || selectedLesson.content_file)) && (
                          <div className="lesson-document">
                            <iframe
                              src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(selectedLesson.content_url || selectedLesson.content_file)}`}
                              className="lesson-document"
                              title={selectedLesson.title || 'Lesson PowerPoint'}
                            />
                          </div>
                        )}
                        {/* Inline Word document display */}
                        {(selectedLesson.detectedType === 'doc' && (selectedLesson.content_url || selectedLesson.content_file)) && (
                          <div className="lesson-document">
                            <iframe
                              src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(selectedLesson.content_url || selectedLesson.content_file)}`}
                              className="lesson-document"
                              title={selectedLesson.title || 'Lesson Document'}
                            />
                          </div>
                        )}
                        {/* Document viewer for other non-video lessons */}
                        {selectedLesson.detectedType !== 'video' &&
                          selectedLesson.detectedType !== 'youtube' &&
                          selectedDocument && (
                            <DocumentViewer
                              open={!!selectedDocument}
                              onClose={() => setSelectedDocument(null)}
                              document={selectedDocument}
                            />
                          )}
                        {/* External link lesson type */}
                        {selectedLesson.detectedType === 'link' && (selectedLesson.content_url || selectedLesson.content_file) && (
                          <div className="external-link-card">
                            <Typography variant="body1" color="primary" gutterBottom>
                              <Link style={{ verticalAlign: 'middle', marginRight: 8, color: '#1976d2', fontSize: '1.5rem' }} />
                              External Resource
                            </Typography>
                            <Typography variant="body2" color="textSecondary" paragraph>
                              <a
                                href={selectedLesson.content_url || selectedLesson.content_file}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: '#1976d2', textDecoration: 'underline', wordBreak: 'break-all', fontWeight: 500 }}
                              >
                                {selectedLesson.content_url || selectedLesson.content_file}
                              </a>
                            </Typography>
                          </div>
                        )}
                        {/* Resources Section */}
                        {course?.course?.resources?.length > 0 && (
                          <div className="resources-section">
                            <Typography variant="h6" gutterBottom>
                              Resources
                            </Typography>
                            {course.resources.map(resource => (
                              <div
                                key={resource.id}
                                className="resource-item"
                                onClick={() => handleResourceSelect(resource)}
                              >
                                {renderFileIcon(resource.type)}
                                <div className="resource-info">
                                  <span>{resource.title}</span>
                                  <span className="resource-meta">{resource.type.toUpperCase()}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <Typography>Select a lesson from the sidebar to begin.</Typography>
                    )}
                  </div>
                )}
                {activeTab === 1 && (
                  <div className="feedback-tab">
                    <Typography variant="h6" gutterBottom>
                      Provide Feedback
                    </Typography>
                    {/* Feedback form remains the same */}
                    <div className="rating-section">
                      <span>Rate this course:</span>
                      <div className="rating-stars">
                        {[1, 2, 3, 4, 5].map(star => (
                          <button
                            key={star}
                            className="icon-button"
                            onClick={() => setFeedbackRating(star)}
                            aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
                          >
                            {feedbackRating >= star ? <Star /> : <StarBorder />}
                          </button>
                        ))}
                      </div>
                    </div>
                    <textarea
                      rows="5"
                      placeholder="Share your feedback about this course..."
                      value={feedbackText}
                      onChange={e => setFeedbackText(e.target.value)}
                      className="feedback-textarea"
                    />
                    {feedbackError && <div className="error-message">{feedbackError}</div>}
                    <button
                      className="action-button primary"
                      onClick={handleFeedbackSubmit}
                      disabled={!feedbackText.trim()}
                    >
                      Submit Feedback
                    </button>
                  </div>
                )}
              </div>
              {/* Sidebar toggle button always visible, sidebar content only if open */}
              <div className={`dialog-sidebar ${isSidebarOpen ? 'open' : 'closed'}`} style={{ position: 'relative', minWidth: isSidebarOpen ? 280 : 0, transition: 'min-width 0.2s' }}>
                {/* Sidebar header and modules only if open */}
                {isSidebarOpen ? (
                  <>
                    <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56 }}>
                      <Typography variant="h6">Course Content</Typography>
                      <button
                        className="sidebar-toggle"
                        style={{ marginLeft: 8, width: 40, height: 40, borderRadius: 20, background: '#f5f5f5', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                        onClick={() => setIsSidebarOpen(false)}
                      >
                        <ArrowBack />
                      </button>
                    </div>
                    <div className="sidebar-modules">
                      {course?.course?.modules?.map(module => (
                        <div key={module.id} className="module-section">
                          <button
                            className="module-header"
                            onClick={() => toggleModule(module.id)}
                          >
                            <h3>{module.title}</h3>
                            <div className="module-info">
                              <span className="module-progress">
                                {calculateModuleProgress(module)}% Complete
                              </span>
                              {/* Show number of lessons in this module */}
                              <span style={{ fontSize: '0.95rem', color: '#888', marginLeft: 8 }}>
                                Lessons: {module.lessons?.length || 0}
                              </span>
                              {expandedModules[module.id] ? <ExpandLess /> : <ExpandMore />}
                            </div>
                          </button>
                          {expandedModules[module.id] && (
                            <div className="module-content">
                              {module.lessons.map(lesson => (
                                <div
                                  key={lesson.id}
                                  className={`lesson-item ${selectedLesson?.id === lesson.id ? 'active' : ''}`}
                                  onClick={() => handleLessonSelect(lesson)}
                                >
                                  <div className="lesson-header">
                                    {renderFileIcon(lesson.type)}
                                    <div className="lesson-info">
                                      <span>{lesson.title}</span>
                                      <span className="lesson-meta">{lesson.duration} • {lesson.type}</span>
                                    </div>
                                    <Tooltip title={lesson.is_completed ? 'Completed' : 'Not Completed'}>
                                      <span className="lesson-status">
                                        {lesson.is_completed ? <CheckCircleOutline /> : null}
                                      </span>
                                    </Tooltip>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )) || <Typography>No modules available</Typography>}
                    </div>
                  </>
                ) : (
                  <button
                    className="sidebar-toggle"
                    style={{ position: 'absolute', top: 16, left: 0, width: 40, height: 40, borderRadius: 20, background: '#f5f5f5', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}
                    onClick={() => setIsSidebarOpen(true)}
                  >
                    <MenuIcon />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

// Helper function to format time
const formatTime = (seconds) => {
  if (isNaN(seconds)) return '0:00';
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
};

const StudentCourseList = ({ courses, onFeedback }) => {
  // ...existing state...
  const [filteredCourses, setFilteredCourses] = useState([]);
  const [bookmarks, setBookmarks] = useState([]);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [openCourseDialog, setOpenCourseDialog] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [filters, setFilters] = useState({
    status: 'all',
    search: '',
    sort: 'title',
    view: 'all'
  });

  // Handler to update course progress/status live
  const handleCourseProgressUpdate = (courseId, newProgress, newStatus, startedAt, completedAt) => {
    setFilteredCourses(prev =>
      prev.map(course =>
        course.courseId === courseId
          ? {
              ...course,
              progress: newProgress,
              status: newStatus,
              started_at: startedAt,
              completed_at: completedAt
            }
          : course
      )
    );
  };

  // Debug: Log component initialization
  console.log('StudentCourseList: Initializing component');

  const handleClose = useCallback(() => {
    console.log('StudentCourseList: Closing CourseDialog');
    setOpenCourseDialog(false);
    setSelectedCourse(null);
    setActiveTab(0);
  }, []);

  useEffect(() => {
    console.log('StudentCourseList: useEffect for courses');
    setBookmarks(courses.map(course => course.bookmarked || false));
    const transformedCourses = courses.map(course => {
      if (!course?.course) {
        console.warn('StudentCourseList: Invalid course data:', course);
        return null;
      }
      return {
        ...course,
        courseId: course.course.id,
        title: course.course.title || 'Untitled Course',
        thumbnail: course.course.thumbnail.includes('http')
          ? course.course.thumbnail
          : `${API_BASE_URL}${course.course.thumbnail}`,
        description: course.course.description || '',
        resources: course.course.resources || [],
        modules: (course.course.modules || []).map(module => ({
          ...module,
          lessons: (module.lessons || []).map(lesson => ({
            ...lesson,
            is_completed: lesson.is_completed || false
          }))
        })),
        instructors: course.course.instructors || [],
        status: course.completed_at ? 'completed' : course.progress > 0 ? 'in_progress' : 'not_started'
      };
    }).filter(course => course !== null);
    setFilteredCourses(transformedCourses);
  }, [courses]);

  useEffect(() => {
    console.log('StudentCourseList: useEffect for filters/bookmarks');
    let result = [...courses].map(course => {
      if (!course?.course) {
        console.warn('StudentCourseList: Invalid course data:', course);
        return null;
      }
      return {
        ...course,
        courseId: course.course.id,
        title: course.course.title || 'Untitled Course',
        thumbnail: course.course.thumbnail.includes('http')
          ? course.course.thumbnail
          : `${API_BASE_URL}${course.course.thumbnail}`,
        description: course.course.description || '',
        resources: course.course.resources || [],
        modules: (course.course.modules || []).map(module => ({
          ...module,
          lessons: (module.lessons || []).map(lesson => ({
            ...lesson,
            is_completed: lesson.is_completed || false
          }))
        })),
        instructors: course.course.instructors || [],
        status: course.completed_at ? 'completed' : course.progress > 0 ? 'in_progress' : 'not_started'
      };
    }).filter(course => course !== null);

    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      result = result.filter(course => 
        course.title.toLowerCase().includes(searchLower) ||
        course.modules.some(module => 
          module.title.toLowerCase().includes(searchLower) ||
          module.lessons.some(lesson => lesson.title.toLowerCase().includes(searchLower))
        )
      );
    }

    if (filters.status !== 'all') {
      result = result.filter(course => course.status === filters.status);
    }

    if (filters.view === 'bookmarked') {
      result = result.filter((course, index) => bookmarks[index]);
    }

    result.sort((a, b) => {
      if (filters.sort === 'title') {
        return a.title.localeCompare(b.title);
      } else if (filters.sort === 'progress') {
        return b.progress - a.progress;
      } else if (filters.sort === 'enrolled_at') {
        return new Date(b.enrolled_at) - new Date(a.enrolled_at);
      }
      return 0;
    });

    setFilteredCourses(result);
  }, [courses, filters, bookmarks]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleBookmark = useCallback(
    throttle(index => {
      setBookmarks(prev => {
        const newBookmarks = [...prev];
        newBookmarks[index] = !newBookmarks[index];
        return newBookmarks;
      });
    }, 300),
    []
  );

  const handleOpenCourse = useCallback(course => {
    console.log('StudentCourseList: Opening course', course.title);
    setSelectedCourse(course);
    setActiveTab(0);
    setOpenCourseDialog(true);
  }, []);

  const stats = {
    total: courses.length,
    inProgress: courses.filter(c => c.status === 'in_progress').length,
    completed: courses.filter(c => c.status === 'completed').length,
    notStarted: courses.filter(c => c.status === 'not_started').length
  };

  return (
    <div className="course-list-container">
      <StudentDashboardDarkModeToggle />
      <div className="course-list-header">
        <h1>My Learning</h1>
        <a href="/courses" className="action-button primary">
          <Search />
          Browse Courses
        </a>
      </div>
      <div className="stats-grid">
        {[
          { label: 'Total Courses', value: stats.total },
          { label: 'In Progress', value: stats.inProgress },
          { label: 'Completed', value: stats.completed },
          { label: 'Not Started', value: stats.notStarted }
        ].map(stat => (
          <div key={stat.label} className="stat-card">
            <span className="stat-label">{stat.label}</span>
            <span className="stat-value">{stat.value}</span>
          </div>
        ))}
      </div>
      <div className="filters">
        <div className="filter-group">
          <Search className="filter-icon" />
          <input
            type="text"
            placeholder="Search courses, modules, or lessons..."
            value={filters.search}
            onChange={e => handleFilterChange('search', e.target.value)}
            className="filter-input"
          />
        </div>
        <div className="filter-group">
          <FilterList className="filter-icon" />
          <select
            value={filters.status}
            onChange={e => handleFilterChange('status', e.target.value)}
            className="filter-select"
          >
            <option value="all">All Statuses</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="not_started">Not Started</option>
          </select>
        </div>
        <div className="filter-group">
          <Sort className="filter-icon" />
          <select
            value={filters.sort}
            onChange={e => handleFilterChange('sort', e.target.value)}
            className="filter-select"
          >
            <option value="title">Sort by Title</option>
            <option value="progress">Sort by Progress</option>
            <option value="enrolled_at">Sort by Enrollment Date</option>
          </select>
        </div>
        <div className="filter-group">
          <select
            value={filters.view}
            onChange={e => handleFilterChange('view', e.target.value)}
            className="filter-select"
          >
            <option value="all">All Courses</option>
            <option value="bookmarked">Bookmarked</option>
          </select>
        </div>
      </div>
      <div className="course-grid">
        {courses.length === 0 ? (
          <EmptyState />
        ) : (
          filteredCourses.map((course, index) => (
            <CourseCard
              key={course.id}
              course={course}
              bookmarked={bookmarks[index]}
              onBookmark={() => handleBookmark(index)}
              onOpen={() => handleOpenCourse(course)}
              onFeedback={onFeedback}
            />
          ))
        )}
      </div>
      {selectedCourse && (
        <CourseDialog
          open={openCourseDialog}
          onClose={handleClose}
          course={selectedCourse}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onFeedback={onFeedback}
          onCourseProgressUpdate={handleCourseProgressUpdate} // <-- Pass this prop
        />
      )}
    </div>
  );
};

function StudentDashboardDarkModeToggle() {
  const [darkMode, setDarkMode] = useState(false);
  useEffect(() => {
    const body = document.body;
    if (darkMode) {
      body.classList.add('student-dashboard-dark');
    } else {
      body.classList.remove('student-dashboard-dark');
    }
    return () => {
      body.classList.remove('student-dashboard-dark');
    };
  }, [darkMode]);
  return (
    <button
      className="action-button"
      style={{ position: 'absolute', top: 24, right: 24, zIndex: 1001 }}
      onClick={() => setDarkMode((prev) => !prev)}
    >
      {darkMode ? 'Bright Mode' : 'Dark Mode'}
    </button>
  );
}

const YouTubePlayer = ({ videoId, onComplete }) => {
  const [playedSeconds, setPlayedSeconds] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const timerRef = React.useRef();

  // Called when YouTube player is ready, gets duration
  const onReady = (event) => {
    setDuration(event.target.getDuration());
  };

  // Start timer when video plays
  const onPlay = () => {
    setIsPlaying(true);
    if (!timerRef.current) {
      timerRef.current = setInterval(() => {
        setPlayedSeconds(prev => prev + 1);
      }, 1000);
    }
  };

  // Pause timer when video pauses
  const onPause = () => {
    setIsPlaying(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  // Cleanup timer on unmount
  useEffect(() => {
    if (playedSeconds >= duration && duration > 0) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      onComplete && onComplete();
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [playedSeconds, duration, onComplete]);

  return (
    <div>
      <YouTube
        videoId={videoId}
        onReady={onReady}
        onPlay={onPlay}
        onPause={onPause}
      />
      <div style={{ marginTop: 8, fontSize: '0.95rem', color: '#888' }}>
        Progress: {Math.min(playedSeconds, duration)} / {duration} seconds
      </div>
    </div>
  );
};

export default StudentCourseList;
