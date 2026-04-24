import discord
from discord.ext import commands
import os
import sqlite3

# =========================
# INTENTS
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

def get_team(uid):
    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        if clanovi and uid in clanovi.split(","):
            return ime.upper()
    return None

def tim_exists(name):
    c.execute("SELECT * FROM timovi WHERE ime=?", (name.upper(),))
    return c.fetchone()

def admin(ctx):
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

@bot.command()
async def create(ctx, name):
    name = name.upper()
    uid = str(ctx.author.id)

    if tim_exists(name):
        return await ctx.send("❌ Team exists.")

    c.execute("INSERT INTO timovi VALUES (?,?)", (name, uid))
    conn.commit()

    await ctx.send(f"🏆 Team {name} created.")

@bot.command()
async def join(ctx, name):
    uid = str(ctx.author.id)

    if get_team(uid):
        return await ctx.send("❌ Already in team.")

    t = tim_exists(name)
    if not t:
        return await ctx.send("❌ Team not found.")

    clanovi = lista(t[1])

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
# LEADERBOARD (FIXED)
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
        name = member.display_name if member else "Unknown"

        team = get_team(uid) or "No team"

        embed.add_field(
            name=f"{place}. {name}",
            value=f"{rank(acr)}\nACR: {acr}\nTeam: {team}\n🏆 Tournaments: {t}",
            inline=False
        )

        place += 1

    await ctx.send(embed=embed)

# =========================
# ADMIN COMMANDS MENU
# =========================
@bot.command()
async def admincommands(ctx):
    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    embed = discord.Embed(title="🛠 ADMIN COMMANDS", color=0xe74c3c)

    embed.add_field(name="Match",
                    value="!start <A> <B> <map>\n!win <team> <score> <mvp>",
                    inline=False)

    embed.add_field(name="ACR",
                    value="!acr @player kills deaths assists adr hs util flash",
                    inline=False)

    embed.add_field(name="Teams",
                    value="!addplayer @user <team>\n!removeplayer @user",
                    inline=False)

    embed.add_field(name="Tournament",
                    value="!tournamentwin <userID>",
                    inline=False)

    await ctx.send(embed=embed)

# =========================
# ADD / REMOVE PLAYER (RESTORED)
# =========================
@bot.command()
async def addplayer(ctx, member: discord.Member, team):
    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    uid = str(member.id)
    team = team.upper()

    t = tim_exists(team)
    if not t:
        return await ctx.send("❌ Team not found.")

    clanovi = lista(t[1])

    if len(clanovi) >= 5:
        return await ctx.send("❌ Team full.")

    clanovi.append(uid)

    c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
              (",".join(clanovi), team))
    conn.commit()

    await ctx.send(f"✅ Added {member.display_name} to {team}")

@bot.command()
async def removeplayer(ctx, member: discord.Member):
    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    uid = str(member.id)

    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        l = lista(clanovi)
        if uid in l:
            l.remove(uid)
            c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
                      (",".join(l), ime))
            conn.commit()
            return await ctx.send(f"🚪 Removed from {ime}")

    await ctx.send("❌ Not found in any team.")

# =========================
# TOURNAMENT WIN
# =========================
@bot.command()
async def tournamentwin(ctx, user_id):
    if not admin(ctx):
        return await ctx.send("❌ Admin only.")

    igrac(str(user_id))
    c.execute("UPDATE igraci SET turniri=turniri+1 WHERE id=?", (str(user_id),))
    conn.commit()

    await ctx.send(f"🏆 Tournament win added to {user_id}")

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
