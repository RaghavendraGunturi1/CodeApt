"""
ExecutionService: Centralized, production-grade service for code execution via Piston API.

- Encapsulates all Piston communication
- Provides a single interface for code execution
- Handles retries, timeouts, connection pooling, and error normalization
- Centralizes language/runtime mapping
- Prepares for future async/queue integration
"""

import os
import logging
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import Dict, Any, Optional, Tuple

# Structured result object
class ExecutionResult:
    def __init__(self, success: bool, stdout: str = '', stderr: str = '',
                 compile_output: str = '', status: str = '',
                 exit_code: Optional[int] = None, reason: str = '',
                 internal_error: Optional[str] = None, raw: Optional[dict] = None):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.compile_output = compile_output
        self.status = status  # 'success', 'compile_error', 'runtime_error', 'timeout', 'memory_limit', 'internal_error'
        self.exit_code = exit_code
        self.reason = reason
        self.internal_error = internal_error
        self.raw = raw or {}

    def to_dict(self):
        return {
            'success': self.success,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'compile_output': self.compile_output,
            'status': self.status,
            'exit_code': self.exit_code,
            'reason': self.reason,
            'internal_error': self.internal_error,
        }

class ExecutionService:
    # Centralized language/runtime mapping
    LANGUAGE_MAP = {
        'python': {'language': 'python', 'version': '3.12.0'},
        'c': {'language': 'c', 'version': '10.2.0'},
        'cpp': {'language': 'c++', 'version': '10.2.0'},
        'c++': {'language': 'c++', 'version': '10.2.0'},
        'javascript': {'language': 'javascript', 'version': '20.11.1'},
        'js': {'language': 'javascript', 'version': '20.11.1'},
        'java': {'language': 'java', 'version': '15.0.2'},
    }

    def __init__(self):
        self.logger = logging.getLogger('ExecutionService')
        self.piston_url = os.environ.get('PISTON_URL', 'https://exec.codeapt.in/api/v2/execute')
        self.run_timeout = float(os.environ.get('EXEC_RUN_TIMEOUT', 8.0))
        self.compile_timeout = float(os.environ.get('EXEC_COMPILE_TIMEOUT', 4.0))
        self.run_memory_limit = int(os.environ.get('EXEC_RUN_MEMORY_LIMIT', 256 * 1024 * 1024))
        self.compile_memory_limit = int(os.environ.get('EXEC_COMPILE_MEMORY_LIMIT', 256 * 1024 * 1024))
        self.max_retries = int(os.environ.get('EXEC_MAX_RETRIES', 2))
        self.session = self._init_session()

    def _init_session(self):
        session = requests.Session()
        retries = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        return session

    def get_language_config(self, language: str) -> Dict[str, str]:
        return self.LANGUAGE_MAP.get(language.lower(), self.LANGUAGE_MAP['python'])

    def execute_code(self, code: str, language: str, stdin: str = "") -> ExecutionResult:
        config = self.get_language_config(language)
        payload = {
            "language": config['language'],
            "version": config['version'],
            "files": [{"content": code}],
            "stdin": stdin,
            "args": [],
            "compile_timeout": self.compile_timeout,
            "run_timeout": self.run_timeout,
            "compile_memory_limit": self.compile_memory_limit,
            "run_memory_limit": self.run_memory_limit,
        }
        headers = {'Content-Type': 'application/json'}
        try:
            resp = self.session.post(
                self.piston_url,
                json=payload,
                headers=headers,
                timeout=self.run_timeout + self.compile_timeout + 2
            )
            if resp.status_code != 200:
                self.logger.error(f"Piston error: {resp.status_code} {resp.text}")
                return ExecutionResult(
                    success=False,
                    status='internal_error',
                    reason=f'Piston error: {resp.status_code}',
                    internal_error=resp.text
                )
            data = resp.json()
            return self._parse_response(data)
        except requests.Timeout:
            self.logger.warning("Piston execution timeout")
            return ExecutionResult(success=False, status='timeout', reason='Execution timed out')
        except Exception as e:
            self.logger.exception("Piston execution failed")
            return ExecutionResult(success=False, status='internal_error', reason='Internal error', internal_error=str(e))

    def _parse_response(self, data: Dict[str, Any]) -> ExecutionResult:
        # Piston v2 response normalization
        run = data.get('run', {})
        compile_ = data.get('compile', {})
        stdout = run.get('stdout', '')
        stderr = run.get('stderr', '')
        compile_output = compile_.get('stdout', '') + compile_.get('stderr', '')
        exit_code = run.get('code', None)
        status = 'success'
        reason = ''
        if compile_ and compile_.get('code', 0) != 0:
            status = 'compile_error'
            reason = 'Compilation failed'
        elif run.get('signal') == 'SIGKILL':
            status = 'memory_limit'
            reason = 'Memory limit exceeded'
        elif exit_code and exit_code != 0:
            status = 'runtime_error'
            reason = 'Runtime error'
        return ExecutionResult(
            success=(status == 'success'),
            stdout=stdout,
            stderr=stderr,
            compile_output=compile_output,
            status=status,
            exit_code=exit_code,
            reason=reason,
            raw=data
        )

# Singleton instance for import
execution_service = ExecutionService()
