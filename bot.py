import discord
from discord.ext import commands
import os
import random

# ------------------------
# DEBUG ENV CHECK
# ------------------------
print("ENV CHECK:", os.environ.get("TOKEN", "NOT FOUND"))

# ------------------------
# INTENTS (OBAVEZNO)
# ------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------
# MEMORY SYSTEM
# ------------------------
teams = {"A": [], "B": []}
elo = {}
wins = {}
losses = {}

# ------------------------
# BOT READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# IMPORTANT FIX (COMMAND PROCESSING)
# ------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# ------------------------
# PING TEST
# ------------------------
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# ------------------------
# JOIN TEAM
# ------------------------
@bot.command()
async def join(ctx, team):
    team = team.upper()
    user = str(ctx.author.id)

    if team not in teams:
        await ctx.send("❌ Team mora biti A ili B")
        return

    for t in teams:
        if user in teams[t]:
            teams[t].remove(user)

    teams[team].append(user)

    if user not in elo:
        elo[user] = 1000
        wins[user] = 0
        losses[user] = 0

    await ctx.send(f"🎮 {ctx.author.name} joined team {team}")

# ------------------------
# LEAVE TEAM
# ------------------------
@bot.command()
async def leave(ctx):
    user = str(ctx.author.id)

    for t in teams:
        if user in teams[t]:
            teams[t].remove(user)

    await ctx.send(f"🚪 {ctx.author.name} left the match.")

# ------------------------
# TEAMS VIEW
# ------------------------
@bot.command()
async def teams(ctx):
    def fmt(team):
        return [f"<@{u}>" for u in teams[team]]

    await ctx.send(
        f"🎮 TEAM A: {fmt('A')}\n🎮 TEAM B: {fmt('B')}"
    )

# ------------------------
# WIN SYSTEM (ELO UPDATE)
# ------------------------
@bot.command()
async def win(ctx, team):
    team = team.upper()

    if team not in teams:
        await ctx.send("❌ Team mora biti A ili B")
        return

    winner = teams[team]
    loser = teams["B" if team == "A" else "A"]

    for u in winner:
        elo[u] = elo.get(u, 1000) + 25
        wins[u] = wins.get(u, 0) + 1

    for u in loser:
        elo[u] = elo.get(u, 1000) - 25
        losses[u] = losses.get(u, 0) + 1

    await ctx.send(f"🏆 Team {team} WON! ELO updated.")

# ------------------------
# ELO CHECK
# ------------------------
@bot.command()
async def elo(ctx):
    user = str(ctx.author.id)
    await ctx.send(f"📊 Your ELO: {elo.get(user, 1000)}")

# ------------------------
# STATS
# ------------------------
@bot.command()
async def stats(ctx):
    user = str(ctx.author.id)

    await ctx.send(
        f"📊 STATS\n"
        f"ELO: {elo.get(user, 1000)}\n"
        f"Wins: {wins.get(user, 0)}\n"
        f"Losses: {losses.get(user, 0)}"
    )

# ------------------------
# LEADERBOARD
# ------------------------
@bot.command()
async def leaderboard(ctx):
    sorted_elo = sorted(elo.items(), key=lambda x: x[1], reverse=True)

    msg = "🏆 CS2 LEADERBOARD\n\n"

    for i, (user, score) in enumerate(sorted_elo[:10], start=1):
        msg += f"{i}. <@{user}> — {score}\n"

    await ctx.send(msg)

# ------------------------
# FUN COMMANDS
# ------------------------
@bot.command()
async def map(ctx):
    maps = ["Mirage", "Inferno", "Dust2", "Nuke", "Overpass", "Ancient"]
    await ctx.send(f"🗺️ Map: {random.choice(maps)}")

@bot.command()
async def knife(ctx):
    winner = random.choice(["CT", "T"])
    await ctx.send(f"🔪 Knife round winner: {winner}")

# ------------------------
# START BOT
# ------------------------
token = os.getenv("TOKEN")

if token is None:
    print("❌ TOKEN not found in environment variables!")
else:
    bot.run(token)
