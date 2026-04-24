import discord
from discord.ext import commands
import os
import sqlite3

# =========================
# SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ANN_CHANNEL = "announcements"
AKTIVNI_MEC = None
ZADNJI_POBJEDNIK = None

# =========================
# DB
# =========================
conn = sqlite3.connect("bot.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS igraci (
    id TEXT PRIMARY KEY,
    acr INTEGER DEFAULT 1000,
    pobjede INTEGER DEFAULT 0,
    porazi INTEGER DEFAULT 0,
    mvp INTEGER DEFAULT 0,
    turniri INTEGER DEFAULT 0
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
def lista(x):
    return [i for i in x.split(",") if i]

def igrac(uid):
    c.execute("SELECT * FROM igraci WHERE id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO igraci VALUES (?,1000,0,0,0,0)", (uid,))
        conn.commit()

def tim(ime):
    c.execute("SELECT * FROM timovi WHERE ime=?", (ime.upper(),))
    return c.fetchone()

def get_team(uid):
    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        if clanovi and uid in clanovi.split(","):
            return ime.upper()
    return None

def admin(ctx):
    return ctx.author.guild_permissions.administrator

async def announce(ctx, embed):
    kanal = discord.utils.get(ctx.guild.text_channels, name=ANN_CHANNEL)
    if kanal:
        await kanal.send(embed=embed)
    else:
        await ctx.send(embed=embed)

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# =========================
# COMMANDS MENU (PLAYER)
# =========================
@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="🎮 PLAYER COMMANDS", color=0x2ecc71)

    embed.add_field(
        name="Team System",
        value="!create <name>\n!join <team>\n!leave",
        inline=False
    )

    embed.add_field(
        name="Stats",
        value="!stats [@user]",
        inline=False
    )

    embed.add_field(
        name="Other",
        value="!leaderboard",
        inline=False
    )

    await ctx.send(embed=embed)

# =========================
# ADMIN COMMANDS MENU
# =========================
@bot.command()
async def admincommands(ctx):
    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    embed = discord.Embed(title="🛠 ADMIN COMMANDS", color=0xe74c3c)

    embed.add_field(
        name="Match",
        value="!start <teamA> <teamB> <map>\n!win <team> <score> <mvpID>",
        inline=False
    )

    embed.add_field(
        name="ACR SYSTEM",
        value="!acr @player kills deaths assists adr hs util flash",
        inline=False
    )

    embed.add_field(
        name="Teams",
        value="!addplayer @user <team>\n!removeplayer @user",
        inline=False
    )

    embed.add_field(
        name="Tournament",
        value="!tournamentwin <userID>",
        inline=False
    )

    await ctx.send(embed=embed)

# =========================
# TEAM SYSTEM (RESTORED)
# =========================
@bot.command()
async def create(ctx, ime):
    ime = ime.upper()
    uid = str(ctx.author.id)

    if tim(ime):
        return await ctx.send("❌ Team already exists.")

    c.execute("INSERT INTO timovi VALUES (?,?)", (ime, uid))
    conn.commit()

    await ctx.send(f"🏆 Team {ime} created.")

@bot.command()
async def join(ctx, ime):
    uid = str(ctx.author.id)

    if get_team(uid):
        return await ctx.send("❌ Already in a team.")

    t = tim(ime)
    if not t:
        return await ctx.send("❌ Team not found.")

    clanovi = lista(t[1])

    if len(clanovi) >= 5:
        return await ctx.send("❌ Team full.")

    clanovi.append(uid)

    c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
              (",".join(clanovi), ime.upper()))
    conn.commit()

    await ctx.send("✅ Joined team.")

@bot.command()
async def leave(ctx):
    uid = str(ctx.author.id)

    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        l = lista(clanovi)
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

    igrac(uid)

    c.execute("SELECT acr,pobjede,porazi,mvp,turniri FROM igraci WHERE id=?", (uid,))
    acr,w,l,m,t = c.fetchone()

    embed = discord.Embed(title=f"📊 Stats - {member.display_name}", color=0x3498db)
    embed.add_field(name="ACR", value=acr)
    embed.add_field(name="Wins", value=w)
    embed.add_field(name="Losses", value=l)
    embed.add_field(name="MVP", value=m)
    embed.add_field(name="Tournaments", value=t)

    await ctx.send(embed=embed)

# =========================
# LEADERBOARD (FIXED + CLEAN)
# =========================
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT id, acr, turniri FROM igraci ORDER BY acr DESC")
    rows = c.fetchall()

    embed = discord.Embed(title="🏆 Leaderboard", color=0xf1c40f)

    def rank(acr):
        if acr < 900: return "🟫 Bronze"
        if acr < 1100: return "⬜ Silver"
        if acr < 1300: return "🟨 Gold"
        if acr < 1500: return "🟦 Platinum"
        if acr < 1700: return "🟪 Diamond"
        return "🔥 Elite"

    place = 1

    for uid, acr, t in rows[:10]:
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"User"

        team = get_team(uid) or "No team"

        embed.add_field(
            name=f"{place}. {name}",
            value=f"{rank(acr)}\nACR: {acr}\nTeam: {team}\n🏆 Tournaments: {t}",
            inline=False
        )

        place += 1

    await ctx.send(embed=embed)

# =========================
# ACR PRO v2 (UNCHANGED LOGIC, STABLE)
# =========================
@bot.command()
async def acr(ctx, member: discord.Member,
              kills: int, deaths: int, assists: int,
              adr: float, hs: float, util: int, flash: int):

    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    uid = str(member.id)
    igrac(uid)

    team = get_team(uid)
    if not team:
        return await ctx.send("❌ No team.")

    if not ZADNJI_POBJEDNIK:
        return await ctx.send("❌ No match.")

    win = team.upper() == ZADNJI_POBJEDNIK.upper()

    score = (
        kills * 1.2
        - deaths * 0.8
        + assists * 0.5
        + adr * 0.05
        + hs * 0.1
        + util * 0.02
        + flash * 0.3
    )

    if win:
        score += 20
    else:
        score -= 15

    change = int(max(-50, min(80, score)))

    c.execute("UPDATE igraci SET acr=acr+? WHERE id=?", (change, uid))
    conn.commit()

    await ctx.send(f"📊 ACR updated for {member.display_name}: {change:+}")

# =========================
# RUN
# =========================
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("NO TOKEN")
