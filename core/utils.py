# core/utils.py
import requests

# CONFIGURATION: Your DevTunnel URL pointing to the local Piston container
PISTON_API_URL = "https://2b9xkx83-2000.inc1.devtunnels.ms/api/v2/execute"

def execute_code_piston(code, language, input_data=""):
    """
    Central function to run code using your Local Piston instance via DevTunnel.
    Returns: The output string (stdout) or error message.
    """
    # UPDATED: Matches the versions found on your server
    language_map = {
        'python': {'language': 'python', 'version': '3.12.0'},
        'javascript': {'language': 'javascript', 'version': '20.11.1'}, # Updated to match index
        'java': {'language': 'java', 'version': '15.0.2'},
        'cpp': {'language': 'c++', 'version': '10.2.0'},
        'c': {'language': 'c', 'version': '10.2.0'},
    }
    
    # Default to Python if unknown
    config = language_map.get(language, language_map['python'])

    payload = {
        "language": config['language'],
        "version": config['version'],
        "files": [{"content": code}],
        "stdin": input_data
    }

    # CRITICAL: This header prevents the DevTunnel "Warning" page from blocking the API
    headers = {
        'Content-Type': 'application/json',
        'X-Tunnel-Skip-Anti-Phishing-Page': 'true'
    }

    try:
        # Timeout set to 10s to account for DevTunnel latency
        response = requests.post(PISTON_API_URL, json=payload, headers=headers, timeout=10)
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            # Combine stdout and stderr so the user sees errors too
            output = result.get('run', {}).get('output', '')
            return output.strip()
        else:
            # If 400 occurs again, print the error message from Piston to debug
            return f"Error: API returned {response.status_code}. Msg: {response.text}"
            
    except requests.exceptions.Timeout:
        return "Error: Execution timed out (DevTunnel might be slow)."
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to DevTunnel. Is the link active?"
    except Exception as e:
        return f"Error: Connection failed - {str(e)}"