import discord
import random
import asyncio
import time
import os
import aiohttp
#from PIL import Image, ImageDraw #Removed as no longer needed
from discord.ext import commands
from Cogs.utils.currency_helper import process_bet_amount
from Cogs.utils.mongo import Users, Servers
from colorama import Fore
from Cogs.utils.emojis import emoji

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

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green, emoji="🎈")
    async def play_again_button(self, button, interaction):
        # Only the original player can use this button
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the view to prevent double clicks
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with the same parameters
        await self.cog.pump(self.ctx, str(self.bet_amount), self.difficulty)

class PumpGameView(discord.ui.View):
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
        self.current_pumps = 0
        self.max_pumps = 12
        self.game_over = False
        self.cashout_clicked = False

        # Set difficulty-specific parameters
        if self.difficulty == "easy":
            self.probability = 0.75
            self.multipliers = [1.00, 1.27, 1.69, 2.25, 3.00, 4.00, 5.34, 7.13, 9.49, 12.65, 16.87, 22.49, 29.98]
        elif self.difficulty == "medium":
            self.probability = 0.50
            self.multipliers = [1.00, 1.90, 3.80, 7.60, 15.20, 30.40, 60.80, 121.60, 243.20, 486.40, 972.80, 1945.60, 3891.20]
        elif self.difficulty == "hard":
            self.probability = 0.30
            self.multipliers = [1.00, 3.17, 10.56, 35.19, 117.28, 390.95, 1303.15, 4344.32, 14480.00, 48288.50, 161019.30, 536257.00, 1788234.00]
        elif self.difficulty == "extreme":
            self.probability = 0.15
            self.multipliers = [1.00, 6.33, 42.22, 281.48, 1876.54, 12511.60, 83333.34, 556206.00, 3707317.00, 24675324.70, 164502000.00, 1099530000.00, 7330200000.00]

        # Current multiplier (starts at 1x)
        self.current_multiplier = self.multipliers[0]

        # Add the buttons
        self.update_buttons()

    def update_buttons(self):
        """Update the buttons based on game state"""
        # Clear existing buttons
        self.clear_items()

        # If game is over, don't add any buttons
        if self.game_over:
            return

        # Add pump button
        pump_button = discord.ui.Button(
            label="Pump", 
            style=discord.ButtonStyle.danger, 
            emoji="🎈",
            custom_id="pump"
        )
        pump_button.callback = self.pump_callback
        self.add_item(pump_button)

        # Add cash out button if not on the first pump
        if self.current_pumps > 0:
            cash_out_button = discord.ui.Button(
                label="Cash Out", 
                style=discord.ButtonStyle.success, 
                emoji="💰",
                custom_id="cash_out"
            )
            cash_out_button.callback = self.cash_out_callback
            self.add_item(cash_out_button)

    def calculate_payout(self):
        """Calculate the payout based on current multiplier"""
        return round(self.bet_amount * self.current_multiplier, 2)

    def get_balloon_display(self):
        """Generate a text-based balloon representation based on current pumps"""
        # Create a visual representation of balloon size with ASCII
        if self.current_pumps == 0:
            return "🎈 Balloon is ready to be pumped!"

        # Add visual representation of pressure
        filled = "█" * self.current_pumps
        empty = "▒" * (self.max_pumps - self.current_pumps)

        # Choose color emoji based on pump count
        if self.current_pumps < 4:
            color = "🟢"
        elif self.current_pumps < 8:
            color = "🟡"
        else:
            color = "🔴"

        pressure_bar = f"{color} |{filled}{empty}| {self.current_pumps}/{self.max_pumps}"

        return pressure_bar


    def create_embed(self, status="playing", display_message=""):
        """Create game embed with current state"""

        bet_description = f"`{self.tokens_used} points`"

        # Get balloon visual representation
        balloon_display = self.get_balloon_display()

        #currency = "credits"

        if status == "playing":
            embed = discord.Embed(
                title=":information_source: | Pump Game",
                description=f"**Keep pumping the balloon for bigger rewards, but don't let it pop!**",
                color=0xFF3366
            )
            embed.add_field(
                name="📊 Pressure",
                value=balloon_display,
                inline=False
            )
            embed.add_field(
                name="💰 Bet & Potential Win",
                value=f"**Bet:** {bet_description}\n**Multiplier:** {self.current_multiplier:.2f}x\n**Potential Win:** `{self.calculate_payout():.2f} points`",
                inline=False
            )
            if self.current_pumps > 0:
                embed.set_footer(text=f"BetSync Casino • Keep pumping for bigger rewards or cash out now!")
            else:
                embed.set_footer(text=f"BetSync Casino • Pump to start!")

        elif status == "win_pump":
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Successful Pump!",
                description=f"**The balloon got bigger!**",
                color=0x00FF00
            )
            embed.add_field(
                name="📊 Pressure",
                value=balloon_display,
                inline=False
            )
            embed.add_field(
                name="💰 Bet & Potential Win",
                value=f"**Bet:** {bet_description}\n**Multiplier:** {self.current_multiplier:.2f}x\n**Potential Win:** `{self.calculate_payout():.2f} points`",
                inline=False
            )
            if self.current_pumps == self.max_pumps:
                embed.set_footer(text=f"BetSync Casino • Max pumps reached! Automatic cashout!")
            else:
                embed.set_footer(text=f"BetSync Casino • Continue pumping or cash out now!")

        elif status == "lose":
            embed = discord.Embed(
                title="<:no:1344252518305234987> | POPPED!",
                description=f"**Oh no! The balloon popped after {self.current_pumps} pumps!**\n\nBetter luck next time!",
                color=0xFF0000
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Bet:** {bet_description}\n**Lost Amount:** `{self.bet_amount:.2f} points`",
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • The balloon popped!")

        elif status == "cash_out":
            payout = self.calculate_payout()
            profit = payout - self.bet_amount
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Cashed Out!",
                description=f"**Wise decision!** You've cashed out after **{self.current_pumps}/{self.max_pumps}** pumps!",
                color=0x00FF00
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Bet:** `{self.bet_amount:.2f} points`\n**Multiplier:** {self.current_multiplier:.2f}x\n**Winnings:** {payout:.2f} credits\n**Profit:** {profit:.2f} credits",
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • You've secured your winnings!")

        elif status == "max_pumps":
            payout = self.calculate_payout()
            profit = payout - self.bet_amount
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Maximum Pumps!",
                description=f"**Amazing!** You've reached the maximum of **{self.max_pumps}** pumps! The balloon is at its limit!",
                color=0x00FF00
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Bet:** `{self.bet_amount:.2f} points`\n**Multiplier:** {self.current_multiplier:.2f}x\n**Winnings:** `{payout:.2f} points`\n**Profit:** `{profit:.2f} points`",
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • Maximum pumps achieved! Automatic cashout!")

        embed.set_author(name=f"Player: {self.ctx.author.name}", icon_url=self.ctx.author.avatar.url)
        return embed

    async def pump_callback(self, interaction):
        """Handle clicks on pump button"""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Check if the pump is successful based on difficulty probability
        # Check for curse - force pop at 1.6x-1.8x multiplier range
        curse_cog = self.ctx.bot.get_cog('AdminCurseCog')
        if (curse_cog and curse_cog.is_player_cursed(self.ctx.author.id) and 
            1.6 <= self.current_multiplier <= 1.8):

            # Force balloon to pop
            balloon_popped = True

            # Consume curse and send webhook notification
            curse_cog.consume_curse(self.ctx.author.id)
            await self.send_curse_webhook(self.ctx.author, "pump", self.bet_amount, self.current_multiplier)
        else:
            # Calculate pop chance based on difficulty and pumps
            self.difficulty_rates = {
                "easy": 0.25,
                "medium": 0.50,
                "hard": 0.70,
                "extreme": 0.85
            }
            # Calculate pop chance based on difficulty and pumps
            base_failure_rate = self.difficulty_rates[self.difficulty]
            # Increase failure rate with each pump (exponential growth)
            failure_rate = base_failure_rate * (1.1 ** self.current_pumps)

            # Cap at 95% to always give some chance
            failure_rate = min(failure_rate, 0.95)

            # Check if balloon pops
            balloon_popped = random.random() < failure_rate

        if balloon_popped:
            # Pump failed - balloon pops
            self.game_over = True
            self.clear_items()  # Remove all buttons

            # Send the game over message
            embed = self.create_embed(status="lose")
            # No image for popped balloon

            await interaction.response.edit_message(attachments=[], embed=embed, view=None)

            # Process the loss
            await self.process_loss()
        else:
            # Pump successful
            self.current_pumps += 1

            # Update the current multiplier
            self.current_multiplier = self.multipliers[self.current_pumps]

            # If max pumps reached, auto cash out
            if self.current_pumps >= self.max_pumps:
                self.game_over = True
                await interaction.response.defer()
                return await self.process_cashout(interaction)

            # Update buttons for next pump
            self.update_buttons()

            # Update the message with the new pumps count
            embed = self.create_embed(status="win_pump")

            await interaction.response.edit_message(embed=embed, view=self)

    async def cash_out_callback(self, interaction):
        """Process player's decision to cash out"""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.game_over = True
        self.cashout_clicked = True

        # Disable all buttons
        self.clear_items()

        # Acknowledge the interaction first
        await interaction.response.defer()

        # Process the cashout
        await self.process_cashout(interaction)

    async def on_timeout(self):
        """Handle timeout"""
        if not self.game_over and self.current_pumps > 0:
            # Auto cash out if game times out and player has pumped at least once
            await self.process_cashout(None)
        elif not self.game_over:
            # Just disable buttons if no pumps yet
            self.clear_items()
            try:
                await self.message.edit(view=self)
            except:
                pass

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

    async def process_cashout(self, interaction):
        """Process cashout - update database and end game"""
        payout = self.calculate_payout()

        db = Users()
        try:
            # Update user's balance
            db.update_balance(self.ctx.author.id, payout, "credits", "$inc")

            # Create win history entry
            win_entry = {
                "type": "win",
                "game": "pump",
                "bet": self.bet_amount,
                "amount": payout,
                "multiplier": self.current_multiplier,
                "pumps": self.current_pumps,
                "difficulty": self.difficulty,
                "timestamp": int(time.time())
            }

            # Update user history and stats
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {
                    "$push": {"history": {"$each": [win_entry], "$slice": -100}},
                    "$inc": {
                        "total_played": 1,
                        "total_won": 1,
                        "total_earned": payout
                    }
                }
            )

            # Update server stats if in a guild
            if isinstance(self.ctx.channel, discord.TextChannel):
                server_db = Servers()
                server_profit = self.bet_amount - payout

                # Update server profit
                server_db.update_server_profit(self.ctx, self.ctx.guild.id, server_profit, game="pump")

                # Add to server history
                server_bet_entry = win_entry.copy()
                server_bet_entry.update({
                    "user_id": self.ctx.author.id,
                    "user_name": self.ctx.author.name
                })

                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
                )
        except Exception as e:
            print(f"Error processing cashout: {e}")
            return False

        # Create cashout embed with appropriate status
        status = "max_pumps" if self.current_pumps >= self.max_pumps else "cash_out"
        cashout_embed = self.create_embed(status=status)

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty,
            #"tokens" if self.tokens_used > 0 else "credits"  # Use tokens if they were used originally
        )

        # Update the message
        await self.message.edit(attachments=[], embed=cashout_embed, view=play_again_view) #removed attachments
        play_again_view.message = self.message

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True

    async def process_loss(self):
        """Process loss - update database and end game"""
        db = Users()

        # Create loss history entry
        loss_entry = {
            "type": "loss",
            "game": "pump",
            "bet": self.bet_amount,
            "amount": self.bet_amount,
            "multiplier": 0,
            "pumps": self.current_pumps,
            "difficulty": self.difficulty,
            "timestamp": int(time.time())
        }

        # Update user history and stats directly in one operation
        db.collection.update_one(
            {"discord_id": self.ctx.author.id},
            {
                "$push": {"history": {"$each": [loss_entry], "$slice": -100}},
                "$inc": {
                    "total_played": 1,
                    "total_lost": 1,
                    "total_spent": self.bet_amount
                }
            }
        )

        # Update server stats if in a guild
        if isinstance(self.ctx.channel, discord.TextChannel):
            server_db = Servers()

            # Update server profit directly
            server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="pump")

            # Add to server history
            server_bet_entry = loss_entry.copy()
            server_bet_entry.update({
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name
            })

            # Update server history directly
            server_db.collection.update_one(
                {"server_id": self.ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
            )

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty,
            #"tokens" if self.tokens_used > 0 else "credits"  # Use tokens if they were used originally
        )

        # Add play again button
        await self.message.edit(view=play_again_view)
        play_again_view.message = self.message

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


class PumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["balloon"])
    async def pump(self, ctx, bet_amount: str = None, difficulty: str = None):
        """Play Pump - pump a balloon for increasingly higher multipliers!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":information_source: | How to Play Pump",
                description=(
                    "**Pump** is a game where you inflate a balloon for increasingly higher multipliers!\n\n"
                    "**Usage:** `!pump <amount> <difficulty>`\n"
                    "**Example:** `!pump 100 easy`\n\n"
                    "**Difficulty Levels:**\n"
                    "- **Easy:** 75% success rate per pump\n"
                    "- **Medium:** 50% success rate per pump\n"
                    "- **Hard:** 30% success rate per pump\n"
                    "- **Extreme:** 15% success rate per pump\n\n"
                    "Each successful pump increases your multiplier. You can cash out at any time, but if the balloon pops, you lose your bet!"
                ),
                color=0xFF3366
            )
            embed.set_footer(text="BetSync Casino • Aliases: !balloon")
            return await ctx.reply(embed=embed)

        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate and set default difficulty
        if not difficulty:
            difficulty = "easy"
        else:
            difficulty = difficulty.lower()
            if difficulty not in ["easy", "medium", "hard", "extreme"]:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Difficulty",
                    description="Please choose from: **easy**, **medium**, **hard**, or **extreme**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Preparing Pump Game",
            description="Please wait while we set up your game.",
            color=0xFF3366
        )
        loading_message = await ctx.reply(embed=loading_embed)

        db = Users()
        from Cogs.utils.currency_helper import process_bet_amount as pt
        success, bet_info, error_embed = await pt(ctx, bet_amount, loading_message)
        if not success: 
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)
        tokens_used = bet_info["tokens_used"]
        total_bet = bet_info["total_bet_amount"]

        game_view = PumpGameView(
            self, 
            ctx, 
            total_bet, 
            difficulty, 
            tokens_used=tokens_used,
            #credits_used=credits_used,
            timeout=60  # 1 minute timeout
        )

        await loading_message.delete()

        # Create initial embed
        initial_embed = game_view.create_embed(status="playing")

        game_message = await ctx.reply(embed=initial_embed, view=game_view)
        game_view.message = game_message

        self.ongoing_games[ctx.author.id] = {
            "game_type": "pump",
            "game_view": game_view,
            "start_time": time.time()
        }


def setup(bot):
    bot.add_cog(PumpCog(bot))