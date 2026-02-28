#!/usr/bin/env python
"""
Simple FIX logon test - shows exact message being sent
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.execution.fix_client_v2 import FIXMessage
from datetime import datetime, UTC

# Recreate the exact logon message we're sending
sender_comp_id = "demo.pepperstone.5227001"
target_comp_id = "cServer"  # Case sensitive!
username = "5227001"
password = "5227001_password"

header_fields = {
    '34': '1',  # MsgSeqNum
    '49': sender_comp_id,  # SenderCompID
    '57': 'TRADE',  # TargetSubID
    '50': 'any_string',  # SenderSubID
    '52': datetime.now(UTC).strftime('%Y%m%d-%H:%M:%S'),  # SendingTime
    '56': target_comp_id,  # TargetCompID
}

logon_fields = {
    '98': '0',  # EncryptMethod
    '108': '30',  # HeartBtInt
    '141': 'Y',  # ResetSeqNumFlag
    '553': username,  # Username
    '554': password,  # Password
}

message = FIXMessage.create_message('A', logon_fields, header_fields)

print("=" * 80)
print("FIX LOGON MESSAGE DIAGNOSTIC")
print("=" * 80)
print()
print("Message (pipe-delimited for readability):")
print(message.replace('\x01', '|'))
print()
print("Message breakdown:")
print("-" * 80)

parts = message.split('\x01')
for part in parts:
    if '=' in part:
        tag, value = part.split('=', 1)
        tag_name = {
            '8': 'BeginString',
            '9': 'BodyLength',
            '10': 'CheckSum',
            '34': 'MsgSeqNum',
            '35': 'MsgType',
            '49': 'SenderCompID',
            '50': 'SenderSubID',
            '52': 'SendingTime',
            '56': 'TargetCompID',
            '57': 'TargetSubID',
            '98': 'EncryptMethod',
            '108': 'HeartBtInt',
            '141': 'ResetSeqNumFlag',
            '553': 'Username',
            '554': 'Password',
        }.get(tag, f'Tag{tag}')
        
        # Mask password
        display_value = value if tag != '554' else '*' * len(value)
        print(f"  {tag:>3} = {display_value:20s} ({tag_name})")

print()
print("=" * 80)
print("COMPARISON WITH PEPPERSTONE EXAMPLE:")
print("=" * 80)
print()
print("Expected order after BeginString, BodyLength, MsgType:")
print("  34 (MsgSeqNum)")
print("  49 (SenderCompID)")
print("  57 (TargetSubID)")
print("  50 (SenderSubID)")
print("  52 (SendingTime)")
print("  56 (TargetCompID)")
print("  98 (EncryptMethod)")
print("  108 (HeartBtInt)")
print("  141 (ResetSeqNumFlag)")
print("  553 (Username)")
print("  554 (Password)")
print("  10 (CheckSum)")
print()
print("Pepperstone example from docs:")
print("8=FIX.4.4|9=126|35=A|34=1|49=theBroker.12345|57=TRADE|50=any_string|")
print("52=20170117-08:03:04|56=CSERVER|98=0|108=30|141=Y|553=12345|")
print("554=passw0rd!|10=131|")
print()
print("=" * 80)
print("POSSIBLE ISSUES TO CHECK:")
print("=" * 80)
print()
print("1. Is the password correct?")
print("   Current: 5227001_password")
print("   → Check your Pepperstone cTrader FIX API credentials")
print()
print("2. Is FIX API enabled on account 5227001?")
print("   → Log into cTrader → Settings → FIX API")
print()
print("3. Is this the correct server?")
print("   Current: demo-us-eqx-01.p.c-trader.com:5212")
print("   → Verify in cTrader FIX API settings")
print()
print("4. Is the account number correct?")
print("   Current: 5227001")
print()
