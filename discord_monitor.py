"""
Discord Self-Bot Join Monitor → Telegram Alerts
Monitors 42 servers for new members, sends detailed Telegram alerts.
Includes Flask keep‑alive for 24/7 hosting on Render.
"""

import asyncio
import os
import requests
import discord
import logging
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# ------------------ SUPPRESS DISCORD LOGS ------------------
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.client').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)

# ------------------ READ TOKENS FROM ENVIRONMENT ------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not DISCORD_TOKEN or not TELEGRAM_TOKEN or not CHAT_ID:
    raise Exception("Missing environment variables: DISCORD_TOKEN, TELEGRAM_TOKEN, CHAT_ID")

# ------------------ ALL 42 SERVERS (ID → friendly name) ------------------
SERVERS = {
    # Original 32
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
    # New 10 servers
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

# Servers to ignore (spammy)
IGNORED_SERVERS = {"703994580499955784", "1067165013397213286"}

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
last_debug_time = {}

# ------------------ TELEGRAM SENDER ------------------
def escape_md(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))

def send_telegram_alert(member, server_name: str):
    joined_at = member.joined_at
    joined_str = joined_at.strftime("%Y-%m-%d %H:%M UTC") if joined_at else "Unknown"
    discrim = f"#{member.discriminator}" if member.discriminator and member.discriminator != "0" else ""

    # Calculate account age
    now = datetime.utcnow()
    delta = now - member.created_at
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = delta.days % 30
    if years > 0:
        age_str = f"{years}y {months}m {days}d"
    elif months > 0:
        age_str = f"{months}m {days}d"
    else:
        age_str = f"{days}d"

    text = (
        f"🚨 *New Member Joined\\!*\n\n"
        f"🏠 *Server:* {escape_md(server_name)}\n"
        f"👤 *Username:* `{escape_md(member.name)}{escape_md(discrim)}`\n"
        f"✨ *Display name:* {escape_md(member.display_name)}\n"
        f"🆔 *User ID:* `{escape_md(str(member.id))}`\n"
        f"📅 *Joined server:* {escape_md(joined_str)}\n"
        f"📆 *Account age:* {escape_md(age_str)}\n"
        f"👥 *Member count:* {escape_md(str(member.guild.member_count))}\n"
        f"📍 *Location:* not available via Discord API"
    )

    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "MarkdownV2"},
            timeout=10,
        )
        if resp.json().get("ok"):
            print(f"  ✅ Alert sent for {member.name} in {server_name}")
        else:
            print(f"  ❌ Telegram error: {resp.json()}")
    except Exception as e:
        print(f"  ❌ Telegram exception: {e}")

# ------------------ FLASK KEEP-ALIVE (for Render) ------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Join monitor is alive."

def run_webserver():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_webserver)
    t.daemon = True
    t.start()

# ------------------ DISCORD CLIENT ------------------
client = discord.Client()
verified_servers = {}
joined_servers = set()

@client.event
async def on_ready():
    print("=" * 60)
    print(f"✅ LOGGED IN AS: {client.user} ({client.user.id})")
    print(f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n📋 SERVERS YOU ARE IN:")
    for guild in client.guilds:
        ignored = " [IGNORED]" if str(guild.id) in IGNORED_SERVERS else ""
        print(f"  🔹 {guild.name}{ignored} – ID: {guild.id} – Members: {guild.member_count}")
        joined_servers.add(str(guild.id))

    print("\n📡 VERIFYING MONITORED SERVERS...")
    for guild_id, name in SERVERS.items():
        if guild_id in joined_servers:
            guild = discord.utils.get(client.guilds, id=int(guild_id))
            print(f"  ✅ {name} – ID: {guild_id} – Members: {guild.member_count if guild else '?'}")
            verified_servers[guild_id] = name
        else:
            print(f"  ❌ {name} – ID: {guild_id} – NOT IN SERVER")

    print(f"\n📊 SUMMARY: Monitoring {len(verified_servers)}/{len(SERVERS)} servers")
    print("\n🚀 Bot is running. Waiting for new members...\n")

@client.event
async def on_member_join(member):
    gid = str(member.guild.id)
    if gid in IGNORED_SERVERS:
        return
    if gid not in verified_servers:
        # rate‑limit debug prints
        now = time.time()
        if now - last_debug_time.get(gid, 0) > 30:
            print(f"🔍 [DEBUG] Join in non‑monitored server: {member.guild.name} (ID: {gid})")
            last_debug_time[gid] = now
        return

    server_name = verified_servers[gid]
    print(f"🔔 [{server_name}] {member.name} just joined! Total members: {member.guild.member_count}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, send_telegram_alert, member, server_name)

# ------------------ RUN ------------------
if __name__ == "__main__":
    keep_alive()   # start Flask web server
    print("\n🚀 STARTING DISCORD SELF-BOT MONITOR (42 servers)")
    print("⚠️  WARNING: This violates Discord ToS – use at your own risk\n")
    try:
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Fatal error: {e}")