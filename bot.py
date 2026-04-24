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
AKTIVNI_MEC = None
ZADNJI_POBJEDNIK = None

# =========================
# DATABASE
# =========================
conn = sqlite3.connect("bot.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS igraci (
    id TEXT PRIMARY KEY,
    acr INTEGER DEFAULT 1000,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    mvp INTEGER DEFAULT 0,
    tournaments INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS timovi (
    ime TEXT PRIMARY KEY,
    clanovi TEXT
)
""")

conn.commit()

# =========================
# HELPERS
# =========================
def ensure_player(uid):
    c.execute("SELECT * FROM igraci WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO igraci VALUES (?,1000,0,0,0,0)", (uid,))
        conn.commit()

def get_team(uid):
    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        if clanovi and uid in clanovi.split(","):
            return ime.upper()
    return None

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

async def announce(ctx, embed):
    channel = discord.utils.get(ctx.guild.text_channels, name=ANN_CHANNEL)
    if channel:
        await channel.send(embed=embed)
    else:
        await ctx.send(embed=embed)

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
    embed = discord.Embed(title="🎮 Commands", color=0x2ecc71)
    embed.add_field(name="Team", value="!create !join !leave", inline=False)
    embed.add_field(name="Stats", value="!stats", inline=False)
    embed.add_field(name="Leaderboard", value="!leaderboard", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def create(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    c.execute("SELECT * FROM timovi WHERE ime=?", (name,))
    if c.fetchone():
        return await ctx.send("❌ Team exists.")

    c.execute("INSERT INTO timovi VALUES (?,?)", (name, uid))
    conn.commit()
    await ctx.send(f"🏆 Team {name} created.")

@bot.command()
async def join(ctx, name):
    uid = str(ctx.author.id)

    if get_team(uid):
        return await ctx.send("❌ Already in team.")

    c.execute("SELECT clanovi FROM timovi WHERE ime=?", (name.upper(),))
    t = c.fetchone()
    if not t:
        return await ctx.send("❌ Team not found.")

    clanovi = t[0].split(",") if t[0] else []

    if len(clanovi) >= 5:
        return await ctx.send("❌ Team full.")

    clanovi.append(uid)

    c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
              (",".join(clanovi), name.upper()))
    conn.commit()

    await ctx.send("✅ Joined team.")

@bot.command()
async def leave(ctx):
    uid = str(ctx.author.id)

    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        if clanovi:
            l = clanovi.split(",")
            if uid in l:
                l.remove(uid)
                c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
                          (",".join(l), ime))
                conn.commit()
                return await ctx.send("🚪 Left team.")

    await ctx.send("❌ Not in team.")

# =========================
# STATS
# =========================
@bot.command()
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)

    ensure_player(uid)

    c.execute("SELECT acr,wins,losses,mvp,tournaments FROM igraci WHERE id=?", (uid,))
    acr,w,l,m,t = c.fetchone()

    embed = discord.Embed(title=f"📊 Stats {member.display_name}", color=0x3498db)
    embed.add_field(name="ACR", value=acr)
    embed.add_field(name="Wins", value=w)
    embed.add_field(name="Losses", value=l)
    embed.add_field(name="MVP", value=m)
    embed.add_field(name="Tournaments", value=t)

    await ctx.send(embed=embed)

# =========================
# LEADERBOARD (FIXED)
# =========================
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT id, acr, tournaments FROM igraci ORDER BY acr DESC")
    rows = c.fetchall()

    embed = discord.Embed(title="🏆 Leaderboard", color=0xf1c40f)

    def rank(acr):
        if acr < 900: return "Bronze"
        if acr < 1100: return "Silver"
        if acr < 1300: return "Gold"
        if acr < 1500: return "Platinum"
        return "Elite"

    i = 1
    for uid, acr, t in rows[:10]:
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else "Unknown"

        team = get_team(uid) or "No team"

        embed.add_field(
            name=f"{i}. {name}",
            value=f"{rank(acr)} | ACR {acr}\nTeam: {team}\n🏆 {t}",
            inline=False
        )
        i += 1

    await ctx.send(embed=embed)

# =========================
# ADMIN BASIC
# =========================
@bot.command()
async def admincommands(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only.")

    await ctx.send("!start !win !addplayer !removeplayer !tournamentwin")

@bot.command()
async def addplayer(ctx, member: discord.Member, team):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only.")

    uid = str(member.id)

    c.execute("SELECT clanovi FROM timovi WHERE ime=?", (team.upper(),))
    t = c.fetchone()
    if not t:
        return await ctx.send("❌ Team not found.")

    l = t[0].split(",") if t[0] else []

    if uid in l:
        return await ctx.send("❌ Already in team.")

    l.append(uid)

    c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
              (",".join(l), team.upper()))
    conn.commit()

    await ctx.send("✅ Added.")

@bot.command()
async def removeplayer(ctx, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only.")

    uid = str(member.id)

    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        if clanovi and uid in clanovi.split(","):
            l = clanovi.split(",")
            l.remove(uid)

            c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
                      (",".join(l), ime))
            conn.commit()

            return await ctx.send("🚪 Removed.")

# =========================
# TOURNAMENT
# =========================
@bot.command()
async def tournamentwin(ctx, user_id):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin only.")

    ensure_player(str(user_id))

    c.execute("UPDATE igraci SET tournaments=tournaments+1 WHERE id=?", (str(user_id),))
    conn.commit()

    await ctx.send("🏆 Tournament added.")

# =========================
# RUN
# =========================
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("NO TOKEN")
