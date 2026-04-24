import discord
from discord.ext import commands
import os
import sqlite3
import random
from datetime import datetime

# ═══════════════════════════════════════════════
#  POSTAVLJANJE BOTA
# ═══════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ═══════════════════════════════════════════════
#  KANALI
# ═══════════════════════════════════════════════
KANAL_OBJAVE      = "announcements"   # turniri, start meca, opce objave
KANAL_REZULTATI   = "rezultati"       # rezultati meceva
KANAL_DOBRODOSLICA = "general"        # dolazak novih clanova

# ═══════════════════════════════════════════════
#  RANG → ULOGA MAPIRANJE
# ═══════════════════════════════════════════════
# Naziv uloge mora tocno odgovarati nazivu uloge na Discordu
RANG_ULOGE = {
    "◈ Legendarni":   2500,
    "◈ Elitni":       2000,
    "◈ Majstorski":   1800,
    "◈ Dijamantni":   1600,
    "◈ Platinasti":   1400,
    "◈ Zlatni":       1200,
    "◈ Srebrni":      1050,
    "◈ Brončani":      900,
    "◈ Željezni":        0,
}

# ═══════════════════════════════════════════════
#  BAZA PODATAKA
# ═══════════════════════════════════════════════
conn = sqlite3.connect("bot.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.executescript("""
CREATE TABLE IF NOT EXISTS igraci (
    id TEXT PRIMARY KEY,
    acr INTEGER DEFAULT 1000,
    pobjede INTEGER DEFAULT 0,
    porazi INTEGER DEFAULT 0,
    mvp INTEGER DEFAULT 0,
    turniri INTEGER DEFAULT 0,
    tim TEXT,
    registriran TEXT
);

CREATE TABLE IF NOT EXISTS timovi (
    naziv TEXT PRIMARY KEY,
    clanovi TEXT DEFAULT '',
    kreiran TEXT
);

CREATE TABLE IF NOT EXISTS meczevi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tim_a TEXT,
    tim_b TEXT,
    mapa TEXT,
    rezultat TEXT,
    pobjednik TEXT,
    gubitnik TEXT,
    mvp_id TEXT,
    odigrano TEXT
);

CREATE TABLE IF NOT EXISTS kazne (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    igrac_id TEXT,
    razlog TEXT,
    kazna INTEGER,
    admin_id TEXT,
    datum TEXT
);
""")
conn.commit()

# ═══════════════════════════════════════════════
#  RANG SUSTAV
# ═══════════════════════════════════════════════
RANGOVI = [
    (0,    "◈ Željezni",    0x7f8c8d),
    (900,  "◈ Brončani",    0xcd6133),
    (1050, "◈ Srebrni",     0x95a5a6),
    (1200, "◈ Zlatni",      0xf1c40f),
    (1400, "◈ Platinasti",  0x1abc9c),
    (1600, "◈ Dijamantni",  0x3498db),
    (1800, "◈ Majstorski",  0x9b59b6),
    (2000, "◈ Elitni",      0xe74c3c),
    (2500, "◈ Legendarni",  0xff6b35),
]

def dohvati_rang(acr: int):
    rang = RANGOVI[0]
    for entry in RANGOVI:
        if acr >= entry[0]:
            rang = entry
    return rang[1], rang[2]

def rang_naziv(acr: int) -> str:
    return dohvati_rang(acr)[0]

def rang_boja(acr: int) -> int:
    return dohvati_rang(acr)[1]

def rang_napredak(acr: int) -> str:
    for i, (min_acr, naziv, _) in enumerate(RANGOVI):
        if i + 1 < len(RANGOVI):
            sljedeci_min = RANGOVI[i + 1][0]
            if acr < sljedeci_min:
                napredak = acr - min_acr
                potrebno = sljedeci_min - min_acr
                posto = int((napredak / potrebno) * 10)
                traka = "█" * posto + "░" * (10 - posto)
                return f"`{traka}` {napredak}/{potrebno}"
    return "`██████████` MAX RANG"

# ═══════════════════════════════════════════════
#  AUTO ULOGA — CORE FUNKCIJA
# ═══════════════════════════════════════════════
async def azuriraj_ulogu(guild: discord.Guild, member: discord.Member, acr: int):
    """Ukloni sve stare rang uloge i dodaj novu prema ACR-u."""
    naziv_nove_uloge = rang_naziv(acr)

    # Dohvati sve rang uloge koje postoje na serveru
    sve_rang_uloge = []
    for naziv_uloge in RANG_ULOGE:
        uloga = discord.utils.get(guild.roles, name=naziv_uloge)
        if uloga:
            sve_rang_uloge.append(uloga)

    # Ukloni sve stare rang uloge
    uloge_za_ukloniti = [u for u in member.roles if u in sve_rang_uloge]
    if uloge_za_ukloniti:
        try:
            await member.remove_roles(*uloge_za_ukloniti)
        except discord.Forbidden:
            pass

    # Dodaj novu rang ulogu
    nova_uloga = discord.utils.get(guild.roles, name=naziv_nove_uloge)
    if nova_uloga:
        try:
            await member.add_roles(nova_uloga)
        except discord.Forbidden:
            pass

async def azuriraj_ulogu_po_id(guild: discord.Guild, uid: str, acr: int):
    """Pomocna funkcija — dohvaca member po ID-u pa azurira ulogu."""
    try:
        member = guild.get_member(int(uid))
        if not member:
            member = await guild.fetch_member(int(uid))
        if member:
            await azuriraj_ulogu(guild, member, acr)
    except (discord.NotFound, discord.HTTPException):
        pass

# ═══════════════════════════════════════════════
#  POMOCNE FUNKCIJE
# ═══════════════════════════════════════════════
def osiguraj_igraca(uid: str):
    c.execute("SELECT id FROM igraci WHERE id=?", (uid,))
    if not c.fetchone():
        sada = datetime.utcnow().strftime("%d.%m.%Y")
        c.execute("INSERT INTO igraci (id, registriran) VALUES (?,?)", (uid, sada))
        conn.commit()

def dohvati_igraca(uid: str):
    osiguraj_igraca(uid)
    c.execute("SELECT * FROM igraci WHERE id=?", (uid,))
    return c.fetchone()

def dohvati_tim_igraca(uid: str):
    c.execute("SELECT naziv, clanovi FROM timovi")
    for red in c.fetchall():
        clanovi = red["clanovi"].split(",") if red["clanovi"] else []
        if uid in clanovi:
            return red["naziv"]
    return None

def dohvati_clanove_tima(naziv: str):
    c.execute("SELECT clanovi FROM timovi WHERE naziv=?", (naziv.upper(),))
    red = c.fetchone()
    if not red or not red["clanovi"]:
        return []
    return [m for m in red["clanovi"].split(",") if m]

def je_admin(ctx) -> bool:
    return ctx.author.guild_permissions.administrator

async def objavi(ctx, embed: discord.Embed):
    kanal = discord.utils.get(ctx.guild.text_channels, name=KANAL_OBJAVE)
    if kanal:
        await kanal.send(embed=embed)
    else:
        await ctx.send(embed=embed)

async def objavi_rezultat(ctx, embed: discord.Embed):
    kanal = discord.utils.get(ctx.guild.text_channels, name=KANAL_REZULTATI)
    if kanal:
        await kanal.send(embed=embed)
    else:
        await ctx.send(embed=embed)

def spremi_mec(tim_a, tim_b, mapa, rezultat, pobjednik, gubitnik, mvp_id):
    c.execute("""
        INSERT INTO meczevi (tim_a, tim_b, mapa, rezultat, pobjednik, gubitnik, mvp_id, odigrano)
        VALUES (?,?,?,?,?,?,?,?)
    """, (tim_a, tim_b, mapa, rezultat, pobjednik, gubitnik, mvp_id,
          datetime.utcnow().strftime("%d.%m.%Y %H:%M")))
    c.execute("""
        DELETE FROM meczevi WHERE id NOT IN (
            SELECT id FROM meczevi ORDER BY id DESC LIMIT 20
        )
    """)
    conn.commit()

def greska_embed(poruka: str) -> discord.Embed:
    return discord.Embed(description=f"```diff\n- {poruka}\n```", color=0xe74c3c)

def uspjeh_embed(naslov: str, poruka: str = None) -> discord.Embed:
    e = discord.Embed(title=f"✦ {naslov}", color=0x2ecc71)
    if poruka:
        e.description = poruka
    return e

# ═══════════════════════════════════════════════
#  EVENTI
# ═══════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"╔══════════════════════════════╗")
    print(f"║   BOT ONLINE: {bot.user}")
    print(f"╚══════════════════════════════╝")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="CS2 | !commands")
    )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=greska_embed(f"Nedostaje argument: {error.param.name}  •  Koristi !commands"))
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(embed=greska_embed("Korisnik nije pronađen."))
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=greska_embed("Neispravan tip argumenta."))
    elif isinstance(error, commands.CommandNotFound):
        pass

@bot.event
async def on_member_join(member: discord.Member):
    uid = str(member.id)
    osiguraj_igraca(uid)

    # Dodijeli pocetnu rang ulogu (Zeljezni, 1000 ACR)
    await azuriraj_ulogu(member.guild, member, 1000)

    kanal = discord.utils.get(member.guild.text_channels, name=KANAL_DOBRODOSLICA)
    if kanal:
        embed = discord.Embed(
            title="◈ Novi Igrač",
            description=(
                f"**{member.display_name}** se pridružio serveru.\n"
                f"Dobrodošao u arenu.\n\n"
                f"Pročitaj **#pravila** i **#bot-komande** za početak."
            ),
            color=0x3498db
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="⚡ Početni ACR", value="1000")
        embed.add_field(name="🎖️ Rang", value=rang_naziv(1000))
        embed.set_footer(text=f"Član #{member.guild.member_count}")
        await kanal.send(embed=embed)

# ═══════════════════════════════════════════════
#  TIMOVI
# ═══════════════════════════════════════════════
@bot.command()
async def stvori(ctx, *, naziv: str):
    uid = str(ctx.author.id)
    naziv = naziv.upper().strip()

    if len(naziv) > 20:
        return await ctx.send(embed=greska_embed("Naziv tima ne smije biti duži od 20 znakova."))
    if dohvati_tim_igraca(uid):
        return await ctx.send(embed=greska_embed("Već si u timu. Izađi prvo s !izlaz"))

    c.execute("SELECT naziv FROM timovi WHERE naziv=?", (naziv,))
    if c.fetchone():
        return await ctx.send(embed=greska_embed(f"Tim {naziv} već postoji."))

    sada = datetime.utcnow().strftime("%d.%m.%Y")
    c.execute("INSERT INTO timovi VALUES (?,?,?)", (naziv, uid, sada))
    osiguraj_igraca(uid)
    c.execute("UPDATE igraci SET tim=? WHERE id=?", (naziv, uid))
    conn.commit()

    embed = discord.Embed(title="◈ Tim Stvoren", color=0x2ecc71)
    embed.add_field(name="Naziv", value=f"**{naziv}**")
    embed.add_field(name="Kapetan", value=ctx.author.display_name)
    embed.add_field(name="Mjesta", value="1 / 5")
    embed.set_footer(text=f"Stvoreno {sada}")
    await ctx.send(embed=embed)

@bot.command()
async def pridruzi(ctx, *, naziv: str):
    uid = str(ctx.author.id)
    naziv = naziv.upper().strip()

    if dohvati_tim_igraca(uid):
        return await ctx.send(embed=greska_embed("Već si u timu. Izađi prvo s !izlaz"))

    c.execute("SELECT naziv FROM timovi WHERE naziv=?", (naziv,))
    if not c.fetchone():
        return await ctx.send(embed=greska_embed(f"Tim {naziv} ne postoji."))

    clanovi = dohvati_clanove_tima(naziv)
    if len(clanovi) >= 5:
        return await ctx.send(embed=greska_embed("Tim je pun (max 5 igrača)."))

    clanovi.append(uid)
    c.execute("UPDATE timovi SET clanovi=? WHERE naziv=?", (",".join(clanovi), naziv))
    osiguraj_igraca(uid)
    c.execute("UPDATE igraci SET tim=? WHERE id=?", (naziv, uid))
    conn.commit()

    embed = discord.Embed(title="◈ Pridružen Timu", color=0x2ecc71)
    embed.add_field(name="Tim", value=f"**{naziv}**")
    embed.add_field(name="Igrač", value=ctx.author.display_name)
    embed.add_field(name="Mjesta", value=f"{len(clanovi)} / 5")
    await ctx.send(embed=embed)

@bot.command()
async def izlaz(ctx):
    uid = str(ctx.author.id)
    naziv_tima = dohvati_tim_igraca(uid)

    if not naziv_tima:
        return await ctx.send(embed=greska_embed("Nisi u nijednom timu."))

    clanovi = dohvati_clanove_tima(naziv_tima)
    clanovi = [m for m in clanovi if m != uid]
    c.execute("UPDATE timovi SET clanovi=? WHERE naziv=?", (",".join(clanovi), naziv_tima))
    c.execute("UPDATE igraci SET tim=NULL WHERE id=?", (uid,))
    conn.commit()

    embed = discord.Embed(title="◈ Napustio Tim", color=0xe67e22)
    embed.add_field(name="Tim", value=naziv_tima)
    embed.add_field(name="Igrač", value=ctx.author.display_name)
    await ctx.send(embed=embed)

@bot.command()
async def tim(ctx, *, naziv: str):
    naziv = naziv.upper().strip()
    c.execute("SELECT kreiran FROM timovi WHERE naziv=?", (naziv,))
    red = c.fetchone()
    if not red:
        return await ctx.send(embed=greska_embed(f"Tim {naziv} ne postoji."))

    clanovi = dohvati_clanove_tima(naziv)
    embed = discord.Embed(title=f"◈ Tim  {naziv}", color=0x3498db)
    embed.description = "─" * 32

    if clanovi:
        ukupni_acr = 0
        lista = []
        for uid in clanovi:
            member = ctx.guild.get_member(int(uid))
            ime = member.display_name if member else "Nepoznat"
            p = dohvati_igraca(uid)
            ukupni_acr += p["acr"]
            lista.append(f"◦ **{ime}** — {rang_naziv(p['acr'])}  •  ACR: **{p['acr']}**")
        embed.add_field(name="Sastav", value="\n".join(lista), inline=False)
        embed.add_field(name="Prosječni ACR", value=str(ukupni_acr // len(clanovi)))
        embed.add_field(name="Igrači", value=f"{len(clanovi)} / 5")
    else:
        embed.description = "Tim nema članova."

    embed.set_footer(text=f"Osnovan: {red['kreiran']}")
    await ctx.send(embed=embed)

@bot.command()
async def timovi_lista(ctx):
    c.execute("SELECT naziv, clanovi FROM timovi ORDER BY naziv")
    svi = c.fetchall()

    if not svi:
        return await ctx.send(embed=greska_embed("Nema registriranih timova."))

    embed = discord.Embed(title="◈ Registrirani Timovi", color=0x9b59b6)
    embed.description = "─" * 32 + "\n"
    for red in svi:
        clanovi = [m for m in red["clanovi"].split(",") if m] if red["clanovi"] else []
        embed.add_field(name=f"◦ {red['naziv']}", value=f"Igrači: **{len(clanovi)}/5**", inline=True)

    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  STATISTIKE
# ═══════════════════════════════════════════════
@bot.command()
async def statistike(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)
    osiguraj_igraca(uid)
    p = dohvati_igraca(uid)

    ukupno = p["pobjede"] + p["porazi"]
    winrate = round((p["pobjede"] / ukupno * 100), 1) if ukupno > 0 else 0

    embed = discord.Embed(color=rang_boja(p["acr"]))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.title = rang_naziv(p["acr"])
    embed.description = f"**Napredak do sljedećeg ranga**\n{rang_napredak(p['acr'])}"
    embed.add_field(name="⚡ ACR", value=f"**{p['acr']}**")
    embed.add_field(name="✦ Pobjede", value=f"**{p['pobjede']}**")
    embed.add_field(name="✦ Porazi", value=f"**{p['porazi']}**")
    embed.add_field(name="📊 Win Rate", value=f"**{winrate}%**")
    embed.add_field(name="⭐ MVP", value=f"**{p['mvp']}**")
    embed.add_field(name="🏆 Turniri", value=f"**{p['turniri']}**")
    embed.add_field(name="👥 Tim", value=f"**{p['tim'] or 'Bez tima'}**")
    embed.add_field(name="📅 Registriran", value=f"**{p['registriran'] or 'N/A'}**")
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  LJESTVICA
# ═══════════════════════════════════════════════
@bot.command()
async def ljestvica(ctx):
    redovi = c.execute(
        "SELECT id, acr, pobjede, porazi, turniri, tim FROM igraci ORDER BY acr DESC LIMIT 10"
    ).fetchall()

    if not redovi:
        return await ctx.send(embed=greska_embed("Još nema igrača na ljestvici."))

    embed = discord.Embed(
        title="◈ ACR Ljestvica",
        description="─" * 32,
        color=0xf1c40f
    )

    oznake = ["🥇", "🥈", "🥉", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
    for i, red in enumerate(redovi):
        member = ctx.guild.get_member(int(red["id"]))
        ime = member.display_name if member else "Nepoznat"
        ukupno = red["pobjede"] + red["porazi"]
        wr = round(red["pobjede"] / ukupno * 100) if ukupno > 0 else 0

        embed.add_field(
            name=f"{oznake[i]}  {ime}",
            value=(
                f"{rang_naziv(red['acr'])}  •  **{red['acr']}** ACR\n"
                f"W/L: {red['pobjede']}/{red['porazi']} ({wr}%)  •  🏆 {red['turniri']}  •  👥 {red['tim'] or '—'}"
            ),
            inline=False
        )

    embed.set_footer(text=f"Ažurirano: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  MEČ SUSTAV (ADMIN)
# ═══════════════════════════════════════════════
@bot.command()
async def start(ctx, tim_a: str, tim_b: str, mapa: str):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    tim_a = tim_a.upper()
    tim_b = tim_b.upper()

    embed = discord.Embed(title="◈ Meč Počinje", color=0xe67e22)
    embed.description = "─" * 32
    embed.add_field(name="⚔️  Dvoboj", value=f"**{tim_a}**  vs  **{tim_b}**", inline=False)
    embed.add_field(name="🗺️  Mapa", value=f"**{mapa}**")
    embed.add_field(name="🕐  Početak", value=datetime.utcnow().strftime("%d.%m.%Y %H:%M") + " UTC")
    embed.set_footer(text="Neka pobijedi bolji tim.")
    await objavi(ctx, embed)

@bot.command()
async def pobjeda(ctx, pobjednicki_tim: str, gubitnicki_tim: str, rezultat: str, mapa: str, mvp: discord.Member):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    pobjednicki_tim = pobjednicki_tim.upper()
    gubitnicki_tim = gubitnicki_tim.upper()
    mvp_uid = str(mvp.id)

    # Pobjednicki tim — azuriraj ACR i uloge
    for uid in dohvati_clanove_tima(pobjednicki_tim):
        osiguraj_igraca(uid)
        bonus = 40 if uid == mvp_uid else 25
        c.execute("UPDATE igraci SET acr=acr+?, pobjede=pobjede+1 WHERE id=?", (bonus, uid))
        conn.commit()
        novi_acr = dohvati_igraca(uid)["acr"]
        await azuriraj_ulogu_po_id(ctx.guild, uid, novi_acr)

    # Gubitnicki tim — azuriraj ACR i uloge
    for uid in dohvati_clanove_tima(gubitnicki_tim):
        osiguraj_igraca(uid)
        c.execute("UPDATE igraci SET acr=MAX(0, acr-20), porazi=porazi+1 WHERE id=?", (uid,))
        conn.commit()
        novi_acr = dohvati_igraca(uid)["acr"]
        await azuriraj_ulogu_po_id(ctx.guild, uid, novi_acr)

    # MVP bonus
    osiguraj_igraca(mvp_uid)
    c.execute("UPDATE igraci SET mvp=mvp+1, acr=acr+10 WHERE id=?", (mvp_uid,))
    conn.commit()
    novi_acr_mvp = dohvati_igraca(mvp_uid)["acr"]
    await azuriraj_ulogu_po_id(ctx.guild, mvp_uid, novi_acr_mvp)

    spremi_mec(pobjednicki_tim, gubitnicki_tim, mapa, rezultat, pobjednicki_tim, gubitnicki_tim, mvp_uid)

    embed = discord.Embed(title="◈ Rezultat Meča", color=0x2ecc71)
    embed.description = "─" * 32
    embed.add_field(name="🏅  Pobjednik", value=f"**{pobjednicki_tim}**")
    embed.add_field(name="💀  Poraženi", value=f"**{gubitnicki_tim}**")
    embed.add_field(name="📊  Rezultat", value=f"**{rezultat}**")
    embed.add_field(name="🗺️  Mapa", value=f"**{mapa}**")
    embed.add_field(name="⭐  MVP", value=f"**{mvp.display_name}**")
    embed.add_field(
        name="⚡  ACR Promjene",
        value=f"**{pobjednicki_tim}** +25 (MVP +40+10)\n**{gubitnicki_tim}** −20",
        inline=False
    )
    await objavi_rezultat(ctx, embed)

# ═══════════════════════════════════════════════
#  ACR ADMIN KOMANDA
# ═══════════════════════════════════════════════
@bot.command()
async def acr(ctx, member: discord.Member, k: int, d: int, a: int, adr: int, hs: int, util: int, flashevi: int):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    uid = str(member.id)
    osiguraj_igraca(uid)

    rezultat = round(
        (k * 2.0) + (a * 1.5) + (adr * 0.3) +
        (hs * 1.2) + (util * 0.5) + (flashevi * 0.2) - (d * 1.5)
    )

    stari_acr = dohvati_igraca(uid)["acr"]
    c.execute("UPDATE igraci SET acr=MAX(0, acr+?) WHERE id=?", (rezultat, uid))
    conn.commit()
    novi_acr = dohvati_igraca(uid)["acr"]

    # Azuriraj ulogu
    await azuriraj_ulogu(ctx.guild, member, novi_acr)

    stari_rang = rang_naziv(stari_acr)
    novi_rang = rang_naziv(novi_acr)
    predznak = "+" if rezultat >= 0 else ""

    embed = discord.Embed(title="◈ ACR Ažuriran", color=rang_boja(novi_acr))
    embed.add_field(name="Igrač", value=member.display_name)
    embed.add_field(name="Promjena", value=f"**{predznak}{rezultat}**")
    embed.add_field(name="ACR", value=f"{stari_acr} → **{novi_acr}**")

    # Pokazi rank up/down ako se rang promijenio
    if stari_rang != novi_rang:
        if novi_acr > stari_acr:
            embed.add_field(name="🎉 RANK UP!", value=f"{stari_rang} → **{novi_rang}**", inline=False)
        else:
            embed.add_field(name="📉 Rang pao", value=f"{stari_rang} → **{novi_rang}**", inline=False)
    else:
        embed.add_field(name="Rang", value=novi_rang)

    embed.add_field(
        name="Performanse",
        value=f"K: {k}  D: {d}  A: {a}\nADR: {adr}  HS: {hs}%  Util: {util}  Flash: {flashevi}",
        inline=False
    )
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  TURNIRSKA POBJEDA (ADMIN)
# ═══════════════════════════════════════════════
@bot.command()
async def turnir(ctx, naziv_tima: str):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    naziv_tima = naziv_tima.upper()
    clanovi = dohvati_clanove_tima(naziv_tima)

    if not clanovi:
        return await ctx.send(embed=greska_embed(f"Tim {naziv_tima} ne postoji ili je prazan."))

    for uid in clanovi:
        osiguraj_igraca(uid)
        c.execute("UPDATE igraci SET turniri=turniri+1, acr=acr+150 WHERE id=?", (uid,))
        conn.commit()
        novi_acr = dohvati_igraca(uid)["acr"]
        await azuriraj_ulogu_po_id(ctx.guild, uid, novi_acr)

    embed = discord.Embed(title="◈ Turnirski Prvak", color=0xf39c12)
    embed.description = f"Tim **{naziv_tima}** osvaja turnir!"
    embed.add_field(name="🎁 Nagrada", value="+150 ACR za sve članove", inline=False)

    imena = []
    for uid in clanovi:
        m = ctx.guild.get_member(int(uid))
        imena.append(f"◦ {m.display_name if m else 'Nepoznat'}")
    embed.add_field(name="👥 Sastav", value="\n".join(imena), inline=False)
    embed.set_footer(text=datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"))
    await objavi(ctx, embed)

# ═══════════════════════════════════════════════
#  ADMIN — DODAJ / UKLONI IGRAČA
# ═══════════════════════════════════════════════
@bot.command()
async def dodaj(ctx, member: discord.Member, naziv_tima: str):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    uid = str(member.id)
    naziv_tima = naziv_tima.upper()

    if dohvati_tim_igraca(uid):
        return await ctx.send(embed=greska_embed("Igrač je već u nekom timu."))

    c.execute("SELECT naziv FROM timovi WHERE naziv=?", (naziv_tima,))
    if not c.fetchone():
        return await ctx.send(embed=greska_embed(f"Tim {naziv_tima} ne postoji."))

    clanovi = dohvati_clanove_tima(naziv_tima)
    if len(clanovi) >= 5:
        return await ctx.send(embed=greska_embed("Tim je pun (max 5 igrača)."))

    clanovi.append(uid)
    c.execute("UPDATE timovi SET clanovi=? WHERE naziv=?", (",".join(clanovi), naziv_tima))
    osiguraj_igraca(uid)
    c.execute("UPDATE igraci SET tim=? WHERE id=?", (naziv_tima, uid))
    conn.commit()

    embed = uspjeh_embed("Igrač Dodan")
    embed.add_field(name="Igrač", value=member.display_name)
    embed.add_field(name="Tim", value=naziv_tima)
    await ctx.send(embed=embed)

@bot.command()
async def ukloni(ctx, member: discord.Member):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    uid = str(member.id)
    naziv_tima = dohvati_tim_igraca(uid)

    if not naziv_tima:
        return await ctx.send(embed=greska_embed("Igrač nije ni u jednom timu."))

    clanovi = dohvati_clanove_tima(naziv_tima)
    clanovi = [m for m in clanovi if m != uid]
    c.execute("UPDATE timovi SET clanovi=? WHERE naziv=?", (",".join(clanovi), naziv_tima))
    c.execute("UPDATE igraci SET tim=NULL WHERE id=?", (uid,))
    conn.commit()

    embed = uspjeh_embed("Igrač Uklonjen")
    embed.add_field(name="Igrač", value=member.display_name)
    embed.add_field(name="Iz tima", value=naziv_tima)
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  POVIJEST MEČEVA
# ═══════════════════════════════════════════════
@bot.command()
async def povijest(ctx):
    redovi = c.execute("SELECT * FROM meczevi ORDER BY id DESC LIMIT 20").fetchall()

    if not redovi:
        return await ctx.send(embed=greska_embed("Još nema odigranih mečeva."))

    embed = discord.Embed(
        title="◈ Povijest Mečeva",
        description="─" * 32,
        color=0x9b59b6
    )

    for red in redovi:
        mvp_member = ctx.guild.get_member(int(red["mvp_id"])) if red["mvp_id"] else None
        mvp_ime = mvp_member.display_name if mvp_member else "Nepoznat"
        embed.add_field(
            name=f"#{red['id']}  {red['tim_a']} vs {red['tim_b']}",
            value=(
                f"🏅 **{red['pobjednik']}**  •  {red['rezultat']}\n"
                f"🗺️ {red['mapa']}  •  ⭐ {mvp_ime}\n"
                f"🕐 {red['odigrano']} UTC"
            ),
            inline=False
        )

    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  RANG LISTA
# ═══════════════════════════════════════════════
@bot.command()
async def rangovi(ctx):
    embed = discord.Embed(
        title="◈ Rang Sustav",
        description="─" * 32,
        color=0xf1c40f
    )

    for i, (min_acr, naziv, _) in enumerate(RANGOVI):
        if i + 1 < len(RANGOVI):
            raspon = f"{min_acr} – {RANGOVI[i + 1][0] - 1} ACR"
        else:
            raspon = f"{min_acr}+ ACR"
        embed.add_field(name=naziv, value=raspon, inline=False)

    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  SYNC ULOGA (ADMIN) — za postojece igrače
# ═══════════════════════════════════════════════
@bot.command()
async def sync_uloge(ctx):
    """Sinkronizira rang uloge za sve igrače u bazi — korisno za prvi setup."""
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    msg = await ctx.send(embed=discord.Embed(
        description="⏳ Sinkronizacija rang uloga u tijeku...",
        color=0xe67e22
    ))

    svi = c.execute("SELECT id, acr FROM igraci").fetchall()
    uspjeh = 0
    greska = 0

    for red in svi:
        try:
            await azuriraj_ulogu_po_id(ctx.guild, red["id"], red["acr"])
            uspjeh += 1
        except Exception:
            greska += 1

    embed = discord.Embed(title="◈ Sync Završen", color=0x2ecc71)
    embed.add_field(name="✅ Ažurirano", value=str(uspjeh))
    embed.add_field(name="❌ Greška", value=str(greska))
    embed.add_field(name="📊 Ukupno", value=str(len(svi)))
    await msg.edit(embed=embed)

# ═══════════════════════════════════════════════
#  IZAZOV
# ═══════════════════════════════════════════════
aktivni_izazovi = {}

@bot.command()
async def izazovi(ctx, naziv_tima: str):
    uid = str(ctx.author.id)
    moj_tim = dohvati_tim_igraca(uid)
    naziv_tima = naziv_tima.upper()

    if not moj_tim:
        return await ctx.send(embed=greska_embed("Nisi ni u jednom timu."))
    if moj_tim == naziv_tima:
        return await ctx.send(embed=greska_embed("Ne možeš izazvati vlastiti tim."))

    c.execute("SELECT naziv FROM timovi WHERE naziv=?", (naziv_tima,))
    if not c.fetchone():
        return await ctx.send(embed=greska_embed(f"Tim {naziv_tima} ne postoji."))

    aktivni_izazovi[naziv_tima] = moj_tim

    embed = discord.Embed(title="◈ Izazov Poslan", color=0xe67e22)
    embed.description = (
        f"**{moj_tim}** izaziva **{naziv_tima}** na meč!\n\n"
        f"Kapetan tima **{naziv_tima}** može prihvatiti s `!prihvati`"
    )
    await ctx.send(embed=embed)

@bot.command()
async def prihvati(ctx):
    uid = str(ctx.author.id)
    moj_tim = dohvati_tim_igraca(uid)

    if not moj_tim or moj_tim not in aktivni_izazovi:
        return await ctx.send(embed=greska_embed("Nemaš aktivnih izazova."))

    izazivac = aktivni_izazovi.pop(moj_tim)

    embed = discord.Embed(title="◈ Izazov Prihvaćen!", color=0x2ecc71)
    embed.description = (
        f"**{izazivac}** vs **{moj_tim}**\n\n"
        f"Meč je dogovoren! Admin treba pokrenuti s:\n"
        f"`!start {izazivac} {moj_tim} <mapa>`"
    )
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  KAZNA / DISCIPLINA (ADMIN)
# ═══════════════════════════════════════════════
@bot.command()
async def kazna(ctx, member: discord.Member, iznos: int, *, razlog: str):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    uid = str(member.id)
    osiguraj_igraca(uid)

    stari_acr = dohvati_igraca(uid)["acr"]
    c.execute("UPDATE igraci SET acr=MAX(0, acr-?) WHERE id=?", (iznos, uid))
    c.execute(
        "INSERT INTO kazne (igrac_id, razlog, kazna, admin_id, datum) VALUES (?,?,?,?,?)",
        (uid, razlog, iznos, str(ctx.author.id), datetime.utcnow().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()

    novi_acr = dohvati_igraca(uid)["acr"]
    await azuriraj_ulogu(ctx.guild, member, novi_acr)

    embed = discord.Embed(title="◈ Disciplinska Mjera", color=0xe74c3c)
    embed.add_field(name="Igrač", value=member.display_name)
    embed.add_field(name="Kazna", value=f"−{iznos} ACR")
    embed.add_field(name="ACR", value=f"{stari_acr} → **{novi_acr}**")
    embed.add_field(name="Rang", value=rang_naziv(novi_acr))
    embed.add_field(name="Razlog", value=razlog, inline=False)
    embed.add_field(name="Admin", value=ctx.author.display_name)
    await ctx.send(embed=embed)

@bot.command()
async def kazne_povijest(ctx, member: discord.Member = None):
    if member:
        uid = str(member.id)
        redovi = c.execute(
            "SELECT * FROM kazne WHERE igrac_id=? ORDER BY id DESC LIMIT 10", (uid,)
        ).fetchall()
        naslov = f"◈ Kazne — {member.display_name}"
    else:
        redovi = c.execute("SELECT * FROM kazne ORDER BY id DESC LIMIT 10").fetchall()
        naslov = "◈ Posljednjih 10 Kazni"

    if not redovi:
        return await ctx.send(embed=greska_embed("Nema zabilježenih kazni."))

    embed = discord.Embed(title=naslov, color=0xe74c3c)
    for red in redovi:
        igrac = ctx.guild.get_member(int(red["igrac_id"]))
        ime = igrac.display_name if igrac else "Nepoznat"
        embed.add_field(
            name=f"#{red['id']}  {ime}  −{red['kazna']} ACR",
            value=f"Razlog: {red['razlog']}\n🕐 {red['datum']}",
            inline=False
        )
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  RESET IGRAČA (ADMIN)
# ═══════════════════════════════════════════════
@bot.command()
async def reset_igraca(ctx, member: discord.Member):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu koristiti ovu komandu."))

    uid = str(member.id)
    c.execute(
        "UPDATE igraci SET acr=1000, pobjede=0, porazi=0, mvp=0, turniri=0 WHERE id=?",
        (uid,)
    )
    conn.commit()

    # Reset uloge na Zeljezni (1000 ACR)
    await azuriraj_ulogu(ctx.guild, member, 1000)

    embed = uspjeh_embed("Statistike Resetirane")
    embed.add_field(name="Igrač", value=member.display_name)
    embed.add_field(name="ACR reset na", value="1000")
    embed.add_field(name="Rang reset na", value=rang_naziv(1000))
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  SERVER STATISTIKE
# ═══════════════════════════════════════════════
@bot.command()
async def server(ctx):
    ukupno_igrac = c.execute("SELECT COUNT(*) FROM igraci").fetchone()[0]
    ukupno_tim = c.execute("SELECT COUNT(*) FROM timovi").fetchone()[0]
    ukupno_mec = c.execute("SELECT COUNT(*) FROM meczevi").fetchone()[0]

    top = c.execute("SELECT id, acr FROM igraci ORDER BY acr DESC LIMIT 1").fetchone()
    top_ime = "N/A"
    if top:
        m = ctx.guild.get_member(int(top["id"]))
        top_ime = f"{m.display_name if m else 'Nepoznat'} ({top['acr']} ACR)"

    embed = discord.Embed(title=f"◈ {ctx.guild.name}  —  Server Info", color=0x3498db)
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.add_field(name="👥 Registrirani igrači", value=str(ukupno_igrac))
    embed.add_field(name="🎮 Aktivni timovi", value=str(ukupno_tim))
    embed.add_field(name="⚔️ Odigrani mečevi", value=str(ukupno_mec))
    embed.add_field(name="🏆 Vodeći igrač", value=top_ime, inline=False)
    embed.set_footer(text=f"Discord: {ctx.guild.member_count} članova")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  USPOREDBA IGRAČA
# ═══════════════════════════════════════════════
@bot.command()
async def usporedi(ctx, igrac1: discord.Member, igrac2: discord.Member):
    uid1, uid2 = str(igrac1.id), str(igrac2.id)
    osiguraj_igraca(uid1)
    osiguraj_igraca(uid2)
    p1, p2 = dohvati_igraca(uid1), dohvati_igraca(uid2)

    def wr(p):
        uk = p["pobjede"] + p["porazi"]
        return round(p["pobjede"] / uk * 100, 1) if uk > 0 else 0

    def znak(a, b):
        return "✦" if a > b else "◦"

    embed = discord.Embed(title=f"◈ {igrac1.display_name}  vs  {igrac2.display_name}", color=0xf1c40f)
    embed.add_field(
        name=igrac1.display_name,
        value=(
            f"ACR: **{p1['acr']}** {znak(p1['acr'], p2['acr'])}\n"
            f"W/L: {p1['pobjede']}/{p1['porazi']}\n"
            f"WR: {wr(p1)}% {znak(wr(p1), wr(p2))}\n"
            f"MVP: {p1['mvp']} {znak(p1['mvp'], p2['mvp'])}\n"
            f"Turniri: {p1['turniri']} {znak(p1['turniri'], p2['turniri'])}\n"
            f"Rang: {rang_naziv(p1['acr'])}"
        )
    )
    embed.add_field(
        name=igrac2.display_name,
        value=(
            f"ACR: **{p2['acr']}** {znak(p2['acr'], p1['acr'])}\n"
            f"W/L: {p2['pobjede']}/{p2['porazi']}\n"
            f"WR: {wr(p2)}% {znak(wr(p2), wr(p1))}\n"
            f"MVP: {p2['mvp']} {znak(p2['mvp'], p1['mvp'])}\n"
            f"Turniri: {p2['turniri']} {znak(p2['turniri'], p1['turniri'])}\n"
            f"Rang: {rang_naziv(p2['acr'])}"
        )
    )
    pobjednik = igrac1.display_name if p1["acr"] >= p2["acr"] else igrac2.display_name
    embed.set_footer(text=f"✦ označava prednost  •  Viši ACR: {pobjednik}")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  SLUČAJNA MAPA / VETO
# ═══════════════════════════════════════════════
CS2_MAPE = [
    "Mirage", "Inferno", "Dust2", "Nuke", "Ancient",
    "Vertigo", "Anubis", "Cache", "Overpass", "Train"
]

@bot.command()
async def mapa(ctx):
    odabrana = random.choice(CS2_MAPE)
    embed = discord.Embed(
        title="◈ Odabrana Mapa",
        description=f"# {odabrana}",
        color=0xe67e22
    )
    embed.set_footer(text="Nasumično odabrano  •  CS2 Kompetitivni Pool")
    await ctx.send(embed=embed)

@bot.command()
async def veto(ctx, tim_a: str, tim_b: str):
    mape = CS2_MAPE.copy()
    random.shuffle(mape)

    embed = discord.Embed(title="◈ Mapa Veto", color=0x9b59b6)
    embed.description = f"**{tim_a.upper()}** vs **{tim_b.upper()}**\n─────────────────────\n"
    for i, m in enumerate(mape, 1):
        embed.description += f"`{i}.` **{m}**\n"
    embed.set_footer(text="Timovi izmjenično banuju mape")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  KOMANDE (HELP)
# ═══════════════════════════════════════════════
@bot.command()
async def commands(ctx):
    embed = discord.Embed(
        title="◈ Popis Komandi",
        description="─" * 32,
        color=0x3498db
    )

    embed.add_field(name="👥  Timovi", value=(
        "`!stvori <naziv>` — Stvori tim\n"
        "`!pridruzi <naziv>` — Pridruži se timu\n"
        "`!izlaz` — Napusti tim\n"
        "`!tim <naziv>` — Info o timu\n"
        "`!timovi_lista` — Svi timovi\n"
        "`!izazovi <naziv_tima>` — Izazovi tim na meč\n"
        "`!prihvati` — Prihvati izazov"
    ), inline=False)

    embed.add_field(name="📊  Statistike", value=(
        "`!statistike [@korisnik]` — Prikaz statistika\n"
        "`!ljestvica` — Top 10 igrača po ACR-u\n"
        "`!povijest` — Zadnjih 20 mečeva\n"
        "`!usporedi @igrac1 @igrac2` — Usporedi dva igrača\n"
        "`!rangovi` — Prikaz rang sustava\n"
        "`!server` — Statistike servera"
    ), inline=False)

    embed.add_field(name="🎮  Mapa", value=(
        "`!mapa` — Nasumična CS2 mapa\n"
        "`!veto <timA> <timB>` — Prikaz veto liste mapa"
    ), inline=False)

    embed.add_field(name="🔐  Admin", value=(
        "`!adminkomande` — Prikaz admin komandi"
    ), inline=False)

    embed.set_footer(text="◈ CS2 Esports Bot  •  !adminkomande za admin opcije")
    await ctx.send(embed=embed)

@bot.command()
async def adminkomande(ctx):
    if not je_admin(ctx):
        return await ctx.send(embed=greska_embed("Samo administratori mogu vidjeti ove komande."))

    embed = discord.Embed(
        title="◈ Admin Komande",
        description="─" * 32,
        color=0xe74c3c
    )

    embed.add_field(name="⚔️  Meč", value=(
        "`!start <timA> <timB> <mapa>` — Početak meča\n"
        "`!pobjeda <pobjednik> <gubitnik> <rezultat> <mapa> @mvp` — Unos rezultata"
    ), inline=False)

    embed.add_field(name="⚡  ACR", value=(
        "`!acr @korisnik <k> <d> <a> <adr> <hs> <util> <flash>` — Ručna korekcija ACR-a"
    ), inline=False)

    embed.add_field(name="👥  Igrači", value=(
        "`!dodaj @korisnik <tim>` — Dodaj igrača u tim\n"
        "`!ukloni @korisnik` — Ukloni igrača iz tima\n"
        "`!reset_igraca @korisnik` — Reset statistika igrača"
    ), inline=False)

    embed.add_field(name="🏆  Turnir", value=(
        "`!turnir <naziv_tima>` — Dodijeli turnirsku pobjedu (+150 ACR)"
    ), inline=False)

    embed.add_field(name="⚖️  Disciplina", value=(
        "`!kazna @korisnik <iznos> <razlog>` — Oduzmi ACR kao kaznu\n"
        "`!kazne_povijest [@korisnik]` — Pregled svih kazni"
    ), inline=False)

    embed.add_field(name="🔧  Sustav", value=(
        "`!sync_uloge` — Sinkronizira rang uloge za sve igrače"
    ), inline=False)

    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════
#  POKRETANJE
# ═══════════════════════════════════════════════
token = os.getenv("TOKEN")
if not token:
    print("❌ TOKEN nije pronađen u environment varijablama!")
else:
    bot.run(token)
