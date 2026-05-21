import os
import requests
import discord
import asyncio
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string
from threading import Thread

# ------------------ READ TOKENS ------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not DISCORD_TOKEN or not TELEGRAM_TOKEN or not CHAT_ID:
    raise Exception("Missing environment variables")

# ------------------ SERVERS ------------------
SERVERS = {
    "1196857788220067943": "Variational",
    "667044843901681675": "Optimism",
    "1364669301751283793": "Solflare",
    # ... (all 42 servers)
}

IGNORED_SERVERS = {"703994580499955784", "1067165013397213286"}
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_telegram(text):
    try:
        requests.post(TELEGRAM_API + "/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_startup_message(connected_count, total_count):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = f"✅ Monitor Online\nConnected: {connected_count}/{total_count}\nStarted: {now_str}\nWatching for joins..."
    send_telegram(text)

# ------------------ DISCORD CLIENT ------------------
client = discord.Client()
verified_servers = {}

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    connected = 0
    for guild in client.guilds:
        if str(guild.id) in SERVERS and str(guild.id) not in IGNORED_SERVERS:
            verified_servers[str(guild.id)] = guild.name
            connected += 1
    send_startup_message(connected, len(SERVERS))
    print(f"Monitoring {connected}/{len(SERVERS)} servers")

@client.event
async def on_member_join(member):
    gid = str(member.guild.id)
    if gid not in verified_servers:
        return
    server_name = verified_servers[gid]
    # Build simple alert
    text = f"🚨 NEW MEMBER JOINED\n🏠 Server: {server_name}\n👤 Username: {member.name}\n🆔 ID: {member.id}"
    send_telegram(text)
    print(f"🔔 [{server_name}] {member.name} joined")

# ------------------ FLASK DASHBOARD ------------------
app = Flask(__name__)

@app.route('/')
@app.route('/dashboard')
def dashboard():
    # Simple HTML dashboard
    html = '''
    <!DOCTYPE html>
    <html>
    <head><title>Discord Monitor Dashboard</title></head>
    <body>
        <h1>Discord Join Monitor</h1>
        <p>Monitoring {{ count }} servers for new members</p>
        <ul>
        {% for name in names %}
            <li>{{ name }}</li>
        {% endfor %}
        </ul>
    </body>
    </html>
    '''
    return render_template_string(html, count=len(verified_servers), names=list(verified_servers.values()))

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ------------------ RUN ------------------
if __name__ == "__main__":
    # Start Flask in background
    Thread(target=run_flask, daemon=True).start()
    # Run Discord client
    client.run(DISCORD_TOKEN)
