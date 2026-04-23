import discord
from discord.ext import commands
import os
import sqlite3

# =========================
# BOT SETUP (SAFE INTENTS)
# =========================
intents = discord.Intents.default()
intents.message_content = True  # only needed intent

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ANN_CHANNEL = "announcements"
active_match = None

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
    losses INTEGER DEFAULT 0,
    mvp INTEGER DEFAULT 0
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
    mvp TEXT
)
""")

conn.commit()

# =========================
# HELPERS
# =========================
def clean(m):
    return [x for x in m.split(",") if x]

def create_player(uid):
    c.execute("SELECT * FROM players WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO players VALUES (?,1000,0,0,0)", (uid,))
        conn.commit()

def get_team(name):
    c.execute("SELECT * FROM teams WHERE name=?", (name.upper(),))
    return c.fetchone()

def in_team(uid):
    c.execute("SELECT name FROM teams WHERE members LIKE ?", (f"%{uid}%",))
    return c.fetchone()

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

def ann(guild, embed):
    ch = discord.utils.get(guild.text_channels, name=ANN_CHANNEL)
    if ch:
        return ch.send(embed=embed)

# =========================
# PLAYER UPDATE
# =========================
def update_player(uid, win):
    create_player(uid)

    if win:
        c.execute("UPDATE players SET acr=acr+25,wins=wins+1 WHERE id=?", (uid,))
    else:
        c.execute("UPDATE players SET acr=acr-25,losses=losses+1 WHERE id=?", (uid,))

    conn.commit()

def add_mvp(uid):
    create_player(uid)
    c.execute("UPDATE players SET mvp=mvp+1 WHERE id=?", (uid,))
    conn.commit()

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# =========================
# TEAMS
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
        return await ctx.send("❌ Team not found")

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
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)

    create_player(uid)

    c.execute("SELECT acr,wins,losses,mvp FROM players WHERE id=?", (uid,))
    a,w,l,m = c.fetchone()

    embed = discord.Embed(title=f"📊 STATS - {member.name}", color=0x00ffcc)
    embed.add_field(name="ACR", value=a)
    embed.add_field(name="Wins", value=w)
    embed.add_field(name="Losses", value=l)
    embed.add_field(name="MVPs", value=m)

    await ctx.send(embed=embed)

# =========================
# LEADERBOARD
# =========================
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT name, acr FROM teams ORDER BY acr DESC")
    rows = c.fetchall()

    embed = discord.Embed(title="🏆 LEADERBOARD", color=0xf1c40f)

    for i,(n,a) in enumerate(rows,1):
        embed.add_field(name=f"{i}. {n}", value=f"{a} ACR", inline=False)

    await ctx.send(embed=embed)

# =========================
# MATCH HISTORY
# =========================
@bot.command()
async def matches(ctx):
    c.execute("SELECT team_a,team_b,map,winner,score,mvp FROM matches ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()

    embed = discord.Embed(title="📜 MATCH HISTORY", color=0x95a5a6)

    for a,b,map,w,score,mvp in rows:
        embed.add_field(
            name=f"{a} vs {b}",
            value=f"{map} | {w} won | {score} | MVP <@{mvp}>",
            inline=False
        )

    await ctx.send(embed=embed)

# =========================
# ADMIN CHECK
# =========================
def admin(ctx):
    return ctx.author.guild_permissions.administrator

# =========================
# ADMIN COMMANDS
# =========================
@bot.command()
async def addplayer(ctx, team, user: discord.Member):
    if not admin(ctx):
        return await ctx.send("❌ Admin only")

    team = team.upper()
    uid = str(user.id)

    c.execute("SELECT members FROM teams WHERE name=?", (team,))
    m = clean(c.fetchone()[0])

    if uid not in m and len(m) < 5:
        m.append(uid)

    c.execute("UPDATE teams SET members=? WHERE name=?",
              (",".join(m), team))
    conn.commit()

    await ctx.send("✅ Added player")

@bot.command()
async def removeplayer(ctx, team, user: discord.Member):
    if not admin(ctx):
        return await ctx.send("❌ Admin only")

    team = team.upper()
    uid = str(user.id)

    c.execute("SELECT members FROM teams WHERE name=?", (team,))
    m = clean(c.fetchone()[0])

    if uid in m:
        m.remove(uid)

    c.execute("UPDATE teams SET members=? WHERE name=?",
              (",".join(m), team))
    conn.commit()

    await ctx.send("✅ Removed player")

# =========================
# MATCH START
# =========================
active_match = None

@bot.command()
async def start(ctx, a, b, map):
    global active_match

    if not admin(ctx):
        return await ctx.send("❌ Admin only")

    active_match = {"a": a.upper(), "b": b.upper(), "map": map}

    embed = discord.Embed(title="🔥 MATCH STARTED", color=0xff0000)
    embed.add_field(name="Teams", value=f"{a} vs {b}")
    embed.add_field(name="Map", value=map)

    await ann(ctx.guild, embed) or await ctx.send(embed=embed)

# =========================
# MATCH WIN
# =========================
@bot.command()
async def win(ctx, winner, score, mvp):
    global active_match

    if not active_match:
        return await ctx.send("❌ No match")

    a = active_match["a"]
    b = active_match["b"]

    winner = winner.upper()
    loser = a if winner == b else b

    def update(team, win):
        c.execute("SELECT members FROM teams WHERE name=?", (team,))
        members = clean(c.fetchone()[0])

        for m in members:
            update_player(m, win)

    update(winner, True)
    update(loser, False)

    add_mvp(mvp)

    c.execute("""
    INSERT INTO matches (team_a,team_b,map,winner,score,mvp)
    VALUES (?,?,?,?,?,?)
    """, (a,b,active_match["map"],winner,score,mvp))

    conn.commit()

    embed = discord.Embed(title="🏆 MATCH RESULT", color=0x2ecc71)
    embed.add_field(name="Winner", value=winner)
    embed.add_field(name="Score", value=score)
    embed.add_field(name="MVP", value=f"<@{mvp}>")

    active_match = None

    await ann(ctx.guild, embed) or await ctx.send(embed=embed)

# =========================
# RUN BOT
# =========================
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("NO TOKEN")
