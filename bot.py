import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import json
import os
import random
from itertools import combinations
import time

from dotenv import load_dotenv
load_dotenv()

processed_matches = {}  # Use a dictionary to store match timestamps

    
intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

PLAYER_FILE = "players.json"

def load_players():
    if os.path.exists(PLAYER_FILE):
        try:
            with open(PLAYER_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data  
        except (json.JSONDecodeError, ValueError):
            pass  
    return {}  

def save_players():
    with open(PLAYER_FILE, "w") as f:
        json.dump(players, f, indent=4)

players = load_players()

@bot.event
async def on_ready():
    print(f"✅ Bot is online! Logged in as {bot.user}")

@bot.command(name="Admin")
async def show_admin_menu(ctx):
    await ctx.send("📌 **Admin Menu - Select an action below:**", view=AdminMenuView())

# ✅ Admin Menu View
class AdminMenuView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegisterButton())
        self.add_item(AllPlayersButton())
        self.add_item(RemovePlayerButton())

class RegisterButton(Button):
    def __init__(self):
        super().__init__(label="Register Player", style=discord.ButtonStyle.success)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RegisterModal())

class AllPlayersButton(Button):
    def __init__(self):
        super().__init__(label="Show All Players", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await send_all_players(interaction)

class RemovePlayerButton(Button):
    def __init__(self):
        super().__init__(label="Remove Player", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🗑️ Select a player to remove:", view=RemovePlayerView())

class RemovePlayerView(View):
    def __init__(self):
        super().__init__(timeout=60)
        for player in players.keys():
            self.add_item(RemovePlayerButtonOption(player))

class RemovePlayerButtonOption(Button):
    def __init__(self, player_name):
        super().__init__(label=player_name, style=discord.ButtonStyle.danger)
        self.player_name = player_name
    async def callback(self, interaction: discord.Interaction):
        del players[self.player_name]
        save_players()
        await interaction.response.send_message(f"🗑️ Player {self.player_name} has been removed.")

class RegisterModal(Modal, title="Player Registration"):
    name = TextInput(label="Player Name", placeholder="Enter player name")
    base_rating = TextInput(label="Base Rating", placeholder="Enter base rating", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        try:
            base_rating = int(self.base_rating.value.strip())
        except ValueError:
            await interaction.response.send_message("⚠️ Invalid rating! Please enter a number.", ephemeral=True)
            return
        if name in players:
            await interaction.response.send_message(f"⚠️ Player {name} is already registered!", ephemeral=True)
            return
        players[name] = {"base_rating": base_rating, "current_rating": base_rating}
        save_players()
        await interaction.response.send_message(f"✅ Player {name} registered with base rating {base_rating}!")

async def send_all_players(interaction):
    if not players:
        await interaction.response.send_message("⚠️ No players registered yet!")
        return
    embed = discord.Embed(title="📋 **Registered Players**", color=discord.Color.blue())
    for name, data in players.items():
        base_rating = data.get("base_rating", "N/A")
        current_rating = data.get("current_rating", "N/A")
        embed.add_field(name=name, value=f"🏅 Base Rating: {base_rating}\n🔥 Current Rating: {current_rating}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.command(name="chala")
async def pick_team(ctx):
    if not players:
        await ctx.send("⚠️ No players registered yet!")
        return
    await ctx.send("👥 **Select up to 8 players for the match:**", view=MultiColumnPlayerSelectionView())

class MultiColumnPlayerSelectionView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.selected_players = []  
        player_list = [(name, players[name]["current_rating"]) for name in players.keys()]
        player_list.sort(key=lambda x: x[1], reverse=True)  

        columns = [player_list[i:i+4] for i in range(0, len(player_list), 4)]  
        for column in columns:
            for name, rating in column:
                self.add_item(PlayerButton(name, rating, self))
        
        self.confirm_button = ConfirmMatchupsButton(self)
        self.clear_button = ClearSelectionButton(self)
        self.add_item(self.confirm_button)
        self.add_item(self.clear_button)
        self.confirm_button.disabled = True

class PlayerButton(Button):
    def __init__(self, name, rating, parent_view):
        super().__init__(label=f"{name} ({rating})", style=discord.ButtonStyle.primary)
        self.name = name
        self.rating = rating
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if self.name in self.parent_view.selected_players:
            self.parent_view.selected_players.remove(self.name)
            self.style = discord.ButtonStyle.primary
        else:
            self.parent_view.selected_players.append(self.name)
            self.style = discord.ButtonStyle.success  

        self.parent_view.confirm_button.disabled = len(self.parent_view.selected_players) < 4
        await interaction.response.edit_message(view=self.parent_view)

class ConfirmMatchupsButton(Button):
    def __init__(self, parent_view):
        super().__init__(label="Confirm Selection", style=discord.ButtonStyle.success)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if len(self.parent_view.selected_players) < 4:
            await interaction.response.send_message("⚠️ Select at least 4 players to form teams.", ephemeral=True)
            return

        matchups = generate_matchups(self.parent_view.selected_players)
        await interaction.response.send_message(
            embed=create_matchup_embed(matchups),
            view=MatchupSelectionView(matchups)
        )

class ClearSelectionButton(Button):
    def __init__(self, parent_view):
        super().__init__(label="Clear Selection", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_players.clear()
        self.parent_view.confirm_button.disabled = True
        await interaction.response.edit_message(view=self.parent_view)

class MatchupSelectionView(View):
    def __init__(self, matchups):
        super().__init__()
        self.matchups = matchups  

        for i, (team1, team2, rating1, rating2, diff) in enumerate(matchups, start=1):
            label = f"Select Matchup {i}"
            self.add_item(MatchupButton(label, team1, team2))

class MatchupButton(Button):
    def __init__(self, label, team1, team2):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.team1 = team1
        self.team2 = team2

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"✅ **You selected Matchup:**\n"
            f"**Team 1:** {', '.join(self.team1)}\n"
            f"**Team 2:** {', '.join(self.team2)}\n\n"
            f"🔽 **Now select the winner!**",
            view=WinnerSelectionView(self.team1, self.team2)
        )

class WinnerSelectionView(View):
    def __init__(self, team1, team2):
        super().__init__()
        self.team1 = team1
        self.team2 = team2

        self.add_item(WinnerButton("Team 1 Wins", team1, team2))
        self.add_item(WinnerButton("Team 2 Wins", team2, team1))

# Track processed matches to prevent duplicate ELO updates

import time  # Ensure time is imported

# Define a cooldown period (in seconds) before allowing the same matchup again
MATCH_COOLDOWN = 20  # 20 seconds 
class WinnerButton(Button):
    def __init__(self, label, winning_team, losing_team):
        super().__init__(label=label, style=discord.ButtonStyle.success)
        self.winning_team = winning_team
        self.losing_team = losing_team

    async def callback(self, interaction: discord.Interaction):  
        # Generate a unique match identifier
        matchup_key = tuple(sorted(self.winning_team + self.losing_team))
        current_time = time.time()

        # Check if this matchup was processed recently
        if matchup_key in processed_matches:
            last_time = processed_matches[matchup_key]
            if current_time - last_time < MATCH_COOLDOWN:
                await interaction.response.send_message(
                    "⚠️ ELO ratings have already been updated for this matchup recently! Try again later.", 
                    ephemeral=True
                )
                return

        # Update the match time to allow new results
        processed_matches[matchup_key] = current_time  # ✅ Now it updates and allows future matches

        # Get total team ratings
        winning_team_rating = sum(players[p]["current_rating"] for p in self.winning_team)
        losing_team_rating = sum(players[p]["current_rating"] for p in self.losing_team)
        rating_diff = abs(winning_team_rating - losing_team_rating)

        # Default gains/losses
        base_gain = 6
        base_loss = -6

        if rating_diff >= 100:  # Large difference case
            if winning_team_rating < losing_team_rating:  # Underdog wins
                gain, loss = 8, -8
            else:  # Favorite wins
                gain, loss = 4, -4
        else:
            gain, loss = base_gain, base_loss

        # Update ratings and generate message
        message = "🏆 **Match Result**\n\n"

        for player in self.winning_team:
            players[player]["current_rating"] += gain
            message += f"✅ **{player}**: +{gain} (New: {players[player]['current_rating']})\n"

        for player in self.losing_team:
            players[player]["current_rating"] += loss
            message += f"❌ **{player}**: {loss} (New: {players[player]['current_rating']})\n"

        # Save updated ratings
        save_players()

        # Send the result message
        await interaction.response.send_message(message)



def update_elo_ratings(winning_team, losing_team, k_factor=10):  
    rating_changes = {}

    for player in winning_team:
        old_rating = players[player]["current_rating"]
        change = k_factor  
        players[player]["current_rating"] += change
        rating_changes[player] = (players[player]["current_rating"], change)  # Store (new_rating, change)

    for player in losing_team:
        old_rating = players[player]["current_rating"]
        change = -k_factor  
        players[player]["current_rating"] += change
        rating_changes[player] = (players[player]["current_rating"], change)  # Store (new_rating, change)

    return rating_changes




def create_balanced_teams(players):
    num_players = len(players)
    players_data = {p: players[p]["current_rating"] for p in players}  
    all_possible_matchups = []

    for combo in combinations(players, num_players // 2):
        team1 = list(combo)
        team2 = [p for p in players if p not in team1]
        
        rating1 = sum(players_data[p] for p in team1)
        rating2 = sum(players_data[p] for p in team2)
        diff = abs(rating1 - rating2)
        
        all_possible_matchups.append((team1, team2, rating1, rating2, diff))

    # Sort by rating difference (smallest first)
    all_possible_matchups.sort(key=lambda x: x[4])

    best_matchup = all_possible_matchups[0]  # Least difference
    second_best_matchup = None

    # Find a second-best distinct matchup (ensuring it's not just swapped)
    for matchup in all_possible_matchups[1:]:
        if set(matchup[0]) != set(best_matchup[1]):  # Ensure it's a different team split
            second_best_matchup = matchup
            break

    if second_best_matchup is None:  # Fallback if no distinct second matchup is found
        second_best_matchup = all_possible_matchups[1] if len(all_possible_matchups) > 1 else best_matchup

    return [best_matchup, second_best_matchup]


def generate_matchups(selected_players):
    selected_players_data = {player: players[player] for player in selected_players}
    
    if len(selected_players) < 4 or len(selected_players) % 2 != 0:
        return [([], [], 0, 0)]  

    matchups = create_balanced_teams(selected_players_data)
    return matchups

def create_matchup_embed(matchups):
    embed = discord.Embed(title="🔀 Matchup Options", description="Choose a balanced team matchup!", color=discord.Color.blue())

    for i, (team1, team2, rating1, rating2, diff) in enumerate(matchups, start=1):
        embed.add_field(
            name=f"Matchup {i}",
           value=f"```"
                  f"Team 1: {', '.join(team1)} (Rating: {rating1})\n"
                  f"Team 2: {', '.join(team2)} (Rating: {rating2})\n"
                  f"Difference: {diff}"
                  f"```",
            inline=False
        )
    return embed

@bot.command(name="show")
async def show_players_menu(ctx):
    await ctx.send("📋 **Player List - Click below to view all players**", view=AllPlayersView())

class AllPlayersView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AllPlayersButton())  # Reusing the button from Admin Menu


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)