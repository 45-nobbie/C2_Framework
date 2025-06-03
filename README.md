# C2 Framework: Project Zeus (Placeholder Name - can be changed!)

## Project Overview

This project is a multi-functional Command and Control (C2) framework for red teaming simulations. It focuses on stealthy communication (DNS tunneling, HTTP) and robust agent/server functionality, starting with Windows agents.

**For educational and research purposes only. Use only in authorized, controlled environments.**

## Features

- **Server Interface:** Command-Line Interface (CLI)
- **Agent Target:** Windows (Python)
- **Communication:** DNS tunneling (in progress), HTTP (implemented)
- **Agent Functionalities:**
    - Execute shell commands
    - Upload/Download files (planned)
    - List directories (planned)
    - Gather system information (planned)
    - (Future) Process manipulation, screenshot, keylogging, persistence, etc.

## Folder Structure

```
C2_Framework/
├── server/
│   ├── c2_server.py           # Main server CLI
│   ├── core/                  # Core logic (agent/task management, comms interface)
│   ├── modules/
│   │   ├── dns_listener.py    # DNS C2 server module (in progress)
│   │   └── http_listener.py   # HTTP C2 server module (working)
│   ├── database/
│   │   └── db_manager.py      # SQLite DB manager
│   ├── utils/                 # Logging, encoding, helpers
│   └── requirements.txt
├── agent/
│   └── windows/
│       ├── agent.py           # Main agent logic (HTTP beaconing)
│       ├── comms/             # DNS client (planned)
│       ├── implant/           # Command execution, system info, file ops (planned)
│       └── persistence/       # (future)
├── docs/                      # Architecture, protocol, setup, usage
├── tests/                     # (empty, to be filled)
└── README.md
```

## Architecture

- **C2 Server:** Python, manages agents/tasks, handles incoming comms (HTTP/DNS).
- **C2 Agent:** Python for Windows, lightweight, beacons to server, executes tasks.
- **Communication:** HTTP (working), DNS tunneling (in progress).

See [`docs/architecture.md`](docs/architecture.md) for a detailed diagram and breakdown.

## Setup & Installation

See [`docs/setup_guide.md`](docs/setup_guide.md) for full instructions.

**Quick Start (HTTP mode):**
1. Install Python 3.x and dependencies:
    ```
    pip install -r server/requirements.txt
    ```
2. Start the server:
    ```
    python server/c2_server.py
    ```
3. Start the agent (on Windows target):
    ```
    python agent/windows/agent.py
    ```

## Usage

- Use the CLI (`python server/c2_server.py`) to list agents, interact, and send commands.
- Agents beacon to the server and execute received tasks.
- See [`docs/usage_guide.md`](docs/usage_guide.md) for details.

## Development Status

- **Phase 1: Foundational C2**
    - [x] Core C2 Server CLI
    - [x] HTTP Listener (agent/server)
    - [ ] DNS Tunneling Module (in progress)
    - [x] Basic Windows Agent (HTTP)
    - [x] Command & Control Flow (HTTP)
    - [ ] File operations, persistence, advanced features

## Contributing

Contributions are welcome! See guidelines in this file or contact the maintainers.

## License

This project is licensed under the [LICENSE](LICENSE) file.

## Disclaimer

This tool is for educational and authorized penetration testing purposes only. The developers are not responsible for any misuse or damage caused by this software.