import discord
from discord.ext import commands
import os
import random

# ------------------------
# ENV CHECK
# ------------------------
print("ENV CHECK:", os.environ.get("TOKEN", "NOT FOUND"))

# ------------------------
# INTENTS
# ------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------
# DATABASE (IN MEMORY)
# ------------------------
teams = {"A": [], "B": []}
player_elo = {}
player_wins = {}
player_losses = {}

# ------------------------
# READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# COMMAND PROCESS FIX
# ------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# ------------------------
# PING
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

    # remove from other team
    for t in teams:
        if user in teams[t]:
            teams[t].remove(user)

    teams[team].append(user)

    # init player
    if user not in player_elo:
        player_elo[user] = 1000
        player_wins[user] = 0
        player_losses[user] = 0

    await ctx.send(f"🎮 {ctx.author.name} joined team {team}")

# ------------------------
# LEAVE
# ------------------------
@bot.command()
async def leave(ctx):
    user = str(ctx.author.id)

    for t in teams:
        if user in teams[t]:
            teams[t].remove(user)

    await ctx.send(f"🚪 {ctx.author.name} left the match.")

# ------------------------
# TEAMS
# ------------------------
@bot.command()
async def teams(ctx):

    def format_team(team):
        return [f"<@{u}>" for u in teams[team]]

    await ctx.send(
        f"🎮 TEAM A: {format_team('A')}\n"
        f"🎮 TEAM B: {format_team('B')}"
    )

# ------------------------
# WIN SYSTEM (ELO FIXED)
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
        player_elo[u] = player_elo.get(u, 1000) + 25
        player_wins[u] = player_wins.get(u, 0) + 1

    for u in loser:
        player_elo[u] = player_elo.get(u, 1000) - 25
        player_losses[u] = player_losses.get(u, 0) + 1

    await ctx.send(f"🏆 Team {team} WON! ELO updated.")

# ------------------------
# ELO
# ------------------------
@bot.command()
async def elo(ctx):
    user = str(ctx.author.id)
    await ctx.send(f"📊 Your ELO: {player_elo.get(user, 1000)}")

# ------------------------
# STATS
# ------------------------
@bot.command()
async def stats(ctx):
    user = str(ctx.author.id)

    await ctx.send(
        f"📊 STATS\n"
        f"ELO: {player_elo.get(user, 1000)}\n"
        f"Wins: {player_wins.get(user, 0)}\n"
        f"Losses: {player_losses.get(user, 0)}"
    )

# ------------------------
# LEADERBOARD
# ------------------------
@bot.command()
async def leaderboard(ctx):
    sorted_players = sorted(player_elo.items(), key=lambda x: x[1], reverse=True)

    msg = "🏆 CS2 LEADERBOARD\n\n"

    for i, (user, score) in enumerate(sorted_players[:10], start=1):
        msg += f"{i}. <@{user}> — {score}\n"

    await ctx.send(msg)

# ------------------------
# FUN
# ------------------------
@bot.command()
async def map(ctx):
    maps = ["Mirage", "Inferno", "Dust2", "Nuke", "Overpass", "Ancient"]
    await ctx.send(f"🗺️ Map: {random.choice(maps)}")

@bot.command()
async def knife(ctx):
    await ctx.send(f"🔪 Winner: {random.choice(['CT', 'T'])}")

# ------------------------
# START BOT
# ------------------------
token = os.getenv("TOKEN")

if not token:
    print("❌ TOKEN not found!")
else:
    bot.run(token)
