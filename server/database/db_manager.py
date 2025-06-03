import sqlite3
import os
import sys
import logging # Import logging

# Add necessary paths to sys.path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from logger import setup_logger # Import setup_logger

# Set up logging - direct all db_manager output to a file, disable console output
logger = setup_logger('db_manager', 'logs/db_manager.log', level=logging.DEBUG, console_output=False)


class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None # Initialize connection to None
        logger.info(f"DBManager initialized with database: {self.db_path}")

    def _connect(self):
        """Establishes a connection to the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # Allows accessing columns by name
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}", exc_info=True)
            return None

    def initialize_db(self):
        """Creates the agents and tasks tables if they don't exist."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        hostname TEXT,
                        username TEXT,
                        os_info TEXT,
                        ip_address TEXT,
                        checkin_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'active'
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id INTEGER NOT NULL,
                        command TEXT NOT NULL,
                        status TEXT DEFAULT 'pending', -- pending, sent, completed, failed
                        output TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (agent_id) REFERENCES agents (id)
                    )
                """)
                conn.commit()
                logger.info("Database tables initialized successfully.")
            except sqlite3.Error as e:
                logger.error(f"Error initializing database tables: {e}", exc_info=True)
            finally:
                conn.close()

    def add_agent(self, session_id, hostname, username, os_info, ip_address):
        """Adds a new agent or updates an existing one on beacon."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                # Check if agent already exists
                cursor.execute("SELECT id FROM agents WHERE session_id = ?", (session_id,))
                agent_id = cursor.fetchone()

                if agent_id:
                    # Update existing agent's info and last_seen time
                    cursor.execute("""
                        UPDATE agents
                        SET hostname = ?, username = ?, os_info = ?, ip_address = ?, last_seen = CURRENT_TIMESTAMP, status = 'active'
                        WHERE session_id = ?
                    """, (hostname, username, os_info, ip_address, session_id))
                    logger.debug(f"Agent {session_id} updated.")
                else:
                    # Add new agent
                    cursor.execute("""
                        INSERT INTO agents (session_id, hostname, username, os_info, ip_address)
                        VALUES (?, ?, ?, ?, ?)
                    """, (session_id, hostname, username, os_info, ip_address))
                    logger.debug(f"Agent {session_id} added.")
                conn.commit()
                logger.info(f"Agent {session_id} added/updated.")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error adding/updating agent {session_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return False

    def get_all_agents(self):
        """Retrieves all registered agents."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM agents")
                agents = cursor.fetchall()
                return [dict(agent) for agent in agents]
            except sqlite3.Error as e:
                logger.error(f"Error getting all agents: {e}", exc_info=True)
            finally:
                conn.close()
        return []

    def get_agent_by_id(self, agent_id):
        """Retrieves an agent by its primary key ID."""
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

    def get_agent_by_session_id(self, session_id):
        """Retrieves an agent by its unique session ID."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM agents WHERE session_id = ?", (session_id,))
                agent = cursor.fetchone()
                return dict(agent) if agent else None
            except sqlite3.Error as e:
                logger.error(f"Error getting agent by session ID {session_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return None

    def add_task(self, agent_id, command):
        """Adds a new task for an agent. Returns the new task's ID."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (agent_id, command, status)
                    VALUES (?, ?, ?)
                """, (agent_id, command, 'pending'))
                conn.commit()
                task_id = cursor.lastrowid # Get the ID of the last inserted row
                logger.info(f"Task '{command}' added for agent ID {agent_id}. Task ID: {task_id}")
                return task_id
            except sqlite3.Error as e:
                logger.error(f"Error adding task for agent {agent_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return None

    def get_pending_tasks(self, agent_id):
        """Retrieves all pending tasks for a specific agent."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                # Tasks can be 'pending' or 'sent' to be considered for retrieval by agent
                cursor.execute("SELECT * FROM tasks WHERE agent_id = ? AND (status = 'pending' OR status = 'sent') ORDER BY timestamp ASC", (agent_id,))
                tasks = cursor.fetchall()
                return [dict(task) for task in tasks]
            except sqlite3.Error as e:
                logger.error(f"Error getting pending tasks for agent {agent_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return []

    def update_task_status(self, task_id, status, output=None):
        """Updates the status and optional output of a task."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                if output is not None:
                    cursor.execute("""
                        UPDATE tasks
                        SET status = ?, output = ?
                        WHERE id = ?
                    """, (status, output, task_id))
                else:
                    cursor.execute("""
                        UPDATE tasks
                        SET status = ?
                        WHERE id = ?
                    """, (status, task_id))
                conn.commit()
                logger.info(f"Task {task_id} status updated to {status}.")
                return True
            except sqlite3.Error as e:
                logger.error(f"Error updating task {task_id} status to {status}: {e}", exc_info=True)
            finally:
                conn.close()
        return False

    def get_task_by_id(self, task_id):
        """Retrieves a single task by its ID."""
        conn = self._connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
                task = cursor.fetchone()
                return dict(task) if task else None
            except sqlite3.Error as e:
                logger.error(f"Error getting task by ID {task_id}: {e}", exc_info=True)
            finally:
                conn.close()
        return None