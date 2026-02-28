"""
Pepperstone cTrader FIX Order Adapter

Handles order execution via FIX protocol with Pepperstone.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Callable, Dict
import simplefix

from ..events import OrderEvent, FillEvent, OrderType, OrderSide

logger = logging.getLogger(__name__)


class PepperstoneOrderAdapter:
    """
    Pepperstone-specific FIX order adapter.
    
    Handles:
    - NewOrderSingle (35=D) messages
    - ExecutionReport (35=8) parsing
    - Order status tracking
    """
    
    def __init__(self, fix_session, account: str):
        """
        Initialize adapter.
        
        Args:
            fix_session: FIXSession instance (trade connection)
            account: Account number (e.g., "5227001")
        """
        self.fix_session = fix_session
        self.account = account
        
        # Order tracking
        self.pending_orders: Dict[str, OrderEvent] = {}
        self.fill_callback: Optional[Callable] = None
        
        logger.info(f"Pepperstone adapter initialized for account {account}")
    
    def set_fill_callback(self, callback: Callable[[FillEvent], None]):
        """Set callback for fill events."""
        self.fill_callback = callback
    
    def submit_order(self, order: OrderEvent) -> bool:
        """
        Submit order via FIX NewOrderSingle.
        
        Args:
            order: Order to submit
            
        Returns:
            True if submitted successfully
        """
        try:
            # Create NewOrderSingle message (35=D)
            msg = simplefix.FixMessage()
            msg.append_pair(8, "FIX.4.4", header=True)  # BeginString
            msg.append_pair(35, "D")  # MsgType = NewOrderSingle
            
            # Generate ClOrdID (Client Order ID)
            cl_ord_id = f"COPILOT_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            msg.append_pair(11, cl_ord_id)  # ClOrdID
            
            # Symbol (55)
            msg.append_pair(55, order.symbol)
            
            # Side (54): 1=Buy, 2=Sell
            side_value = "1" if order.side == OrderSide.BUY else "2"
            msg.append_pair(54, side_value)
            
            # TransactTime (60)
            transact_time = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            msg.append_pair(60, transact_time)
            
            # OrderQty (38)
            msg.append_pair(38, str(int(order.quantity)))
            
            # OrdType (40): 1=Market, 2=Limit, 3=Stop
            if order.order_type == OrderType.MARKET:
                msg.append_pair(40, "1")
            elif order.order_type == OrderType.LIMIT:
                msg.append_pair(40, "2")
                if order.limit_price:
                    msg.append_pair(44, f"{order.limit_price:.5f}")  # Price
            elif order.order_type == OrderType.STOP:
                msg.append_pair(40, "3")
                if order.stop_price:
                    msg.append_pair(99, f"{order.stop_price:.5f}")  # StopPx
            
            # Account (1)
            msg.append_pair(1, self.account)
            
            # TimeInForce (59): 0=Day, 1=GTC, 3=IOC, 4=FOK
            msg.append_pair(59, "0")  # Day order
            
            # Store pending order
            self.pending_orders[cl_ord_id] = order
            
            # Send via FIX session
            self.fix_session.send_raw_message(msg)
            
            logger.info(f"Order submitted: {cl_ord_id} - {order.side.value} "
                       f"{order.quantity} {order.symbol}")
            logger.debug(f"FIX Message: {msg}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            return False
    
    def handle_execution_report(self, msg: simplefix.FixMessage):
        """
        Parse ExecutionReport (35=8) from broker.
        
        Args:
            msg: FIX ExecutionReport message
        """
        try:
            # Extract fields
            cl_ord_id = msg.get(11)  # ClOrdID
            exec_type = msg.get(150)  # ExecType
            ord_status = msg.get(39)  # OrdStatus
            symbol = msg.get(55)  # Symbol
            side_val = msg.get(54)  # Side
            
            logger.info(f"ExecutionReport: ClOrdID={cl_ord_id}, ExecType={exec_type}, "
                       f"OrdStatus={ord_status}, Symbol={symbol}")
            
            # ExecType values:
            # 0=New, 1=PartialFill, 2=Fill, 4=Canceled, 8=Rejected
            
            if exec_type == b'2' or exec_type == '2':  # Fill
                self._handle_fill(msg, cl_ord_id)
            elif exec_type == b'1' or exec_type == '1':  # PartialFill
                self._handle_fill(msg, cl_ord_id, partial=True)
            elif exec_type == b'8' or exec_type == '8':  # Rejected
                reject_reason = msg.get(103) or msg.get(58)  # OrdRejReason or Text
                logger.error(f"Order rejected: {cl_ord_id} - {reject_reason}")
            elif exec_type == b'0' or exec_type == '0':  # New
                logger.info(f"Order accepted: {cl_ord_id}")
            
        except Exception as e:
            logger.error(f"Error parsing ExecutionReport: {e}")
    
    def _handle_fill(self, msg: simplefix.FixMessage, cl_ord_id: str, 
                     partial: bool = False):
        """
        Handle fill from ExecutionReport.
        
        Args:
            msg: FIX message
            cl_ord_id: Client order ID
            partial: True if partial fill
        """
        try:
            # Extract fill details
            symbol = msg.get(55).decode() if isinstance(msg.get(55), bytes) else msg.get(55)
            side_val = msg.get(54).decode() if isinstance(msg.get(54), bytes) else msg.get(54)
            side = OrderSide.BUY if side_val == '1' else OrderSide.SELL
            
            # LastQty (32) = quantity filled in this report
            last_qty = float(msg.get(32).decode() if isinstance(msg.get(32), bytes) else msg.get(32))
            
            # LastPx (31) = fill price
            last_px = float(msg.get(31).decode() if isinstance(msg.get(31), bytes) else msg.get(31))
            
            # Commission (12) - optional
            commission_val = msg.get(12)
            commission = float(commission_val.decode() if isinstance(commission_val, bytes) else commission_val) if commission_val else 0.0
            
            # ExecID (17) = broker's execution ID
            exec_id = msg.get(17).decode() if isinstance(msg.get(17), bytes) else msg.get(17)
            
            logger.info(f"Fill received: {last_qty} {symbol} @ {last_px:.5f}")
            
            # Create FillEvent
            fill = FillEvent(
                order_id=cl_ord_id if isinstance(cl_ord_id, str) else cl_ord_id.decode(),
                symbol=symbol,
                side=side,
                quantity=last_qty,
                fill_price=last_px,
                commission=commission,
                slippage=0.0,  # Actual slippage calculated from expected vs actual price
                timestamp=datetime.utcnow(),
                exchange_order_id=exec_id
            )
            
            # Call fill callback
            if self.fill_callback:
                self.fill_callback(fill)
            
            # Remove from pending if fully filled
            if not partial and cl_ord_id in self.pending_orders:
                del self.pending_orders[cl_ord_id]
            
        except Exception as e:
            logger.error(f"Error handling fill: {e}")
    
    def cancel_order(self, cl_ord_id: str, symbol: str) -> bool:
        """
        Cancel order via FIX OrderCancelRequest.
        
        Args:
            cl_ord_id: Client order ID to cancel
            symbol: Symbol
            
        Returns:
            True if cancel request submitted
        """
        try:
            msg = simplefix.FixMessage()
            msg.append_pair(8, "FIX.4.4", header=True)  # BeginString
            msg.append_pair(35, "F")  # MsgType = OrderCancelRequest
            msg.append_pair(11, f"{cl_ord_id}_CANCEL")  # New ClOrdID
            msg.append_pair(41, cl_ord_id)  # OrigClOrdID
            msg.append_pair(55, symbol)  # Symbol
            
            transact_time = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            msg.append_pair(60, transact_time)
            
            self.fix_session.send_raw_message(msg)
            logger.info(f"Cancel request submitted for {cl_ord_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
