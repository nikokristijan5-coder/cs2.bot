import discord
from discord.ext import commands
import os
import sqlite3

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # 🔥 KLJUČNO za username fix

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
# PLAYER COMMANDS
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
# LEADERBOARD FIX (FULL STABLE)
# =========================
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT id, acr, turniri FROM igraci ORDER BY acr DESC")
    rows = c.fetchall()

    embed = discord.Embed(title="🏆 Leaderboard", color=0xf1c40f)

    def rank(acr):
        if acr < 900:
            return "🟫 Bronze"
        elif acr < 1100:
            return "⬜ Silver"
        elif acr < 1300:
            return "🟨 Gold"
        elif acr < 1500:
            return "🟦 Platinum"
        elif acr < 1700:
            return "🟪 Diamond"
        return "🔥 Elite"

    seen = set()
    place = 1

    for uid, acr, t in rows:
        if uid in seen:
            continue
        seen.add(uid)

        # 🔥 ULTRA FIX: uvijek dohvati user
        member = ctx.guild.get_member(int(uid))

        if member is None:
            try:
                member = await bot.fetch_user(int(uid))
            except:
                member = None

        name = member.display_name if member else f"User {uid}"

        team = get_team(uid) or "No team"

        embed.add_field(
            name=f"{place}. {name}",
            value=f"{rank(acr)}\nACR: {acr}\nTeam: {team}\n🏆 Tournaments: {t}",
            inline=False
        )

        place += 1
        if place > 10:
            break

    await ctx.send(embed=embed)


# =========================
# ACR PRO v2 (STABLE)
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
        return await ctx.send("❌ Player not in team.")

    if not ZADNJI_POBJEDNIK:
        return await ctx.send("❌ No active match.")

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

    acr_change = int(max(-50, min(80, score)))

    c.execute("SELECT acr FROM igraci WHERE id=?", (uid,))
    old = c.fetchone()[0]

    if win:
        c.execute("UPDATE igraci SET acr=acr+?, pobjede=pobjede+1 WHERE id=?", (acr_change, uid))
    else:
        c.execute("UPDATE igraci SET acr=acr+?, porazi=porazi+1 WHERE id=?", (acr_change, uid))

    conn.commit()

    c.execute("SELECT acr FROM igraci WHERE id=?", (uid,))
    new = c.fetchone()[0]

    embed = discord.Embed(title="📊 ACR PRO v2", color=0x9b59b6)
    embed.add_field(name="Player", value=member.display_name)
    embed.add_field(name="Team", value=team)
    embed.add_field(name="Result", value="WIN" if win else "LOSS")
    embed.add_field(name="Change", value=f"{acr_change:+}")
    embed.add_field(name="Old", value=old)
    embed.add_field(name="New", value=new)

    await ctx.send(embed=embed)


# =========================
# MATCH SYSTEM
# =========================
@bot.command()
async def start(ctx, a, b, mapa):
    global AKTIVNI_MEC
    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    AKTIVNI_MEC = {"a": a.upper(), "b": b.upper(), "mapa": mapa}

    embed = discord.Embed(title="🔥 MATCH STARTED", color=0xe67e22)
    embed.add_field(name="Teams", value=f"{a} vs {b}")
    embed.add_field(name="Map", value=mapa)

    await announce(ctx, embed)


@bot.command()
async def win(ctx, team, score, mvp):
    global AKTIVNI_MEC, ZADNJI_POBJEDNIK

    if not AKTIVNI_MEC:
        return await ctx.send("❌ No match.")

    ZADNJI_POBJEDNIK = team.upper()

    igrac(str(mvp))
    c.execute("UPDATE igraci SET mvp=mvp+1 WHERE id=?", (str(mvp),))
    conn.commit()

    embed = discord.Embed(title="🏆 MATCH RESULT", color=0x2ecc71)
    embed.add_field(name="Winner", value=team)
    embed.add_field(name="Score", value=score)
    embed.add_field(name="MVP", value=f"<@{mvp}>")

    AKTIVNI_MEC = None

    await announce(ctx, embed)


# =========================
# RUN
# =========================
token = os.getenv("TOKEN")

if token:
    bot.run(token)
else:
    print("NO TOKEN")
