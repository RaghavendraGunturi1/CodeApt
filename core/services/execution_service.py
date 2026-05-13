"""
Centralized, production-grade execution service for CodeApt.
Handles all Piston API communication, language/runtime mapping, execution limits, retries, and error handling.
Future-ready for async/queue integration.
"""
import os
import logging
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import Dict, Any, Optional

# Structured result object
class ExecutionResult:
    def __init__(self, *, success: bool, output: str = '', error: str = '',
                 compile_error: bool = False, runtime_error: bool = False,
                 timeout: bool = False, memory_limit: bool = False, internal_error: bool = False,
                 status_code: int = 200, raw_response: Optional[Dict[str, Any]] = None):
        self.success = success
        self.output = output
        self.error = error
        self.compile_error = compile_error
        self.runtime_error = runtime_error
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.internal_error = internal_error
        self.status_code = status_code
        self.raw_response = raw_response or {}

    def to_dict(self):
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'compile_error': self.compile_error,
            'runtime_error': self.runtime_error,
            'timeout': self.timeout,
            'memory_limit': self.memory_limit,
            'internal_error': self.internal_error,
            'status_code': self.status_code,
        }

class ExecutionService:
    # Centralized language/runtime mapping
    LANGUAGE_MAP = {
        'python': {'language': 'python', 'version': '3.12.0'},
        'c': {'language': 'c', 'version': '10.2.0'},
        'cpp': {'language': 'cpp', 'version': '10.2.0'},
        'c++': {'language': 'cpp', 'version': '10.2.0'},
        'javascript': {'language': 'javascript', 'version': '20.11.1'},
        'js': {'language': 'javascript', 'version': '20.11.1'},
        'java': {'language': 'java', 'version': '15.0.2'},
    }

    def __init__(self):
        self.logger = logging.getLogger('core.services.execution_service')
        self.session = requests.Session()
        retries = Retry(
            total=int(os.environ.get('EXECUTION_RETRY_COUNT', 2)),
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        self.piston_url = os.environ.get('PISTON_URL', 'https://exec.codeapt.in/api/v2/execute')
        self.run_timeout = int(os.environ.get('EXECUTION_RUN_TIMEOUT', 7))
        self.compile_timeout = int(os.environ.get('EXECUTION_COMPILE_TIMEOUT', 5))
        self.run_memory_limit = int(os.environ.get('EXECUTION_RUN_MEMORY_LIMIT', 128 * 1024 * 1024))  # 128MB
        self.compile_memory_limit = int(os.environ.get('EXECUTION_COMPILE_MEMORY_LIMIT', 128 * 1024 * 1024))

    def get_language_config(self, language: str) -> Dict[str, str]:
        lang = (language or '').lower()
        config = self.LANGUAGE_MAP.get(lang)
        if not config:
            self.logger.warning(f"Invalid language requested: {language}")
            return self.LANGUAGE_MAP['python']
        return config

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
            resp = self.session.post(self.piston_url, json=payload, headers=headers, timeout=self.run_timeout + 2)
            if resp.status_code != 200:
                self.logger.error(f"Piston returned non-200: {resp.status_code}")
                return ExecutionResult(success=False, error="Execution service unavailable.", internal_error=True, status_code=resp.status_code)
            data = resp.json()
            # Normalize result
            if data.get('run', {}).get('stderr'):
                # Runtime error
                return ExecutionResult(success=False, output=data.get('run', {}).get('stdout', ''), error=data['run']['stderr'], runtime_error=True, raw_response=data)
            if data.get('compile', {}).get('stderr'):
                # Compile error
                return ExecutionResult(success=False, error=data['compile']['stderr'], compile_error=True, raw_response=data)
            if data.get('run', {}).get('signal') == 'SIGKILL':
                # Timeout or memory limit
                if 'memory' in (data.get('run', {}).get('stderr') or '').lower():
                    return ExecutionResult(success=False, error="Memory limit exceeded.", memory_limit=True, raw_response=data)
                return ExecutionResult(success=False, error="Time limit exceeded.", timeout=True, raw_response=data)
            # Success
            return ExecutionResult(success=True, output=data.get('run', {}).get('stdout', ''), raw_response=data)
        except requests.Timeout:
            self.logger.error("Execution timed out.")
            return ExecutionResult(success=False, error="Execution timed out.", timeout=True, internal_error=True)
        except Exception as e:
            self.logger.exception("Internal execution error.")
            return ExecutionResult(success=False, error="Internal error.", internal_error=True)

# Singleton instance for import
execution_service = ExecutionService()
