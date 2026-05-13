# core/utils.py
from core.services.execution_service import execution_service, ExecutionResult

# Backward compatibility: provide a drop-in function for legacy imports
def execute_code_piston(code, language, input_data=""):
    """
    Legacy wrapper for code execution. Returns only output string for backward compatibility.
    """
    result = execution_service.execute_code(code, language, input_data)
    # For legacy code, return output or error as a string
    if result.success:
        return result.output.strip()
    return result.error or "Execution failed."