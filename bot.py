import discord
from discord.ext import commands
import os
import sqlite3

# ------------------------
# SETUP
# ------------------------
print("ENV CHECK:", os.environ.get("TOKEN", "NOT FOUND"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ADMIN_ROLE = "Admin"

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

c.execute("""
CREATE TABLE IF NOT EXISTS match (
    team_a TEXT,
    team_b TEXT,
    active INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS checkin (
    id TEXT PRIMARY KEY
)
""")

conn.commit()

# ------------------------
# HELPERS
# ------------------------
def is_admin(ctx):
    return any(role.name == ADMIN_ROLE for role in ctx.author.roles)

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name.upper(),))
    return c.fetchone()

def update_team_acr(team):
    c.execute("SELECT members FROM teams WHERE name=?", (team,))
    members = c.fetchone()[0].split(",")

    total = 0
    for m in members:
        c.execute("SELECT acr FROM players WHERE id=?", (m,))
        r = c.fetchone()
        if r:
            total += r[0]

    avg = int(total / len(members)) if members else 1000

    c.execute("UPDATE teams SET acr=? WHERE name=?", (avg, team))
    conn.commit()

# ------------------------
# PLAYER INIT
# ------------------------
def create_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO players (id, acr, wins, losses) VALUES (?,1000,0,0)", (uid,))
        conn.commit()

# ------------------------
# HELP COMMAND
# ------------------------
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🎮 CS2 ESPORTS BOT COMMANDS",
        color=0x00ffcc
    )

    embed.add_field(name="👥 Teams",
        value="`!create <name>`\n`!join <team>`", inline=False)

    embed.add_field(name="⚔ Matches",
        value="`!start <team1> <team2>`\n`!win A/B`", inline=False)

    embed.add_field(name="📊 Stats",
        value="`!acr` `!stats` `!leaderboard`", inline=False)

    embed.add_field(name="🎟 Tournament",
        value="`!checkin`\n`!announce <text>` (Admin)", inline=False)

    await ctx.send(embed=embed)

# ------------------------
# CREATE TEAM
# ------------------------
@bot.command()
async def create(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    if get_team(name):
        await ctx.send("❌ Team exists")
        return

    c.execute("INSERT INTO teams VALUES (?,?,?,1000)", (name, uid, uid))
    conn.commit()

    await ctx.send(f"🏆 Team {name} created")

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

    members = team[2].split(",")

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

    await ctx.send(f"🎮 Joined {name}")

# ------------------------
# START MATCH
# ------------------------
@bot.command()
async def start(ctx, a, b):
    if not is_admin(ctx):
        await ctx.send("❌ Admin only")
        return

    a = a.upper()
    b = b.upper()

    if not get_team(a) or not get_team(b):
        await ctx.send("❌ Team missing")
        return

    c.execute("DELETE FROM match")
    c.execute("INSERT INTO match VALUES (?,?,1)", (a, b))
    conn.commit()

    embed = discord.Embed(
        title="🔥 MATCH STARTED",
        description=f"**{a} vs {b}**",
        color=0xff0000
    )

    await ctx.send(embed=embed)

# ------------------------
# WIN SYSTEM
# ------------------------
@bot.command()
async def win(ctx, side):
    side = side.upper()

    c.execute("SELECT * FROM match WHERE active=1")
    m = c.fetchone()

    if not m:
        await ctx.send("❌ No match")
        return

    a, b = m[0], m[1]

    winner = a if side == "A" else b
    loser = b if side == "A" else a

    def update(team, win):
        c.execute("SELECT members FROM teams WHERE name=?", (team,))
        members = c.fetchone()[0].split(",")

        for m in members:
            create_player(m)

            if win:
                c.execute("UPDATE players SET acr = acr + 25, wins = wins + 1 WHERE id=?", (m,))
            else:
                c.execute("UPDATE players SET acr = acr - 25, losses = losses + 1 WHERE id=?", (m,))

        update_team_acr(team)

    update(winner, True)
    update(loser, False)

    conn.commit()

    await ctx.send(f"🏆 {winner} WON THE MATCH!")

# ------------------------
# ACR
# ------------------------
@bot.command()
async def acr(ctx):
    uid = str(ctx.author.id)
    create_player(uid)

    c.execute("SELECT acr FROM players WHERE id=?", (uid,))
    val = c.fetchone()[0]

    await ctx.send(f"📊 ACR: {val}")

# ------------------------
# CHECKIN
# ------------------------
@bot.command()
async def checkin(ctx):
    uid = str(ctx.author.id)

    c.execute("INSERT OR IGNORE INTO checkin VALUES (?)", (uid,))
    conn.commit()

    await ctx.send("✅ Checked in for tournament")

# ------------------------
# ANNOUNCE
# ------------------------
@bot.command()
async def announce(ctx, *, text):
    if not is_admin(ctx):
        await ctx.send("❌ Admin only")
        return

    embed = discord.Embed(
        title="📢 TOURNAMENT ANNOUNCEMENT",
        description=text,
        color=0x00ff00
    )

    await ctx.send(embed=embed)

# ------------------------
# LEADERBOARD (FIXED)
# ------------------------
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT name, acr FROM teams ORDER BY acr DESC")
    teams = c.fetchall()

    embed = discord.Embed(
        title="🏆 TEAM LEADERBOARD (ACR)",
        color=0xFFD700
    )

    for i, (name, acr) in enumerate(teams, 1):
        c.execute("SELECT members FROM teams WHERE name=?", (name,))
        members = c.fetchone()[0].split(",")

        mentions = "\n".join([f"<@{m}>" for m in members])

        embed.add_field(
            name=f"{i}. {name} — {acr} ACR",
            value=mentions,
            inline=False
        )

    await ctx.send(embed=embed)

# ------------------------
# START
# ------------------------
token = os.getenv("TOKEN")

if not token:
    print("❌ TOKEN missing")
else:
    bot.run(token)
