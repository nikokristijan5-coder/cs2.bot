import discord
from discord.ext import commands
import os
import sqlite3

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ANN_CHANNEL = "announcements"

active_match = None
snapshot = {}

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("esports.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    acr INTEGER DEFAULT 1000,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS teams (
    name TEXT PRIMARY KEY,
    members TEXT,
    acr INTEGER DEFAULT 1000
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_a TEXT,
    team_b TEXT,
    map TEXT,
    winner TEXT,
    score TEXT,
    mvp TEXT,
    adr TEXT
)
""")

conn.commit()

# =========================
# HELPERS
# =========================
def clean(m):
    return [x for x in m.split(",") if x.strip()]

def create_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO players VALUES (?,1000,0,0)", (uid,))
        conn.commit()

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name.upper(),))
    return c.fetchone()

def in_team(uid):
    c.execute("SELECT name FROM teams WHERE members LIKE ?", (f"%{uid}%",))
    return c.fetchone()

def is_admin(ctx):
    return any(r.permissions.administrator for r in ctx.author.roles)

def ann_channel(guild):
    for ch in guild.text_channels:
        if ch.name == ANN_CHANNEL:
            return ch
    return None

def send_ann(guild, embed):
    ch = ann_channel(guild)
    if ch:
        return ch.send(embed=embed)
    return None

# =========================
# TEAM ACR UPDATE
# =========================
def update_team_acr(team):
    c.execute("SELECT members FROM teams WHERE name=?", (team,))
    members = clean(c.fetchone()[0])

    total = 0
    count = 0

    for m in members:
        c.execute("SELECT acr FROM players WHERE id=?", (m,))
        r = c.fetchone()
        if r:
            total += r[0]
            count += 1

    avg = int(total / count) if count else 1000

    c.execute("UPDATE teams SET acr=? WHERE name=?", (avg, team))
    conn.commit()

# =========================
# PLAYER UPDATE (ACR FIX)
# =========================
def update_player(uid, win):
    create_player(uid)

    if win:
        c.execute("UPDATE players SET acr=acr+25,wins=wins+1 WHERE id=?", (uid,))
        c.execute("UPDATE players SET acr=acr+5 WHERE id=?", (uid,))
    else:
        c.execute("UPDATE players SET acr=acr-25,losses=losses+1 WHERE id=?", (uid,))
        c.execute("UPDATE players SET acr=acr-8 WHERE id=?", (uid,))

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# =========================
# PLAYER COMMANDS
# =========================
@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="🎮 PLAYER COMMANDS", color=0x00ffcc)
    embed.add_field(name="Teams", value="!create !join !leave", inline=False)
    embed.add_field(name="Stats", value="!stats !leaderboard", inline=False)
    await ctx.send(embed=embed)

# =========================
# ADMIN COMMANDS
# =========================
@bot.command()
async def admincommands(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    embed = discord.Embed(title="🛠 ADMIN COMMANDS", color=0xff0000)
    embed.add_field(name="Match", value="!start A B map\n!win A/B score mvp adr", inline=False)
    await ctx.send(embed=embed)

# =========================
# TEAM SYSTEM
# =========================
@bot.command()
async def create(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    if get_team(name):
        return await ctx.send("❌ Team exists")

    c.execute("INSERT INTO teams VALUES (?,?,1000)", (name, uid))
    conn.commit()

    await ctx.send(f"🏆 Team {name} created")

@bot.command()
async def join(ctx, name):
    uid = str(ctx.author.id)

    if in_team(uid):
        return await ctx.send("❌ Already in team")

    team = get_team(name.upper())
    if not team:
        return await ctx.send("❌ Not found")

    members = clean(team[1])

    if len(members) >= 5:
        return await ctx.send("❌ Team full")

    members.append(uid)

    c.execute("UPDATE teams SET members=? WHERE name=?",
              (",".join(members), name.upper()))
    conn.commit()

    await ctx.send("✅ Joined")

@bot.command()
async def leave(ctx):
    uid = str(ctx.author.id)

    c.execute("SELECT name, members FROM teams")
    teams = c.fetchall()

    for n, m in teams:
        mem = clean(m)
        if uid in mem:
            mem.remove(uid)
            c.execute("UPDATE teams SET members=? WHERE name=?",
                      (",".join(mem), n))

    conn.commit()
    await ctx.send("🚪 Left team")

# =========================
# STATS
# =========================
@bot.command()
async def stats(ctx):
    uid = str(ctx.author.id)
    create_player(uid)

    c.execute("SELECT acr,wins,losses FROM players WHERE id=?", (uid,))
    a,w,l = c.fetchone()

    await ctx.send(f"📊 ACR {a} | Wins {w} | Losses {l}")

# =========================
# LEADERBOARD
# =========================
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT name, acr FROM teams ORDER BY acr DESC")
    rows = c.fetchall()

    embed = discord.Embed(title="🏆 LEADERBOARD", color=0xFFD700)

    for i,(n,a) in enumerate(rows,1):
        c.execute("SELECT members FROM teams WHERE name=?", (n,))
        members = clean(c.fetchone()[0])

        embed.add_field(
            name=f"{i}. {n} — {a} ACR",
            value="\n".join([f"<@{m}>" for m in members]) or "No players",
            inline=False
        )

    await ctx.send(embed=embed)

# =========================
# START MATCH
# =========================
@bot.command()
async def start(ctx, a, b, map):
    global active_match, snapshot

    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    a,b = a.upper(), b.upper()

    c.execute("SELECT members, acr FROM teams WHERE name=?", (a,))
    am, aa = c.fetchone()

    c.execute("SELECT members, acr FROM teams WHERE name=?", (b,))
    bm, ba = c.fetchone()

    snapshot = {"a": aa, "b": ba}

    active_match = {"a": a, "b": b, "map": map.upper()}

    embed = discord.Embed(title="🔥 MATCH STARTED", color=0xff0000)
    embed.add_field(name="Match", value=f"{a} vs {b}")
    embed.add_field(name="Map", value=map.upper())
    embed.add_field(name="ACR", value=f"{a}: {aa} | {b}: {ba}")

    await send_ann(ctx.guild, embed) or await ctx.send(embed=embed)

# =========================
# WIN MATCH
# =========================
@bot.command()
async def win(ctx, side, score, mvp, adr):
    global active_match, snapshot

    if not active_match:
        return await ctx.send("❌ No match")

    a,b = active_match["a"], active_match["b"]
    map = active_match["map"]

    winner = a if side.upper()=="A" else b
    loser = b if winner==a else a

    def update(team, win):
        c.execute("SELECT members FROM teams WHERE name=?", (team,))
        members = clean(c.fetchone()[0])

        for m in members:
            update_player(m, win)

    update(winner, True)
    update(loser, False)

    update_team_acr(winner)
    update_team_acr(loser)

    c.execute("""
    INSERT INTO matches (team_a,team_b,map,winner,score,mvp,adr)
    VALUES (?,?,?,?,?,?,?)
    """, (a,b,map,winner,score,mvp,adr))

    conn.commit()

    active_match = None

    embed = discord.Embed(title="🏆 MATCH RESULT", color=0x2ecc71)
    embed.add_field(name="Winner", value=winner)
    embed.add_field(name="Score", value=score)
    embed.add_field(name="Map", value=map)
    embed.add_field(name="MVP", value=f"<@{mvp}>")
    embed.add_field(name="ADR", value=adr)
    embed.add_field(name="Loser", value=loser)

    await send_ann(ctx.guild, embed) or await ctx.send(embed=embed)

# =========================
# START BOT
# =========================
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("❌ TOKEN missing")
