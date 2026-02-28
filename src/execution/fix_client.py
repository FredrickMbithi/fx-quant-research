"""
FIX Session Manager

Manages FIX protocol sessions with Pepperstone cTrader.
Handles connection lifecycle, heartbeats, and message routing.

Note: This uses simplefix library (pure Python) for easier Kali Linux compatibility.
If QuickFIX is available, it can be swapped in for better performance.
"""

import logging
import socket
import ssl
import time
from typing import Dict, Optional, Callable
from datetime import datetime
from threading import Thread, Lock
import yaml

try:
    import simplefix
    HAS_SIMPLEFIX = True
except ImportError:
    HAS_SIMPLEFIX = False
    logging.warning("simplefix not installed - FIX client will not work")

logger = logging.getLogger(__name__)


class FIXSession:
    """
    FIX protocol session management.
    
    Handles:
    - Connection establishment (SSL)
    - Logon/Logout
    - Heartbeat monitoring
    - Sequence number management
    - Message parsing and routing
    """
    
    def __init__(self, session_config: Dict, message_handler: Optional[Callable] = None):
        """
        Initialize FIX session.
        
        Args:
            session_config: Session configuration dict with:
                - host, port_ssl, sender_comp_id, target_comp_id, sender_sub_id
            message_handler: Callback for incoming messages
        """
        if not HAS_SIMPLEFIX:
            raise ImportError("simplefix library required: pip install simplefix")
        
        self.config = session_config
        self.message_handler = message_handler
        
        # Connection details
        self.host = session_config['host']
        self.port = session_config['port_ssl']
        self.sender_comp_id = session_config['sender_comp_id']
        self.target_comp_id = session_config['target_comp_id']
        self.sender_sub_id = session_config.get('sender_sub_id', '')
        
        # Connection state
        self.socket = None
        self.connected = False
        self.logged_on = False
        
        # Sequence numbers
        self.msg_seq_num = 1
        self.expected_target_num = 1
        self.seq_lock = Lock()
        
        # Heartbeat
        self.heartbeat_interval = session_config.get('heartbeat_interval', 30)
        self.last_heartbeat_sent = None
        self.last_message_received = None
        
        # Background thread for message receiving
        self.receiver_thread = None
        self.running = False
        
        logger.info(f"FIX session initialized: {self.sender_comp_id} -> {self.target_comp_id}")
    
    def connect(self) -> bool:
        """
        Establish SSL connection and logon.
        
        Returns:
            True if connected and logged on successfully
        """
        try:
            # Create SSL socket
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.settimeout(10.0)  # Connection timeout
            
            # Wrap with SSL
            context = ssl.create_default_context()
            self.socket = context.wrap_socket(raw_socket, server_hostname=self.host)
            self.socket.settimeout(1.0)  # Set timeout for recv() operations
            
            # Connect
            logger.info(f"Connecting to {self.host}:{self.port}...")
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info("✓ Connected")
            
            # Send logon message
            if self._send_logon():
                # Start receiver thread
                self.running = True
                self.receiver_thread = Thread(target=self._receive_messages, daemon=True)
                self.receiver_thread.start()
                logger.info("Receiver thread started, waiting for logon response...")
                
                # Wait for logon response
                wait_time = 0
                max_wait = 10
                while wait_time < max_wait and not self.logged_on:
                    time.sleep(0.5)
                    wait_time += 0.5
                
                if self.logged_on:
                    logger.info("✓ Logged on to FIX session")
                    return True
                else:
                    logger.error(f"Logon timeout after {wait_time}s or rejected")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            self.connected = False
            return False
    
    def disconnect(self):
        """Send logout and close connection."""
        if self.logged_on:
            self._send_logout()
            time.sleep(1)
        
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        
        self.connected = False
        self.logged_on = False
        logger.info("FIX session disconnected")
    
    def _send_logon(self) -> bool:
        """Send logon message."""
        try:
            msg = simplefix.FixMessage()
            msg.append_pair(8, "FIX.4.4", header=True)  # BeginString
            msg.append_pair(35, "A")  # MsgType = Logon
            msg.append_pair(49, self.sender_comp_id)  # SenderCompID
            
            if self.sender_sub_id:
                msg.append_pair(50, self.sender_sub_id)  # SenderSubID
            
            msg.append_pair(56, self.target_comp_id)  # TargetCompID
            msg.append_pair(34, self.msg_seq_num)  # MsgSeqNum
            msg.append_pair(52, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))  # SendingTime
            msg.append_pair(98, 0)  # EncryptMethod = None
            msg.append_pair(108, self.heartbeat_interval)  # HeartBtInt
            
            # Add Password if configured (tag 554)
            if 'password' in self.config:
                msg.append_pair(554, self.config['password'])
            
            # ResetSeqNumFlag (tag 141) - request reset on logon
            msg.append_pair(141, 'Y')
            
            self._send_message(msg)
            logger.info("Logon message sent")
            logger.debug(f"Logon: SenderCompID={self.sender_comp_id}, "
                        f"SenderSubID={self.sender_sub_id}, "
                        f"TargetCompID={self.target_comp_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send logon: {e}")
            return False
    
    def _send_logout(self):
        """Send logout message."""
        try:
            msg = simplefix.FixMessage()
            msg.append_pair(8, "FIX.4.4", header=True)  # BeginString
            msg.append_pair(35, "5")  # MsgType = Logout
            msg.append_pair(49, self.sender_comp_id)
            if self.sender_sub_id:
                msg.append_pair(50, self.sender_sub_id)
            msg.append_pair(56, self.target_comp_id)
            msg.append_pair(34, self.msg_seq_num)
            msg.append_pair(52, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))
            
            self._send_message(msg)
            logger.info("Logout message sent")
            
        except Exception as e:
            logger.error(f"Failed to send logout: {e}")
    
    def _send_heartbeat(self):
        """Send heartbeat message."""
        try:
            msg.append_pair(8, "FIX.4.4", header=True)  # BeginString
            msg.append_pair(35, "0")  # MsgType = Heartbeat
            msg.append_pair(49, self.sender_comp_id)
            if self.sender_sub_id:
                msg.append_pair(50, self.sender_sub_id)
            msg.append_pair(56, self.target_comp_id)
            msg.append_pair(34, self.msg_seq_num)
            msg.append_pair(52, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))
            
            self._send_message(msg)
            self.last_heartbeat_sent = time.time()
            self.last_heartbeat_sent = time.time()
            logger.debug("Heartbeat sent")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    def _send_message(self, msg: 'simplefix.FixMessage'):
        """
        Send FIX message with sequence number management.
        
        Args:
            msg: FIX message to send
        """
        with self.seq_lock:
            # Encode and send (BeginString already set in message creation)
            encoded = msg.encode()
            self.socket.sendall(encoded)
            self.msg_seq_num += 1
    
    def _receive_messages(self):
        """Background thread to receive and parse messages."""
        parser = simplefix.FixParser()
        logger.info("Receiver thread running...")
        
        while self.running and self.connected:
            try:
                # Receive data
                data = self.socket.recv(4096)
                if not data:
                    logger.warning("Connection closed by peer")
                    break
                
                logger.debug(f"Received {len(data)} bytes")
                
                # Parse FIX messages
                parser.append_buffer(data)
                
                while True:
                    msg = parser.get_message()
                    if msg is None:
                        break
                    
                    self._handle_message(msg)
                    self.last_message_received = time.time()
                
                # Check if heartbeat needed
                if self.last_heartbeat_sent is None or \
                   (time.time() - self.last_heartbeat_sent) > self.heartbeat_interval:
                    self._send_heartbeat()
                
            except socket.timeout:
                # Timeout is normal, check heartbeat
                if self.last_heartbeat_sent is None or \
                   (time.time() - self.last_heartbeat_sent) > self.heartbeat_interval:
                    self._send_heartbeat()
                continue
                
            except Exception as e:
                if self.running:
                    logger.error(f"Receive error: {e}", exc_info=True)
                break
        
        logger.info("Receiver thread stopped")
    
    def _handle_message(self, msg: 'simplefix.FixMessage'):
        """
        Handle incoming FIX message.
        
        Args:
            msg: Parsed FIX message
        """
        msg_type = msg.get(35)  # MsgType
        
        if msg_type == b'A':  # Logon
            logger.info("Received Logon acknowledgment")
            self.logged_on = True
            
        elif msg_type == b'0':  # Heartbeat
            logger.debug("Received Heartbeat")
            
        elif msg_type == b'1':  # Test Request
            logger.debug("Received Test Request")
            # Should send heartbeat in response
            self._send_heartbeat()
            
        elif msg_type == b'5':  # Logout
            logout_text = msg.get(58)  # Text field
            if logout_text:
                logout_text = logout_text.decode() if isinstance(logout_text, bytes) else logout_text
                logger.warning(f"Received Logout from server: {logout_text}")
            else:
                logger.warning("Received Logout from server")
            self.logged_on = False
            
        else:
            # Pass to external handler
            if self.message_handler:
                self.message_handler(msg)
            else:
                logger.debug(f"Unhandled message type: {msg_type}")
    
    def send_raw_message(self, msg: 'simplefix.FixMessage'):
        """
        Send a FIX message (used by market data handler, order handler, etc.).
        
        Args:
            msg: FIX message prepared by caller
        """
        if not self.logged_on:
            raise RuntimeError("Not logged on to FIX session")
        
        # Add standard header fields if not already present
        if not msg.get(49):  # SenderCompID
            msg.append_pair(49, self.sender_comp_id)
        if self.sender_sub_id and not msg.get(50):  # SenderSubID
            msg.append_pair(50, self.sender_sub_id)
        if not msg.get(56):  # TargetCompID
            msg.append_pair(56, self.target_comp_id)
        if not msg.get(34):  # MsgSeqNum
            msg.append_pair(34, self.msg_seq_num)
        if not msg.get(52):  # SendingTime
            msg.append_pair(52, datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))
        
        self._send_message(msg)


class FIXSessionManager:
    """
    Manages multiple FIX sessions (price + trade).
    """
    
    def __init__(self, config_path: str):
        """
        Initialize session manager.
        
        Args:
            config_path: Path to broker config YAML
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.connection_config = config['connection']
        
        # Sessions
        self.price_session = None
        self.trade_session = None
    
    def connect_all(self, price_handler: Callable = None, trade_handler: Callable = None) -> bool:
        """
        Connect both price and trade sessions.
        
        Args:
            price_handler: Callback for price messages
            trade_handler: Callback for trade messages
        
        Returns:
            True if both sessions connected successfully
        """
        # Price session
        self.price_session = FIXSession(
            self.connection_config['price'],
            message_handler=price_handler
        )
        
        # Trade session
        self.trade_session = FIXSession(
            self.connection_config['trade'],
            message_handler=trade_handler
        )
        
        # Connect
        price_ok = self.price_session.connect()
        trade_ok = self.trade_session.connect()
        
        if price_ok and trade_ok:
            logger.info("✓ All FIX sessions connected")
            return True
        else:
            logger.error("Failed to connect all sessions")
            return False
    
    def disconnect_all(self):
        """Disconnect all sessions."""
        if self.price_session:
            self.price_session.disconnect()
        if self.trade_session:
            self.trade_session.disconnect()
        
        logger.info("All FIX sessions disconnected")
