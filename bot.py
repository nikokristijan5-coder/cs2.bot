import discord
from discord.ext import commands
import os
import sqlite3

# ------------------------
# SETUP
# ------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ADMIN_ROLE = "Admin"
ANN = "announcements"

active_match = None
match_snapshot = {}

# ------------------------
# DATABASE
# ------------------------
conn = sqlite3.connect("cs2.db")
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
    owner TEXT,
    members TEXT,
    acr INTEGER DEFAULT 1000
)
""")

conn.commit()

# ------------------------
# HELPERS
# ------------------------
def clean_members(raw):
    return [m for m in raw.split(",") if m.strip()]

def create_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO players VALUES (?,1000,0,0)", (uid,))
        conn.commit()

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name.upper(),))
    return c.fetchone()

def is_admin(ctx):
    return any(r.name.lower() == ADMIN_ROLE.lower() for r in ctx.author.roles)

def get_ann(guild):
    for ch in guild.text_channels:
        if ch.name == ANN:
            return ch
    return None

def update_team_acr(team):
    c.execute("SELECT members FROM teams WHERE name=?", (team,))
    members = clean_members(c.fetchone()[0])

    total = 0
    count = 0

    for m in members:
        c.execute("SELECT acr FROM players WHERE id=?", (m,))
        r = c.fetchone()
        if r:
            total += r[0]
            count += 1

    avg = int(total / count) if count > 0 else 1000

    c.execute("UPDATE teams SET acr=? WHERE name=?", (avg, team))
    conn.commit()

# ------------------------
# READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# PLAYER COMMANDS
# ------------------------
@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="🎮 PLAYER COMMANDS", color=0x00ffcc)

    embed.add_field(name="Teams", value="!create !join !leave", inline=False)
    embed.add_field(name="Stats", value="!stats !leaderboard", inline=False)

    await ctx.send(embed=embed)

# ------------------------
# ADMIN COMMANDS
# ------------------------
@bot.command()
async def admincommands(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    embed = discord.Embed(title="🛠 ADMIN COMMANDS", color=0xff0000)

    embed.add_field(name="Match", value="!start <A> <B> <map>\n!win A/B <score> <mvp> <adr>\n!resetmatch", inline=False)
    embed.add_field(name="Teams", value="(future upgrades ready)", inline=False)

    await ctx.send(embed=embed)

# ------------------------
# TEAM SYSTEM
# ------------------------
@bot.command()
async def create(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    if get_team(name):
        return await ctx.send("❌ Team exists")

    c.execute("INSERT INTO teams VALUES (?,?,?,1000)", (name, uid, uid))
    conn.commit()

    await ctx.send(f"🏆 Team {name} created")

@bot.command()
async def join(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    c.execute("SELECT name FROM teams WHERE members LIKE ?", (f"%{uid}%",))
    if c.fetchone():
        return await ctx.send("❌ Already in team")

    team = get_team(name)
    if not team:
        return await ctx.send("❌ Not found")

    members = clean_members(team[2])

    if len(members) >= 5:
        return await ctx.send("❌ Team full")

    members.append(uid)

    c.execute("UPDATE teams SET members=? WHERE name=?",
              (",".join(members), name))
    conn.commit()

    await ctx.send(f"🎮 Joined {name}")

@bot.command()
async def leave(ctx):
    uid = str(ctx.author.id)

    c.execute("SELECT name, members FROM teams")
    teams = c.fetchall()

    for name, members in teams:
        m = clean_members(members)
        if uid in m:
            m.remove(uid)
            c.execute("UPDATE teams SET members=? WHERE name=?",
                      (",".join(m), name))

    conn.commit()
    await ctx.send("🚪 Left team")

# ------------------------
# STATS
# ------------------------
@bot.command()
async def stats(ctx):
    uid = str(ctx.author.id)
    create_player(uid)

    c.execute("SELECT acr,wins,losses FROM players WHERE id=?", (uid,))
    acr, w, l = c.fetchone()

    embed = discord.Embed(title="📊 STATS", color=0x00ffcc)
    embed.add_field(name="ACR", value=acr)
    embed.add_field(name="Wins", value=w)
    embed.add_field(name="Losses", value=l)

    await ctx.send(embed=embed)

# ------------------------
# LEADERBOARD (FIXED)
# ------------------------
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT name, acr FROM teams ORDER BY acr DESC")
    teams = c.fetchall()

    embed = discord.Embed(title="🏆 LEADERBOARD", color=0xFFD700)

    for i, (name, acr) in enumerate(teams, 1):
        c.execute("SELECT members FROM teams WHERE name=?", (name,))
        members = clean_members(c.fetchone()[0])

        embed.add_field(
            name=f"{i}. {name} — {acr} ACR",
            value="\n".join([f"<@{m}>" for m in members]) or "No players",
            inline=False
        )

    await ctx.send(embed=embed)

# ------------------------
# MATCH START (MAP + ACR SNAPSHOT)
# ------------------------
@bot.command()
async def start(ctx, a, b, map):
    global active_match, match_snapshot

    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    if active_match:
        return await ctx.send("❌ Match already running")

    a, b = a.upper(), b.upper()

    if not get_team(a) or not get_team(b):
        return await ctx.send("❌ Missing team")

    c.execute("SELECT acr FROM teams WHERE name=?", (a,))
    a_acr = c.fetchone()[0]

    c.execute("SELECT acr FROM teams WHERE name=?", (b,))
    b_acr = c.fetchone()[0]

    match_snapshot = {"a": a_acr, "b": b_acr}

    active_match = {"a": a, "b": b, "map": map.upper(), "active": True}

    channel = get_ann(ctx.guild)

    embed = discord.Embed(title="🔥 MATCH STARTED", color=0xff0000)
    embed.add_field(name="Match", value=f"{a} vs {b}")
    embed.add_field(name="Map", value=map.upper())
    embed.add_field(name="ACR A", value=a_acr)
    embed.add_field(name="ACR B", value=b_acr)

    await (channel.send(embed=embed) if channel else ctx.send(embed=embed))

# ------------------------
# WIN SYSTEM (FULL REPORT)
# ------------------------
@bot.command()
async def win(ctx, side, score, mvp, adr):
    global active_match, match_snapshot

    if not active_match or not active_match["active"]:
        return await ctx.send("❌ No active match")

    a, b = active_match["a"], active_match["b"]
    map = active_match["map"]

    winner = a if side.upper() == "A" else b
    loser = b if winner == a else a

    def update(team, win):
        c.execute("SELECT members FROM teams WHERE name=?", (team,))
        members = clean_members(c.fetchone()[0])

        for m in members:
            create_player(m)

            if win:
                c.execute("UPDATE players SET acr=acr+25,wins=wins+1 WHERE id=?", (m,))
            else:
                c.execute("UPDATE players SET acr=acr-25,losses=losses+1 WHERE id=?", (m,))

    update(winner, True)
    update(loser, False)

    update_team_acr(winner)
    update_team_acr(loser)

    conn.commit()

    active_match["active"] = False

    c.execute("SELECT acr FROM teams WHERE name=?", (winner,))
    w_after = c.fetchone()[0]

    c.execute("SELECT acr FROM teams WHERE name=?", (loser,))
    l_after = c.fetchone()[0]

    embed = discord.Embed(title="🏆 MATCH FINISHED", color=0x00ff00)

    embed.add_field(name="Map", value=map)
    embed.add_field(name="Score", value=score)
    embed.add_field(name="MVP", value=f"<@{mvp}>")
    embed.add_field(name="ADR", value=adr)

    embed.add_field(name="ACR CHANGE",
                    value=f"{a}: {match_snapshot['a']} → {w_after if winner==a else l_after}\n"
                          f"{b}: {match_snapshot['b']} → {w_after if winner==b else l_after}")

    channel = get_ann(ctx.guild)
    await (channel.send(embed=embed) if channel else ctx.send(embed=embed))

# ------------------------
# RESET
# ------------------------
@bot.command()
async def resetmatch(ctx):
    global active_match

    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    active_match = None
    await ctx.send("🔄 Match reset")

# ------------------------
# START BOT
# ------------------------
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("❌ TOKEN missing")
