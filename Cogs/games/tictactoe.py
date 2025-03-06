
import discord
import asyncio
import time
import datetime
import random
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import io
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class TicTacToeInviteView(discord.ui.View):
    def __init__(self, cog, ctx, opponent, bet_amount, timeout=45):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.opponent = opponent
        self.bet_amount = bet_amount
        self.accepted = False
        self.currency_used = "tokens"  # Default currency

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This invite is not for you!", ephemeral=True)
        
        # Disable buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        self.accepted = True
        # Start the game
        await interaction.response.send_message(f"Challenge accepted! Starting Tic Tac Toe game...", ephemeral=True)
        await self.cog.start_game(self.ctx, self.opponent, self.bet_amount)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This invite is not for you!", ephemeral=True)
        
        # Disable buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        # Send decline message
        decline_embed = discord.Embed(
            title="❌ | Challenge Declined",
            description=f"{self.opponent.mention} has declined the Tic Tac Toe challenge.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=decline_embed)
        self.stop()

    async def on_timeout(self):
        if not self.accepted:
            # Disable buttons after timeout
            for child in self.children:
                child.disabled = True
                
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Error updating message on timeout: {e}")
                
            timeout_embed = discord.Embed(
                title="⏱️ | Challenge Expired",
                description=f"The Tic Tac Toe challenge has expired.",
                color=discord.Color.gold()
            )
            await self.ctx.channel.send(embed=timeout_embed)


class TicTacToeGame:
    def __init__(self, cog, ctx, player1, player2, bet_amount):
        self.cog = cog
        self.ctx = ctx
        self.player1 = player1  # X player (challenger)
        self.player2 = player2  # O player (opponent)
        self.bet_amount = bet_amount
        self.current_player = player1
        self.board = [None] * 9
        self.game_over = False
        self.winner = None
        self.message = None
        self.view = None
        self.last_move_time = time.time()
        self.timeout = 45  # 45 seconds timeout

    def check_winner(self):
        # Check rows
        for i in range(0, 9, 3):
            if self.board[i] is not None and self.board[i] == self.board[i+1] == self.board[i+2]:
                return self.board[i]
        
        # Check columns
        for i in range(3):
            if self.board[i] is not None and self.board[i] == self.board[i+3] == self.board[i+6]:
                return self.board[i]
        
        # Check diagonals
        if self.board[0] is not None and self.board[0] == self.board[4] == self.board[8]:
            return self.board[0]
        if self.board[2] is not None and self.board[2] == self.board[4] == self.board[6]:
            return self.board[2]
        
        # Check for draw
        if None not in self.board:
            return "draw"
        
        return None

    def create_board_image(self):
        # Create a new image with dark background
        width, height = 450, 450
        background = Image.new('RGBA', (width, height), (43, 45, 49, 255))
        draw = ImageDraw.Draw(background)
        
        # Draw the grid
        cell_size = width // 3
        line_width = 5
        line_color = (70, 70, 70, 255)
        
        # Draw vertical lines
        draw.line([(cell_size, 0), (cell_size, height)], fill=line_color, width=line_width)
        draw.line([(cell_size*2, 0), (cell_size*2, height)], fill=line_color, width=line_width)
        
        # Draw horizontal lines
        draw.line([(0, cell_size), (width, cell_size)], fill=line_color, width=line_width)
        draw.line([(0, cell_size*2), (width, cell_size*2)], fill=line_color, width=line_width)
        
        # Draw X's and O's
        for i in range(9):
            row, col = i // 3, i % 3
            x_center = col * cell_size + cell_size // 2
            y_center = row * cell_size + cell_size // 2
            marker_size = cell_size // 2 - 20
            
            if self.board[i] == "X":
                # Draw X
                draw.line(
                    [(x_center - marker_size, y_center - marker_size), 
                     (x_center + marker_size, y_center + marker_size)], 
                    fill=(255, 255, 255, 255), width=10
                )
                draw.line(
                    [(x_center + marker_size, y_center - marker_size), 
                     (x_center - marker_size, y_center + marker_size)], 
                    fill=(255, 255, 255, 255), width=10
                )
            elif self.board[i] == "O":
                # Draw O
                draw.ellipse(
                    [(x_center - marker_size, y_center - marker_size), 
                     (x_center + marker_size, y_center + marker_size)], 
                    outline=(0, 119, 255, 255), width=10
                )
                # Draw inner circle for the O
                inner_size = marker_size // 2
                draw.ellipse(
                    [(x_center - inner_size, y_center - inner_size), 
                     (x_center + inner_size, y_center + inner_size)], 
                    fill=(43, 45, 49, 255), outline=(0, 119, 255, 255), width=5
                )
        
        # Save to bytes
        img_buf = io.BytesIO()
        background.save(img_buf, format='PNG')
        img_buf.seek(0)
        return discord.File(img_buf, filename="tictactoe.png")

    def create_embed(self):
        title = "🎮 | Tic Tac Toe"
        
        if self.game_over:
            if self.winner == "X":
                description = f"**Winner: {self.player1.mention} (X)**\n{self.player1.mention} wins {self.bet_amount * 1.95:.2f} tokens!"
                color = discord.Color.green()
            elif self.winner == "O":
                description = f"**Winner: {self.player2.mention} (O)**\n{self.player2.mention} wins {self.bet_amount * 1.95:.2f} tokens!"
                color = discord.Color.green()
            else:  # Draw
                description = f"**Game ended in a draw!**\nBoth players get their {self.bet_amount:.2f} tokens back."
                color = discord.Color.gold()
        else:
            description = f"**{self.player1.mention}** (X) vs **{self.player2.mention}** (O)\n\nCurrent turn: **{self.current_player.mention}** ({'X' if self.current_player == self.player1 else 'O'})"
            color = discord.Color.blue()
            
        # Add timeout info
        time_left = max(0, int(self.timeout - (time.time() - self.last_move_time)))
        description += f"\n\nTime remaining: **{time_left}** seconds"
            
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_image(url="attachment://tictactoe.png")
        embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)
        return embed

    async def handle_timeout(self):
        await asyncio.sleep(self.timeout)
        
        if not self.game_over and self.message:
            time_elapsed = time.time() - self.last_move_time
            
            if time_elapsed >= self.timeout:
                self.game_over = True
                
                # Return bets as it's a timeout
                timeout_embed = discord.Embed(
                    title="⏱️ | Game Timeout",
                    description=f"The game has timed out! Both players get their {self.bet_amount:.2f} tokens back.",
                    color=discord.Color.gold()
                )
                timeout_embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)
                
                # Disable all buttons
                if self.view:
                    for child in self.view.children:
                        child.disabled = True
                    await self.message.edit(embed=timeout_embed, view=self.view)
                
                # Process refunds
                db = Users()
                db.update_balance(self.player1.id, self.bet_amount, "tokens", "$inc")
                db.update_balance(self.player2.id, self.bet_amount, "tokens", "$inc")
                
                # Update history
                timestamp = int(datetime.datetime.now().timestamp())
                history_entry = {
                    "type": "draw",
                    "game": "tictactoe",
                    "bet": self.bet_amount,
                    "timestamp": timestamp
                }
                
                # Add to player histories
                db.collection.update_one(
                    {"discord_id": self.player1.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )
                
                db.collection.update_one(
                    {"discord_id": self.player2.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )


class TicTacToeButton(discord.ui.Button):
    def __init__(self, row, col, game):
        super().__init__(style=discord.ButtonStyle.secondary, row=row//3, label=" ")
        self.row = row
        self.col = col
        self.game = game
        self.position = row * 3 + col

    async def callback(self, interaction: discord.Interaction):
        # Check if it's the current player's turn
        if interaction.user != self.game.current_player:
            return await interaction.response.send_message("It's not your turn!", ephemeral=True)
        
        # Check if the position is already taken
        if self.game.board[self.position] is not None:
            return await interaction.response.send_message("That position is already taken!", ephemeral=True)
        
        # Update the board with the current player's marker
        if self.game.current_player == self.game.player1:
            self.game.board[self.position] = "X"
            self.game.current_player = self.game.player2
        else:
            self.game.board[self.position] = "O"
            self.game.current_player = self.game.player1
        
        # Reset timeout timer
        self.game.last_move_time = time.time()
        
        # Disable the button
        self.disabled = True
        
        # Check for winner
        self.game.winner = self.game.check_winner()
        if self.game.winner:
            self.game.game_over = True
            
            # Disable all buttons
            for child in self.view.children:
                child.disabled = True
            
            # Process rewards
            db = Users()
            timestamp = int(datetime.datetime.now().timestamp())
            
            if self.game.winner == "draw":
                # Return bets for draw
                db.update_balance(self.game.player1.id, self.game.bet_amount, "tokens", "$inc")
                db.update_balance(self.game.player2.id, self.game.bet_amount, "tokens", "$inc")
                
                # Update history for both players
                history_entry = {
                    "type": "draw",
                    "game": "tictactoe",
                    "bet": self.game.bet_amount, 
                    "timestamp": timestamp
                }
                
                db.collection.update_one(
                    {"discord_id": self.game.player1.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )
                
                db.collection.update_one(
                    {"discord_id": self.game.player2.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )
            else:
                # Determine winner and loser
                winner_id = self.game.player1.id if self.game.winner == "X" else self.game.player2.id
                loser_id = self.game.player2.id if self.game.winner == "X" else self.game.player1.id
                
                # Calculate winnings (1.95x bet)
                winnings = self.game.bet_amount * 1.95
                
                # Update winner's balance
                db.update_balance(winner_id, winnings, "tokens", "$inc")
                
                # Update history for winner
                win_history = {
                    "type": "win",
                    "game": "tictactoe",
                    "amount": winnings,
                    "bet": self.game.bet_amount,
                    "timestamp": timestamp
                }
                
                # Update history for loser
                loss_history = {
                    "type": "loss",
                    "game": "tictactoe",
                    "amount": self.game.bet_amount,
                    "timestamp": timestamp
                }
                
                db.collection.update_one(
                    {"discord_id": winner_id},
                    {"$push": {"history": {"$each": [win_history], "$slice": -100}}}
                )
                
                db.collection.update_one(
                    {"discord_id": loser_id},
                    {"$push": {"history": {"$each": [loss_history], "$slice": -100}}}
                )
                
                # Update stats
                db.collection.update_one(
                    {"discord_id": winner_id},
                    {"$inc": {"total_won": 1, "total_earned": winnings}}
                )
                
                db.collection.update_one(
                    {"discord_id": loser_id},
                    {"$inc": {"total_lost": 1}}
                )
        
        # Update the board image and embed
        board_file = self.game.create_board_image()
        game_embed = self.game.create_embed()
        
        await interaction.response.edit_message(embed=game_embed, attachments=[board_file], view=self.view)


class TicTacToeView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
        
        # Add buttons for each position
        for i in range(9):
            row, col = i // 3, i % 3
            self.add_item(TicTacToeButton(row, col, game))


class TicTacToeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}
        self.active_invites = {}

    @commands.command(aliases=["ttt", "tictac"])
    async def tictactoe(self, ctx, opponent: discord.Member = None, bet_amount: str = None):
        """Play Tic Tac Toe with another player for tokens!"""
        if not opponent or not bet_amount:
            usage_embed = discord.Embed(
                title="🎮 How to Play Tic Tac Toe",
                description=(
                    "**Tic Tac Toe** is a classic game where you try to get three of your marks in a row!\n\n"
                    "**Usage:** `!tictactoe <opponent> <bet_amount>`\n"
                    "**Example:** `!tictactoe @friend 100`\n\n"
                    "- **Challenge another player and place a bet**\n"
                    "- **Take turns placing X's and O's on the board**\n"
                    "- **First to get 3 in a row wins 1.95x their bet!**\n"
                    "- **If there's a draw, both players get their bets back**\n"
                ),
                color=0x00FFAE
            )
            usage_embed.set_footer(text="BetSync Casino • Aliases: !ttt, !tictac")
            return await ctx.reply(embed=usage_embed)
        
        # Check if opponent is valid
        if opponent.id == ctx.author.id:
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Opponent",
                    description="You cannot play against yourself!",
                    color=discord.Color.red()
                )
            )
        
        if opponent.bot:
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Opponent",
                    description="You cannot play against bots!",
                    color=discord.Color.red()
                )
            )
        
        # Check if either player is already in a game
        if ctx.author.id in self.active_games or ctx.author.id in self.active_invites:
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Game In Progress",
                    description="You already have an active game or invite!",
                    color=discord.Color.red()
                )
            )
        
        if opponent.id in self.active_games or opponent.id in self.active_invites:
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Opponent Busy",
                    description=f"{opponent.mention} is already in another game!",
                    color=discord.Color.red()
                )
            )
        
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Tic Tac Toe Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Process bet amount
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, "tokens", loading_message)
        
        # If processing failed, return the error
        if not success:
            return await loading_message.edit(embed=error_embed)
        
        # Extract needed values from bet_info
        tokens_used = bet_info["tokens_used"]
        total_bet = bet_info["total_bet_amount"]
        
        # Create invite view
        invite_view = TicTacToeInviteView(self, ctx, opponent, total_bet)
        
        # Delete loading message
        await loading_message.delete()
        
        # Mark both players as having active invites
        self.active_invites[ctx.author.id] = True
        self.active_invites[opponent.id] = True
        
        # Send invite message
        invite_embed = discord.Embed(
            title="🎮 | Tic Tac Toe Challenge",
            description=(
                f"{ctx.author.mention} has challenged {opponent.mention} to a game of Tic Tac Toe!\n\n"
                f"**Bet Amount:** {total_bet} tokens\n"
                f"**Potential Winnings:** {total_bet * 1.95:.2f} tokens"
            ),
            color=discord.Color.blue()
        )
        invite_embed.set_footer(text="This invite expires in 45 seconds", icon_url=self.bot.user.avatar.url)
        
        invite_message = await ctx.send(embed=invite_embed, view=invite_view)
        invite_view.message = invite_message
        
        # Wait for the view to finish (either accepted, declined, or timed out)
        await invite_view.wait()
        
        # If not accepted, refund the challenger's tokens
        if not invite_view.accepted:
            db = Users()
            db.update_balance(ctx.author.id, total_bet, "tokens", "$inc")
            
            # Clear active invites
            if ctx.author.id in self.active_invites:
                del self.active_invites[ctx.author.id]
            if opponent.id in self.active_invites:
                del self.active_invites[opponent.id]

    async def start_game(self, ctx, opponent, bet_amount):
        """Start a Tic Tac Toe game after the invite is accepted"""
        # Process opponent's bet
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, str(bet_amount), "tokens", None, user=opponent)
        
        # If processing failed, refund the challenger and return
        if not success:
            # Refund challenger's bet
            db = Users()
            db.update_balance(ctx.author.id, bet_amount, "tokens", "$inc")
            
            # Notify about the error
            error_embed.title = "<:no:1344252518305234987> | Opponent's Bet Failed"
            await ctx.send(embed=error_embed)
            
            # Clear active invites
            if ctx.author.id in self.active_invites:
                del self.active_invites[ctx.author.id]
            if opponent.id in self.active_invites:
                del self.active_invites[opponent.id]
            
            return
        
        # Clear active invites and create active game
        if ctx.author.id in self.active_invites:
            del self.active_invites[ctx.author.id]
        if opponent.id in self.active_invites:
            del self.active_invites[opponent.id]
        
        # Create the game
        game = TicTacToeGame(self, ctx, ctx.author, opponent, bet_amount)
        
        # Create the view
        view = TicTacToeView(game)
        game.view = view
        
        # Generate initial board image
        board_file = game.create_board_image()
        
        # Send initial game state
        game_embed = game.create_embed()
        game.message = await ctx.send(embed=game_embed, file=board_file, view=view)
        
        # Store the active game
        self.active_games[ctx.author.id] = game
        self.active_games[opponent.id] = game
        
        # Start timeout handling
        self.bot.loop.create_task(game.handle_timeout())
        
        # Record game starts for both players
        db = Users()
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": bet_amount}}
        )
        
        db.collection.update_one(
            {"discord_id": opponent.id},
            {"$inc": {"total_played": 1, "total_spent": bet_amount}}
        )
        
        # Also record for server stats if applicable
        server_db = Servers()
        server_db.collection.update_one(
            {"server_id": ctx.guild.id},
            {"$inc": {"games_played": 1, "total_wagered": bet_amount * 2}},
            upsert=True
        )


def setup(bot):
    bot.add_cog(TicTacToeCog(bot))
