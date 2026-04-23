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

# 🔥 important: disable default help command
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

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
def create_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO players (id, acr, wins, losses) VALUES (?,1000,0,0)", (uid,))
        conn.commit()

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name.upper(),))
    return c.fetchone()

def is_admin(ctx):
    return any(role.name == "Admin" for role in ctx.author.roles)

# ------------------------
# READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# COMMANDS MENU (REPLACEMENT FOR HELP)
# ------------------------
@bot.command()
async def commands(ctx):
    embed = discord.Embed(
        title="🎮 CS2 ESPORTS BOT COMMANDS",
        color=0x00ffcc
    )

    embed.add_field(
        name="👥 Teams",
        value="`!create <name>`\n`!join <team>`",
        inline=False
    )

    embed.add_field(
        name="⚔ Matches",
        value="`!start <team1> <team2>` (Admin)\n`!win A/B`",
        inline=False
    )

    embed.add_field(
        name="📊 Stats",
        value="`!acr` `!stats` `!leaderboard`",
        inline=False
    )

    embed.add_field(
        name="🎟 Tournament",
        value="`!checkin`\n`!announce <text>` (Admin)",
        inline=False
    )

    await ctx.send(embed=embed)

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
# START MATCH (ADMIN ONLY)
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
        await ctx.send("❌ No active match")
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

    await ctx.send("✅ Checked in")

# ------------------------
# ANNOUNCE (ADMIN)
# ------------------------
@bot.command()
async def announce(ctx, *, text):
    if not is_admin(ctx):
        await ctx.send("❌ Admin only")
        return

    embed = discord.Embed(
        title="📢 ANNOUNCEMENT",
        description=text,
        color=0x00ff00
    )

    await ctx.send(embed=embed)

# ------------------------
# LEADERBOARD
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

        members_list = "\n".join([f"<@{m}>" for m in members])

        embed.add_field(
            name=f"{i}. {name} — {acr} ACR",
            value=members_list,
            inline=False
        )

    await ctx.send(embed=embed)

# ------------------------
# START BOT
# ------------------------
token = os.getenv("TOKEN")

if not token:
    print("❌ TOKEN missing")
else:
    bot.run(token)
