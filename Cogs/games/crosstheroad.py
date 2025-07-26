# Implementing the curse lose mechanic to CrossTheRoadGame class.
import discord
import random
import asyncio
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from colorama import Fore
from Cogs.utils.emojis import emoji
import os
import aiohttp

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, difficulty, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty
        #self.currency_type = currency_type
        self.message = None

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True
        # Update the message with disabled buttons
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green, emoji="🐓")
    async def play_again_button(self, button, interaction):
        # Only the original player can use this button
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the view to prevent double clicks
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)
        await interaction.response.defer()
        # Start a new game with the same parameters
        await self.cog.crosstheroad(self.ctx, str(self.bet_amount), self.difficulty)

class CrossTheRoadGame(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, difficulty, tokens_used=0, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty.lower()
        self.tokens_used = tokens_used
        #self.credits_used = credits_used
        self.currency_type = "points"  # Always pay out in credits
        self.message = None
        self.current_lane = 0
        self.lanes_crossed = 0
        self.max_lanes = 25
        self.cashout_clicked = False
        self.game_over = False

        # Set difficulty-specific parameters
        if self.difficulty == "easy":
            self.hit_chance = 0.16  # 9% chance to hit a car
            self.multiplier_increment = 1.10
        elif self.difficulty == "medium":
            self.hit_chance = 0.25  # 17% chance to hit a car
            self.multiplier_increment = 1.30
        elif self.difficulty == "hard":
            self.hit_chance = 0.37  # 25% chance to hit a car
            self.multiplier_increment = 1.50
        elif self.difficulty == "extreme":
            self.hit_chance = 0.47  # 45% chance to hit a car
            self.multiplier_increment = 1.70

        # Current multiplier (starts at 1.00x)
        self.current_multiplier = 1.00

    def calculate_payout(self):
        """Calculate the payout based on current multiplier"""
        return round(self.bet_amount * self.current_multiplier, 2)

    def generate_game_progress(self):
        """Generate a visual representation of game progress with sliding window view"""
        # Create alternating black and white road emojis for all lanes
        road_emojis = []
        for i in range(self.max_lanes):
            # Use "⬛" for black road and "⬜" for white road
            road_emoji = "⬛" if i % 2 == 0 else "⬜"
            road_emojis.append(road_emoji)

        # Set up sliding window (show 5 lanes at a time)
        visible_lanes = 5

        # Calculate the window start position - always try to keep the current lane in the middle
        window_start = max(0, self.lanes_crossed - 2)

        # Make sure we don't go past the end
        if window_start + visible_lanes > self.max_lanes:
            window_start = max(0, self.max_lanes - visible_lanes)

        # Get the visible section of lanes
        visible_section = road_emojis[window_start:window_start + visible_lanes]

        # Calculate position of chicken/crash within visible section
        chicken_pos = self.lanes_crossed - window_start

        # Build the progress display
        if self.game_over and chicken_pos >= 0 and chicken_pos < len(visible_section):
            # If game over due to collision within visible area
            lanes_before = "".join(visible_section[:chicken_pos])
            lanes_after = "".join(visible_section[chicken_pos+1:])
            progress = "🏁" + lanes_before + "💥" + lanes_after
        elif not self.game_over and chicken_pos >= 0 and chicken_pos < len(visible_section):
            # Normal progress within visible area
            lanes_before = "".join(visible_section[:chicken_pos])
            lanes_after = "".join(visible_section[chicken_pos:])
            progress = "🏁" + lanes_before + "🐓" + "".join(visible_section[chicken_pos+1:])
        else:
            # Default case (shouldn't happen often)
            progress = "🏁" + "".join(visible_section) + ("🐓" if not self.game_over else "")

        # Add indicators for lanes before/after visible section
        progress_info = f"Lane: {self.lanes_crossed+1}/{self.max_lanes}"
        if window_start > 0:
            progress = "◀️ " + progress
        if window_start + visible_lanes < self.max_lanes:
            progress = progress + " ▶️"

        return progress

    def create_embed(self, status="playing"):
        """Create game embed with current state"""
        # Format bet description
        #if self.tokens_used > 0 and self.credits_used > 0:
         #   bet_description = f"**{self.tokens_used} tokens** + **{self.credits_used} credits**"
        #elif self.tokens_used > 0:
            #bet_description = f"**{self.tokens_used} tokens**"
        #else:
        bet_description = f"`{self.tokens_used} points`"

        if status == "playing":
            embed = discord.Embed(
                title="🐓 Cross the Road",
                description=f"**Help the chicken cross the road without getting hit!**",
                color=0x00FFAE
            )
            embed.add_field(
                name="🎮 Game Stats",
                value=f"**Difficulty:** {self.difficulty.capitalize()}\n**Lane:** {self.lanes_crossed+1}/{self.max_lanes}\n**Current Multiplier:** {self.current_multiplier:.2f}x",
                inline=True
            )
            embed.add_field(
                name="💰 Bet & Winnings",
                value=f"**Bet:** {bet_description}\n**Potential Win:** `{self.calculate_payout()} points`\n\n",
                inline=True
            )
            embed.add_field(
                name="🛣️ Road Progress",
                value=self.generate_game_progress(),
                inline=False
            )
            #embed.add_field(
                #name="ℹ️ Instructions",
                #value="• Click **Cross Lane** to move forward and increase your multiplier\n• Click **Cash Out** to collect your winnings\n• Be careful! There's a chance of hitting a car with each lane crossed",
                #inline=False
            #)

        elif status == "win":
            payout = self.calculate_payout()
            embed = discord.Embed(
                title="<:yes:1355501647538815106> Chicken Safely Crossed!",
                description=f"**Congratulations!** Your chicken has safely crossed **{self.lanes_crossed}/{self.max_lanes}** lanes!",
                color=0x00FF00
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Initial Bet:** {bet_description}\n**Final Multiplier:** {self.current_multiplier:.2f}x\n**Payout:** `{payout} points`",
                inline=False
            )
            embed.add_field(
                name="🛣️ Final Progress",
                value=self.generate_game_progress(),
                inline=False
            )

        elif status == "lost":
            embed = discord.Embed(
                title="<:no:1344252518305234987> Chicken Got Hit!",
                description=f"**Oh no!** Your chicken got hit by a car after crossing **{self.lanes_crossed}/{self.max_lanes}** lanes.",
                color=0xFF0000
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Initial Bet:** {bet_description}\n**Lost Amount:** `{self.bet_amount}`",
                inline=False
            )
            embed.add_field(
                name="🛣️ Final Progress",
                value=self.generate_game_progress(),
                inline=False
            )

        embed.set_footer(text=f"BetSync Casino • Player: {self.ctx.author.name}")
        return embed

    async def on_timeout(self):
        """Handle timeout - consider as cashout if possible"""
        if not self.game_over and self.lanes_crossed > 0:
            # Auto cashout on timeout if at least one lane was crossed
            await self.process_cashout()

        # Disable buttons
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

    async def process_cashout(self):
        """Process cashout - update database and end game"""
        if self.lanes_crossed == 0:
            # Can't cashout without crossing at least one lane
            return False

        payout = self.calculate_payout()

        # Mark game as complete
        self.game_over = True
        self.cashout_clicked = True

        # Update database with winnings (always in credits)
        db = Users()
        db.update_balance(self.ctx.author.id, payout, "credits", "$inc")

        # Create history entry for user


        # Also update server stats if available
        try:
            server_db = Servers()
            server_profit = self.bet_amount - payout
            server_db.update_server_profit(self.ctx, self.ctx.guild.id, server_profit, game="crosstheroad")

            # Add bet to server history with all required fiel
        except Exception as e:
            print(f"Error updating server history: {e}")

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty, 
            #self.currency_type,
            timeout=15
        )

        # Update the message with win embed and play again button
        await self.message.edit(embed=self.create_embed(status="win"), view=play_again_view)
        play_again_view.message = self.message

        # Remove from ongoing games
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True

    async def send_curse_webhook(self, user, game, bet_amount, multiplier):
        """Send curse trigger notification to webhook"""
        webhook_url = os.environ.get("LOSE_WEBHOOK")
        if not webhook_url:
            return

        try:
            embed = {
                "title": "🎯 Curse Triggered",
                "description": f"A cursed player has been forced to lose",
                "color": 0x8B0000,
                "fields": [
                    {"name": "User", "value": f"{user.name} ({user.id})", "inline": False},
                    {"name": "Game", "value": game.capitalize(), "inline": True},
                    {"name": "Bet Amount", "value": f"{bet_amount:.2f} points", "inline": True},
                    {"name": "Multiplier at Loss", "value": f"{multiplier:.2f}x", "inline": True}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            }

            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            print(f"Error sending curse webhook: {e}")


    async def process_loss(self):
        """Process loss - update database and end game"""
        # Mark game as complete
        self.game_over = True


        # Also update server stats if available
        try:
            server_db = Servers()
            server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="crosstheroad")

            # Add bet to server history with all required fields
        except Exception as e:
            print(f"Error updating server history: {e}")

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty, 
            #self.currency_type,
            timeout=15
        )

        # Update the message with loss embed and play again button
        await self.message.edit(embed=self.create_embed(status="lost"), view=play_again_view)
        play_again_view.message = self.message

        # Remove from ongoing games
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True

    @discord.ui.button(label="Cross Lane", style=discord.ButtonStyle.primary, emoji="🚶‍♂️")
    async def cross_lane_button(self, button, interaction):
        # Only game owner can interact
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Check if game is already over
        if self.game_over:
            return await interaction.response.send_message("This game has already ended.", ephemeral=True)

        # Roll for car collision
        await interaction.response.defer()
        if random.random() < self.hit_chance:
            # Player got hit
            #await interaction.response.defer()
            await self.process_loss()
            return

        # Successfully crossed lane
        self.lanes_crossed += 1

        # Update multiplier
        self.current_multiplier *= self.multiplier_increment

        # Check if reached maximum lanes
        if self.lanes_crossed >= self.max_lanes:
            # Automatically cash out at max lanes
            #await interaction.response.defer()
            await self.process_cashout()
            return

        # Update the message with new state
        await interaction.message.edit(embed=self.create_embed(status="playing"))

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        # Only game owner can interact
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Check if game is already over
        if self.game_over:
            return await interaction.response.send_message("This game has already ended.", ephemeral=True)

        # Check if at least one lane was crossed
        if self.lanes_crossed == 0:
            return await interaction.response.send_message("You need to cross at least one lane before cashing out!", ephemeral=True)

        # Process cashout
        await interaction.response.defer()
        await self.process_cashout()

class CrossTheRoadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["ctr", "chicken", "road"])
    async def crosstheroad(self, ctx, bet_amount: str = None, difficulty: str = None):
        """Play Cross the Road - help your chicken cross the road without getting hit!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🐓 How to Play Cross the Road",
                description=(
                    "**Cross the Road** is a game where you help a chicken cross a busy road!\n\n"
                    "**Usage:** `!crosstheroad <amount> <difficulty>`\n"
                    "**Example:** `!crosstheroad 100 easy` or `!crosstheroad 50 hard`\n"
                    #"**Difficulties:**\n"
                    #"- **Easy:** 9% hit chance, 1.10x multiplier per lane\n"
                    #"- **Medium:** 17% hit chance, 1.30x multiplier per lane\n"
                    #"- **Hard:** 25% hit chance, 1.50x multiplier per lane\n"
                    #"- **Extreme:** 45% hit chance, 1.70x multiplier per lane\n\n"
                    "Each time you cross a lane, your multiplier increases. You can cash out anytime or continue for higher rewards! If you hit a car, you lose your bet."
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !ctr, !chicken, !road")
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        if not difficulty or difficulty.lower() not in ["easy", "medium", "hard", "expert"]:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Valid difficulties are: easy, medium, hard, expert",
                color=0xFF0000
            )
            return await ctx.reply(embed=error_embed)

        # Send loading message
       # loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Cross The Road Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Validate difficulty first before processing any bet


        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        # If processing failed, return the error
        if not success:
            return await loading_message.edit(embed=error_embed)

        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]

        # Create the game
        game_view = CrossTheRoadGame(
            self, 
            ctx, 
            total_bet, 
            difficulty, 
            tokens_used=tokens_used,
            #credits_used=credits_used,
            timeout=120  # 2 minute timeout
        )

        # Delete loading message
        await loading_message.delete()

        # Send game message
        game_message = await ctx.reply(embed=game_view.create_embed(status="playing"), view=game_view)
        game_view.message = game_message

        # Add to ongoing games
        self.ongoing_games[ctx.author.id] = {
            "game_type": "crosstheroad",
            "game_view": game_view,
            "start_time": time.time()
        }

def setup(bot):
    bot.add_cog(CrossTheRoadCog(bot))