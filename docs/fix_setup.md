# FIX API Setup Guide

**How to obtain and configure your Pepperstone cTrader FIX API credentials**

---

## 🔑 What is a FIX Password?

The FIX API password is **different** from your regular trading login password. It's a separate credential specifically for programmatic API access.

- **Trading password**: Used to log into cTrader web/desktop platform
- **FIX password**: Used for FIX protocol API connections (this system)

---

## 📋 Step-by-Step Instructions

### 1. Open cTrader Platform

Log into your Pepperstone cTrader account (web or desktop version)

### 2. Navigate to FIX API Settings

- Click the **Settings** icon (gear icon, usually in top-right)
- Select **FIX API** from the menu

### 3. Locate Your FIX Credentials

You should see:

```
Account Login: 5227001
FIX Password: [your actual password]
```

**Important**: The FIX password typically looks random, like:

- `xK9pQw2m`
- `BzP3nWq8`
- Similar alphanumeric string

### 4. Generate FIX Password (If Not Present)

If you don't see a FIX password displayed:

1. Look for a button labeled **"Generate FIX Password"** or **"Enable FIX API"**
2. Click it to generate a new password
3. **Copy the password immediately** - it may not be shown again
4. Save it securely (password manager recommended)

### 5. Configure Your Environment

Create a `.env` file in the project root directory:

```bash
# Create .env file
touch .env
nano .env  # or use your preferred editor
```

Add your credentials:

```bash
FIX_PASSWORD=your_actual_fix_password_here
FIX_USERNAME=5227001
```

**Example:**

```bash
FIX_PASSWORD=xK9pQw2m
FIX_USERNAME=5227001
```

### 6. Verify Configuration

Test your credentials with simulation mode:

```bash
python deploy_momentum_production.py --mode simulation
```

This will attempt FIX connection (logon only) without trading.

**Expected output:**

```
✓ Price connection established (SSL)
✓ QUOTE session logged in successfully
✓ Trade connection established (SSL)
✓ TRADE session logged in successfully
```

---

## ⚠️ Troubleshooting

### Error: "Logon rejected: Invalid credentials"

**Cause**: Wrong FIX password

**Solutions:**

1. Double-check you copied the FIX password correctly (not trading password)
2. Make sure there's no extra whitespace in `.env` file
3. Try regenerating FIX password in cTrader settings
4. Verify account number is correct (5227001 for demo)

### Error: "RET_INVALID_DATA"

**Cause**: FIX API not enabled on account

**Solutions:**

1. Check FIX API is enabled in cTrader settings
2. Contact Pepperstone support to enable FIX API
3. Confirm using demo account (live requires separate approval)

### Can't Find FIX API Settings

**Possible reasons:**

- Using mobile app (FIX settings only available on web/desktop)
- Account type doesn't support FIX API
- FIX API feature not available in your region

**Solution:**
Contact Pepperstone support:

- Email: support@pepperstone.com
- Ask: "Please enable FIX API on my demo account 5227001"
- Request FIX API credentials

---

## 🔒 Security Best Practices

### Protect Your Credentials

1. **Never commit `.env` to Git**
   - Already in `.gitignore`
   - Contains sensitive credentials

2. **Use environment variables**
   - System reads from `.env` automatically
   - Never hardcode passwords in source files

3. **Rotate passwords periodically**
   - Generate new FIX password every 90 days
   - Update `.env` with new password

4. **Limit account permissions**
   - Use demo account for testing
   - Live account requires separate approval from Pepperstone

### File Permissions

Secure your `.env` file:

```bash
# Set read-only for owner only
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- (600)
```

---

## 📝 Configuration Reference

### Minimal `.env` Configuration

```bash
FIX_PASSWORD=your_password_here
FIX_USERNAME=5227001
```

### Full `.env` Configuration (All Options)

```bash
# Required
FIX_PASSWORD=your_password_here
FIX_USERNAME=5227001

# Optional - Override defaults
FIX_SENDER_COMP_ID=demo.pepperstone.5227001
FIX_TARGET_COMP_ID=cServer

# Connection endpoints (demo servers)
FIX_PRICE_HOST=demo-us-eqx-01.p.c-trader.com
FIX_PRICE_PORT=5211
FIX_TRADE_HOST=demo-us-eqx-01.p.c-trader.com
FIX_TRADE_PORT=5212
```

### Alternative Servers

If primary server is unavailable, try:

```bash
# US-EQX-02 (alternate US data center)
FIX_PRICE_HOST=demo-us-eqx-02.p.c-trader.com
FIX_TRADE_HOST=demo-us-eqx-02.p.c-trader.com

# European servers (if closer to you)
FIX_PRICE_HOST=demo-eu-eqx-01.p.c-trader.com
FIX_TRADE_HOST=demo-eu-eqx-01.p.c-trader.com
```

---

## 🧪 Testing Your Connection

### Test 1: Logon Only (Safe)

```bash
python deploy_momentum_production.py --mode simulation
```

This will:

- Connect to FIX API
- Send Logon messages
- Maintain heartbeats
- **NOT** send market orders (simulation mode)

### Test 2: Live Connection Test

Use the FIX logon test script:

```bash
python tests/integration/test_fix_logon.py
```

Expected output:

```
Connecting to price server...
✓ Price connection established (SSL)
✓ QUOTE session logged in successfully
Connecting to trade server...
✓ Trade connection established (SSL)
✓ TRADE session logged in successfully
Connection test PASSED
```

---

## 📚 Related Documentation

- [Deployment Guide](deployment_guide.md) - Full deployment instructions
- [Implementation Status](implementation_status.md) - FIX API feature completion

---

## 💡 Common Questions

**Q: Do I need separate credentials for demo and live?**

A: Yes. Demo and live accounts have different credentials:

- Demo: Account 5227001, separate FIX password
- Live: Your live account number, separate FIX password

**Q: Can I use the same FIX password for multiple connections?**

A: Yes, but only one active session per account at a time. Multiple logins with same credentials will disconnect previous session.

**Q: How long does FIX password last?**

A: FIX passwords don't expire, but it's good practice to rotate them every 90 days for security.

**Q: Is my FIX password the same as my cTrader Password?**

A: No! They are completely different:

- cTrader password: Login to platform
- FIX password: API access only

---

_Last updated: February 25, 2026_
