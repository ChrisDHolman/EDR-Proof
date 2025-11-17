"""
FastAPI Application for CDR Validation Pipeline
Main entry point for the hybrid automation system
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from tasks.phase1_cdr import process_cdr_batch
from tasks.phase2_av import scan_av_batch
from tasks.phase3_edr import test_edr_batch
from tasks.job_manager import JobManager
from src.utils.logger import setup_logger

# Initialize logging
setup_logger()
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="EDR-PROOF CDR Validation Pipeline",
    description="Automated pipeline for validating CDR effectiveness across EDR/AV solutions",
    version="1.0.0"
)

# Initialize job manager
job_manager = JobManager()

# Pydantic models for API
class BatchJobRequest(BaseModel):
    """Request to process a batch of files"""
    file_paths: Optional[List[str]] = None  # List of blob paths, or None to process all in container
    container_name: str = "test-files"
    phases: List[int] = [1, 2, 3]  # Which phases to run
    priority: str = "normal"  # low, normal, high

class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_files: int
    processed_files: int
    failed_files: int
    current_phase: Optional[int]
    progress_percentage: float
    results_summary: Optional[Dict[str, Any]]

class JobResultsResponse(BaseModel):
    """Detailed job results"""
    job_id: str
    status: str
    results: Dict[str, Any]


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EDR-PROOF Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                background: white;
                border-radius: 10px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            h1 { color: #667eea; margin-bottom: 10px; }
            .subtitle { color: #666; font-size: 14px; }
            .controls {
                background: white;
                border-radius: 10px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .btn {
                background: #667eea;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 14px;
                cursor: pointer;
                transition: background 0.3s;
            }
            .btn:hover { background: #5568d3; }
            .btn-success { background: #48bb78; }
            .btn-success:hover { background: #38a169; }
            .input-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                color: #4a5568;
                font-weight: 500;
            }
            input[type="text"], select {
                width: 100%;
                padding: 10px;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-size: 14px;
            }
            .jobs-container {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .job-card {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 15px;
                transition: box-shadow 0.3s;
            }
            .job-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .job-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            .job-id {
                font-family: monospace;
                color: #667eea;
                font-weight: bold;
            }
            .status-badge {
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
            }
            .status-pending { background: #fef5e7; color: #f39c12; }
            .status-running { background: #e8f4f8; color: #3498db; }
            .status-completed { background: #e8f8f5; color: #27ae60; }
            .status-failed { background: #fadbd8; color: #e74c3c; }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: #e2e8f0;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 10px;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transition: width 0.3s;
            }
            .job-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            .stat {
                text-align: center;
                padding: 10px;
                background: #f7fafc;
                border-radius: 6px;
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #667eea;
            }
            .stat-label {
                font-size: 12px;
                color: #718096;
                margin-top: 5px;
            }
            .phase-indicator {
                display: inline-block;
                padding: 2px 8px;
                background: #667eea;
                color: white;
                border-radius: 4px;
                font-size: 11px;
                margin-left: 10px;
            }
            #notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                display: none;
                z-index: 1000;
            }
            .notification-success { border-left: 4px solid #48bb78; }
            .notification-error { border-left: 4px solid #f56565; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>EDR-PROOF Dashboard</h1>
                <p class="subtitle">Content Disarm & Reconstruction Validation Pipeline</p>
            </div>

            <div class="controls">
                <h2 style="margin-bottom: 20px; color: #2d3748;">Start New Job</h2>
                <form id="jobForm">
                    <div class="input-group">
                        <label>Container Name</label>
                        <input type="text" id="containerName" value="test-files" placeholder="Azure Blob Container">
                    </div>
                    <div class="input-group">
                        <label>Phases to Run</label>
                        <div style="display: flex; gap: 15px; margin-top: 8px;">
                            <label style="display: flex; align-items: center;">
                                <input type="checkbox" id="phase1" checked style="margin-right: 5px;">
                                Phase 1 (CDR)
                            </label>
                            <label style="display: flex; align-items: center;">
                                <input type="checkbox" id="phase2" checked style="margin-right: 5px;">
                                Phase 2 (AV)
                            </label>
                            <label style="display: flex; align-items: center;">
                                <input type="checkbox" id="phase3" checked style="margin-right: 5px;">
                                Phase 3 (EDR)
                            </label>
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Priority</label>
                        <select id="priority">
                            <option value="normal">Normal</option>
                            <option value="high">High</option>
                            <option value="low">Low</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-success">Start Batch Job</button>
                </form>
            </div>

            <div class="jobs-container">
                <h2 style="margin-bottom: 20px; color: #2d3748;">Active Jobs</h2>
                <div id="jobsList"></div>
            </div>
        </div>

        <div id="notification"></div>

        <script>
            // Auto-refresh jobs every 5 seconds
            setInterval(loadJobs, 5000);
            loadJobs();

            // Handle form submission
            document.getElementById('jobForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const phases = [];
                if (document.getElementById('phase1').checked) phases.push(1);
                if (document.getElementById('phase2').checked) phases.push(2);
                if (document.getElementById('phase3').checked) phases.push(3);

                const data = {
                    container_name: document.getElementById('containerName').value,
                    phases: phases,
                    priority: document.getElementById('priority').value
                };

                try {
                    const response = await fetch('/api/jobs/batch', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    if (response.ok) {
                        const result = await response.json();
                        showNotification('Job started: ' + result.job_id, 'success');
                        loadJobs();
                    } else {
                        const error = await response.json();
                        showNotification('Error: ' + error.detail, 'error');
                    }
                } catch (err) {
                    showNotification('Network error: ' + err.message, 'error');
                }
            });

            async function loadJobs() {
                try {
                    const response = await fetch('/api/jobs');
                    const jobs = await response.json();

                    const container = document.getElementById('jobsList');

                    if (jobs.length === 0) {
                        container.innerHTML = '<p style="color: #718096; text-align: center;">No jobs yet. Start a batch job above.</p>';
                        return;
                    }

                    container.innerHTML = jobs.map(job => `
                        <div class="job-card">
                            <div class="job-header">
                                <div>
                                    <span class="job-id">${job.job_id}</span>
                                    ${job.current_phase ? `<span class="phase-indicator">Phase ${job.current_phase}</span>` : ''}
                                </div>
                                <span class="status-badge status-${job.status}">${job.status}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${job.progress_percentage}%"></div>
                            </div>
                            <div style="text-align: center; margin-bottom: 10px; color: #4a5568; font-size: 14px;">
                                ${job.progress_percentage.toFixed(1)}% Complete
                            </div>
                            <div class="job-stats">
                                <div class="stat">
                                    <div class="stat-value">${job.total_files}</div>
                                    <div class="stat-label">Total Files</div>
                                </div>
                                <div class="stat">
                                    <div class="stat-value">${job.processed_files}</div>
                                    <div class="stat-label">Processed</div>
                                </div>
                                <div class="stat">
                                    <div class="stat-value">${job.failed_files}</div>
                                    <div class="stat-label">Failed</div>
                                </div>
                                <div class="stat">
                                    <div class="stat-value">${formatDuration(job)}</div>
                                    <div class="stat-label">Duration</div>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } catch (err) {
                    console.error('Failed to load jobs:', err);
                }
            }

            function formatDuration(job) {
                const start = new Date(job.created_at);
                const end = job.completed_at ? new Date(job.completed_at) : new Date();
                const diff = Math.floor((end - start) / 1000);

                if (diff < 60) return diff + 's';
                if (diff < 3600) return Math.floor(diff / 60) + 'm';
                return Math.floor(diff / 3600) + 'h ' + Math.floor((diff % 3600) / 60) + 'm';
            }

            function showNotification(message, type) {
                const notif = document.getElementById('notification');
                notif.textContent = message;
                notif.className = 'notification-' + type;
                notif.style.display = 'block';
                setTimeout(() => notif.style.display = 'none', 5000);
            }
        </script>
    </body>
    </html>
    """


@app.post("/api/jobs/batch", response_model=Dict[str, str])
async def create_batch_job(request: BatchJobRequest):
    """
    Create a new batch processing job

    This will process files through selected phases:
    - Phase 1: CDR processing (Glasswall, OPSWAT, Votiro)
    - Phase 2: AV scanning (OPSWAT MetaDefender, ReversingLabs)
    - Phase 3: EDR testing (CrowdStrike, SentinelOne, Sophos)
    """
    try:
        job_id = str(uuid.uuid4())

        logger.info(f"Creating batch job {job_id} for container {request.container_name}")

        # Create job record
        job_manager.create_job(
            job_id=job_id,
            container_name=request.container_name,
            file_paths=request.file_paths,
            phases=request.phases,
            priority=request.priority
        )

        # Start processing based on phases
        if 1 in request.phases:
            # Phase 1: CDR Processing
            process_cdr_batch.apply_async(
                args=[job_id, request.container_name, request.file_paths],
                queue='phase1',
                priority=get_celery_priority(request.priority)
            )

        return {
            "job_id": job_id,
            "status": "pending",
            "message": f"Batch job created successfully. Processing {len(request.file_paths) if request.file_paths else 'all'} files."
        }

    except Exception as e:
        logger.error(f"Failed to create batch job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs", response_model=List[JobStatusResponse])
async def list_jobs(limit: int = 20):
    """List all jobs (most recent first)"""
    try:
        jobs = job_manager.list_jobs(limit=limit)
        return jobs
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get status of a specific job"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(job_id: str):
    """Get detailed results for a completed job"""
    try:
        results = job_manager.get_job_results(job_id)
        if not results:
            raise HTTPException(status_code=404, detail=f"Results for job {job_id} not found")
        return {
            "job_id": job_id,
            "status": results.get("status", "unknown"),
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    try:
        success = job_manager.cancel_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or cannot be cancelled")
        return {"message": f"Job {job_id} cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


def get_celery_priority(priority: str) -> int:
    """Convert priority string to Celery priority number"""
    priority_map = {
        "low": 3,
        "normal": 5,
        "high": 7
    }
    return priority_map.get(priority, 5)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
