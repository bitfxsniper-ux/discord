"""
Discord Self-Bot Join Monitor → Telegram Alerts (Polling Mode)
Monitors 42 servers for new members via API polling.
Works without View Audit Log permission – captures every join.
"""

import asyncio
import os
import requests
import time
from datetime import datetime, timezone
from flask import Flask
from threading import Thread
from collections import deque

# ------------------ READ TOKENS ------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not DISCORD_TOKEN or not TELEGRAM_TOKEN or not CHAT_ID:
    raise Exception("Missing environment variables")

# ------------------ 42 SERVERS (ID → name) ------------------
SERVERS = {
    "1196857788220067943": "Variational",
    "667044843901681675": "Optimism",
    "1364669301751283793": "Solflare",
    "925207817923743794": "SOL Decoder",
    "402910780124561410": "Compound",
    "978714252934258779": "Zcash",
    "1240797310196125857": "Lombard",
    "1255553987206447194": "OP_NET",
    "1296015181985349715": "STBL",
    "1381686363233194004": "Bullpen",
    "710897173927297116": "Polymarket",
    "1024239646357594122": "THENA",
    "1230430080514396161": "Yei Finance",
    "1209575590362095676": "Avalon Labs",
    "943473409541685319": "Camelot DEX",
    "1139242134495559801": "SPARK DotFi",
    "551050633898360852": "Fluid",
    "841556000632078378": "Bullet",
    "491256308461207573": "Algorand",
    "1329085279411245088": "Falcon Finance",
    "895116209958297631": "LoopScale",
    "793925570739044362": "Goldfinch",
    "885256081289379850": "Ledger OP3N",
    "1385014051272265868": "Shelby",
    "1219739501673451551": "MegaETH",
    "1443079201996410987": "Alien",
    "334085157441110017": "Horizen",
    "1165826384975908924": "Midnight Network",
    "473781666251538452": "Build on Circle",
    "933846070344167464": "Moonwell Fi",
    "839766295808311306": "Telcoin",
    "1270276651636232282": "Pharos",
    "1211893851489304576": "ORANGE WEB3",
    "1268289052264632434": "SKY",
    "1334957028334112922": "40 Acres",
    "943486047625572392": "Peaq Network",
    "900389466781401098": "MapMetrics",
    "1139239009772642416": "AERODROME",
    "842045244035301406": "Limitless",
    "765195245016449027": "Bluefin",
    "1456786812382085459": "Flying Tulip",
    "1303532852003995689": "Vanish Trade",
}

IGNORED_SERVERS = {"703994580499955784", "1067165013397213286"}

HEADERS = {"Authorization": DISCORD_TOKEN}

# ------------------ TELEGRAM SENDER (no location) ------------------
def escape_md(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "MarkdownV2"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_startup_message(connected, total):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = (
        f"✅ *Monitor Online*\n"
        f"Connected: `{connected}/{total}` servers\n"
        f"Started: `{now_str}`\n"
        f"Watching for new joins (polling every 45s)..."
    )
    send_telegram(text)

# ------------------ MEMBER FETCH (pagination for large servers) ------------------
def get_all_members(guild_id):
    """Fetch all member IDs from a Discord guild using pagination."""
    members = []
    after = None
    url = f"https://discord.com/api/v9/guilds/{guild_id}/members?limit=1000"
    while True:
        if after:
            paginated_url = f"{url}&after={after}"
        else:
            paginated_url = url
        response = requests.get(paginated_url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch members for {guild_id}: {response.status_code}")
            break
        data = response.json()
        if not data:
            break
        members.extend(data)
        after = data[-1]['user']['id']
        if len(data) < 1000:
            break
    return members

# ------------------ FLASK KEEP-ALIVE ------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Join monitor is alive (polling mode)."

def run_webserver():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_webserver)
    t.daemon = True
    t.start()

# ------------------ POLLING ENGINE ------------------
previous_members = {}  # guild_id -> set of user IDs
member_details = {}    # guild_id -> dict {user_id: member_object}
last_poll = {}

def account_age(created_at):
    now = datetime.now(timezone.utc)
    delta = now - created_at
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = delta.days % 30
    if years > 0:
        return f"{years}y {months}m {days}d"
    elif months > 0:
        return f"{months}m {days}d"
    else:
        return f"{days}d"

def format_alert(member, server_name):
    joined_at = member.get('joined_at')
    joined_str = joined_at.replace('T', ' ').replace('Z', ' UTC') if joined_at else "Unknown"
    user = member['user']
    username = user.get('global_name') or user['username']
    user_id = user['id']
    discrim = f"#{user.get('discriminator', '0')}" if user.get('discriminator') and user['discriminator'] != '0' else ""
    display_name = member.get('nick') or username
    created = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
    age_str = account_age(created)
    member_count = "?"  # we don't fetch member count in polling to save requests; can be added optionally

    text = (
        f"🚨 *New Member Joined\\!*\n\n"
        f"🏠 *Server:* {escape_md(server_name)}\n"
        f"👤 *Username:* `{escape_md(username)}{escape_md(discrim)}`\n"
        f"✨ *Display name:* {escape_md(display_name)}\n"
        f"🆔 *User ID:* `{user_id}`\n"
        f"📅 *Joined server:* {escape_md(joined_str)}\n"
        f"📆 *Account age:* {escape_md(age_str)}"
    )
    # Note: total member count omitted because it would require an extra API call per join
    return text

def monitor_servers():
    global previous_members, member_details
    while True:
        for guild_id, server_name in SERVERS.items():
            if guild_id in IGNORED_SERVERS:
                continue
            try:
                members = get_all_members(guild_id)
                current_ids = {m['user']['id'] for m in members}
                if guild_id in previous_members:
                    old_ids = previous_members[guild_id]
                    new_ids = current_ids - old_ids
                    for uid in new_ids:
                        # find the member object
                        member_obj = next((m for m in members if m['user']['id'] == uid), None)
                        if member_obj:
                            alert_text = format_alert(member_obj, server_name)
                            send_telegram(alert_text)
                            print(f"🔔 [{server_name}] New member {member_obj['user']['username']} (polling)")
                previous_members[guild_id] = current_ids
                # Optional: store member details for future alerts
                for m in members:
                    member_details.setdefault(guild_id, {})[m['user']['id']] = m
            except Exception as e:
                print(f"Error polling {server_name} ({guild_id}): {e}")
        time.sleep(45)  # poll every 45 seconds

# ------------------ START ------------------
if __name__ == "__main__":
    keep_alive()
    # Verify which servers the bot is actually a member of (for startup message)
    print("Checking server membership...")
    test_url = "https://discord.com/api/v9/users/@me/guilds"
    resp = requests.get(test_url, headers=HEADERS)
    if resp.status_code == 200:
        user_guilds = {str(g['id']) for g in resp.json()}
        connected = sum(1 for sid in SERVERS if sid in user_guilds and sid not in IGNORED_SERVERS)
    else:
        connected = 0
    total = len(SERVERS)
    send_startup_message(connected, total)
    print(f"Starting polling monitor: {connected}/{total} servers reachable.")
    # Start polling in a separate thread
    poll_thread = Thread(target=monitor_servers, daemon=True)
    poll_thread.start()
    # Keep main thread alive
    while True:
        time.sleep(60)
