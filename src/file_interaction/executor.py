"""
File Interaction Engine
Intelligently executes/opens files based on type to trigger EDR behavioral analysis
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import subprocess
import time
import os
import logging
import platform

from ..utils.helpers import get_file_info

logger = logging.getLogger(__name__)


@dataclass
class InteractionResult:
    """Result of file interaction"""
    success: bool
    file_path: str
    file_type: str
    interaction_method: str
    duration_seconds: float
    start_time: datetime
    end_time: datetime
    error_message: Optional[str] = None
    process_spawned: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'interaction_method': self.interaction_method,
            'duration_seconds': self.duration_seconds,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'error_message': self.error_message,
            'process_spawned': self.process_spawned
        }


class FileExecutor:
    """
    Smart file executor that interacts with files based on their type

    This triggers EDR behavioral analysis by:
    - Executing EXEs/DLLs
    - Opening Office documents (with macro enablement)
    - Opening PDFs
    - Extracting archives
    - Simulating user interactions
    """

    def __init__(self, interaction_duration: int = 180, enable_macros: bool = True):
        """
        Initialize file executor

        Args:
            interaction_duration: How long to interact with file (seconds)
            enable_macros: Whether to enable macros for Office docs
        """
        self.interaction_duration = interaction_duration
        self.enable_macros = enable_macros
        self.logger = logging.getLogger(__name__)
        self.is_windows = platform.system() == 'Windows'

    def execute_file(self, file_path: str) -> InteractionResult:
        """
        Execute or interact with a file based on its type

        Args:
            file_path: Path to file

        Returns:
            Interaction result
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file information
        file_info = get_file_info(file_path)
        file_type = file_info['category']
        extension = file_info['file_extension']

        self.logger.info(f"Executing {file_type} file: {file_path}")

        start_time = datetime.now()

        try:
            # Route to appropriate handler based on file type
            if file_type == 'executable':
                result = self._execute_binary(file_path)
            elif file_type == 'office_document':
                result = self._open_office_document(file_path)
            elif file_type == 'pdf':
                result = self._open_pdf(file_path)
            elif file_type == 'archive':
                result = self._extract_archive(file_path)
            elif file_type == 'script':
                result = self._execute_script(file_path, extension)
            else:
                result = self._open_with_default(file_path)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return InteractionResult(
                success=result.get('success', False),
                file_path=file_path,
                file_type=file_type,
                interaction_method=result.get('method', 'unknown'),
                duration_seconds=duration,
                start_time=start_time,
                end_time=end_time,
                error_message=result.get('error'),
                process_spawned=result.get('process_spawned')
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self.logger.error(f"Error executing file: {e}")
            return InteractionResult(
                success=False,
                file_path=file_path,
                file_type=file_type,
                interaction_method='failed',
                duration_seconds=duration,
                start_time=start_time,
                end_time=end_time,
                error_message=str(e)
            )

    def _execute_binary(self, file_path: str) -> Dict[str, Any]:
        """Execute EXE/DLL/binary file"""
        try:
            if not self.is_windows:
                return {'success': False, 'error': 'Cannot execute Windows binaries on non-Windows OS'}

            # Execute the binary and let it run for interaction_duration
            process = subprocess.Popen(
                [file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            self.logger.info(f"Executed {file_path}, PID: {process.pid}")

            # Wait for interaction duration or until process exits
            try:
                process.wait(timeout=self.interaction_duration)
            except subprocess.TimeoutExpired:
                # Process still running - terminate it
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()

            return {
                'success': True,
                'method': 'direct_execution',
                'process_spawned': True
            }

        except Exception as e:
            self.logger.error(f"Error executing binary: {e}")
            return {'success': False, 'error': str(e), 'method': 'direct_execution'}

    def _open_office_document(self, file_path: str) -> Dict[str, Any]:
        """Open Office document (Word, Excel, PowerPoint)"""
        try:
            if self.is_windows:
                # Use start command to open with default application
                os.startfile(file_path)
                method = 'windows_startfile'
            else:
                # On Linux, try LibreOffice
                subprocess.Popen(['libreoffice', file_path])
                method = 'libreoffice'

            self.logger.info(f"Opened Office document: {file_path}")

            # Wait for interaction duration
            time.sleep(self.interaction_duration)

            # Try to close the application (best effort)
            self._close_office_applications()

            return {
                'success': True,
                'method': method,
                'process_spawned': True
            }

        except Exception as e:
            self.logger.error(f"Error opening Office document: {e}")
            return {'success': False, 'error': str(e), 'method': 'office_open'}

    def _open_pdf(self, file_path: str) -> Dict[str, Any]:
        """Open PDF file"""
        try:
            if self.is_windows:
                os.startfile(file_path)
                method = 'windows_startfile'
            else:
                # Try common PDF viewers
                for viewer in ['evince', 'okular', 'xpdf']:
                    try:
                        subprocess.Popen([viewer, file_path])
                        method = viewer
                        break
                    except FileNotFoundError:
                        continue
                else:
                    return {'success': False, 'error': 'No PDF viewer found', 'method': 'pdf_open'}

            self.logger.info(f"Opened PDF: {file_path}")

            # Wait for interaction duration
            time.sleep(self.interaction_duration)

            return {
                'success': True,
                'method': method,
                'process_spawned': True
            }

        except Exception as e:
            self.logger.error(f"Error opening PDF: {e}")
            return {'success': False, 'error': str(e), 'method': 'pdf_open'}

    def _extract_archive(self, file_path: str) -> Dict[str, Any]:
        """Extract archive file"""
        try:
            import zipfile
            import tarfile

            extract_dir = file_path + '_extracted'
            os.makedirs(extract_dir, exist_ok=True)

            ext = os.path.splitext(file_path)[1].lower()

            if ext in ['.zip', '.jar']:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                method = 'zipfile_extract'

            elif ext in ['.tar', '.gz', '.bz2']:
                with tarfile.open(file_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_dir)
                method = 'tarfile_extract'

            else:
                return {'success': False, 'error': f'Unsupported archive type: {ext}', 'method': 'archive_extract'}

            self.logger.info(f"Extracted archive to {extract_dir}")

            return {
                'success': True,
                'method': method,
                'process_spawned': False
            }

        except Exception as e:
            self.logger.error(f"Error extracting archive: {e}")
            return {'success': False, 'error': str(e), 'method': 'archive_extract'}

    def _execute_script(self, file_path: str, extension: str) -> Dict[str, Any]:
        """Execute script file"""
        try:
            interpreters = {
                '.py': 'python',
                '.ps1': 'powershell',
                '.bat': 'cmd',
                '.cmd': 'cmd',
                '.sh': 'bash',
                '.js': 'node'
            }

            interpreter = interpreters.get(extension)
            if not interpreter:
                return {'success': False, 'error': f'No interpreter for {extension}', 'method': 'script_exec'}

            if extension == '.ps1' and self.is_windows:
                cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', file_path]
            elif extension in ['.bat', '.cmd'] and self.is_windows:
                cmd = ['cmd', '/c', file_path]
            else:
                cmd = [interpreter, file_path]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait with timeout
            try:
                process.wait(timeout=self.interaction_duration)
            except subprocess.TimeoutExpired:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()

            return {
                'success': True,
                'method': f'script_{interpreter}',
                'process_spawned': True
            }

        except Exception as e:
            self.logger.error(f"Error executing script: {e}")
            return {'success': False, 'error': str(e), 'method': 'script_exec'}

    def _open_with_default(self, file_path: str) -> Dict[str, Any]:
        """Open file with default system handler"""
        try:
            if self.is_windows:
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', file_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])

            self.logger.info(f"Opened file with default handler: {file_path}")

            # Wait for interaction duration
            time.sleep(self.interaction_duration)

            return {
                'success': True,
                'method': 'default_handler',
                'process_spawned': True
            }

        except Exception as e:
            self.logger.error(f"Error opening file: {e}")
            return {'success': False, 'error': str(e), 'method': 'default_handler'}

    def _close_office_applications(self):
        """Try to close Office applications (Windows)"""
        if not self.is_windows:
            return

        office_processes = ['WINWORD.EXE', 'EXCEL.EXE', 'POWERPNT.EXE', 'OUTLOOK.EXE']

        for process_name in office_processes:
            try:
                subprocess.run(
                    ['taskkill', '/F', '/IM', process_name],
                    capture_output=True,
                    timeout=5
                )
            except Exception:
                pass
