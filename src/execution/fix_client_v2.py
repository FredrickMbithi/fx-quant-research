"""
FIX Protocol Client for Pepperstone cTrader

Implements FIX 4.4 protocol for connecting to Pepperstone's cTrader platform.
Based on official cTrader FIX API documentation (Rules of Engagement).
"""

import socket
import ssl
import logging
from datetime import datetime, UTC
from typing import Optional, Callable, Dict, List, Tuple
import threading
import time

logger = logging.getLogger(__name__)

# Note: TargetCompID is case-sensitive - must be 'cServer' not 'CSERVER'


class FIXMessage:
    """Helper class for constructing FIX 4.4 messages"""
    
    SOH = '\x01'  # Start of Header delimiter
    
    @staticmethod
    def calculate_checksum(message: str) -> str:
        """Calculate FIX checksum (modulo 256 of sum of bytes)"""
        checksum = sum(ord(c) for c in message) % 256
        return f"{checksum:03d}"
    
    @staticmethod
    def create_message(msg_type: str, fields: dict | List[Tuple[str, str]], header_fields: dict) -> str:
        """
        Create a complete FIX message with header, body, and trailer.
        
        Args:
            msg_type: FIX message type (tag 35)
            fields: Body fields as {tag: value} dict
            header_fields: Header fields (SenderCompID, TargetCompID, etc.)
        """
        # Body construction starts with MsgType
        body = f"35={msg_type}{FIXMessage.SOH}"
        
        # Add header fields in proper order (after MsgType)
        # Per Pepperstone docs: 34, 49, 57, 50, 52, 56
        for tag in ['34', '49', '57', '50', '52', '56']:
            if tag in header_fields:
                body += f"{tag}={header_fields[tag]}{FIXMessage.SOH}"
        
        # Add message-specific fields
        # Accept either dict (unique tags) or list of (tag, value) to allow repeats
        if isinstance(fields, list):
            for tag, value in fields:
                # If value is iterable (list/tuple), expand to multiple tag instances
                if isinstance(value, (list, tuple)):
                    for v in value:
                        body += f"{tag}={v}{FIXMessage.SOH}"
                else:
                    body += f"{tag}={value}{FIXMessage.SOH}"
        else:
            for tag, value in sorted(fields.items(), key=lambda x: int(x[0])):
                body += f"{tag}={value}{FIXMessage.SOH}"
        
        # Calculate body length
        body_length = len(body)
        
        # Construct header (BeginString and BodyLength)
        header = f"8=FIX.4.4{FIXMessage.SOH}9={body_length}{FIXMessage.SOH}"
        
        # Calculate checksum (header + body)
        message_without_checksum = header + body
        checksum = FIXMessage.calculate_checksum(message_without_checksum)
        
        # Add trailer
        trailer = f"10={checksum}{FIXMessage.SOH}"
        
        return message_without_checksum + trailer
    
    @staticmethod
    def parse_message(raw_message: str) -> dict:
        """Parse a FIX message into a dictionary of tag-value pairs"""
        fields = {}
        parts = raw_message.split(FIXMessage.SOH)
        
        for part in parts:
            if '=' in part:
                tag, value = part.split('=', 1)
                fields[tag] = value
        
        return fields


class PepperstoneFIXClient:
    """
    FIX 4.4 client for Pepperstone cTrader.
    
    Handles both QUOTE and TRADE connections for market data and order execution.
    """
    
    def __init__(self, config: dict):
        """
        Initialize FIX client.
        
        Args:
            config: Configuration dict with connection details
        """
        self.config = config
        
        # Connection state
        self.price_socket: Optional[socket.socket] = None
        self.trade_socket: Optional[socket.socket] = None
        self.price_seq_num = 1
        self.trade_seq_num = 1
        self.is_price_logged_in = False
        self.is_trade_logged_in = False
        
        # Message handlers
        self.on_execution_report: Optional[Callable] = None
        self.on_market_data: Optional[Callable] = None  # callback(symbol, bid, ask, timestamp)
        self.on_position_report: Optional[Callable] = None  # callback(positions: List[dict])
        
        # Heartbeat settings
        self.heartbeat_interval = 30  # seconds
        self.last_price_heartbeat = time.time()
        self.last_trade_heartbeat = time.time()
        self.last_price_received = time.time()  # Track when we last received ANY message
        self.last_trade_received = time.time()
        
        # Connection health
        self.price_connection_healthy = False
        self.trade_connection_healthy = False
        self.connection_timeout = 90  # Consider dead if no response for 90s (3x heartbeat)
        
        # Market data state
        self.last_market_data_time: Optional[datetime] = None
        self.latest_bid: Optional[float] = None
        self.latest_ask: Optional[float] = None
        
        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds (will use exponential backoff)
        
        # Threads
        self.price_thread: Optional[threading.Thread] = None
        self.trade_thread: Optional[threading.Thread] = None
        self.running = False
    
    def connect_price(self) -> bool:
        """Connect to price (market data) server"""
        try:
            logger.info(f"Connecting to price server {self.config['price_host']}:{self.config['price_port_ssl']}")
            
            # Create SSL socket
            context = ssl.create_default_context()
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.price_socket = context.wrap_socket(raw_socket, server_hostname=self.config['price_host'])
            
            # Connect
            self.price_socket.connect((self.config['price_host'], self.config['price_port_ssl']))
            logger.info("✓ Price connection established (SSL)")
            
            # Send Logon
            return self._logon('QUOTE', self.price_socket, is_price=True)
            
        except Exception as e:
            logger.error(f"Price connection failed: {e}")
            return False
    
    def connect_trade(self) -> bool:
        """Connect to trade (execution) server"""
        try:
            logger.info(f"Connecting to trade server {self.config['trade_host']}:{self.config['trade_port_ssl']}")
            
            # Create SSL socket
            context = ssl.create_default_context()
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.trade_socket = context.wrap_socket(raw_socket, server_hostname=self.config['trade_host'])
            
            # Connect
            self.trade_socket.connect((self.config['trade_host'], self.config['trade_port_ssl']))
            logger.info("✓ Trade connection established (SSL)")
            
            # Send Logon
            return self._logon('TRADE', self.trade_socket, is_price=False)
            
        except Exception as e:
            logger.error(f"Trade connection failed: {e}")
            return False
    
    def _logon(self, sender_sub_id: str, sock: socket.socket, is_price: bool) -> bool:
        """
        Send Logon message (MsgType=A)
        
        Per cTrader FIX API documentation:
        - Tag 98 (EncryptMethod): 0 = NONE_OTHER
        - Tag 108 (HeartBtInt): Heartbeat interval in seconds
        - Tag 141 (ResetSeqNumFlag): Y = reset sequence numbers
        - Tag 553 (Username): Numeric trader login
        - Tag 554 (Password): FIX API password
        """
        try:
            # Prepare header fields
            header_fields = {
                '49': self.config['sender_comp_id'],  # e.g., demo.pepperstone.5227001
                '56': self.config['target_comp_id'],  # CSERVER
                '34': str(self.price_seq_num if is_price else self.trade_seq_num),
                '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),
                '57': sender_sub_id,  # TargetSubID: QUOTE or TRADE
                '50': 'any_string',  # SenderSubID: can be any string per docs
            }
            
            # Logon body fields (in order per FIX spec)
            logon_fields = {
                '98': '0',  # EncryptMethod: NONE_OTHER
                '108': str(self.heartbeat_interval),  # HeartBtInt
                '141': 'Y',  # ResetSeqNumFlag
                '553': self.config['username'],  # Numeric trader login
                '554': self.config['password'],  # FIX password
            }
            
            # Create message
            message = FIXMessage.create_message('A', logon_fields, header_fields)
            
            logger.info(f"Sending Logon ({sender_sub_id})...")
            logger.info(f"Logon message: {message.replace(FIXMessage.SOH, '|')}")
            
            # Send
            sock.sendall(message.encode('ascii'))
            
            # Increment sequence number
            if is_price:
                self.price_seq_num += 1
            else:
                self.trade_seq_num += 1
            
            # Wait for response
            response = self._receive_message(sock)
            logger.info(f"Logon response: {response.replace(FIXMessage.SOH, '|')}")
            
            # Parse response
            fields = FIXMessage.parse_message(response)
            
            # Check if Logon accepted (MsgType=A) or rejected (MsgType=5)
            if fields.get('35') == 'A':
                logger.info(f"✓ {sender_sub_id} session logged in successfully")
                if is_price:
                    self.is_price_logged_in = True
                    self.last_price_received = time.time()  # Initialize receive timestamp
                else:
                    self.is_trade_logged_in = True
                    self.last_trade_received = time.time()  # Initialize receive timestamp
                
                # Start heartbeat thread
                if is_price:
                    self.price_thread = threading.Thread(
                        target=self._heartbeat_loop,
                        args=(sock, sender_sub_id, True),
                        daemon=True
                    )
                    self.price_thread.start()
                else:
                    self.trade_thread = threading.Thread(
                        target=self._heartbeat_loop,
                        args=(sock, sender_sub_id, False),
                        daemon=True
                    )
                    self.trade_thread.start()
                
                return True
            elif fields.get('35') == '5':  # Logout
                error_msg = fields.get('58', 'Unknown error')
                logger.error(f"✗ Logon rejected: {error_msg}")
                return False
            else:
                logger.error(f"✗ Unexpected response to Logon: MsgType={fields.get('35')}")
                return False
                
        except Exception as e:
            logger.error(f"Logon failed: {e}", exc_info=True)
            return False
    
    def _heartbeat_loop(self, sock: socket.socket, sender_sub_id: str, is_price: bool):
        """Background thread to send heartbeats and receive messages"""
        logger.info(f"Heartbeat thread started for {sender_sub_id}")
        self.running = True
        
        # Mark connection as healthy when thread starts
        if is_price:
            self.price_connection_healthy = True
        else:
            self.trade_connection_healthy = True
        
        while self.running:
            try:
                # Check for incoming messages
                sock.settimeout(1.0)
                try:
                    response = self._receive_message(sock, timeout=1.0)
                    if response:
                        logger.debug(f"Received: {response.replace(FIXMessage.SOH, '|')}")
                        # Update last received timestamp
                        if is_price:
                            self.last_price_received = time.time()
                        else:
                            self.last_trade_received = time.time()
                        self._handle_message(response, sender_sub_id)
                except socket.timeout:
                    pass
                
                # Send heartbeat if needed
                last_hb = self.last_price_heartbeat if is_price else self.last_trade_heartbeat
                if time.time() - last_hb > self.heartbeat_interval:
                    self._send_heartbeat(sock, sender_sub_id, is_price)
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Heartbeat loop error: {e}")
                    # Mark connection as unhealthy
                    if is_price:
                        self.price_connection_healthy = False
                    else:
                        self.trade_connection_healthy = False
                break
        
        # Mark connection as unhealthy when thread exits
        if is_price:
            self.price_connection_healthy = False
        else:
            self.trade_connection_healthy = False
            
        logger.info(f"Heartbeat thread stopped for {sender_sub_id}")
    
    def _send_heartbeat(self, sock: socket.socket, sender_sub_id: str, is_price: bool):
        """Send Heartbeat message (MsgType=0)"""
        try:
            header_fields = {
                '49': self.config['sender_comp_id'],
                '56': self.config['target_comp_id'],
                '34': str(self.price_seq_num if is_price else self.trade_seq_num),
                '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),
                '57': sender_sub_id,
                '50': 'any_string',
            }
            
            message = FIXMessage.create_message('0', {}, header_fields)
            sock.sendall(message.encode('ascii'))
            
            if is_price:
                self.price_seq_num += 1
                self.last_price_heartbeat = time.time()
            else:
                self.trade_seq_num += 1
                self.last_trade_heartbeat = time.time()
            
            logger.debug(f"Heartbeat sent ({sender_sub_id})")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            # Re-raise to trigger connection health update in heartbeat loop
            raise
    
    def _handle_message(self, message: str, sender_sub_id: str):
        """Handle incoming FIX message"""
        fields = FIXMessage.parse_message(message)
        msg_type = fields.get('35')
        
        if msg_type == '0':  # Heartbeat
            logger.debug(f"Heartbeat received from {sender_sub_id}")
        elif msg_type == '8':  # Execution Report
            logger.info("Execution Report received")
            if self.on_execution_report:
                self.on_execution_report(fields)
        elif msg_type in ('X', 'W'):  # MarketDataIncremental / Snapshot
            self._handle_market_data_message(message)
        elif msg_type == 'j':  # Business Message Reject
            logger.error(f"Business Reject: {fields.get('58', 'Unknown')}")
        elif msg_type == '3':  # Reject
            logger.error(f"Session Reject: {fields.get('58', 'Unknown')}")
    
    def _receive_message(self, sock: socket.socket, timeout: float = 5.0) -> str:
        """Receive a complete FIX message from socket"""
        sock.settimeout(timeout)
        buffer = b''
        
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                
                buffer += chunk
                
                # Check if we have a complete message (ends with SOH after checksum)
                if b'\x0110=' in buffer and buffer.count(b'\x01') >= 3:
                    # Find the end of checksum
                    checksum_start = buffer.find(b'\x0110=')
                    if checksum_start != -1:
                        # Checksum is 3 digits + SOH
                        checksum_end = checksum_start + 7  # \x01 + 10= + 3 digits + \x01
                        if len(buffer) >= checksum_end:
                            # We have a complete message
                            buffer = buffer[:checksum_end]
                            break
            
            return buffer.decode('ascii')
            
        except socket.timeout:
            return buffer.decode('ascii') if buffer else ''

    def subscribe_market_data(self, symbols: List[str], depth: int = 1) -> Optional[str]:
        """
        Send MarketDataRequest (MsgType=V) for given symbols.
        
        Args:
            symbols: List of symbols (e.g., ['GBPUSD'])
            depth: Market depth (default 1 = top of book)
        
        Returns:
            MDReqID string if sent, None on failure
        """
        if not self.is_price_logged_in or self.price_socket is None:
            logger.error("Cannot subscribe to market data: PRICE session not logged in")
            return None
        
        try:
            md_req_id = f"MD_{int(time.time() * 1000)}"
            
            header_fields = {
                '49': self.config['sender_comp_id'],
                '56': self.config['target_comp_id'],
                '34': str(self.price_seq_num),
                '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),
                '57': 'QUOTE',
                '50': 'any_string',
            }
            
            # Build repeating groups using list of tuples to preserve duplicates
            fields: List[Tuple[str, str]] = [
                ('262', md_req_id),   # MDReqID
                ('263', '1'),         # SubscriptionRequestType: 1 = Snapshot + Updates
                ('264', str(depth)),  # MarketDepth
                ('267', '2'),         # NoMDEntryTypes (bid + ask)
                ('269', '0'),         # MDEntryType: BID
                ('269', '1'),         # MDEntryType: OFFER
                ('146', str(len(symbols))),  # NoRelatedSym
            ]
            
            for sym in symbols:
                fields.append(('55', sym))  # Symbol
            
            message = FIXMessage.create_message('V', fields, header_fields)
            
            logger.info(f"Subscribing market data for {symbols} (MDReqID={md_req_id})")
            logger.debug(f"MarketDataRequest: {message.replace(FIXMessage.SOH, '|')}")
            
            self.price_socket.sendall(message.encode('ascii'))
            self.price_seq_num += 1
            return md_req_id
        
        except Exception as e:
            logger.error(f"Market data subscription failed: {e}", exc_info=True)
            return None

    def _handle_market_data_message(self, raw_message: str):
        """
        Parse MarketDataSnapshot/Incremental and trigger market data callback.
        
        Supports BID (269=0) and ASK (269=1) entries.
        """
        symbol, bid, ask, ts = self._parse_market_data(raw_message)
        
        # Update internal state
        if bid is not None:
            self.latest_bid = bid
        if ask is not None:
            self.latest_ask = ask
        self.last_market_data_time = ts
        
        # Trigger callback
        if self.on_market_data and symbol and bid is not None and ask is not None:
            try:
                self.on_market_data(symbol, bid, ask, ts)
            except Exception as exc:
                logger.error(f"Market data callback failed: {exc}", exc_info=True)

    def _parse_market_data(self, raw_message: str) -> tuple[Optional[str], Optional[float], Optional[float], datetime]:
        """
        Parse FIX market data message into bid/ask.
        
        Returns:
            (symbol, bid, ask, timestamp)
        """
        parts = raw_message.split(FIXMessage.SOH)
        symbol = None
        bid = None
        ask = None
        current_entry: Dict[str, str] = {}
        entries: List[Dict[str, str]] = []
        
        for part in parts:
            if '=' not in part:
                continue
            tag, value = part.split('=', 1)
            
            if tag == '55':
                symbol = value
            elif tag == '269':
                # Start of new MDEntry
                if current_entry:
                    entries.append(current_entry)
                current_entry = {'269': value}
            elif tag in ('270', '271', '272', '273'):
                current_entry[tag] = value
        
        if current_entry:
            entries.append(current_entry)
        
        # Extract bid/ask
        for entry in entries:
            entry_type = entry.get('269')
            price = float(entry.get('270')) if '270' in entry else None
            if entry_type == '0' and price is not None:
                bid = price
            elif entry_type == '1' and price is not None:
                ask = price
        
        # Timestamp
        ts = datetime.now(UTC)
        date_tag = None
        time_tag = None
        for entry in entries:
            if '272' in entry:
                date_tag = entry['272']
            if '273' in entry:
                time_tag = entry['273']
        if date_tag and time_tag:
            try:
                ts = datetime.strptime(f"{date_tag}-{time_tag}", "%Y%m%d-%H:%M:%S.%f").replace(tzinfo=UTC)
            except ValueError:
                try:
                    ts = datetime.strptime(f"{date_tag}-{time_tag}", "%Y%m%d-%H:%M:%S").replace(tzinfo=UTC)
                except ValueError:
                    pass
        
        return symbol, bid, ask, ts
    
    def send_new_order(self, symbol: str, side: str, quantity: float, 
                       order_type: str = 'MARKET', price: Optional[float] = None,
                       stop_px: Optional[float] = None,
                       position_id: Optional[str] = None) -> Optional[str]:
        """
        Send New Order Single (MsgType=D)
        
        Args:
            symbol: FIX Symbol ID (check cTrader Symbol Info window)
            side: "BUY" or "SELL"
            quantity: Order size in units
            order_type: "MARKET", "LIMIT", or "STOP"
            price: Limit price (required for LIMIT orders)
            stop_px: Stop price (required for STOP orders)
            position_id: Position ID to add to (optional, for hedged accounts)
        
        Returns:
            Client order ID if successful, None otherwise
        """
        if not self.is_trade_logged_in:
            logger.error("Cannot send order: not logged in to TRADE session")
            return None
        
        try:
            # Generate unique ClOrdID
            cl_ord_id = f"ORD_{int(time.time() * 1000)}"
            
            # Header fields
            header_fields = {
                '49': self.config['sender_comp_id'],
                '56': self.config['target_comp_id'],
                '34': str(self.trade_seq_num),
                '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),
                '57': 'TRADE',
                '50': 'any_string',
            }
            
            # Order fields (in order per FIX spec)
            order_fields = {
                '11': cl_ord_id,  # ClOrdID
                '55': symbol,  # Symbol (FIX ID)
                '54': '1' if side.upper() == 'BUY' else '2',  # Side
                '60': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),  # TransactTime
                '38': str(int(quantity)),  # OrderQty
                '40': {'MARKET': '1', 'LIMIT': '2', 'STOP': '3'}[order_type.upper()],  # OrdType
            }
            
            # Add price for LIMIT orders
            if order_type.upper() == 'LIMIT' and price is not None:
                order_fields['44'] = f"{price:.5f}"
            
            # Add stop price for STOP orders
            if order_type.upper() == 'STOP' and stop_px is not None:
                order_fields['99'] = f"{stop_px:.5f}"
            
            # Add position ID if specified
            if position_id:
                order_fields['721'] = position_id
            
            # Create message
            message = FIXMessage.create_message('D', order_fields, header_fields)
            
            logger.info(f"Sending {order_type} {side} order: {quantity} units of symbol {symbol}")
            logger.debug(f"Order message: {message.replace(FIXMessage.SOH, '|')}")
            
            # Send
            self.trade_socket.sendall(message.encode('ascii'))
            self.trade_seq_num += 1
            
            logger.info(f"✓ Order sent (ClOrdID: {cl_ord_id})")
            
            return cl_ord_id
            
        except Exception as e:
            logger.error(f"Failed to send order: {e}", exc_info=True)
            return None
    
    def disconnect(self):
        """Disconnect from both sessions"""
        self.running = False
        
        # Send Logout to both sessions
        if self.is_price_logged_in and self.price_socket:
            self._logout(self.price_socket, 'QUOTE', True)
        
        if self.is_trade_logged_in and self.trade_socket:
            self._logout(self.trade_socket, 'TRADE', False)
        
        # Wait for threads
        if self.price_thread:
            self.price_thread.join(timeout=2.0)
        if self.trade_thread:
            self.trade_thread.join(timeout=2.0)
        
        # Close sockets
        if self.price_socket:
            self.price_socket.close()
        if self.trade_socket:
            self.trade_socket.close()
        
        logger.info("Disconnected from FIX sessions")
    
    def _logout(self, sock: socket.socket, sender_sub_id: str, is_price: bool):
        """Send Logout message (MsgType=5)"""
        try:
            header_fields = {
                '49': self.config['sender_comp_id'],
                '56': self.config['target_comp_id'],
                '34': str(self.price_seq_num if is_price else self.trade_seq_num),
                '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),
                '57': sender_sub_id,
                '50': 'any_string',
            }
            
            message = FIXMessage.create_message('5', {}, header_fields)
            sock.sendall(message.encode('ascii'))
            
            if is_price:
                self.price_seq_num += 1
            else:
                self.trade_seq_num += 1
            
            logger.info(f"Logout sent ({sender_sub_id})")
            
            # Wait for logout response
            response = self._receive_message(sock, timeout=2.0)
            if response:
                logger.debug(f"Logout response: {response.replace(FIXMessage.SOH, '|')}")
            
        except Exception as e:
            logger.error(f"Logout failed: {e}")
    
    def request_positions(self) -> bool:
        """
        Request current positions (Position Report).
        
        Sends OrderMassStatusRequest (MsgType=AF) to retrieve all open positions.
        On response, triggers on_position_report callback.
        
        Returns:
            True if request sent successfully
        """
        if not self.is_trade_logged_in:
            logger.error("Cannot request positions: TRADE session not logged in")
            return False
        
        try:
            mass_status_req_id = f"POS_{int(time.time() * 1000)}"
            
            header_fields = {
                '49': self.config['sender_comp_id'],
                '56': self.config['target_comp_id'],
                '34': str(self.trade_seq_num),
                '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),
                '57': 'TRADE',
                '50': 'any_string',
            }
            
            # OrderMassStatusRequest fields
            fields = {
                '584': mass_status_req_id,  # MassStatusReqID
                '585': '7',  # MassStatusReqType: 7 = Status for all orders
            }
            
            message = FIXMessage.create_message('AF', fields, header_fields)
            
            logger.info(f"Requesting positions (MassStatusReqID={mass_status_req_id})")
            logger.debug(f"OrderMassStatusRequest: {message.replace(FIXMessage.SOH, '|')}")
            
            self.trade_socket.sendall(message.encode('ascii'))
            self.trade_seq_num += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Position request failed: {e}", exc_info=True)
            return False
    
    def is_connected(self) -> bool:
        """
        Check if both PRICE and TRADE connections are healthy.
        
        A connection is healthy if:
        1. The heartbeat thread is running (connection_healthy flag is True)
        2. We've received a message within the timeout period
        
        Returns:
            True if both connections are healthy
        """
        current_time = time.time()
        
        # Check PRICE connection
        price_ok = (
            self.price_connection_healthy and
            self.is_price_logged_in and
            (current_time - self.last_price_received) < self.connection_timeout
        )
        
        # Check TRADE connection
        trade_ok = (
            self.trade_connection_healthy and
            self.is_trade_logged_in and
            (current_time - self.last_trade_received) < self.connection_timeout
        )
        
        return price_ok and trade_ok
    
    def get_connection_status(self) -> dict:
        """
        Get detailed connection status for both sessions.
        
        Returns:
            Dictionary with connection details
        """
        current_time = time.time()
        
        return {
            'price': {
                'logged_in': self.is_price_logged_in,
                'thread_healthy': self.price_connection_healthy,
                'last_received_ago': current_time - self.last_price_received,
                'healthy': (
                    self.price_connection_healthy and
                    self.is_price_logged_in and
                    (current_time - self.last_price_received) < self.connection_timeout
                )
            },
            'trade': {
                'logged_in': self.is_trade_logged_in,
                'thread_healthy': self.trade_connection_healthy,
                'last_received_ago': current_time - self.last_trade_received,
                'healthy': (
                    self.trade_connection_healthy and
                    self.is_trade_logged_in and
                    (current_time - self.last_trade_received) < self.connection_timeout
                )
            },
            'overall_healthy': self.is_connected()
        }
    
    def is_market_data_stale(self, max_age_seconds: float = 5.0) -> bool:
        """
        Check if market data is stale (older than max_age_seconds).
        
        Args:
            max_age_seconds: Maximum age in seconds before data is considered stale
        
        Returns:
            True if stale or no data received yet
        """
        if self.last_market_data_time is None:
            return True
        
        age = (datetime.now(UTC) - self.last_market_data_time).total_seconds()
        return age > max_age_seconds
    
    def get_latest_quote(self) -> Optional[Dict[str, float]]:
        """
        Get the latest bid/ask quote.
        
        Returns:
            Dict with 'bid', 'ask', 'mid', 'spread' or None if no data
        """
        if self.latest_bid is None or self.latest_ask is None:
            return None
        
        return {
            'bid': self.latest_bid,
            'ask': self.latest_ask,
            'mid': (self.latest_bid + self.latest_ask) / 2,
            'spread': self.latest_ask - self.latest_bid
        }
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect both sessions with exponential backoff.
        
        Returns:
            True if both sessions reconnected successfully
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return False
        
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
        
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay}s...")
        time.sleep(delay)
        
        try:
            # Stop heartbeat threads
            self.running = False
            if self.price_thread and self.price_thread.is_alive():
                self.price_thread.join(timeout=2.0)
            if self.trade_thread and self.trade_thread.is_alive():
                self.trade_thread.join(timeout=2.0)
            
            # Close existing connections
            if self.price_socket:
                try:
                    self.price_socket.close()
                except:
                    pass
            if self.trade_socket:
                try:
                    self.trade_socket.close()
                except:
                    pass
            
            # Reset state
            self.price_socket = None
            self.trade_socket = None
            self.is_price_logged_in = False
            self.is_trade_logged_in = False
            self.price_connection_healthy = False
            self.trade_connection_healthy = False
            self.price_seq_num = 1
            self.trade_seq_num = 1
            
            # Reconnect
            logger.info("Reconnecting to price session...")
            if not self.connect_price():
                logger.error("Price reconnection failed")
                return False
            
            logger.info("Reconnecting to trade session...")
            if not self.connect_trade():
                logger.error("Trade reconnection failed")
                return False
            
            logger.info("✓ Reconnection successful")
            self.reconnect_attempts = 0  # Reset counter on success
            return True
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False
    
    def parse_execution_report(self, fields: Dict[str, str]) -> Dict:
        """
        Parse ExecutionReport (MsgType=8) into structured data.
        
        Returns dict with:
            - cl_ord_id: Client order ID
            - order_id: Broker order ID
            - exec_type: Execution type (0=New, 1=PartialFill, 2=Fill, 4=Canceled, 8=Rejected)
            - ord_status: Order status (0=New, 1=PartialFill, 2=Filled, 4=Canceled, 8=Rejected)
            - symbol: Symbol
            - side: 1=Buy, 2=Sell
            - order_qty: Order quantity
            - price: Execution price (if filled)
            - cum_qty: Cumulative quantity filled
            - leaves_qty: Remaining quantity
            - text: Reject reason (if rejected)
        """
        return {
            'cl_ord_id': fields.get('11', ''),
            'order_id': fields.get('37', ''),
            'exec_type': fields.get('150', ''),
            'ord_status': fields.get('39', ''),
            'symbol': fields.get('55', ''),
            'side': fields.get('54', ''),
            'order_qty': float(fields.get('38', 0)),
            'price': float(fields.get('31', 0)) if '31' in fields else None,
            'cum_qty': float(fields.get('14', 0)),
            'leaves_qty': float(fields.get('151', 0)),
            'text': fields.get('58', ''),
            'exec_id': fields.get('17', ''),
            'transact_time': fields.get('60', '')
        }
