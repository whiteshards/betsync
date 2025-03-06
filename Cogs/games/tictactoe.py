
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import numpy as np
from Database.users import Users
from Database.servers import Servers

class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}
        self.pending_invites = {}
        self.timeout = 45  # timeout in seconds

    @commands.hybrid_command(name="tictactoe", aliases=["ttt"], description="Play Tic Tac Toe against another player with bets")
    @app_commands.describe(
        opponent="The opponent you want to challenge",
        bet_amount="The amount you want to bet",
        currency_type="The currency type (tokens/t or credits/c)"
    )
    async def tictactoe(self, ctx, opponent: discord.Member, bet_amount, currency_type=None):
        """
        Play Tic Tac Toe against another player with bets.
        
        Parameters:
        -----------
        opponent: discord.Member
            The opponent you want to challenge
        bet_amount: str or float
            The amount you want to bet
        currency_type: str, optional
            The currency type (tokens/t or credits/c)
        """
        # Check if user is challenging themselves
        if opponent.id == ctx.author.id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Opponent",
                description="You cannot play against yourself.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Check if opponent is a bot
        if opponent.bot:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Opponent",
                description="You cannot play against a bot.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Check if user already has an active game
        if ctx.author.id in self.active_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game in Progress",
                description="You already have a Tic Tac Toe game in progress.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Check if opponent already has an active game
        if opponent.id in self.active_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Opponent Busy",
                description=f"{opponent.mention} already has a Tic Tac Toe game in progress.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Check if user already has a pending invite
        if ctx.author.id in self.pending_invites:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invite Pending",
                description="You already have a pending Tic Tac Toe invitation.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Format currency type if provided    
        if currency_type:
            currency_type = currency_type.lower()
            # Allow shorthand T for tokens and C for credits
            if currency_type == 't':
                currency_type = 'tokens'
            elif currency_type == 'c':
                currency_type = 'credits'
                
        # Send loading message
        loading_embed = discord.Embed(
            title="🎮 Setting up Tic Tac Toe...",
            description="Processing your bet...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount
        
        # Process the bet amount using the currency helper but don't deduct yet
        # Just validate the bet to make sure they can afford it
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if not user_data:
            await loading_message.delete()
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description="You need an account to place bets. Use a command to create one.",
                color=0xFF0000
            )
            return await ctx.reply(embed=error_embed)
            
        # Validate bet without deducting
        try:
            # Use process_bet_amount but check the bet without applying it
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)
            
            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)
                
            # Store bet info for later but don't deduct yet
            tokens_used = bet_info["tokens_used"]
            credits_used = bet_info["credits_used"]
            total_bet = bet_info["total_bet_amount"]
            
            # Cancel the previous deduction since we want to deduct only after acceptance
            if tokens_used > 0:
                db.update_balance(ctx.author.id, tokens_used, "tokens", "$inc")
            
            if credits_used > 0:
                db.update_balance(ctx.author.id, credits_used, "credits", "$inc")
                
        except Exception as e:
            print(f"Error validating bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {e}")
        
        # Create the invitation
        invitation = {
            "challenger": ctx.author,
            "opponent": opponent,
            "bet_amount": total_bet,
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "currency_type": currency_type,
            "channel": ctx.channel,
            "time": datetime.datetime.now()
        }
        
        self.pending_invites[ctx.author.id] = invitation
        
        # Create accept/decline view
        view = TicTacToeInvite(self, invitation)
        
        # Create and send invitation embed
        invite_embed = discord.Embed(
            title="🎮 Tic Tac Toe Challenge",
            description=f"{ctx.author.mention} has challenged {opponent.mention} to a game of Tic Tac Toe!",
            color=0x00FFAE
        )
        invite_embed.add_field(name="Bet Amount", value=f"**{total_bet:.2f}**", inline=True)
        
        currency_text = ""
        if tokens_used > 0 and credits_used > 0:
            currency_text = f"({tokens_used:.2f} tokens + {credits_used:.2f} credits)"
        elif tokens_used > 0:
            currency_text = "(tokens)"
        elif credits_used > 0:
            currency_text = "(credits)"
            
        if currency_text:
            invite_embed.add_field(name="Currency", value=currency_text, inline=True)
            
        invite_embed.add_field(name="Timeout", value=f"{self.timeout} seconds", inline=True)
        invite_embed.set_footer(text="Click the buttons below to accept or decline")
        
        await loading_message.delete()
        invitation_message = await ctx.reply(content=f"{opponent.mention}", embed=invite_embed, view=view)
        
        # Set timeout for invitation
        view.message = invitation_message
        self.bot.loop.create_task(self.handle_invitation_timeout(ctx.author.id, invitation_message))
        
    async def handle_invitation_timeout(self, challenger_id, message):
        """Handle invitation timeout"""
        await asyncio.sleep(self.timeout)
        if challenger_id in self.pending_invites:
            invitation = self.pending_invites.pop(challenger_id)
            
            timeout_embed = discord.Embed(
                title="⏱️ Invitation Expired",
                description=f"The Tic Tac Toe invitation from {invitation['challenger'].mention} to {invitation['opponent'].mention} has expired.",
                color=0xFF0000
            )
            
            try:
                await message.edit(embed=timeout_embed, view=None)
            except:
                pass
                
    async def handle_game_timeout(self, game_id, message):
        """Handle game timeout"""
        await asyncio.sleep(self.timeout)
        if game_id in self.active_games:
            game = self.active_games.pop(game_id)
            
            # Return bets to both players
            db = Users()
            
            # Return challenger's bet
            if game["challenger_tokens"] > 0:
                db.update_balance(game["challenger"].id, game["challenger_tokens"], "tokens", "$inc")
            if game["challenger_credits"] > 0:
                db.update_balance(game["challenger"].id, game["challenger_credits"], "credits", "$inc")
                
            # Return opponent's bet
            if game["opponent_tokens"] > 0:
                db.update_balance(game["opponent"].id, game["opponent_tokens"], "tokens", "$inc")
            if game["opponent_credits"] > 0:
                db.update_balance(game["opponent"].id, game["opponent_credits"], "credits", "$inc")
            
            timeout_embed = discord.Embed(
                title="⏱️ Game Timed Out",
                description=f"The Tic Tac Toe game between {game['challenger'].mention} and {game['opponent'].mention} has timed out. Bets have been returned.",
                color=0xFF0000
            )
            
            try:
                await message.edit(embed=timeout_embed, view=None)
            except:
                pass
                
    async def create_board_image(self, board):
        """Create a Tic Tac Toe board image"""
        # Create a blank image
        size = 600
        cell_size = size // 3
        padding = cell_size // 6
        
        # Create a new image with a dark background
        image = Image.new('RGBA', (size, size), (33, 34, 38, 255))
        draw = ImageDraw.Draw(image)
        
        # Draw the grid
        for i in range(1, 3):
            # Horizontal lines
            draw.line([(0, i * cell_size), (size, i * cell_size)], fill=(50, 51, 56, 255), width=5)
            # Vertical lines
            draw.line([(i * cell_size, 0), (i * cell_size, size)], fill=(50, 51, 56, 255), width=5)
        
        # Draw X's and O's
        for i in range(3):
            for j in range(3):
                x = j * cell_size + padding
                y = i * cell_size + padding
                cell_inner_size = cell_size - 2 * padding
                
                if board[i][j] == 'X':
                    # Draw X (white)
                    draw.line([(x, y), (x + cell_inner_size, y + cell_inner_size)], fill=(255, 255, 255, 255), width=15)
                    draw.line([(x + cell_inner_size, y), (x, y + cell_inner_size)], fill=(255, 255, 255, 255), width=15)
                elif board[i][j] == 'O':
                    # Draw O (blue)
                    draw.ellipse([(x, y), (x + cell_inner_size, y + cell_inner_size)], outline=(0, 128, 255, 255), width=15)
                    # Black hole in the middle
                    center_x = x + cell_inner_size // 2
                    center_y = y + cell_inner_size // 2
                    center_size = cell_inner_size // 4
                    draw.ellipse([(center_x - center_size, center_y - center_size), 
                                 (center_x + center_size, center_y + center_size)], 
                                 fill=(33, 34, 38, 255))
        
        # Convert the image to bytes
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
        
    @commands.hybrid_command(name="tictactoe_usage", aliases=["tttusage"], description="Shows how to use the Tic Tac Toe command")
    async def tictactoe_usage(self, ctx):
        """Shows how to use the Tic Tac Toe command"""
        embed = discord.Embed(
            title="Tic Tac Toe Usage",
            description="Challenge another player to a game of Tic Tac Toe with bets.",
            color=0x00FFAE
        )
        
        embed.add_field(
            name="Command Syntax",
            value="```/tictactoe <opponent> <bet_amount> [currency_type]```",
            inline=False
        )
        
        embed.add_field(
            name="Parameters",
            value=(
                "**opponent**: The user you want to challenge\n"
                "**bet_amount**: The amount to bet (can be a number, or 'all'/'max')\n"
                "**currency_type**: (Optional) 'tokens'/'t' or 'credits'/'c'"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Example",
            value="```/tictactoe @User 100 tokens```",
            inline=False
        )
        
        embed.add_field(
            name="Game Rules",
            value=(
                "• Players take turns placing X and O on a 3x3 grid\n"
                "• The first player to get 3 in a row (horizontally, vertically, or diagonally) wins\n"
                "• If the board fills up with no winner, the game is a draw\n"
                "• Winner gets 1.95x their bet amount\n"
                "• In case of a draw, bets are returned\n"
                "• Game and invitation timeout after 45 seconds"
            ),
            inline=False
        )
        
        await ctx.reply(embed=embed)

class TicTacToeInvite(discord.ui.View):
    def __init__(self, cog, invitation):
        super().__init__(timeout=None)
        self.cog = cog
        self.invitation = invitation
        self.message = None
        
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user who clicked is the opponent
        if interaction.user.id != self.invitation["opponent"].id:
            return await interaction.response.send_message("This invitation is not for you.", ephemeral=True)
            
        # Check if the invitation still exists
        challenger_id = self.invitation["challenger"].id
        if challenger_id not in self.cog.pending_invites:
            return await interaction.response.send_message("This invitation has expired.", ephemeral=True)
            
        # Process opponent's bet
        from Cogs.utils.currency_helper import process_bet_amount
        
        # Set up loading message for opponent bet processing
        loading_embed = discord.Embed(
            title="🎮 Setting up Tic Tac Toe...",
            description="Processing opponent's bet...",
            color=0x00FFAE
        )
        
        await interaction.response.edit_message(embed=loading_embed, view=None)
        
        # Process opponent's bet
        bet_amount = self.invitation["bet_amount"]
        currency_type = self.invitation["currency_type"]
        
        success, opponent_bet_info, error_embed = await process_bet_amount(
            interaction, bet_amount, currency_type, self.message
        )
        
        # If processing failed, return the error and return challenger's bet
        if not success:
            # Remove the invitation
            self.cog.pending_invites.pop(challenger_id)
            return await self.message.edit(embed=error_embed, view=None)
            
        # Now that both players have accepted, deduct bets from both players
        db = Users()
        
        # Get challenger and opponent data
        challenger = self.invitation["challenger"]
        opponent = self.invitation["opponent"]
        
        # Process the challenger's bet now (we validated it earlier but didn't deduct)
        challenger_success, challenger_bet_info, challenger_error = await process_bet_amount(
            interaction, bet_amount, currency_type, self.message
        )
        
        if not challenger_success:
            # Return opponent's bet and show error
            if opponent_bet_info["tokens_used"] > 0:
                db.update_balance(opponent.id, opponent_bet_info["tokens_used"], "tokens", "$inc")
            if opponent_bet_info["credits_used"] > 0:
                db.update_balance(opponent.id, opponent_bet_info["credits_used"], "credits", "$inc")
                
            self.cog.pending_invites.pop(challenger_id)
            return await self.message.edit(embed=challenger_error, view=None)
        
        # Both bets processed successfully
        challenger_tokens = challenger_bet_info["tokens_used"] 
        challenger_credits = challenger_bet_info["credits_used"]
        
        opponent_tokens = opponent_bet_info["tokens_used"]
        opponent_credits = opponent_bet_info["credits_used"]
        
        # Remove the invitation from pending
        self.cog.pending_invites.pop(challenger_id)
        
        # Create a new game
        game = {
            "challenger": challenger,
            "opponent": opponent,
            "bet_amount": bet_amount,
            "challenger_tokens": challenger_tokens,
            "challenger_credits": challenger_credits,
            "opponent_tokens": opponent_tokens,
            "opponent_credits": opponent_credits,
            "board": [['', '', ''], ['', '', ''], ['', '', '']],
            "current_turn": random.choice([challenger.id, opponent.id]),
            "channel": self.invitation["channel"],
            "time": datetime.datetime.now()
        }
        
        # Add game to active games for both players
        game_id = f"{challenger.id}_{opponent.id}"
        self.cog.active_games[challenger.id] = game_id
        self.cog.active_games[opponent.id] = game_id
        self.cog.active_games[game_id] = game
        
        # Create game view
        game_view = TicTacToeGame(self.cog, game_id)
        
        # Create initial board image
        board_image = await self.cog.create_board_image(game["board"])
        
        # Create and send game embed
        game_embed = discord.Embed(
            title="🎮 Tic Tac Toe",
            description=f"Game between {challenger.mention} (X) and {opponent.mention} (O)",
            color=0x00FFAE
        )
        
        # Determine who goes first
        current_player = challenger if game["current_turn"] == challenger.id else opponent
        symbol = "X" if current_player.id == challenger.id else "O"
        
        game_embed.add_field(name="Current Turn", value=f"{current_player.mention} ({symbol})", inline=False)
        game_embed.add_field(name="Bet Amount", value=f"**{bet_amount:.2f}**", inline=True)
        game_embed.add_field(name="Timeout", value=f"{self.cog.timeout} seconds", inline=True)
        game_embed.add_field(name="Reward", value=f"Winner gets **{bet_amount * 1.95:.2f}**", inline=True)
        game_embed.set_image(url="attachment://board.png")
        
        # Send game message
        file = discord.File(board_image, filename="board.png")
        game_message = await self.message.edit(content=None, embed=game_embed, attachments=[file], view=game_view)
        
        # Set game message and start timeout
        game_view.message = game_message
        self.cog.bot.loop.create_task(self.cog.handle_game_timeout(game_id, game_message))
        
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user who clicked is the opponent
        if interaction.user.id != self.invitation["opponent"].id:
            return await interaction.response.send_message("This invitation is not for you.", ephemeral=True)
            
        # Check if the invitation still exists
        challenger_id = self.invitation["challenger"].id
        if challenger_id not in self.cog.pending_invites:
            return await interaction.response.send_message("This invitation has expired.", ephemeral=True)
            
        # Remove the invitation
        self.cog.pending_invites.pop(challenger_id)
        
        # Create and send decline embed
        decline_embed = discord.Embed(
            title="🎮 Invitation Declined",
            description=f"{self.invitation['opponent'].mention} has declined the Tic Tac Toe invitation from {self.invitation['challenger'].mention}.",
            color=0xFF0000
        )
        
        await interaction.response.edit_message(embed=decline_embed, view=None)

class TicTacToeGame(discord.ui.View):
    def __init__(self, cog, game_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_id = game_id
        self.message = None
        
        # Add buttons for the 3x3 grid
        for row in range(3):
            for col in range(3):
                self.add_item(TicTacToeButton(row, col))
                
    async def check_winner(self, board):
        """Check if there is a winner or a draw"""
        # Check rows
        for row in range(3):
            if board[row][0] != '' and board[row][0] == board[row][1] == board[row][2]:
                return board[row][0]
                
        # Check columns
        for col in range(3):
            if board[0][col] != '' and board[0][col] == board[1][col] == board[2][col]:
                return board[0][col]
                
        # Check diagonals
        if board[0][0] != '' and board[0][0] == board[1][1] == board[2][2]:
            return board[0][0]
            
        if board[0][2] != '' and board[0][2] == board[1][1] == board[2][0]:
            return board[1][1]
            
        # Check for draw
        is_full = True
        for row in range(3):
            for col in range(3):
                if board[row][col] == '':
                    is_full = False
                    break
            if not is_full:
                break
                
        return 'Draw' if is_full else None
        
    async def handle_game_end(self, winner=None, timeout=False):
        """Handle game end and distribute rewards"""
        if self.game_id not in self.cog.active_games:
            return
            
        game = self.cog.active_games[self.game_id]
        challenger = game["challenger"]
        opponent = game["opponent"]
        bet_amount = game["bet_amount"]
        
        # Remove game from active games
        self.cog.active_games.pop(self.game_id)
        self.cog.active_games.pop(challenger.id)
        self.cog.active_games.pop(opponent.id)
        
        db = Users()
        servers_db = Servers()
        
        # Handle win, loss, or draw
        if timeout:
            # Return bets to both players
            if game["challenger_tokens"] > 0:
                db.update_balance(challenger.id, game["challenger_tokens"], "tokens", "$inc")
            if game["challenger_credits"] > 0:
                db.update_balance(challenger.id, game["challenger_credits"], "credits", "$inc")
                
            if game["opponent_tokens"] > 0:
                db.update_balance(opponent.id, game["opponent_tokens"], "tokens", "$inc")
            if game["opponent_credits"] > 0:
                db.update_balance(opponent.id, game["opponent_credits"], "credits", "$inc")
                
            result_embed = discord.Embed(
                title="⏱️ Game Timed Out",
                description=f"The Tic Tac Toe game between {challenger.mention} and {opponent.mention} has timed out. Bets have been returned.",
                color=0xFF0000
            )
            
        elif winner == 'Draw':
            # Return bets to both players
            if game["challenger_tokens"] > 0:
                db.update_balance(challenger.id, game["challenger_tokens"], "tokens", "$inc")
            if game["challenger_credits"] > 0:
                db.update_balance(challenger.id, game["challenger_credits"], "credits", "$inc")
                
            if game["opponent_tokens"] > 0:
                db.update_balance(opponent.id, game["opponent_tokens"], "tokens", "$inc")
            if game["opponent_credits"] > 0:
                db.update_balance(opponent.id, game["opponent_credits"], "credits", "$inc")
                
            result_embed = discord.Embed(
                title="🎮 Tic Tac Toe - Draw!",
                description=f"The game between {challenger.mention} and {opponent.mention} ended in a draw. Bets have been returned.",
                color=0xFFFF00
            )
            
            # Record game stats
            db.update_game_stats(challenger.id, "tictactoe", "draw", 0)
            db.update_game_stats(opponent.id, "tictactoe", "draw", 0)
            
        else:
            # Determine winner and loser
            winner_user = challenger if winner == 'X' else opponent
            loser_user = opponent if winner == 'X' else challenger
            
            # Calculate winnings (1.95x)
            winnings = bet_amount * 1.95
            
            # Determine currency distribution based on the bet
            winner_tokens_bet = game["challenger_tokens"] if winner_user.id == challenger.id else game["opponent_tokens"]
            winner_credits_bet = game["challenger_credits"] if winner_user.id == challenger.id else game["opponent_credits"]
            
            # Calculate token and credit distribution proportionally
            total_bet = winner_tokens_bet + winner_credits_bet
            
            if total_bet > 0:
                token_ratio = winner_tokens_bet / total_bet
                credit_ratio = winner_credits_bet / total_bet
                
                token_winnings = winnings * token_ratio
                credit_winnings = winnings * credit_ratio
            else:
                # Fallback if there's an issue with the bet calculation
                token_winnings = winnings
                credit_winnings = 0
            
            # Award winnings to winner
            if token_winnings > 0:
                db.update_balance(winner_user.id, token_winnings, "tokens", "$inc")
            if credit_winnings > 0:
                db.update_balance(winner_user.id, credit_winnings, "credits", "$inc")
                
            # Get server data for tax
            server_id = game["channel"].guild.id
            server_data = servers_db.fetch_server(server_id)
            
            try:
                tax_rate = server_data.get("tax_rate", 0) / 100
                tax_account = server_data.get("tax_account", None)
                
                if tax_rate > 0 and tax_account:
                    # Calculate tax
                    tax_amount = (bet_amount * 2) * tax_rate
                    
                    # Split tax between tokens and credits proportionally
                    total_bet_both = (game["challenger_tokens"] + game["challenger_credits"] + 
                                      game["opponent_tokens"] + game["opponent_credits"])
                    
                    total_tokens = game["challenger_tokens"] + game["opponent_tokens"]
                    total_credits = game["challenger_credits"] + game["opponent_credits"]
                    
                    token_tax = tax_amount * (total_tokens / total_bet_both) if total_bet_both > 0 else 0
                    credit_tax = tax_amount * (total_credits / total_bet_both) if total_bet_both > 0 else 0
                    
                    # Add tax to server bank
                    if token_tax > 0:
                        db.update_balance(int(tax_account), token_tax, "tokens", "$inc")
                    if credit_tax > 0:
                        db.update_balance(int(tax_account), credit_tax, "credits", "$inc")
            except Exception as e:
                print(f"Error processing tax: {e}")
            
            result_embed = discord.Embed(
                title=f"🎮 Tic Tac Toe - {winner_user.name} Wins!",
                description=f"{winner_user.mention} has won the game against {loser_user.mention}!",
                color=0x00FF00
            )
            
            result_embed.add_field(name="Bet Amount", value=f"**{bet_amount:.2f}**", inline=True)
            result_embed.add_field(name="Winnings", value=f"**{winnings:.2f}**", inline=True)
            
            # Record game stats
            db.update_game_stats(winner_user.id, "tictactoe", "win", winnings - bet_amount)
            db.update_game_stats(loser_user.id, "tictactoe", "loss", -bet_amount)
            
            # Update server game history
            try:
                servers_db.update_game_history(
                    server_id=server_id,
                    game_type="tictactoe",
                    winner_id=winner_user.id,
                    loser_id=loser_user.id,
                    bet_amount=bet_amount,
                    profit=winnings - bet_amount
                )
            except Exception as e:
                print(f"Error updating server game history: {e}")
                
            # Update user game history
            try:
                db.update_game_history(
                    user_id=winner_user.id,
                    game_type="tictactoe",
                    result="win",
                    bet_amount=bet_amount,
                    profit=winnings - bet_amount,
                    opponent_id=loser_user.id
                )
                
                db.update_game_history(
                    user_id=loser_user.id,
                    game_type="tictactoe",
                    result="loss",
                    bet_amount=bet_amount,
                    profit=-bet_amount,
                    opponent_id=winner_user.id
                )
            except Exception as e:
                print(f"Error updating user game history: {e}")
        
        # Update the message with the result
        await self.message.edit(embed=result_embed, view=None)

class TicTacToeButton(discord.ui.Button):
    def __init__(self, row, col):
        super().__init__(style=discord.ButtonStyle.secondary, label=" ", row=row)
        self.row_pos = row
        self.col_pos = col
        
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        game_id = view.game_id
        
        # Check if game exists
        if game_id not in view.cog.active_games:
            return await interaction.response.send_message("This game no longer exists.", ephemeral=True)
            
        game = view.cog.active_games[game_id]
        
        # Check if it's the user's turn
        if interaction.user.id != game["current_turn"]:
            return await interaction.response.send_message("It's not your turn.", ephemeral=True)
            
        # Check if the position is already taken
        if game["board"][self.row_pos][self.col_pos] != '':
            return await interaction.response.send_message("This position is already taken.", ephemeral=True)
            
        # Determine player symbol
        symbol = 'X' if interaction.user.id == game["challenger"].id else 'O'
        
        # Update the board
        game["board"][self.row_pos][self.col_pos] = symbol
        
        # Toggle turn
        game["current_turn"] = game["opponent"].id if interaction.user.id == game["challenger"].id else game["challenger"].id
        
        # Update the button label
        self.label = symbol
        self.disabled = True
        self.style = discord.ButtonStyle.danger if symbol == 'X' else discord.ButtonStyle.primary
        
        # Check for winner
        winner = await view.check_winner(game["board"])
        
        if winner:
            # Disable all buttons
            for item in view.children:
                item.disabled = True
                
            # Handle game end
            await view.handle_game_end(winner)
            return await interaction.response.edit_message(view=view)
            
        # Update the game embed for next turn
        current_player = game["challenger"] if game["current_turn"] == game["challenger"].id else game["opponent"]
        current_symbol = "X" if current_player.id == game["challenger"].id else "O"
        
        # Create updated board image
        board_image = await view.cog.create_board_image(game["board"])
        
        game_embed = discord.Embed(
            title="🎮 Tic Tac Toe",
            description=f"Game between {game['challenger'].mention} (X) and {game['opponent'].mention} (O)",
            color=0x00FFAE
        )
        
        game_embed.add_field(name="Current Turn", value=f"{current_player.mention} ({current_symbol})", inline=False)
        game_embed.add_field(name="Bet Amount", value=f"**{game['bet_amount']:.2f}**", inline=True)
        game_embed.add_field(name="Timeout", value=f"{view.cog.timeout} seconds", inline=True)
        game_embed.add_field(name="Reward", value=f"Winner gets **{game['bet_amount'] * 1.95:.2f}**", inline=True)
        game_embed.set_image(url="attachment://board.png")
        
        # Update message with new board
        file = discord.File(board_image, filename="board.png")
        await interaction.response.edit_message(attachments=[file], embed=game_embed, view=view)

async def setup(bot):
    await bot.add_cog(TicTacToe(bot))
