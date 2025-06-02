import sqlite3
import os
import sys

# Ensure the utils directory is in the Python path for logger
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from logger import setup_logger

logger = setup_logger('db_manager', 'db.log')

class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path
        logger.info(f"DBManager initialized with path: {self.db_path}")

    def _connect(self):
        """Establishes a connection to the SQLite database."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # Allows accessing columns by name
            return conn
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}", exc_info=True)
            if conn:
                conn.close()
            return None

    def initialize_db(self):
        """Creates necessary tables if they don't exist."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                # Agents table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        hostname TEXT,
                        username TEXT,
                        os_info TEXT,
                        ip_address TEXT,
                        checkin_time TEXT,
                        status TEXT DEFAULT 'active'
                    )
                """)
                # Tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id INTEGER NOT NULL,
                        command TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        output TEXT,
                        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
                logger.info("Database tables checked/created successfully.")
            except sqlite3.Error as e:
                logger.error(f"Error initializing database tables: {e}", exc_info=True)
            finally:
                conn.close()

    def add_agent(self, session_id, hostname, username, os_info, ip_address):
        """Adds a new agent to the database or updates existing one."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO agents (session_id, hostname, username, os_info, ip_address, checkin_time)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                """, (session_id, hostname, username, os_info, ip_address))
                conn.commit()
                logger.info(f"Agent {session_id} added/updated.")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error adding/updating agent: {e}", exc_info=True)
            finally:
                conn.close()
        return False

    def get_all_agents(self):
        """Retrieves all agents from the database."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM agents")
                agents = [dict(row) for row in cursor.fetchall()] # Convert rows to dictionaries
                return agents
            except sqlite3.Error as e:
                logger.error(f"Error getting all agents: {e}", exc_info=True)
            finally:
                conn.close()
        return []

    def get_agent_by_id(self, agent_id):
        """Retrieves an agent by its primary ID."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
                agent = cursor.fetchone()
                return dict(agent) if agent else None
            except sqlite3.Error as e:
                logger.error(f"Error getting agent by ID {agent_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return None

    # --- Placeholder methods for tasks (will be implemented later) ---
    def add_task(self, agent_id, command):
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO tasks (agent_id, command) VALUES (?, ?)", (agent_id, command))
                conn.commit()
                logger.info(f"Task for agent {agent_id} added: {command}")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error adding task for agent {agent_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return False

    def get_pending_tasks(self, agent_id):
        """Retrieves pending tasks for a specific agent."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tasks WHERE agent_id = ? AND status = 'pending'", (agent_id,))
                tasks = [dict(row) for row in cursor.fetchall()]
                return tasks
            except sqlite3.Error as e:
                logger.error(f"Error getting pending tasks for agent {agent_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return []

    def update_task_status(self, task_id, status, output=None):
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                if output:
                    cursor.execute("UPDATE tasks SET status = ?, output = ? WHERE id = ?", (status, output, task_id))
                else:
                    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
                conn.commit()
                logger.info(f"Task {task_id} status updated to {status}.")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error updating task {task_id} status to {status}: {e}", exc_info=True)
            finally:
                conn.close()
        return False

# Example usage for testing DBManager directly
if __name__ == "__main__":
    # This will create a 'c2.db' in the database folder for testing
    db_file = os.path.join(os.path.dirname(__file__), 'test_c2.db')
    print(f"Testing DBManager with temporary database: {db_file}")

    # Clean up old test DB if it exists
    if os.path.exists(db_file):
        os.remove(db_file)

    db = DBManager(db_file)
    db.initialize_db()

    print("\nAdding a test agent...")
    db.add_agent("test_session_123", "VictimPC-1", "user1", "Windows 10", "192.168.1.100")
    db.add_agent("test_session_456", "DevServer", "admin", "Ubuntu 22.04", "10.0.0.5")

    print("\nGetting all agents...")
    agents = db.get_all_agents()
    for agent in agents:
        print(f"Agent: {agent['hostname']} ({agent['ip_address']})")

    print("\nGetting agent by ID 1...")
    agent1 = db.get_agent_by_id(1)
    if agent1:
        print(f"Found Agent 1: {agent1['hostname']}")
    else:
        print("Agent 1 not found.")

    print("\nAdding a test task for agent 1...")
    db.add_task(1, "whoami")
    db.add_task(1, "ipconfig")

    print("\nGetting pending tasks for agent 1...")
    tasks = db.get_pending_tasks(1)
    for task in tasks:
        print(f"Task for Agent {task['agent_id']}: {task['command']}")

    print("\nUpdating task 1 status to completed...")
    db.update_task_status(1, "completed", "NT AUTHORITY\\SYSTEM\n")

    print("\nGetting pending tasks for agent 1 again (should be only one left)...")
    tasks = db.get_pending_tasks(1)
    for task in tasks:
        print(f"Task for Agent {task['agent_id']}: {task['command']}")

    print("\nTest complete. You can delete test_c2.db now.")