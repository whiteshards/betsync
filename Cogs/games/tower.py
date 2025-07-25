import discord
import random
import asyncio
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from colorama import Fore
from Cogs.utils import emojis
import datetime

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, difficulty, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty
        self.currency_type = "points"
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

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green, emoji="🏰")
    async def play_again_button(self, button, interaction):
        # Only the original player can use this button
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the view to prevent double clicks
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with the same parameters
        await self.cog.tower(self.ctx, str(self.bet_amount), self.difficulty)

class TowerGameView(discord.ui.View):
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
        self.current_level = 0
        self.max_levels = 9
        self.game_over = False
        self.cashout_clicked = False
        self.last_diamonds = [] # Added to store diamond positions

        # Set difficulty-specific parameters
        if self.difficulty == "easy":
            self.tiles_per_row = 4
            self.diamonds_per_row = 3
            self.multipliers = [1.27, 1.69, 2.25, 3.00, 4.00, 5.34, 7.12, 9.49, 12.65]
        elif self.difficulty == "medium":
            self.tiles_per_row = 3
            self.diamonds_per_row = 2
            self.multipliers = [1.43, 2.14, 3.21, 4.81, 7.21, 10.82, 16.23, 24.35, 36.52]
        elif self.difficulty == "hard":
            self.tiles_per_row = 2
            self.diamonds_per_row = 1
            self.multipliers = [1.90, 3.80, 7.60, 15.20, 30.40, 60.80, 121.60, 243.20, 486.40]
        elif self.difficulty == "expert":
            self.tiles_per_row = 2
            self.diamonds_per_row = 1
            self.multipliers = [2.85, 8.55, 25.65, 76.95, 230.85, 693.55, 2077.65, 6232.95, 18798.85]
        elif self.difficulty == "master":
            self.tiles_per_row = 4
            self.diamonds_per_row = 1
            self.multipliers = [3.80, 15.20, 60.80, 243.20, 972.80, 3891.20, 15564.80, 62259.20, 249036.80]

        # Current level and multiplier tracking
        self.current_level = 0
        self.current_multiplier = 1.0  # Start with 1.0x multiplier (no bonus until first climb)

        # Generate the tower layout
        self.tower_layout = self.generate_tower_layout()

        # Add the buttons with appropriate labels
        self.update_buttons()

    def generate_tower_layout(self):
        """Generate the tower layout with diamonds placed randomly"""
        tower_layout = []

        # For each level of the tower
        for level in range(self.max_levels):
            # For each level, create a list of tiles (all bombs initially)
            level_tiles = [False] * self.tiles_per_row

            # Randomly place diamonds using shuffle for better randomness
            level_tiles = [False] * self.tiles_per_row
            diamond_indices = random.sample(range(self.tiles_per_row), self.diamonds_per_row)
            for i in diamond_indices:
                level_tiles[i] = True
            random.shuffle(level_tiles) #shuffle the list to make it more random



            tower_layout.append(level_tiles)

        return tower_layout

    def update_buttons(self):
        """Update the buttons based on the current level"""
        # Clear existing buttons
        self.clear_items()

        # If game is over, don't add any buttons
        if self.game_over:
            return

        # Add tile buttons for the current level
        for i in range(self.tiles_per_row):
            button = discord.ui.Button(
                label=f"Tile {i+1}", 
                style=discord.ButtonStyle.primary,
                custom_id=f"tile_{i}"
            )
            button.callback = self.tile_callback
            self.add_item(button)

        # Add cash out button if not on the first level
        if self.current_level > 0:
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

    def create_tower_display(self, selected_tile=None, game_over=False):
        """Create a visual representation of the tower"""
        tower = ""

        # Display the tower levels from top to bottom
        for level in range(self.max_levels - 1, -1, -1):
            level_str = ""

            if game_over:
                # In game over screen, reveal all levels
                for i in range(self.tiles_per_row):
                    level_str += "💎" if self.tower_layout[level][i] else "💣"
            elif level < self.current_level:
                # Level already passed - show diamonds and bombs
                for i in range(self.tiles_per_row):
                    level_str += "💎" if self.tower_layout[level][i] else "💣"
            elif level == self.current_level:
                # Current level - show available tiles
                for i in range(self.tiles_per_row):
                    if i == selected_tile:
                        # Only reveal the selected tile
                        if self.tower_layout[level][i]:
                            level_str += "<a:credit:1339694793277702204>"  # Animated credit for selected diamond
                        else:
                            level_str += "💣"  # Bomb for selected non-diamond
                    else:
                        level_str += "🟦"  # Blue square for unselected tiles
            else:
                # Future level - show locked tiles
                level_str += "⬜" * self.tiles_per_row

            tower += level_str + "\n"

        return tower

    def create_embed(self, status="playing", selected_tile=None):
        """Create game embed with current state"""
        
        bet_description = f"`{self.tokens_used} points`"

        if status == "playing":
            embed = discord.Embed(
                title="🏰 Tower Climb",
                description=f"**Climb the tower by finding diamonds hidden in the tiles!**",
                color=0x00FFAE
            )
            embed.add_field(
                name="🎮 Game Stats",
                value=f"**Difficulty:** {self.difficulty.capitalize()}\n**Level:** {self.current_level+1}/{self.max_levels}\n**Current Multiplier:** {self.current_multiplier:.2f}x",
                inline=True
            )
            embed.add_field(
                name="💰 Bet & Winnings",
                value=f"**Bet:** {bet_description}\n**Potential Win:** `{self.calculate_payout()} points`\n\n",
                inline=True
            )
            embed.add_field(
                name="🏰 Tower",
                value=self.create_tower_display(),
                inline=False
            )
            if self.current_level > 0:
                embed.set_footer(text=f"BetSync Casino • Climb higher for bigger rewards or cash out now!")
            else:
                embed.set_footer(text=f"BetSync Casino • Select a tile to start climbing!")

        elif status == "win_level":
            diamond_emoji = "💎"
            embed = discord.Embed(
                title="🏰 Tower Climb - Diamond Found!",
                description=f"**You selected Tile {selected_tile+1} and found a {diamond_emoji}!**\n\nYou've advanced to level {self.current_level+1}!",
                color=0x00FF00
            )
            embed.add_field(
                name="🎮 Game Stats",
                value=f"**Difficulty:** {self.difficulty.capitalize()}\n**Level:** {self.current_level+1}/{self.max_levels}\n**Current Multiplier:** {self.current_multiplier:.2f}x",
                inline=True
            )
            embed.add_field(
                name="💰 Bet & Winnings",
                value=f"**Bet:** {bet_description}\n**Potential Win:** `{self.calculate_payout()} cpoints`\n\n",
                inline=True
            )
            embed.add_field(
                name="🏰 Tower",
                value=self.create_tower_display(),
                inline=False
            )
            if self.current_level == self.max_levels:
                embed.set_footer(text=f"BetSync Casino • You've reached the top of the tower!")
            else:
                embed.set_footer(text=f"BetSync Casino • Continue climbing or cash out with your winnings!")

        elif status == "lose":
            embed = discord.Embed(
                title="🏰 Tower Climb - Game Over!",
                description=f"**You selected Tile {selected_tile+1} but there was no diamond!**\n\nYou've fallen from the tower!",
                color=0xFF0000
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Initial Bet:** {bet_description}\n**Levels Climbed:** {self.current_level}\n**Lost Amount:** {self.bet_amount}",
                inline=False
            )
            embed.add_field(
                name="🏰 Tower",
                value=self.create_tower_display(selected_tile, game_over=True),
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • Better luck next time!")

        elif status == "cash_out":
            payout = self.calculate_payout()
            profit = payout - self.bet_amount
            embed = discord.Embed(
                title="💰 Tower Climb - Cashed Out!",
                description=f"**Congratulations!** You've successfully climbed **{self.current_level}/{self.max_levels}** levels and decided to cash out!",
                color=0x00FF00
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Initial Bet:** `{self.bet_amount} points`\n**Final Multiplier:** {self.current_multiplier:.2f}x\n**Winnings:** `{payout} points`\n**Profit:** `{profit} points`",
                inline=False
            )
            embed.add_field(
                name="🏰 Tower",
                value=self.create_tower_display(game_over=True),
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • You've secured your winnings!")

        embed.set_author(name=f"Player: {self.ctx.author.name}", icon_url=self.ctx.author.avatar.url)
        return embed

    async def tile_callback(self, interaction):
        """Handle clicks on tile buttons"""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Defer the response to prevent interaction timeout
        await interaction.response.defer()

        # Extract the tile index from the button's custom_id
        tile_index = int(interaction.data["custom_id"].split('_')[1])

        # Check if the tile has a diamond
        if self.tower_layout[self.current_level][tile_index]:
            # Player found a diamond - track it
            if not hasattr(self, 'last_diamonds'):
                self.last_diamonds = []

            self.last_diamonds.append(tile_index)

            # Move to next level
            self.current_level += 1

            # Update the current multiplier based on the level
            if self.current_level < len(self.multipliers):
                self.current_multiplier = self.multipliers[self.current_level - 1]  # Use previous level's multiplier

            # If player reached the top of the tower, they win
            if self.current_level == self.max_levels:
                self.game_over = True
                await self.process_cashout(interaction) #Changed to process_cashout

            # Update buttons for the next level
            self.update_buttons()

            # Send updated embed
            await interaction.followup.edit_message(
                message_id=self.message.id,
                embed=self.create_embed(status="win_level", selected_tile=tile_index), #Changed status to win_level
                view=self
            )
        else:
            # Player hit a bomb - game over
            self.game_over = True
            self.clear_items()  # Remove all buttons

            # Send the game over message
            await interaction.followup.edit_message(
                message_id=self.message.id,
                embed=self.create_embed(status="lose", selected_tile=tile_index),
                view=self
            )

            await self.process_loss() #call process loss function

    async def cash_out_callback(self, interaction: discord.Interaction):
        """Process player's decision to cash out"""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.game_over = True
        self.cashout_clicked = True

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        # Acknowledge the interaction first
        await interaction.response.defer()

        # Process the cashout (using message.edit instead of interaction.followup)
        success = await self.process_cashout(interaction)

        if not success:
            # Only use followup for error messages
            await interaction.followup.send("There was an error processing your cashout. Please contact support.", ephemeral=True)


    async def on_timeout(self):
        """Handle timeout"""
        if not self.game_over and self.current_level > 0:
            await self.process_cashout(self.ctx) #Changed to pass context

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

        if not self.game_over:
            self.game_over = True
            if hasattr(self.ctx.author, 'id') and self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]


    async def process_cashout(self, interaction):
        """Process cashout - update database and end game"""
        payout = self.calculate_payout()
        bet_currency = self.currency_type

        db = Users()
        try:
            # Update user's balance
            db.update_balance(self.ctx.author.id, payout, "credits", "$inc")

            # Create win history entry
            win_entry = {
                "type": "win",
                "game": "tower",
                "bet": self.bet_amount,
                "amount": payout,
                "multiplier": self.current_multiplier,
                "level": self.current_level,
                "timestamp": int(time.time())
            }

            # Update user history and stats directly in one operation
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
            #if isinstance(self.ctx.channel, discord.TextChannel):
            server_db = Servers()
            server_profit = self.bet_amount - payout

                # Update server profit directly
            server_db.update_server_profit(self.ctx, self.ctx.guild.id, server_profit, game="tower")

                # Add to server history
            server_bet_entry = win_entry.copy()
            server_bet_entry.update({
                    "user_id": self.ctx.author.id,
                    "user_name": self.ctx.author.name
                })

                # Update server history directly
            server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
                )
        except Exception as e:
            print(f"Error processing cashout: {e}")
            return False

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty,
            #self.currency_type
        )

        # Fix for the cashout button - replace with direct message edit since we have the message
        cashout_embed = self.create_embed(status="cash_out")
        await self.message.edit(embed=cashout_embed, view=play_again_view)
        play_again_view.message = self.message

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True

    async def process_loss(self):
        """Process loss - update database and end game"""
        # Create loss entry
        loss_entry = {
            "game": "tower",
            "type": "loss",
            "bet": self.bet_amount,
            "amount": self.bet_amount,
            "level": self.current_level + 1,
            "difficulty": self.difficulty,
            "timestamp": int(time.time())
        }

        # Update user history
        db = Users()
        db.update_history(self.ctx.author.id, loss_entry)

        # Update user stats
        db.collection.update_one(
            {"discord_id": self.ctx.author.id},
            {"$inc": {
                "total_lost": 1,
            }}
        )

        # Update server stats if in a guild
        try:
            server_db = Servers()
            # Update server profit using the correct method
            server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="tower")

            # Add to server history
            server_bet_entry = loss_entry.copy()
            server_bet_entry.update({
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name
            })
            server_db.update_history(self.ctx.guild.id, server_bet_entry)
        except Exception as e:
            print(f"Error updating server profit: {e}")

        # Create play again view for loss scenario
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty, 
            #self.currency_type,
            timeout=15
        )

        # Update the message with play again button
        await self.message.edit(view=play_again_view)
        play_again_view.message = self.message

        # Remove from ongoing games
        if hasattr(self.ctx.author, 'id') and self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        server_bet_entry = loss_entry.copy()
        server_bet_entry.update({
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name
            })


class TowerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["twr", "climb", "towers"])
    async def tower(self, ctx, bet_amount: str = None, difficulty: str = None):
        """Play Tower - climb the tower by finding diamonds to multiply your winnings!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🏰 How to Play Tower",
                description=(
                    "**Tower** is a game where you climb a tower by finding diamonds hidden under tiles!\n\n"
                    "**Usage:** `!tower <amount> <difficulty>`\n"
                    "**Example:** `!tower 100 easy`\n\n"
                    "**Difficulty Levels:**\n"
                    "- **Easy:** 4 tiles per row, 3 diamonds per row\n"
                    "- **Medium:** 3 tiles per row, 2 diamonds per row\n"
                    "- **Hard:** 2 tiles per row, 1 diamond per row\n"
                    "- **Expert:** 2 tiles per row, 1 diamond per row\n"
                    "- **Master:** 4 tiles per row, 1 diamond per row\n\n"
                    "Each time you find a diamond, you advance to the next level with a higher multiplier. You can cash out anytime or continue for higher rewards! If you select a tile without a diamond, you lose your bet."
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !twr, !climb")
            return await ctx.reply(embed=embed)

        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        if difficulty is None or difficulty.lower() not in ['easy', 'medium', 'hard', 'expert', 'master']:
            #await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Please choose from: easy, medium, hard, expert, master",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        # Send loading message
        #loading_emoji = emojis.emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Tower Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount using currency_helper
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        # If processing failed, return the error
        if not success:
            return await ctx.reply(embed=error_embed)

        # Extract needed values from bet_info
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]
        bet_amount_value = total_bet

        # Validate difficulty


        # Record game stats
        db = Users()
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": total_bet}}
        )

        # Deduct bet amount from user's balance
        #db.update_balance(ctx.author.id, -tokens_used, "tokens", "$inc")
        #db.update_balance(ctx.author.id, -credits_used, "credits", "$inc")

        # Create game view
        game_view = TowerGameView(
            self, 
            ctx, 
            total_bet, 
            difficulty, 
            tokens_used=tokens_used,
        #dits_used=credits_used,
            timeout=120  # 2 minute timeout
        )

        try:
            # First create the game message
            game_message = await ctx.reply(embed=game_view.create_embed(status="playing"), view=game_view)
            game_view.message = game_message

            # Only delete loading message after successful game creation
            try:
                await loading_message.delete()
            except:
                pass  # Ignore deletion errors

            self.ongoing_games[ctx.author.id] = {
                "game_type": "tower",
                "game_view": game_view,
                "start_time": time.time()
            }

        except Exception as e:
            print(f"Error creating tower game message: {e}")
            
            # Refund the bet if game creation fails
            db = Users()
            db.update_balance(ctx.author.id, tokens_used, "points", "$inc")
            
            # Delete loading message and show error
            try:
                await loading_message.delete()
            except:
                pass
            
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Game Creation Failed",
                description="There was an error creating your tower game. Your bet has been refunded.",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)

    async def update_server_history(self, server_id, game, bet_amount, profit, user_id, user_name):
        try:
            server_db = Servers()
            server_history = {
                "game": game,
                "bet_amount": bet_amount,
                "profit": profit,
                "user_id": user_id,
                "user_name": user_name,
                "timestamp": time.time()
            }
            server_db.update_history(server_id, server_history)
        except Exception as e:
            print(f"Error updating server history: {e}")


def setup(bot):

    def advance_level(self):
        """Advance to the next level and update the multiplier"""
        # Increment level
        self.current_level += 1
        # Update multiplier if we haven't reached the end
        if self.current_level < len(self.multipliers):
            self.current_multiplier = self.multipliers[self.current_level]
        # If we're at the final level and found a diamond, the game is won
        if self.current_level >= len(self.multipliers):
            return True
        return False

    bot.add_cog(TowerCog(bot))