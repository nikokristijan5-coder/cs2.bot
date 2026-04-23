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
ANN_CHANNEL = "announcements"

active_match = None

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
def create_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO players VALUES (?,1000,0,0)", (uid,))
        conn.commit()

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name.upper(),))
    return c.fetchone()

def get_player_team(uid):
    c.execute("SELECT name FROM teams WHERE members LIKE ?", (f"%{uid}%",))
    return c.fetchone()

def is_admin(ctx):
    return any(role.name.lower() == ADMIN_ROLE.lower() for role in ctx.author.roles)

def get_ann_channel(guild):
    for ch in guild.text_channels:
        if ch.name == ANN_CHANNEL:
            return ch
    return None

def remove_from_all_teams(uid):
    c.execute("SELECT name, members FROM teams")
    teams = c.fetchall()

    for name, members in teams:
        m = members.split(",")
        if uid in m:
            m.remove(uid)
            c.execute("UPDATE teams SET members=? WHERE name=?", (",".join(m), name))

    conn.commit()

# ------------------------
# READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# COMMAND MENU
# ------------------------
@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="🎮 CS2 BOT COMMANDS", color=0x00ffcc)

    embed.add_field(
        name="👥 Teams",
        value="!create <name>\n!join <name>\n!leave",
        inline=False
    )

    embed.add_field(
        name="⚔ Match",
        value="!start <A> <B> (Admin)\n!win A/B <score> <mvpID> <adr>\n!resetmatch (Admin)",
        inline=False
    )

    embed.add_field(
        name="📊 Stats",
        value="!stats\n!leaderboard",
        inline=False
    )

    embed.add_field(
        name="📢 Other",
        value="!announce (Admin)",
        inline=False
    )

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

    if get_player_team(uid):
        return await ctx.send("❌ Already in a team")

    team = get_team(name)
    if not team:
        return await ctx.send("❌ Team not found")

    members = team[2].split(",")

    if len(members) >= 5:
        return await ctx.send("❌ Team full (5 max)")

    members.append(uid)

    c.execute("UPDATE teams SET members=? WHERE name=?",
              (",".join(members), name))
    conn.commit()

    await ctx.send(f"🎮 Joined {name}")

@bot.command()
async def leave(ctx):
    uid = str(ctx.author.id)

    if not get_player_team(uid):
        return await ctx.send("❌ Not in team")

    remove_from_all_teams(uid)
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
# MATCH START
# ------------------------
@bot.command()
async def start(ctx, a, b):
    global active_match

    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    if active_match:
        return await ctx.send("❌ Match already running")

    a, b = a.upper(), b.upper()

    if not get_team(a) or not get_team(b):
        return await ctx.send("❌ Team missing")

    active_match = {"a": a, "b": b, "active": True}

    channel = get_ann_channel(ctx.guild)

    embed = discord.Embed(
        title="🔥 MATCH STARTED",
        description=f"{a} vs {b}",
        color=0xff0000
    )

    await (channel.send(embed=embed) if channel else ctx.send(embed=embed))

# ------------------------
# WIN SYSTEM (FULL REPORT)
# ------------------------
@bot.command()
async def win(ctx, side, score, mvp, adr):
    global active_match

    if not active_match or not active_match["active"]:
        return await ctx.send("❌ No active match")

    a, b = active_match["a"], active_match["b"]

    winner = a if side.upper() == "A" else b
    loser = b if winner == a else a

    def update(team, win):
        c.execute("SELECT members FROM teams WHERE name=?", (team,))
        members = c.fetchone()[0].split(",")

        for m in members:
            create_player(m)

            if win:
                c.execute("UPDATE players SET acr=acr+25,wins=wins+1 WHERE id=?", (m,))
            else:
                c.execute("UPDATE players SET acr=acr-25,losses=losses+1 WHERE id=?", (m,))

    update(winner, True)
    update(loser, False)
    conn.commit()

    active_match["active"] = False

    c.execute("SELECT members FROM teams WHERE name=?", (winner,))
    w_members = c.fetchone()[0].split(",")

    c.execute("SELECT members FROM teams WHERE name=?", (loser,))
    l_members = c.fetchone()[0].split(",")

    embed = discord.Embed(title="🏆 MATCH RESULT", color=0x00ff00)
    embed.add_field(name="Winner", value=winner)
    embed.add_field(name="Score", value=score)
    embed.add_field(name="MVP", value=f"<@{mvp}>")
    embed.add_field(name="ADR", value=adr)
    embed.add_field(name="Winner Team", value="\n".join([f"<@{x}>" for x in w_members]))
    embed.add_field(name="Loser Team", value="\n".join([f"<@{x}>" for x in l_members]))

    channel = get_ann_channel(ctx.guild)
    await (channel.send(embed=embed) if channel else ctx.send(embed=embed))

# ------------------------
# RESET MATCH
# ------------------------
@bot.command()
async def resetmatch(ctx):
    global active_match

    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    active_match = None
    await ctx.send("🔄 Match reset")

# ------------------------
# LEADERBOARD
# ------------------------
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT name, acr FROM teams ORDER BY acr DESC")
    teams = c.fetchall()

    embed = discord.Embed(title="🏆 LEADERBOARD", color=0xFFD700)

    for i, (name, acr) in enumerate(teams, 1):
        c.execute("SELECT members FROM teams WHERE name=?", (name,))
        members = c.fetchone()[0].split(",")

        embed.add_field(
            name=f"{i}. {name} ({acr} ACR)",
            value="\n".join([f"<@{m}>" for m in members]),
            inline=False
        )

    await ctx.send(embed=embed)

# ------------------------
# ANNOUNCE
# ------------------------
@bot.command()
async def announce(ctx, *, text):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only")

    channel = get_ann_channel(ctx.guild)

    embed = discord.Embed(title="📢 ANNOUNCEMENT", description=text, color=0x00ff00)

    await (channel.send(embed=embed) if channel else ctx.send(embed=embed))

# ------------------------
# START BOT
# ------------------------
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("❌ TOKEN missing")
