import sys
import os
import shlex # For splitting commands robustly

# Ensure the core and utils directories are in the Python path
# This allows us to import modules like 'db_manager' and 'logger'
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'database'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Import modules (will be created in subsequent steps)
from logger import setup_logger
from db_manager import DBManager 

# Set up logging
logger = setup_logger('c2_server', 'server.log')

class C2Server:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'database', 'c2.db')
        self.db_manager = DBManager(self.db_path)
        logger.info(f"C2 Server initializing. Database at: {self.db_path}")
        self.db_manager.initialize_db() # Ensure tables exist

        self.agents = {} # In-memory cache for active agents {agent_id: agent_object}
        # In a real scenario, this would involve loading from DB and handling beaconing

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

        while True:
            try:
                command_line = input("C2> ").strip()
                if not command_line:
                    continue

                # Use shlex to handle commands with arguments and quotes
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
                    print("Shutting down C2 server. Goodbye!")
                    break
                elif command == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for available commands.")
            except EOFError: # Handles Ctrl+D (Unix)
                print("\nReceived EOF. Exiting C2 server.")
                break
            except KeyboardInterrupt: # Handles Ctrl+C
                print("\nCtrl+C detected. Type 'exit' to shut down gracefully.")
            except Exception as e:
                logger.error(f"An unexpected error occurred in CLI: {e}", exc_info=True)
                print(f"An error occurred: {e}")

if __name__ == "__main__":
    server = C2Server()
    server.start_cli()