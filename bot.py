import discord
from discord.ext import commands
import os
import sqlite3

# =========================
# SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ANN_CHANNEL = "announcements"
AKTIVNI_MEC = None
ZADNJI_POBJEDNIK = None

# =========================
# BAZA
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
# HELPERI
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

def u_timu(uid):
    c.execute("SELECT ime FROM timovi WHERE clanovi LIKE ?", (f"%{uid}%",))
    return c.fetchone()

def get_team(uid):
    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        if uid in clanovi.split(","):
            return ime
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
async def commands(ctx):
    embed = discord.Embed(title="🎮 KOMANDE IGRAČA", color=0x2ecc71)

    embed.add_field(name="Timovi",
                    value="!create <ime>\n!join <ime>\n!leave",
                    inline=False)

    embed.add_field(name="Statistika",
                    value="!stats [@igrac]",
                    inline=False)

    embed.add_field(name="Ostalo",
                    value="!leaderboard",
                    inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def create(ctx, ime):
    ime = ime.upper()
    uid = str(ctx.author.id)

    if tim(ime):
        return await ctx.send("❌ Tim već postoji.")

    c.execute("INSERT INTO timovi VALUES (?,?)", (ime, uid))
    conn.commit()

    await ctx.send(f"🏆 Tim {ime} je kreiran.")

@bot.command()
async def join(ctx, ime):
    uid = str(ctx.author.id)

    if u_timu(uid):
        return await ctx.send("❌ Već si u timu.")

    t = tim(ime)
    if not t:
        return await ctx.send("❌ Tim ne postoji.")

    clanovi = lista(t[1])

    if len(clanovi) >= 5:
        return await ctx.send("❌ Tim je pun.")

    clanovi.append(uid)

    c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
              (",".join(clanovi), ime.upper()))
    conn.commit()

    await ctx.send("✅ Ušao si u tim.")

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
    await ctx.send("🚪 Napustio si tim.")

@bot.command()
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)

    igrac(uid)

    c.execute("SELECT acr,pobjede,porazi,mvp,turniri FROM igraci WHERE id=?", (uid,))
    a,w,l,m,t = c.fetchone()

    embed = discord.Embed(title=f"📊 Statistika - {member.name}", color=0x3498db)
    embed.add_field(name="ACR", value=a)
    embed.add_field(name="Pobjede", value=w)
    embed.add_field(name="Porazi", value=l)
    embed.add_field(name="MVP", value=m)
    embed.add_field(name="Turniri osvojeni", value=t)

    await ctx.send(embed=embed)

# =========================
# 🔥 PREMIUM LEADERBOARD
# =========================
@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT id, acr, turniri FROM igraci ORDER BY acr DESC")
    rows = c.fetchall()

    embed = discord.Embed(title="🏆 Leaderboard", color=0xf1c40f)

    seen = set()
    mjesto = 1

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
        else:
            return "🔥 Elite"

    for uid, acr, turniri in rows:
        if uid in seen:
            continue
        seen.add(uid)

        member = ctx.guild.get_member(int(uid))
        ime = member.name if member else f"User-{uid}"

        team = get_team(uid)
        team_text = team if team else "Nema tim"

        embed.add_field(
            name=f"{mjesto}. {ime}",
            value=f"{rank(acr)}\nACR: {acr}\nTim: {team_text}\n🏆 Turniri: {turniri}",
            inline=False
        )

        mjesto += 1
        if mjesto > 10:
            break

    await ctx.send(embed=embed)

# =========================
# ADMIN COMMANDS
# =========================
@bot.command()
async def admincommands(ctx):
    if not admin(ctx):
        return await ctx.send("❌ Samo admin.")

    embed = discord.Embed(title="🛠 ADMIN KOMANDE", color=0xe74c3c)

    embed.add_field(
        name="Mečevi",
        value="!start <timA> <timB> <mapa>\n!win <pobjednik> <rezultat> <mvpID>",
        inline=False
    )

    embed.add_field(
        name="ACR sistem",
        value="!acr @igrac kills deaths assists adr hs util flash",
        inline=False
    )

    embed.add_field(
        name="Timovi",
        value="!addplayer @igrac <tim>\n!removeplayer @igrac",
        inline=False
    )

    embed.add_field(
        name="Turniri",
        value="!tournamentwin <userID>",
        inline=False
    )

    await ctx.send(embed=embed)

# =========================
# ADMIN TEAM CONTROL
# =========================
@bot.command()
async def addplayer(ctx, member: discord.Member, team_name):
    if not admin(ctx):
        return await ctx.send("❌ Samo admin.")

    uid = str(member.id)
    team_name = team_name.upper()

    t = tim(team_name)
    if not t:
        return await ctx.send("❌ Tim ne postoji.")

    if u_timu(uid):
        return await ctx.send("❌ Igrač je već u timu.")

    clanovi = lista(t[1])

    if len(clanovi) >= 5:
        return await ctx.send("❌ Tim je pun.")

    clanovi.append(uid)

    c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
              (",".join(clanovi), team_name))
    conn.commit()

    await ctx.send(f"✅ {member.mention} dodan u tim {team_name}")

@bot.command()
async def removeplayer(ctx, member: discord.Member):
    if not admin(ctx):
        return await ctx.send("❌ Samo admin.")

    uid = str(member.id)

    c.execute("SELECT ime, clanovi FROM timovi")
    for ime, clanovi in c.fetchall():
        l = lista(clanovi)
        if uid in l:
            l.remove(uid)
            c.execute("UPDATE timovi SET clanovi=? WHERE ime=?",
                      (",".join(l), ime))
            conn.commit()
            return await ctx.send(f"🚪 {member.mention} uklonjen iz tima {ime}")

    await ctx.send("❌ Igrač nije u timu.")

# =========================
# TURNAMENT WIN
# =========================
@bot.command()
async def tournamentwin(ctx, user_id):
    if not admin(ctx):
        return await ctx.send("❌ Samo admin.")

    uid = str(user_id)
    igrac(uid)

    c.execute("UPDATE igraci SET turniri=turniri+1 WHERE id=?", (uid,))
    conn.commit()

    await ctx.send(f"🏆 <@{uid}> osvojio turnir!")

# =========================
# MATCH + ACR (OSTALO OSTALO ISTO)
# =========================
@bot.command()
async def start(ctx, a, b, mapa):
    global AKTIVNI_MEC
    if not admin(ctx):
        return await ctx.send("❌ Samo admin.")

    AKTIVNI_MEC = {"a": a.upper(), "b": b.upper(), "mapa": mapa}

    embed = discord.Embed(title="🔥 ZAPOČEO JE MEČ", color=0xe67e22)
    embed.add_field(name="Timovi", value=f"{a} vs {b}")
    embed.add_field(name="Mapa", value=mapa)

    await announce(ctx, embed)

@bot.command()
async def win(ctx, pobjednik, rezultat, mvp):
    global AKTIVNI_MEC, ZADNJI_POBJEDNIK

    if not AKTIVNI_MEC:
        return await ctx.send("❌ Nema aktivnog meča.")

    pobjednik = pobjednik.upper()
    ZADNJI_POBJEDNIK = pobjednik

    mvp = str(mvp)
    igrac(mvp)
    c.execute("UPDATE igraci SET mvp=mvp+1 WHERE id=?", (mvp,))
    conn.commit()

    embed = discord.Embed(title="🏆 REZULTAT MEČA", color=0x2ecc71)
    embed.add_field(name="Pobjednik", value=pobjednik)
    embed.add_field(name="Rezultat", value=rezultat)
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
    print("TOKEN NIJE PRONAĐEN")
