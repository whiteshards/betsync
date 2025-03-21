import discord
import asyncio
import random
import datetime
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y, game):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y
        self.game = game
        self.disabled = False

    async def callback(self, interaction: discord.Interaction):
        # Verify correct player's turn
        if interaction.user.id != self.game.current_player.id:
            return await interaction.response.send_message("It's not your turn!", ephemeral=True)

        # Place the mark
        #await interaction.response.defer()
        await self.game.make_move(interaction, self.x, self.y)

class TicTacToeGame:
    def __init__(self, cog, ctx, player1, player2, bet_amount, player1_currency_used):
        self.cog = cog
        self.ctx = ctx
        self.player1 = player1  # The player who initiated the game
        self.player2 = player2  # The invited player
        self.bet_amount = bet_amount  # Amount bet by each player
        self.player1_currency_used = player1_currency_used  # Which currency player 1 is using
        self.player2_currency_used = None  # Will be set when player2 accepts
        self.current_player = player1  # Player 1 starts
        self.board = [[None, None, None], [None, None, None], [None, None, None]]
        self.view = None
        self.message = None
        self.winner = None
        self.timeout_task = None
        self.game_over = False
        self.timeout_time = 120  # Timeout in seconds

    def create_text_board(self):
        # Create a text-based representation of the board
        board_str = ""
        
        # Row separators
        horizontal_line = "➖➖➖➖➖\n"
        
        for y in range(3):
            # Add cells for this row
            for x in range(3):
                if self.board[y][x] == self.player1:
                    board_str += "❌ "  # X for player 1
                elif self.board[y][x] == self.player2:
                    board_str += "⭕ "  # O for player 2
                else:
                    board_str += "⬛ "  # Empty cell
            
            board_str += "\n"
            
            # Add horizontal line between rows (except after the last row)
            if y < 2:
                board_str += horizontal_line
                
        return board_str

    def create_game_view(self):
        view = discord.ui.View(timeout=self.timeout_time)
        for y in range(3):
            for x in range(3):
                button = TicTacToeButton(x, y, self)
                # Disable button if cell is already taken
                if self.board[y][x] is not None:
                    button.disabled = True
                    if self.board[y][x] == self.player1:
                        button.label = "X"
                        button.style = discord.ButtonStyle.danger
                    else:
                        button.label = "O"
                        button.style = discord.ButtonStyle.primary
                view.add_item(button)

        self.view = view
        return view

    async def start_game(self):
        # Create initial game embed
        embed = discord.Embed(
            title="🎮 Tic Tac Toe",
            description=(
                f"**{self.player1.name}** (❌) vs **{self.player2.name}** (⭕)\n\n"
                f"**Bet:** {self.bet_amount} {self.player1_currency_used}/player\n"
                f"**Reward:** Winner gets 1.95x their bet\n\n"
                f"**{self.current_player.name}'s turn** ({'❌' if self.current_player == self.player1 else '⭕'})"
            ),
            color=0x00FFAE
        )

        # Post the game message
        self.message = await self.ctx.send(embed=embed, view=self.create_game_view())

        # Start timeout task
        self.timeout_task = asyncio.create_task(self.handle_timeout())

    async def make_move(self, interaction, x, y):
        # Place the mark on the board
        await interaction.response.defer()
        self.board[y][x] = self.current_player

        # Check for win or draw
        winner = self.check_winner()
        is_draw = self.is_board_full()

        # Create updated view to show the latest move first
        updated_view = self.create_game_view()

        if winner:
            self.game_over = True
            self.winner = winner
            
            # First update the message to show the final move
            embed = discord.Embed(
                title="🎮 Tic Tac Toe",
                description=(
                    f"**{self.player1.name}** (❌) vs **{self.player2.name}** (⭕)\n\n"
                    f"**Bet:** {self.bet_amount} {self.player1_currency_used}/player\n"
                    f"**Reward:** Winner gets 1.95x their bet\n\n"
                    f"**{self.current_player.name}** just made a move!"
                ),
                color=0x00FFAE
            )
            
            # Update the message with the latest board state
            await interaction.message.edit(embed=embed, view=updated_view)
            
            # Then end the game with a short delay to show the final move
            await asyncio.sleep(0.5)
            await self.end_game(interaction, winner=winner)
            
        elif is_draw:
            self.game_over = True
            
            # First update the message to show the final move
            embed = discord.Embed(
                title="🎮 Tic Tac Toe",
                description=(
                    f"**{self.player1.name}** (❌) vs **{self.player2.name}** (⭕)\n\n"
                    f"**Bet:** {self.bet_amount} {self.player1_currency_used}/player\n"
                    f"**Reward:** Winner gets 1.95x their bet\n\n"
                    f"**{self.current_player.name}** just made a move!"
                ),
                color=0x00FFAE
            )
            
            # Update the message with the latest board state
            await interaction.response.edit_message(embed=embed, view=updated_view)
            
            # Then end the game with a short delay
            await asyncio.sleep(0.5)
            await self.end_game(interaction, draw=True)
            
        else:
            # Switch current player
            self.current_player = self.player2 if self.current_player == self.player1 else self.player1

            # Update embed
            embed = discord.Embed(
                title="🎮 Tic Tac Toe",
                description=(
                    f"**{self.player1.name}** (❌) vs **{self.player2.name}** (⭕)\n\n"
                    f"**Bet:** {self.bet_amount} {self.player1_currency_used}/player\n"
                    f"**Reward:** Winner gets 1.95x their bet\n\n"
                    f"**{self.current_player.name}'s turn** {'⭕' if self.current_player == self.player2 else '❌'}"
                ),
                color=0x00FFAE
            )

            # Update message with new view
            await interaction.response.edit_message(embed=embed, view=updated_view)

    def check_winner(self):
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return row[0]

        # Check columns
        for col in range(3):
            if (self.board[0][col] == self.board[1][col] == self.board[2][col] and 
                self.board[0][col] is not None):
                return self.board[0][col]

        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return self.board[0][2]

        return None

    def is_board_full(self):
        for row in self.board:
            if None in row:
                return False
        return True

    async def handle_timeout(self):
        try:
            await asyncio.sleep(self.timeout_time)
            if not self.game_over:
                self.game_over = True
                
                # Determine the winner (opposite of current player)
                winner = self.player2 if self.current_player == self.player1 else self.player1
                
                # Create timeout embed
                embed = discord.Embed(
                    title="⌛ Game Timed Out",
                    description=(
                        f"**{self.current_player.name}** didn't make a move in time.\n"
                        f"**{winner.name}** wins by timeout!\n"
                        f"**{winner.name}** received **{self.bet_amount * 1.95:.2f} credits**."
                    ),
                    color=discord.Color.orange()
                )

                # Update the game message
                if self.message:
                    # Create a final view with all buttons disabled
                    final_view = discord.ui.View()
                    for y in range(3):
                        for x in range(3):
                            button = TicTacToeButton(x, y, self)
                            button.disabled = True
                            if self.board[y][x] is not None:
                                if self.board[y][x] == self.player1:
                                    button.label = "X"
                                    button.style = discord.ButtonStyle.danger
                                else:
                                    button.label = "O"
                                    button.style = discord.ButtonStyle.primary
                            final_view.add_item(button)
                            
                    await self.message.edit(embed=embed, view=final_view)

                # Process win reward for the non-timing out player
                await self.process_win_reward(winner)

                # Remove game from ongoing games
                if self.player1.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.player1.id]
                if self.player2.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.player2.id]
        except asyncio.CancelledError:
            pass

    async def end_game(self, interaction, winner=None, draw=False):
        # Cancel timeout task
        if self.timeout_task:
            self.timeout_task.cancel()

        # Create game end embed
        if draw:
            embed = discord.Embed(
                title="🎮 Tic Tac Toe - Draw!",
                description=(
                    f"The game between **{self.player1.name}** and **{self.player2.name}** ended in a draw.\n"
                    f"Both players have been refunded their {self.bet_amount} {self.player1_currency_used}."
                ),
                color=discord.Color.gold()
            )
        else:
            embed = discord.Embed(
                title="🎮 Tic Tac Toe - Game Over!",
                description=(
                    f"**{winner.name}** has won the game against **{self.player2.name if winner == self.player1 else self.player1.name}**!\n"
                    f"**{winner.name}** received **{self.bet_amount * 1.95:.2f} credits**."
                ),
                color=discord.Color.green()
            )

        # Create final view with all buttons disabled but still showing the final state
        final_view = self.create_game_view()
        for item in final_view.children:
            item.disabled = True

        # Try to edit the message, but handle the case where it might have already been modified
        try:
            await interaction.edit_original_response(embed=embed, view=final_view)
        except:
            # Fallback if the original response can't be edited
            try:
                await self.message.edit(embed=embed, view=final_view)
            except:
                # If both fail, try a new response
                await interaction.followup.send(embed=embed, view=final_view)

        # Process rewards
        if draw:
            await self.process_refunds()
        else:
            await self.process_win_reward(winner)

        # Remove game from ongoing games
        if self.player1.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.player1.id]
        if self.player2.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.player2.id]

    async def process_refunds(self):
        # Refund player 1
        db = Users()

        # Different handling based on currency type
        if "tokens" in self.player1_currency_used:
            db.update_balance(self.player1.id, self.bet_amount, "tokens", "$inc")
        elif "credits" in self.player1_currency_used:
            db.update_balance(self.player1.id, self.bet_amount, "credits", "$inc")
        elif "mixed" in self.player1_currency_used:
            # If mixed, need to refund both currencies (specific handling would require more details)
            # For now, assuming the mix info is stored elsewhere and handled by another function
            pass

        # Refund player 2
        if self.player2_currency_used:
            if "tokens" in self.player2_currency_used:
                db.update_balance(self.player2.id, self.bet_amount, "tokens", "$inc")
            elif "credits" in self.player2_currency_used:
                db.update_balance(self.player2.id, self.bet_amount, "credits", "$inc")
            elif "mixed" in self.player2_currency_used:
                # Mixed currency handling for player 2
                pass

    async def process_win_reward(self, winner):
        db = Users()
        loser = self.player2 if winner == self.player1 else self.player1

        # Calculate reward (1.95x bet)
        reward = self.bet_amount * 1.95

        # Award winner with credits
        db.update_balance(winner.id, reward, "credits", "$inc")

        # Add to winner's history
        history_entry_winner = {
            "type": "win",
            "game": "tictactoe",
            "opponent": loser.name,
            "amount": reward,
            "timestamp": int(datetime.datetime.now().timestamp())
        }
        db.collection.update_one(
            {"discord_id": winner.id},
            {"$push": {"history": {"$each": [history_entry_winner], "$slice": -100}}}
        )

        # Add to loser's history
        history_entry_loser = {
            "type": "loss",
            "game": "tictactoe",
            "opponent": winner.name,
            "amount": self.bet_amount,
            "timestamp": int(datetime.datetime.now().timestamp())
        }
        db.collection.update_one(
            {"discord_id": loser.id},
            {"$push": {"history": {"$each": [history_entry_loser], "$slice": -100}}}
        )
        #from Cogs.utils.mongo import Servers
        #serverss = Servers()
        #serverss.update_server_profit(ctx.guild.id, )
        
        # Update server stats
        # This part would be similar to other games, but I don't have complete context
        # of your server stats structure

class TicTacToeInvite(discord.ui.View):
    def __init__(self, cog, ctx, target, bet_amount, currency_used):
        super().__init__(timeout=120)  # 120 second timeout as requested
        self.cog = cog
        self.ctx = ctx
        self.target = target
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.responded = False
        self.timeout_task = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, button, interaction):
        # Check if the correct user is responding
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("This invitation is not for you!", ephemeral=True)

        # Mark as responded to prevent multiple responses
        self.responded = True

        # Process bet for player 2
        from Cogs.utils.currency_helper import process_bet_amount

        success, bet_info, error_embed = await process_bet_amount(
            self.ctx, self.bet_amount, self.currency_used, interaction.message
        )

        if not success:
            return await interaction.response.send_message(embed=error_embed, ephemeral=True)

        # Extract player 2's bet info
        tokens_used = bet_info["tokens_used"]
        credits_used = bet_info["credits_used"]

        # Determine which currency was primarily used
        if tokens_used > 0 and credits_used > 0:
            player2_currency_used = "mixed"
        elif tokens_used > 0:
            player2_currency_used = "tokens"
        else:
            player2_currency_used = "credits"

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Create and start the game
        game = TicTacToeGame(
            self.cog, 
            self.ctx, 
            self.ctx.author, 
            self.target, 
            self.bet_amount, 
            self.currency_used
        )
        game.player2_currency_used = player2_currency_used

        # Register both players as having an ongoing game
        self.cog.ongoing_games[self.ctx.author.id] = game
        self.cog.ongoing_games[self.target.id] = game

        # Start the game
        await game.start_game()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, button, interaction):
        # Check if the correct user is responding
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("This invitation is not for you!", ephemeral=True)

        # Mark as responded
        self.responded = True

        # Disable buttons
        for child in self.children:
            child.disabled = True
            
        try:
            await interaction.response.edit_message(view=self)
        except Exception as e:
            print(f"Error editing message: {e}")
            try:
                await self.message.edit(view=self)
            except:
                pass

        # Refund the inviter
        try:
            db = Users()
            if "tokens" in self.currency_used:
                db.update_balance(self.ctx.author.id, self.bet_amount, "tokens", "$inc")
            elif "credits" in self.currency_used:
                db.update_balance(self.ctx.author.id, self.bet_amount, "credits", "$inc")
            elif "mixed" in self.currency_used:
                # Mixed currency handling would be implemented here
                pass

            # Send decline message with confirmation of refund
            decline_embed = discord.Embed(
                title="❌ Game Invitation Declined",
                description=f"**{self.target.name}** declined your Tic Tac Toe invitation.\nYour {self.bet_amount} {self.currency_used} has been refunded.",
                color=discord.Color.red()
            )
            await self.ctx.send(embed=decline_embed)
        except Exception as e:
            print(f"Error processing refund or sending decline message: {e}")
            # Send a backup message in case of error
            try:
                await self.ctx.send(f"**{self.target.name}** declined the game invitation. There was an issue processing the refund, please contact an admin.")
            except:
                pass

    async def on_timeout(self):
        if not self.responded:
            # Disable buttons
            for child in self.children:
                child.disabled = True

            try:
                # Update the original invitation message with disabled buttons
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Error editing invitation message: {e}")

            # Refund the inviter
            db = Users()
            try:
                if "tokens" in self.currency_used:
                    db.update_balance(self.ctx.author.id, self.bet_amount, "tokens", "$inc")
                elif "credits" in self.currency_used:
                    db.update_balance(self.ctx.author.id, self.bet_amount, "credits", "$inc")
                elif "mixed" in self.currency_used:
                    # Mixed currency handling would be implemented here
                    pass
                
                # Send timeout message
                timeout_embed = discord.Embed(
                    title="⌛ Game Invitation Expired",
                    description=f"**{self.target.name}** did not respond to your Tic Tac Toe invitation.\nYour {self.bet_amount} {self.currency_used} has been refunded.",
                    color=discord.Color.gold()
                )
                await self.ctx.send(embed=timeout_embed)
            except Exception as e:
                print(f"Error processing refund or sending timeout message: {e}")


class TicTacToeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, target: discord.Member = None, bet_amount: str = None, currency_type: str = None):
        """Play Tic Tac Toe against another player with bets!"""
        # Show help if no arguments
        if not target or not bet_amount:
            embed = discord.Embed(
                title="🎮 How to Play Tic Tac Toe",
                description=(
                    "**Tic Tac Toe** is a classic game where you try to get 3 in a row!\n\n"
                    "**Usage:** `!tictactoe <@player> <amount> [currency_type]`\n"
                    "**Example:** `!tictactoe @Friend 100` or `!tictactoe @Friend 100 tokens`\n\n"
                    "- **Win by getting 3 marks in a row (horizontal, vertical, or diagonal)**\n"
                    "- **If you win, you receive 1.95x your bet!**\n"
                    "- **If it's a draw, both players get their bets back**\n"
                    "- **Games timeout after 120 seconds of inactivity**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if target is valid
        if target.id == ctx.author.id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Target",
                description="You cannot play against yourself!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        if target.bot:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Target",
                description="You cannot play against a bot!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Check if either player is already in a game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        if target.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Target Busy",
                description=f"**{target.name}** is already in a game. Try again later.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Tic Tac Toe Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount
        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if user_data == False:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Check if target has an account
        target_data = db.fetch_user(target.id)
        if target_data == False:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Target Not Found",
                description=f"**{target.name}** doesn't have an account. They need to use any command once to register.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Import currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process bet using currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Successful bet processing - extract relevant information
        tokens_used = bet_info["tokens_used"]
        credits_used = bet_info["credits_used"]
        bet_amount_value = bet_info["total_bet_amount"]

        # Determine which currency was primarily used for display purposes
        if tokens_used > 0 and credits_used > 0:
            currency_used = "mixed"
        elif tokens_used > 0:
            currency_used = "tokens"
        else:
            currency_used = "credits"

        # Create invitation embed
        if currency_used == "mixed":
            currency_display = f"{tokens_used} tokens and {credits_used} credits"
        else:
            currency_display = f"{bet_amount_value} {currency_used}"
        await loading_message.delete()

        invite_embed = discord.Embed(
            title="🎮 Tic Tac Toe Invitation",
            description=(
                f"**{ctx.author.name}** has invited **{target.name}** to a game of Tic Tac Toe!\n\n"
                f"**Bet:** {currency_display}\n"
                f"**Reward:** Winner gets 1.95x their bet\n\n"
                f"**{target.name}**, do you accept this challenge?"
            ),
            color=0x00FFAE
        )

        # Create invitation view
        invite_view = TicTacToeInvite(self, ctx, target, bet_amount_value, currency_used)

        # Delete loading message and send invitation
        #await loading_message.delete()
        
        # Set the message attribute before sending to avoid race condition
        try:
            # First send a mention in a separate message to ensure notification
            await ctx.send(f"{target.mention}", delete_after=1)
            # Then send the actual invitation
            invite_message = await ctx.reply(embed=invite_embed, view=invite_view)
            invite_view.message = invite_message
            
            # Print confirmation to console for debugging
            print(f"Successfully sent TicTacToe invitation to {target.name}")
            #await loading_message.delete()
        except Exception as e:
            print(f"Error sending TicTacToe invitation: {e}")
            # Fallback in case of error to ensure invitation is sent
            #await ctx.send(f"{target.mention}, you've been invited to a TicTacToe game! Please check the message above.")

def setup(bot):
    bot.add_cog(TicTacToeCog(bot))