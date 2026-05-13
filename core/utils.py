# core/utils.py

# Centralized execution service import for all code execution
from core.services.execution_service import execution_service, ExecutionResult

def execute_code_piston(code, language, input_data=""):
    """
    Legacy wrapper for backward compatibility. Delegates to the centralized execution service.
    Returns: The output string (stdout) or error message (as before).
    """
    result = execution_service.execute_code(code, language, input_data)
    # Preserve legacy return type: just output string or error message
    if result.success:
        return result.stdout.strip()
    elif result.status == 'timeout':
        return "Error: Execution timed out."
    elif result.status == 'compile_error':
        return f"Error: Compilation failed. {result.compile_output.strip()}"
    elif result.status == 'memory_limit':
        return "Error: Memory limit exceeded."
    elif result.status == 'runtime_error':
        return f"Error: Runtime error. {result.stderr.strip()}"
    elif result.status == 'internal_error':
        return f"Error: Internal error. {result.internal_error or result.reason}"
    else:
        return f"Error: Unknown execution error."