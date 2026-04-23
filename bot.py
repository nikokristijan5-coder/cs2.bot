import discord
from discord.ext import commands
import os
import sqlite3
import random

# ------------------------
# SETUP
# ------------------------
print("ENV CHECK:", os.environ.get("TOKEN", "NOT FOUND"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------
# DATABASE
# ------------------------
conn = sqlite3.connect("cs2.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    elo INTEGER DEFAULT 1000,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS teams (
    name TEXT,
    owner TEXT,
    members TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS match (
    team_a TEXT,
    team_b TEXT,
    active INTEGER
)
""")

conn.commit()

# ------------------------
# HELPERS
# ------------------------
def get_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    return c.fetchone()

def create_player(uid):
    if not get_player(uid):
        c.execute("INSERT INTO players (id, elo, wins, losses) VALUES (?,1000,0,0)", (uid,))
        conn.commit()

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name,))
    return c.fetchone()

def save_team(name, owner, members):
    c.execute("INSERT INTO teams (name, owner, members) VALUES (?,?,?)",
              (name, owner, ",".join(members)))
    conn.commit()

# ------------------------
# READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# CREATE TEAM
# ------------------------
@bot.command()
async def create(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    if get_team(name):
        await ctx.send("❌ Team already exists")
        return

    save_team(name, uid, [uid])
    await ctx.send(f"🏆 Team {name} created by {ctx.author.name}")

# ------------------------
# JOIN TEAM
# ------------------------
@bot.command()
async def join(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    team = get_team(name)

    if not team:
        await ctx.send("❌ Team not found")
        return

    members = team[2].split(",") if team[2] else []

    if uid in members:
        await ctx.send("⚠️ Already in team")
        return

    if len(members) >= 5:
        await ctx.send("❌ Team full (5/5)")
        return

    members.append(uid)

    c.execute("UPDATE teams SET members=? WHERE name=?",
              (",".join(members), name))
    conn.commit()

    await ctx.send(f"🎮 {ctx.author.name} joined {name}")

# ------------------------
# START MATCH
# ------------------------
@bot.command()
async def start(ctx, team_a, team_b):
    team_a = team_a.upper()
    team_b = team_b.upper()

    a = get_team(team_a)
    b = get_team(team_b)

    if not a or not b:
        await ctx.send("❌ One of teams doesn't exist")
        return

    c.execute("DELETE FROM match")
    c.execute("INSERT INTO match VALUES (?,?,1)", (team_a, team_b))
    conn.commit()

    msg = f"🔥 MATCH STARTED!\n\n"
    msg += f"TEAM A: {team_a}\n"
    msg += f"TEAM B: {team_b}\n\n"
    msg += "Use !win A or !win B"

    await ctx.send(msg)

# ------------------------
# WIN SYSTEM
# ------------------------
@bot.command()
async def win(ctx, team):
    team = team.upper()

    c.execute("SELECT * FROM match WHERE active=1")
    match = c.fetchone()

    if not match:
        await ctx.send("❌ No active match")
        return

    team_a, team_b = match[0], match[1]

    winner = team_a if team == "A" else team_b
    loser = team_b if team == "A" else team_a

    # update players in winner team
    for tname in [winner]:
        c.execute("SELECT members FROM teams WHERE name=?", (tname,))
        members = c.fetchone()[0].split(",")

        for m in members:
            create_player(m)
            c.execute("UPDATE players SET elo = elo + 25, wins = wins + 1 WHERE id=?", (m,))

    # losers
    for tname in [loser]:
        c.execute("SELECT members FROM teams WHERE name=?", (tname,))
        members = c.fetchone()[0].split(",")

        for m in members:
            create_player(m)
            c.execute("UPDATE players SET elo = elo - 25, losses = losses + 1 WHERE id=?", (m,))

    c.execute("DELETE FROM match")
    conn.commit()

    await ctx.send(f"🏆 TEAM {team} WON THE MATCH!")

# ------------------------
# ELO
# ------------------------
@bot.command()
async def elo(ctx):
    uid = str(ctx.author.id)
    create_player(uid)

    c.execute("SELECT elo FROM players WHERE id=?", (uid,))
    elo = c.fetchone()[0]

    await ctx.send(f"📊 Your ELO: {elo}")

# ------------------------
# STATS
# ------------------------
@bot.command()
async def stats(ctx):
    uid = str(ctx.author.id)
    create_player(uid)

    c.execute("SELECT elo,wins,losses FROM players WHERE id=?", (uid,))
    elo,wins,losses = c.fetchone()

    await ctx.send(f"📊 ELO: {elo}\nWins: {wins}\nLosses: {losses}")

# ------------------------
# LEADERBOARD
# ------------------------
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT id, elo FROM players ORDER BY elo DESC LIMIT 10")
    rows = c.fetchall()

    msg = "🏆 LEADERBOARD\n\n"

    for i,(uid,elo) in enumerate(rows,1):
        msg += f"{i}. <@{uid}> — {elo}\n"

    await ctx.send(msg)

# ------------------------
# START BOT
# ------------------------
token = os.getenv("TOKEN")

if not token:
    print("❌ TOKEN missing")
else:
    bot.run(token)
