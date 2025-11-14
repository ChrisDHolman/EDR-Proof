"""
Helper utilities for CDR Validation Pipeline
"""

import hashlib
import os
import time
import uuid
import magic
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

logger = logging.getLogger(__name__)


def generate_test_run_id() -> str:
    """Generate a unique test run ID"""
    return str(uuid.uuid4())


def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, sha1, md5)

    Returns:
        Hex digest of file hash
    """
    hash_func = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get comprehensive file information

    Args:
        file_path: Path to file

    Returns:
        Dictionary with file metadata
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    stat = os.stat(file_path)

    # Get MIME type
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
    except:
        mime_type = "application/octet-stream"

    # Get file extension
    file_extension = os.path.splitext(file_path)[1].lower()

    # Determine file category
    category = categorize_file(file_extension, mime_type)

    return {
        'file_name': os.path.basename(file_path),
        'file_path': file_path,
        'file_size': stat.st_size,
        'file_extension': file_extension,
        'mime_type': mime_type,
        'category': category,
        'sha256': calculate_file_hash(file_path, 'sha256'),
        'sha1': calculate_file_hash(file_path, 'sha1'),
        'md5': calculate_file_hash(file_path, 'md5'),
        'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


def categorize_file(extension: str, mime_type: str) -> str:
    """
    Categorize file based on extension and MIME type

    Returns:
        Category string (document, executable, archive, image, etc.)
    """
    office_extensions = ['.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt', '.odt', '.ods', '.odp']
    pdf_extensions = ['.pdf']
    executable_extensions = ['.exe', '.dll', '.msi', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar']
    archive_extensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']
    script_extensions = ['.py', '.rb', '.pl', '.sh', '.bash']

    if extension in office_extensions:
        return 'office_document'
    elif extension in pdf_extensions:
        return 'pdf'
    elif extension in executable_extensions:
        return 'executable'
    elif extension in archive_extensions:
        return 'archive'
    elif extension in image_extensions:
        return 'image'
    elif extension in script_extensions:
        return 'script'
    elif 'text' in mime_type:
        return 'text'
    else:
        return 'unknown'


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing special characters

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    import re
    # Remove or replace special characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return sanitized


def format_bytes(bytes_size: int) -> str:
    """
    Format bytes to human-readable string

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2m 30s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def calculate_cost_estimate(
    vm_size: str,
    duration_seconds: float,
    is_spot: bool = True,
    region: str = "eastus"
) -> float:
    """
    Calculate estimated Azure VM cost

    Args:
        vm_size: VM size (e.g., Standard_D4s_v3)
        duration_seconds: Duration in seconds
        is_spot: Whether using Spot instances
        region: Azure region

    Returns:
        Estimated cost in USD
    """
    # Approximate pricing (as of 2024, adjust as needed)
    # These are rough estimates for eastus region
    vm_pricing = {
        'Standard_D2s_v3': 0.096,   # per hour
        'Standard_D4s_v3': 0.192,
        'Standard_D8s_v3': 0.384,
        'Standard_D16s_v3': 0.768,
    }

    hourly_rate = vm_pricing.get(vm_size, 0.192)  # Default to D4s_v3 if not found

    # Spot instances typically 70-90% cheaper
    if is_spot:
        hourly_rate *= 0.2  # Assume 80% discount

    # Calculate cost
    hours = duration_seconds / 3600
    cost = hourly_rate * hours

    return round(cost, 4)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
def retry_with_backoff(func, *args, **kwargs):
    """
    Execute function with retry and exponential backoff

    Args:
        func: Function to execute
        *args, **kwargs: Function arguments

    Returns:
        Function result
    """
    return func(*args, **kwargs)


def safe_delete_file(file_path: str) -> bool:
    """
    Safely delete a file with error handling

    Args:
        file_path: Path to file

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        else:
            logger.warning(f"File does not exist: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        return False


def ensure_directory(directory: str) -> None:
    """
    Ensure directory exists, create if it doesn't

    Args:
        directory: Directory path
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Created directory: {directory}")


def wait_for_condition(
    condition_func,
    timeout_seconds: int = 300,
    poll_interval: int = 5,
    error_message: str = "Condition not met within timeout"
) -> bool:
    """
    Wait for a condition to be true with timeout

    Args:
        condition_func: Function that returns boolean
        timeout_seconds: Maximum time to wait
        poll_interval: Seconds between checks
        error_message: Error message if timeout

    Returns:
        True if condition met, raises TimeoutError otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if condition_func():
            return True
        time.sleep(poll_interval)

    raise TimeoutError(error_message)


def parse_severity(severity_str: str) -> int:
    """
    Parse severity string to numeric value

    Args:
        severity_str: Severity string (critical, high, medium, low, info)

    Returns:
        Numeric severity (5=critical, 1=info)
    """
    severity_map = {
        'critical': 5,
        'high': 4,
        'medium': 3,
        'low': 2,
        'info': 1,
        'informational': 1
    }
    return severity_map.get(severity_str.lower(), 0)


def generate_vm_name(prefix: str = "vm", test_run_id: Optional[str] = None) -> str:
    """
    Generate unique VM name

    Args:
        prefix: Prefix for VM name
        test_run_id: Optional test run ID

    Returns:
        VM name
    """
    if test_run_id:
        short_id = test_run_id[:8]
    else:
        short_id = uuid.uuid4().hex[:8]

    timestamp = datetime.now().strftime("%m%d%H%M")
    return f"{prefix}-{timestamp}-{short_id}"


def is_azure_running() -> bool:
    """
    Check if running in Azure environment

    Returns:
        True if in Azure, False otherwise
    """
    # Check for Azure metadata service
    try:
        import requests
        response = requests.get(
            'http://169.254.169.254/metadata/instance?api-version=2021-02-01',
            headers={'Metadata': 'true'},
            timeout=2
        )
        return response.status_code == 200
    except:
        return False


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format"""
    return datetime.utcnow().isoformat() + 'Z'


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO format timestamp string to datetime"""
    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
