import React, { useState, useEffect } from 'react';
import { useNotification } from './NotificationContext';
import './Jobs.css';

interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export const JobQueue: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const { addNotification } = useNotification();

  const fetchJobs = async () => {
    try {
      const response = await fetch('/api/jobs');
      if (!response.ok) throw new Error('Failed to fetch jobs');
      const data = await response.json();
      setJobs(data);
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 2000); // poll every 2s
    return () => clearInterval(interval);
  }, []);

  const createJob = async (type: string) => {
    setLoading(true);
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type })
      });
      if (!response.ok) throw new Error('Failed to create job');
      addNotification(`Successfully queued ${type} job`, 'success');
      await fetchJobs();
    } catch (err: any) {
      addNotification(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card job-queue">
      <div className="job-queue-header">
        <h2>Job Queue</h2>
        <div className="job-actions">
          <button 
            disabled={loading} 
            onClick={() => createJob('simulation')}
            className="btn btn-primary"
          >
            Run Simulation
          </button>
          <button 
            disabled={loading} 
            onClick={() => createJob('calibration')}
            className="btn btn-secondary"
          >
            Run Calibration
          </button>
        </div>
      </div>
      
      <div className="job-list">
        {jobs.length === 0 ? (
          <p className="empty-state">No jobs in queue.</p>
        ) : (
          jobs.map(job => (
            <div key={job.id} className="job-item">
              <div className="job-info">
                <strong>{job.type}</strong>
                <span className={`status-badge status-${job.status}`}>
                  {job.status}
                </span>
              </div>
              <div className="job-progress-container">
                <div 
                  className="job-progress-bar" 
                  style={{ width: `${job.progress}%` }}
                ></div>
              </div>
              <div className="job-meta">
                <span>{job.progress}%</span>
                <span>ID: {job.id.substring(0, 8)}...</span>
                {job.error_message && <span className="job-error">{job.error_message}</span>}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
