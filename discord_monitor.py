import os
import requests
import time
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string
from collections import deque

# ------------------ CONFIGURATION ------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not DISCORD_TOKEN or not TELEGRAM_TOKEN or not CHAT_ID:
    raise Exception("Missing environment variables")

# ------------------ 42 SERVERS (ID -> name) ------------------
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

# ------------------ TELEGRAM SENDER ------------------
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "MarkdownV2"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_startup_message(connected, total):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = f"✅ *Monitor Online*\nConnected: `{connected}/{total}` servers\nStarted: `{now_str}`\nPolling every 45s..."
    send_telegram(text)

# ------------------ MEMBER FETCH ------------------
def get_all_members(guild_id):
    members = []
    after = None
    url = f"https://discord.com/api/v9/guilds/{guild_id}/members?limit=1000"
    while True:
        paginated_url = url + (f"&after={after}" if after else "")
        resp = requests.get(paginated_url, headers=HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        members.extend(data)
        after = data[-1]['user']['id']
        if len(data) < 1000:
            break
    return members

# ------------------ POLLING STATE ------------------
previous_members = {}
member_counts = {}
recent_joins = deque(maxlen=50)  # store dicts: {server, username, user_id, time}

def format_join_alert(member, server_name):
    user = member['user']
    username = user.get('global_name') or user['username']
    return {
        "server": server_name,
        "username": username,
        "user_id": user['id'],
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }

def monitor_servers():
    while True:
        for guild_id, server_name in SERVERS.items():
            if guild_id in IGNORED_SERVERS:
                continue
            try:
                members = get_all_members(guild_id)
                current_ids = {m['user']['id'] for m in members}
                old_ids = previous_members.get(guild_id, set())
                new_ids = current_ids - old_ids
                for uid in new_ids:
                    member_obj = next((m for m in members if m['user']['id'] == uid), None)
                    if member_obj:
                        join_info = format_join_alert(member_obj, server_name)
                        recent_joins.appendleft(join_info)
                        # Send Telegram alert
                        from_telegram_alert(member_obj, server_name)
                previous_members[guild_id] = current_ids
                member_counts[guild_id] = len(current_ids)
            except Exception as e:
                print(f"Error polling {server_name}: {e}")
        time.sleep(45)

def from_telegram_alert(member, server_name):
    # Build Telegram message (same as before, but we reuse)
    joined_at = member.get('joined_at', '')
    joined_str = joined_at.replace('T', ' ').replace('Z', ' UTC') if joined_at else "Unknown"
    user = member['user']
    username = user.get('global_name') or user['username']
    user_id = user['id']
    discrim = f"#{user.get('discriminator', '0')}" if user.get('discriminator') and user['discriminator'] != '0' else ""
    display_name = member.get('nick') or username
    created = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
    delta = datetime.now(timezone.utc) - created
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = delta.days % 30
    if years > 0:
        age_str = f"{years}y {months}m {days}d"
    elif months > 0:
        age_str = f"{months}m {days}d"
    else:
        age_str = f"{days}d"

    def escape_md(t):
        special = r"\_*[]()~`>#+-=|{}.!"
        return "".join(f"\\{c}" if c in special else c for c in str(t))

    text = (
        f"🚨 *New Member Joined\\!*\n\n"
        f"🏠 *Server:* {escape_md(server_name)}\n"
        f"👤 *Username:* `{escape_md(username)}{escape_md(discrim)}`\n"
        f"✨ *Display name:* {escape_md(display_name)}\n"
        f"🆔 *User ID:* `{user_id}`\n"
        f"📅 *Joined server:* {escape_md(joined_str)}\n"
        f"📆 *Account age:* {escape_md(age_str)}"
    )
    send_telegram(text)

# ------------------ FLASK WEB SERVER + API ------------------
app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string(DASHBOARD_HTML)

@app.route('/dashboard')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    # Return server list with current member counts and connectivity
    guilds_info = []
    for sid, name in SERVERS.items():
        if sid in IGNORED_SERVERS:
            continue
        member_count = member_counts.get(sid, 0)
        last_poll = "OK" if sid in previous_members else "Pending"
        guilds_info.append({
            "id": sid,
            "name": name,
            "member_count": member_count,
            "status": last_poll
        })
    total_servers = len([s for s in SERVERS if s not in IGNORED_SERVERS])
    monitored = len([s for s in SERVERS if s in previous_members])
    return jsonify({
        "total": total_servers,
        "monitored": monitored,
        "servers": guilds_info,
        "last_update": datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/recent-joins')
def api_recent_joins():
    return jsonify(list(recent_joins))

# HTML DASHBOARD (embedded)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Holly Analytics | Discord Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background: #0a0c10; color: #eef2ff; padding: 2rem; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 2rem; flex-wrap: wrap; gap: 1rem; }
        h1 { font-size: 2.2rem; font-weight: 600; background: linear-gradient(135deg, #a855f7, #3b82f6); -webkit-background-clip: text; background-clip: text; color: transparent; letter-spacing: -0.02em; }
        .badge { background: #1e1f2c; padding: 0.3rem 0.9rem; border-radius: 40px; font-size: 0.8rem; border: 1px solid #2d2f3e; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
        .stat-card { background: #111318; border-radius: 24px; padding: 1.2rem; border: 1px solid #222530; backdrop-filter: blur(4px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .stat-card h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #7e8aa2; margin-bottom: 0.5rem; }
        .stat-number { font-size: 2.4rem; font-weight: 700; color: #a78bfa; }
        .server-table { background: #111318; border-radius: 24px; overflow: hidden; border: 1px solid #222530; margin-bottom: 2rem; }
        .server-table table { width: 100%; border-collapse: collapse; }
        .server-table th { text-align: left; padding: 1rem; background: #0f1119; color: #a0aec0; font-weight: 500; border-bottom: 1px solid #222530; }
        .server-table td { padding: 0.8rem 1rem; border-bottom: 1px solid #1a1c26; font-size: 0.9rem; }
        .server-table tr:hover { background: #161a24; }
        .status-online { color: #10b981; font-weight: 500; display: flex; align-items: center; gap: 0.3rem; }
        .recent-joins { background: #111318; border-radius: 24px; padding: 1rem; border: 1px solid #222530; }
        .recent-joins h2 { font-size: 1.2rem; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .join-entry { padding: 0.6rem; border-bottom: 1px solid #1a1c26; font-family: monospace; font-size: 0.85rem; display: flex; justify-content: space-between; flex-wrap: wrap; }
        .join-time { color: #6b7280; }
        .refresh { text-align: right; margin-bottom: 1rem; }
        .refresh button { background: #1e1f2c; border: none; color: white; padding: 0.4rem 1rem; border-radius: 30px; cursor: pointer; transition: 0.2s; }
        .refresh button:hover { background: #2d2f3e; }
        .footer { text-align: center; margin-top: 2rem; font-size: 0.7rem; color: #4b5563; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🔍 Holly Analytics · Discord Sentinel</h1>
        <div class="badge">Live Monitor · Real‑time</div>
    </div>
    <div class="refresh"><button onclick="fetchAllData()">⟳ Refresh now</button></div>
    <div class="stats-grid" id="statsGrid"></div>
    <div class="server-table">
        <table>
            <thead><tr><th>Server Name</th><th>ID</th><th>Members</th><th>Status</th></tr></thead>
            <tbody id="serverTableBody"></tbody>
        </table>
    </div>
    <div class="recent-joins">
        <h2>📋 Recent join events</h2>
        <div id="recentJoinsList"></div>
    </div>
    <div class="footer">Encrypted channel · Auto‑refresh every 30 seconds</div>
</div>
<script>
    async function fetchStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            document.getElementById('statsGrid').innerHTML = `
                <div class="stat-card"><h3>Total monitored</h3><div class="stat-number">${data.total}</div></div>
                <div class="stat-card"><h3>Active connections</h3><div class="stat-number">${data.monitored}</div></div>
                <div class="stat-card"><h3>Last poll</h3><div class="stat-number">${new Date(data.last_update).toLocaleTimeString()}</div></div>
            `;
            const tbody = document.getElementById('serverTableBody');
            tbody.innerHTML = '';
            data.servers.forEach(s => {
                const row = `<tr>
                    <td><strong>${escapeHtml(s.name)}</strong></td>
                    <td>${s.id}</td>
                    <td>${s.member_count.toLocaleString()}</td>
                    <td class="status-online">● ${s.status === 'OK' ? 'Active' : 'Pending'}</td>
                </tr>`;
                tbody.insertAdjacentHTML('beforeend', row);
            });
        } catch(e) { console.error(e); }
    }
    async function fetchJoins() {
        try {
            const res = await fetch('/api/recent-joins');
            const joins = await res.json();
            const container = document.getElementById('recentJoinsList');
            container.innerHTML = '';
            if(joins.length === 0) {
                container.innerHTML = '<div class="join-entry">No recent joins yet.</div>';
                return;
            }
            joins.forEach(j => {
                const entry = `<div class="join-entry">
                    <span><strong>${escapeHtml(j.username)}</strong> joined <strong>${escapeHtml(j.server)}</strong></span>
                    <span class="join-time">${j.time}</span>
                </div>`;
                container.insertAdjacentHTML('beforeend', entry);
            });
        } catch(e) { console.error(e); }
    }
    function escapeHtml(str) { return str.replace(/[&<>]/g, function(m){if(m==='&') return '&amp;'; if(m==='<') return '&lt;'; if(m==='>') return '&gt;'; return m;}); }
    function fetchAllData() { fetchStatus(); fetchJoins(); }
    fetchAllData();
    setInterval(fetchAllData, 30000);
</script>
</body>
</html>
"""

# ------------------ START THREADS ------------------
if __name__ == "__main__":
    # Start polling in background
    thread = threading.Thread(target=monitor_servers, daemon=True)
    thread.start()
    # Send startup message after a short delay
    time.sleep(5)
    try:
        resp = requests.get("https://discord.com/api/v9/users/@me/guilds", headers=HEADERS)
        user_guilds = {str(g['id']) for g in resp.json()} if resp.status_code == 200 else set()
    except:
        user_guilds = set()
    connected = sum(1 for sid in SERVERS if sid in user_guilds and sid not in IGNORED_SERVERS)
    send_startup_message(connected, len(SERVERS))
    # Run Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
