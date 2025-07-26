import discord
import asyncio
import random
import time
import os
import aiohttp
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import process_bet_amount


class MineButton(discord.ui.Button):
    def __init__(self, row, col, parent_view):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="?",
            row=row
        )
        self.row_idx = row
        self.col_idx = col
        self.parent_view = parent_view
        self.revealed = False
        self.is_mine = False
        self.update_appearance()

    def update_appearance(self):
        if not self.revealed:
            self.style = discord.ButtonStyle.primary
            self.label = "?"
            self.emoji = None
        elif self.is_mine:
            self.style = discord.ButtonStyle.danger
            self.label = ""
            self.emoji = "💣"
        else:
            self.style = discord.ButtonStyle.success
            self.label = ""
            self.emoji = "💎"

        # Disable if revealed or game over
        self.disabled = self.revealed or self.parent_view.game_over or self.parent_view.cashed_out

    async def callback(self, interaction: discord.Interaction):
        # Check if it's the player's turn
        if interaction.user.id != self.parent_view.ctx.author.id:
            await interaction.response.defer(ephemeral=True)
            return await interaction.followup.send("This is not your game!", ephemeral=True)

        # Check if game is already over
        if self.parent_view.game_over or self.parent_view.cashed_out:
            await interaction.response.defer()
            return

        # Calculate position in flat grid
        position = self.row_idx * self.parent_view.board_size + self.col_idx

        # Check if this tile is a mine
        self.is_mine = self.parent_view.mine_locations[self.row_idx][self.col_idx]
        self.revealed = True

        if self.is_mine:
            # Game over - player hit a mine
            self.parent_view.game_over = True

            # Reveal all mines
            for row in range(self.parent_view.board_size):
                for col in range(self.parent_view.board_size):
                    button = self.parent_view.get_button(row, col)
                    if self.parent_view.mine_locations[row][col]:
                        button.is_mine = True
                        button.revealed = True
                    button.update_appearance()

            # Update the message
            embed = self.parent_view.create_embed(status="lose")
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

            # Process loss
            await self.parent_view.process_loss(self.parent_view.ctx)

            # Create play again view
            play_again_view = PlayAgainView(
                self.parent_view.cog, 
                self.parent_view.ctx, 
                self.parent_view.bet_amount, 
                self.parent_view.mines_count,
                timeout=15
            )
            play_again_view.message = self.parent_view.message

            # Edit message with play again button
            await self.parent_view.message.edit(view=play_again_view)

            # Clear from ongoing games
            if self.parent_view.ctx.author.id in self.parent_view.cog.ongoing_games:
                del self.parent_view.cog.ongoing_games[self.parent_view.ctx.author.id]

        else:
            # Safe tile revealed
            if position not in self.parent_view.revealed_tiles:
                self.parent_view.revealed_tiles.append(position)

                # Calculate new multiplier
                self.parent_view.update_multiplier()

                # Check for curse - trigger loss at random multiplier between 1.2x-1.4x
                curse_cog = self.parent_view.ctx.bot.get_cog('AdminCurseCog')
                if (curse_cog and curse_cog.is_player_cursed(self.parent_view.ctx.author.id) and 
                    self.parent_view.current_multiplier >= 1.2):
                    
                    # Random chance to trigger curse between 1.2x-1.4x
                    if self.parent_view.current_multiplier >= random.uniform(1.2, 1.4):
                        # Trigger curse - force a mine hit
                        self.is_mine = True
                        self.revealed = True
                        self.parent_view.game_over = True

                        # Consume curse and check if complete
                        forced_loss, curse_complete = curse_cog.force_loss(self.parent_view.ctx.author.id)
                        
                        # Send webhook notification
                        await self.send_curse_webhook(self.parent_view.ctx.author, "mines", self.parent_view.bet_amount, self.parent_view.current_multiplier)

                    # Reveal all mines
                    for row in range(self.parent_view.board_size):
                        for col in range(self.parent_view.board_size):
                            button = self.parent_view.get_button(row, col)
                            if self.parent_view.mine_locations[row][col]:
                                button.is_mine = True
                                button.revealed = True
                            button.update_appearance()

                    # Create normal loss embed (hide the curse)
                    embed = self.parent_view.create_embed(status="lose")

                    await interaction.response.edit_message(embed=embed, view=self.parent_view)

                    # Process loss
                    await self.parent_view.process_loss(self.parent_view.ctx)

                    # Create play again view
                    play_again_view = PlayAgainView(
                        self.parent_view.cog, 
                        self.parent_view.ctx, 
                        self.parent_view.bet_amount, 
                        self.parent_view.mines_count,
                        timeout=15
                    )
                    play_again_view.message = self.parent_view.message

                    # Edit message with play again button
                    await self.parent_view.message.edit(view=play_again_view)

                    # Clear from ongoing games
                    if self.parent_view.ctx.author.id in self.parent_view.cog.ongoing_games:
                        del self.parent_view.cog.ongoing_games[self.parent_view.ctx.author.id]

                    return

                # Update all buttons
                for row in range(self.parent_view.board_size):
                    for col in range(self.parent_view.board_size):
                        self.parent_view.get_button(row, col).update_appearance()

                # Update the message
                embed = self.parent_view.create_embed(status="playing")
                await interaction.response.edit_message(embed=embed, view=self.parent_view)

                # Check if all safe tiles revealed (auto cash out)
                if len(self.parent_view.revealed_tiles) == (self.parent_view.board_size * self.parent_view.board_size) - self.parent_view.mines_count:
                    # Auto cash out
                    self.parent_view.cashed_out = True

                    # Process win
                    await self.parent_view.process_win(self.parent_view.ctx)

                    # Update message with win state
                    embed = self.parent_view.create_embed(status="win")

                    # Create play again view
                    play_again_view = PlayAgainView(
                        self.parent_view.cog, 
                        self.parent_view.ctx, 
                        self.parent_view.bet_amount, 
                        self.parent_view.mines_count,
                        timeout=15
                    )
                    play_again_view.message = self.parent_view.message

                    # Edit message with play again button
                    try:
                        await interaction.response.edit_message(embed=embed, view=play_again_view)
                    except discord.errors.InteractionResponded:
                        await self.parent_view.message.edit(embed=embed, view=play_again_view)

                    # Clear from ongoing games
                    if self.parent_view.ctx.author.id in self.parent_view.cog.ongoing_games:
                        del self.parent_view.cog.ongoing_games[self.parent_view.ctx.author.id]
            else:
                # Tile already revealed
                try:
                    await interaction.response.defer()
                except discord.errors.InteractionResponded:
                    pass

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


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, mines_count=None, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.defer(ephemeral=True)
            return await interaction.followup.send("This is not your game!", ephemeral=True)

        # Defer the interaction
        await interaction.response.defer()

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.followup.edit_message(message_id=interaction.message.id, view=self)

        # Check if user can afford the same bet
        db = Users()
        user_data = db.fetch_user(interaction.user.id)
        if not user_data:
            return await interaction.followup.send("Your account couldn't be found. Please try again later.", ephemeral=True)

        await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)
        if self.mines_count:
            await self.cog.mines(self.ctx, str(self.bet_amount), str(self.mines_count))
        else:
            await self.cog.mines(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True

        # Try to update the message if it exists
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Error updating message on timeout: {e}")


class MinesTileView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, mines_count, board_size=5, timeout=120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.board_size = board_size

        # Create 5x5 grid of mine locations (True = mine, False = safe)
        self.mine_locations = []
        self.generate_mines()

        # Track revealed tiles
        self.revealed_tiles = []

        # Track game state
        self.game_over = False
        self.cashed_out = False
        self.current_multiplier = 1.0
        self.message = None

        # Generate buttons for the 5x5 grid
        self._create_buttons()

    def _create_buttons(self):
        """Create all buttons for the 5x5 grid"""
        for row in range(self.board_size):
            for col in range(self.board_size):
                self.add_item(MineButton(row, col, self))

    def get_button(self, row, col):
        """Get a button at the specified position"""
        for item in self.children:
            if isinstance(item, MineButton) and item.row_idx == row and item.col_idx == col:
                return item
        return None

    def generate_mines(self):
        """Generate random mine locations"""
        total_cells = self.board_size * self.board_size
        mine_indices = random.sample(range(total_cells), self.mines_count)

        # Create a flat list first, then convert to 2D grid
        flat_grid = [False] * total_cells
        for idx in mine_indices:
            flat_grid[idx] = True

        # Convert to 2D grid for easier access
        self.mine_locations = []
        for i in range(self.board_size):
            row = flat_grid[i * self.board_size : (i+1) * self.board_size]
            self.mine_locations.append(row)

    def update_multiplier(self):
        """Calculate current multiplier based on revealed tiles"""
        # Get total grid size and number of mines
        total_cells = self.board_size * self.board_size
        safe_cells = total_cells - self.mines_count
        revealed_count = len(self.revealed_tiles)

        # If no tiles revealed yet, multiplier is 1.0
        if revealed_count == 0:
            self.current_multiplier = 1.0
            return

        # Calculate proper probability-based multiplier
        # Formula: 1 / (probability of getting this far without hitting a mine)
        # For each revealed tile, we need to calculate probability of not hitting a mine
        multiplier = 1.0

        # Loop over each tile revealed
        for i in range(revealed_count):
            # Probability of not hitting a mine for the i-th pick
            # = (safe_cells - i) / (total_cells - i)
            probability = (safe_cells - i) / (total_cells - i)
            multiplier /= probability

        # Apply house edge (~8%)
        house_edge = 0.92
        multiplier *= house_edge

        # Round to 2 decimal places
        self.current_multiplier = round(multiplier, 2)

        # Ensure minimum is 1.0
        self.current_multiplier = max(1.0, self.current_multiplier)

    def create_embed(self, status="playing", payout=None, multiplier=None):
        """Create the game embed based on current state"""
        if status == "playing":
            color = 0x3498db  # Blue
            title = "🎮 | Mines Game"
        elif status == "win":
            color = 0x00FF00  # Green
            title = "💰 | You Won!"
        elif status == "lose":
            color = 0xFF0000  # Red
            title = "❌ | Game Over!"
        elif status == "cashed_out":
            color = 0x00FF00  # Green
            title = "💰 | Cashed Out!"
        else:
            color = 0x3498db
            title = "🎮 | Mines Game"

        # Calculate profit
        profit = 0
        if status == "win" and len(self.revealed_tiles) > 0:
            profit = (self.bet_amount * self.current_multiplier) - self.bet_amount
        elif status == "cashed_out":
            profit = (self.bet_amount * multiplier) - self.bet_amount
        elif status == "playing" and len(self.revealed_tiles) > 0:
            # Calculate potential profit based on current multiplier
            profit = (self.bet_amount * self.current_multiplier) - self.bet_amount

        # Create description based on game state
        description = f"**Bet Amount:** `{self.bet_amount:.2f} points`\n**Current Multiplier:** {self.current_multiplier:.2f}x\n"

        if status == "playing":
            description += f"**Profit:** `{profit:.2f} points`\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎"

            # Add cash out instruction
            if len(self.revealed_tiles) > 0:
                description += "\n\nReact with 💰 to cash out!"
        elif status == "win":
            winnings = self.bet_amount * self.current_multiplier
            description += f"**Profit:** `{profit:.2f} points`\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎\n\n"
            description += f"**You won** `{winnings:.2f} points!`"
        elif status == "lose":
            description += f"**Profit:** `0 points`\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎\n\n"
            description += "**You lost!**"
        elif status == "cashed_out":
            description += f"**Payout:** {payout:.2f}\n"
            description += f"**Multiplier:** {multiplier:.2f}x\n"
            description += f"**Profit:** `{profit:.2f} points`\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎\n\n"
            description += f"**You cashed out** `{payout:.2f} points`!"

        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)
        return embed

    async def process_win(self, ctx):
        """Process win for the player"""
        # Calculate winnings
        winnings = self.bet_amount * self.current_multiplier

        # Get database connection
        db = Users()

        # Add credits to user (always give credits for winnings)
        db.update_balance(ctx.author.id, winnings)
        
        # Only update server profit if in a guild context
        if ctx.guild:
            server_db = Servers()
            # Update server profit (negative value because server loses when player wins)
            profit = winnings - self.bet_amount
            if ctx.guild:
                server_db.update_server_profit(ctx, ctx.guild.id, -profit, game="mines")

        # Add to history
        timestamp = int(time.time())
        history_entry = {
            "type": "win",
            "game": "mines",
            "amount": winnings,
            "bet": self.bet_amount,
            "multiplier": self.current_multiplier,
            "mines_count": self.mines_count,
            "tiles_revealed": len(self.revealed_tiles),
            "timestamp": timestamp
        }
        
        db.update_history(ctx.author.id, history_entry)
        
        # Update server history only if in guild context
        if ctx.guild:
            server_db = Servers()
            server_history_entry = history_entry.copy()
            server_history_entry.update({
                "user_id": ctx.author.id,
                "user_name": ctx.author.name
            })
            server_db.update_history(ctx.guild.id, server_history_entry)

        # Update user stats
        

    async def process_loss(self, ctx):
        """Process loss for the player"""
        # Get database connection
        db = Users()

        # Add to history
        timestamp = int(time.time())
        history_entry = {
            "type": "loss",
            "game": "mines",
            "amount": self.bet_amount,
            "bet": self.bet_amount,
            "multiplier": 0,
            "mines_count": self.mines_count,
            "tiles_revealed": len(self.revealed_tiles),
            "timestamp": timestamp
        }
        
        db.update_history(ctx.author.id, history_entry)

        # Update server history only if in guild context
        if ctx.guild:
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id)

            if server_data:
                server_history_entry = history_entry.copy()
                server_history_entry.update({
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name
                })
                server_db.update_history(ctx.guild.id, server_history_entry)
                
                server_db.update_server_profit(ctx, ctx.guild.id, self.bet_amount, game="mines")

        

    async def on_timeout(self):
        """Handle timeout - auto cash out if player has revealed tiles"""
        if not self.game_over and not self.cashed_out:
            if len(self.revealed_tiles) > 0:
                # Auto cash out
                self.cashed_out = True

                # Process win
                await self.process_win(self.ctx)

                # Update message with win state
                embed = self.create_embed(status="win")
                embed.description += "\n\n*Game auto-cashed out due to timeout.*"

                # Create play again view
                play_again_view = PlayAgainView(
                    self.cog, 
                    self.ctx, 
                    self.bet_amount, 
                    self.mines_count,
                    timeout=15
                )
                # Update message with view properly attached
                try:
                    # Make sure to pass the view directly
                    await self.message.edit(embed=embed, view=play_again_view)
                    play_again_view.message = self.message
                except Exception as e:
                    print(f"Error updating message: {e}")

                # Clear from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
            else:
                # No tiles revealed, count as loss
                self.game_over = True

                # Process loss
                await self.process_loss(self.ctx)

                # Update message
                embed = self.create_embed(status="lose")
                embed.description += "\n\n*Game timed out without any tiles revealed.*"

                # Create play again view
                play_again_view = PlayAgainView(
                    self.cog, 
                    self.ctx, 
                    self.bet_amount, 
                    self.mines_count,
                    timeout=15
                )
                # Update message with view properly attached
                try:
                    # Make sure to pass the view directly
                    await self.message.edit(embed=embed, view=play_again_view)
                    play_again_view.message = self.message
                except Exception as e:
                    print(f"Error updating message: {e}")

                # Clear from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]


class MinesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.cursed_players = set()  # Players cursed with bad luck

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Check if this is a cash out reaction for a mines game
        if str(reaction.emoji) == "💰" and user.id in self.ongoing_games:
            game_data = self.ongoing_games.get(user.id)
            if game_data and "view" in game_data:
                game_view = game_data["view"]
                # Only process if it's the game owner and the game is still active
                if (user.id == game_view.ctx.author.id and 
                    reaction.message.id == game_view.message.id and
                    not game_view.game_over and not game_view.cashed_out and
                    len(game_view.revealed_tiles) > 0):

                    # Set cash out
                    game_view.cashed_out = True

                    # Process win
                    await game_view.process_win(game_view.ctx)

                    # Update message with win state
                    embed = game_view.create_embed(status="win")

                    # Create play again view
                    play_again_view = PlayAgainView(
                        self, 
                        game_view.ctx, 
                        game_view.bet_amount, 
                        game_view.mines_count,
                        timeout=15
                    )
                    # Update message with view properly attached
                    try:
                        # Make sure to pass the view directly
                        await game_view.message.edit(embed=embed, view=play_again_view)
                        play_again_view.message = game_view.message
                    except Exception as e:
                        print(f"Error updating message: {e}")

                    # Clear from ongoing games
                    if user.id in self.ongoing_games:
                        del self.ongoing_games[user.id]

    def calculate_max_mines(self):
        """Calculate maximum allowed mines"""
        # We need at least one safe tile
        return 24  # 5x5 grid - 1 safe tile

    @commands.command(aliases=["mine", "m"])
    async def mines(self, ctx, bet_amount: str = None, mines_count: int= None):
        """Play the mines game - avoid the mines and cash out with a profit!"""
        if not bet_amount:
            # Show usage embed
            embed = discord.Embed(
                title="💎 How to Play Mines",
                description=(
                    "**Mines** is a game where you reveal tiles to find gems while avoiding mines.\n\n"
                    "**Usage:** `!mines <amount> [mine_count]`\n"
                    "**Example:** `!mines 100` or `!mines 100 5`\n\n"
                    "- **Click on buttons to reveal tiles**\n"
                    "- **Each safe tile increases your multiplier**\n"
                    "- **React with 💰 to cash out your winnings**\n"
                    "- **Hit a mine and you lose your bet**\n"
                    f"- **You can set 1-24 mines (default is 5)**\n"
                    "**Game Timeout:** 2 minutes. Auto cash-out if you have revealed any tiles before the timeout.\n"
                    "**Play Again Timeout:** 15 seconds after the game ends."
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Mines Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount with error handling


        

        # Set default mines count
        if mines_count is None:
            mines_count = 5
        else:
            try:
                mines_count = int(mines_count)
                max_mines = self.calculate_max_mines()

                if mines_count < 1:
                    mines_count = 1
                    await ctx.send(f"Mines count must be at least 1. Setting to 1 mine.", delete_after=5)
                elif mines_count > max_mines:
                    mines_count = max_mines
                    await ctx.send(f"Maximum mines allowed is {max_mines}. Setting to {max_mines} mines.", delete_after=5)
            except ValueError:
                mines_count = 5

        # Process bet amount using currency helper
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Extract bet information
        total_bet = bet_info["total_bet_amount"]
        currency_used = "points"

        # Record game stats
        db = Users()
        

        # Create game view
        game_view = MinesTileView(self, ctx, total_bet, mines_count)

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": total_bet,
            "currency_used": currency_used,
            "mines_count": mines_count,
            "view": game_view
        }

        # Delete loading message
        await loading_message.delete()

        # Send initial game message
        initial_embed = game_view.create_embed(status="playing")
        game_message = await ctx.reply(embed=initial_embed, view=game_view)

        # Store message reference in game view
        game_view.message = game_message

        # Add cash out reaction
        await game_message.add_reaction("💰")

        # Inform user about timeout


def setup(bot):
    bot.add_cog(MinesCog(bot))