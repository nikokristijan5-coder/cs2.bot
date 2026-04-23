import discord
from discord.ext import commands
import os

# INTENTS (bitno za komande)
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------
# BOT READY
# ------------------------
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

# ------------------------
# TEST KOMANDA
# ------------------------
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# ------------------------
# CS2 STYLE TEST KOMANDE
# ------------------------
@bot.command()
async def join(ctx):
    await ctx.send(f"🎮 {ctx.author.name} joined the match queue!")

@bot.command()
async def leave(ctx):
    await ctx.send(f"🚪 {ctx.author.name} left the queue.")

@bot.command()
async def leaderboard(ctx):
    await ctx.send("🏆 CS2 Leaderboard (WIP system)")

# ------------------------
# START BOT (ENV TOKEN)
# ------------------------
token = os.getenv("TOKEN")

if token is None:
    print("❌ TOKEN not found in environment variables!")
else:
    bot.run(token)
