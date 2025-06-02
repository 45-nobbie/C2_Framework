# C2 Framework Architecture

## High-Level Overview

The C2 framework is composed of two main components: the **C2 Server** and the **C2 Agent**. The server acts as the command and control hub for the operator, while agents are deployed on target systems to execute commands and relay information back.

+---------------------+                            +---------------------+
|                     |                            |                     |
|    Operator (You)   |                            |    Victim Machine   |
|                     |                            |   (Windows Agent)   |
|      (Python)       |                            |                     |
|                     |                            |                     |
| +-----------------+ |     DNS Queries/Responses  | +-----------------+ |
| | C2 Server/CLI   |<---------------------------->| | C2 Agent (e.g.,| |
| |   (Python)      | |      (DNS Tunneling)     | |   Python/C++)   | |
| +-----------------+ |                            | +-----------------+ |
|         ^           |                            |         ^           |
|         |           |                            |         |           |
|         |           |                            |         |           |
|         v           |                            |         v           |
| +-----------------+ |                            | +-----------------+ |
| | Database        | |                            | | OS Function     | |
| | (e.g., SQLite)  | |                            | |   Calls (API) | |
| | (Agent info,    | |                            | +-----------------+ |
| |   tasks, etc.)  | |                            |                     |
| +-----------------+ |                            |                     |
+---------------------+                            +---------------------+

## Component Breakdown

### 1. C2 Server (`server/`)

The server is the central brain of the C2 framework. It is responsible for:
* Managing connected agents.
* Queuing and dispatching commands to agents.
* Receiving and processing output/data from agents.
* Providing an operator interface (CLI).
* Handling incoming communication from agents (initially DNS).

#### Key Sub-components:

* **`c2_server.py`**: The main entry point for the server CLI. It orchestrates the various modules.
* **`core/`**: Contains core logic for agent management, tasking, and an abstract communication interface.
    * `agent_manager.py`: Manages the lifecycle and state of agents (registration, check-ins, active/inactive).
    * `task_manager.py`: Handles the creation, queuing, dispatching, and completion of tasks for agents.
    * `communication.py`: Defines an interface for C2 communication, allowing for different protocols to be plugged in.
* **`modules/dns_listener.py`**: The concrete implementation of the DNS communication protocol on the server side. It will listen for DNS queries and parse C2-specific data from them.
* **`database/db_manager.py`**: Manages interaction with the backend database (initially SQLite) to persist agent information, task queues, and collected data.
* **`utils/`**: Helper functions for logging, encoding/decoding data for transport, etc.

### 2. C2 Agent (`agent/windows/` - initially)

The agent is the payload deployed on target systems. Its primary responsibilities are:
* Establishing communication with the C2 server (beaconing).
* Receiving commands from the server.
* Executing commands and gathering data.
* Exfiltrating command output and collected data back to the server.
* Maintaining persistence (future).

#### Key Sub-components:

* **`agent.py`**: The main entry point for the agent. Contains the beaconing loop and orchestrates module execution.
* **`comms/dns_client.py`**: The concrete implementation of the DNS communication protocol on the agent side. It will craft and send DNS queries and parse responses for C2 data.
* **`implant/`**: Contains the core functionalities that the agent can perform.
    * `system_info.py`: Functions to gather details about the target system.
    * `executor.py`: Logic to execute shell commands (e.g., `cmd.exe`, PowerShell).
    * `file_ops.py`: Functions for file system interactions (read, write, list, delete).
* **`persistence/`**: (Future) Modules for establishing persistence on the target system.

## Communication Protocol (Initial: DNS Tunneling)

The initial communication channel will be DNS tunneling. This involves:
* **Encoding Data:** C2 commands and responses will be encoded (e.g., Base64) and chunked to fit within DNS query/response limits.
* **Custom Subdomains:** Agents will make DNS queries for specially crafted subdomains (e.g., `<encoded_data>.c2.yourdomain.com`).
* **Server as Authoritative DNS:** The C2 server will act as an authoritative DNS server for a specific subdomain (`c2.yourdomain.com`), allowing it to intercept and respond to these queries.
* **Data Exfiltration:** Agent sends data by encoding it into DNS query names.
* **Command Ingress:** Server sends commands by encoding them into DNS responses (e.g., TXT records, AAAA records).

**(Detailed specification of DNS tunneling protocol to be documented in `docs/communication_protocol.md`)**

## Database Schema (Initial)

A simple SQLite database will store:

* **`agents` table**:
    * `id` (PRIMARY KEY)
    * `session_id` (Unique ID for current agent session)
    * `hostname`
    * `username`
    * `os_info`
    * `ip_address`
    * `checkin_time` (Last seen timestamp)
    * `status` (e.g., 'active', 'inactive')

* **`tasks` table**:
    * `id` (PRIMARY KEY)
    * `agent_id` (FOREIGN KEY to `agents.id`)
    * `command` (The command string)
    * `status` (e.g., 'pending', 'sent', 'completed', 'failed')
    * `output` (Result of the command)
    * `timestamp` (When the task was created)

**(This schema will evolve as functionalities are added.)**