import discord
import random
import asyncio
import datetime
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class MatchGame:
    """A game where players reveal multipliers on a 4x5 grid and win based on matching multipliers."""
    def __init__(self, bet_amount, user_id):
        self.bet_amount = bet_amount
        self.user_id = user_id
        self.rows = 4
        self.cols = 5
        self.multipliers = [0.2, 0.5, 1.25, 1.75, 2.0, 3.0]
        self.board = self.create_board()
        self.revealed = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self.matched_multiplier = None
        self.game_over = False
        self.revealed_count = 0

    def create_board(self):
        """Create a 4x5 board with 3 of each multiplier randomly placed"""
        # Create a list of all multipliers (3 of each)
        all_multipliers = []
        for multi in self.multipliers:
            all_multipliers.extend([multi] * 3)

        # Add 1 extra 0.2x and 1 extra 0.5x multiplier to fill the remaining 2 spots
        all_multipliers.append(0.2)
        all_multipliers.append(0.5)

        # Shuffle the multipliers
        random.shuffle(all_multipliers)

        # Create the board
        board = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                index = r * self.cols + c
                if index < len(all_multipliers):
                    row.append(all_multipliers[index])
                else:
                    # This shouldn't happen now, but just in case
                    row.append(random.choice(self.multipliers))
            board.append(row)

        return board

    def reveal_tile(self, row, col):
        """Reveal a tile and check if a multiplier has been matched"""
        if self.game_over or self.revealed[row][col]:
            return False

        self.revealed[row][col] = True
        self.revealed_count += 1

        # Check if we've matched any multiplier (3 of the same)
        if self.matched_multiplier is None:
            for multi in self.multipliers:
                matched_count = 0
                for r in range(self.rows):
                    for c in range(self.cols):
                        if self.revealed[r][c] and self.board[r][c] == multi:
                            matched_count += 1

                if matched_count >= 3:
                    self.matched_multiplier = multi
                    self.game_over = True
                    return True

        # Check if all tiles are revealed
        if self.revealed_count >= self.rows * self.cols:
            self.game_over = True

        return False

    def get_winnings(self):
        """Calculate winnings based on matched multiplier"""
        if self.matched_multiplier is None:
            return 0
        return self.bet_amount * self.matched_multiplier

    def get_board_display(self):
        """Generate a text display of the current game board"""
        board_display = ""
        for r in range(self.rows):
            row_display = ""
            for c in range(self.cols):
                if not self.revealed[r][c]:
                    row_display += "❓ "
                else:
                    multiplier = self.board[r][c]
                    # Format based on multiplier value
                    if multiplier <= 0.5:
                        row_display += f"🔴 {multiplier}x "
                    elif multiplier <= 1.75:
                        row_display += f"🟡 {multiplier}x "
                    else:
                        row_display += f"🟢 {multiplier}x "
            board_display += row_display + "\n"
        return board_display

class MatchButton(discord.ui.Button):
    def __init__(self, row, col, match_game, match_cog, ctx):
        # Determine style and label
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="?",
            row=row
        )
        self.ctx = ctx
        self.game_row = row
        self.game_col = col
        self.match_game = match_game
        self.match_cog = match_cog

    async def callback(self, interaction: discord.Interaction):
        # Ensure only the game owner can play
        if interaction.user.id != self.match_game.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Reveal the selected tile
        self.match_game.reveal_tile(self.game_row, self.game_col)

        # Update the button appearance
        if self.match_game.revealed[self.game_row][self.game_col]:
            multiplier = self.match_game.board[self.game_row][self.game_col]
            self.label = f"{multiplier}x"

            # Set color based on multiplier value
            if multiplier <= 0.5:
                self.style = discord.ButtonStyle.danger  # Red for low multipliers
            elif multiplier <= 1.75:
                self.style = discord.ButtonStyle.primary  # Blue for medium multipliers
            else:
                self.style = discord.ButtonStyle.success  # Green for high multipliers

            # Disable the button
            self.disabled = True

        # Check if game is over
        if self.match_game.game_over:
            # Reveal all tiles but don't disable them
            for child in self.view.children:
                if isinstance(child, MatchButton):
                    row = child.game_row
                    col = child.game_col
                    multiplier = self.match_game.board[row][col]
                    child.label = f"{multiplier}x"

                    # Set color based on multiplier value
                    if multiplier <= 0.5:
                        child.style = discord.ButtonStyle.danger  # Red for low multipliers
                    elif multiplier <= 1.75:
                        child.style = discord.ButtonStyle.primary  # Blue for medium multipliers
                    else:
                        child.style = discord.ButtonStyle.success  # Green for high multipliers

            # Process the game result
            await self.match_cog.process_game_result(interaction, self.match_game, self.ctx.guild.id)
        else:
            # Just update the view
            await interaction.response.edit_message(view=self.view)

class PlayAgainButton(discord.ui.Button):
    def __init__(self, match_cog, bet_amount, user_id):
        super().__init__(style=discord.ButtonStyle.success, label="Play Again", row=4)
        self.match_cog = match_cog
        self.bet_amount = bet_amount
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        # Ensure only the original player can click play again
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Start a new game with the same bet amount
        try:
            # Create a mock context with the correct user
            ctx = await self.match_cog.bot.get_context(interaction.message)
            ctx.author = interaction.user  # Override with the actual user
            await self.match_cog.match(ctx, str(self.bet_amount))
        except Exception as e:
            # Handle any errors that might occur
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Could not start a new game: {str(e)}",
                color=discord.Color.red()
            )
            try:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            except:
                pass

class MatchGameView(discord.ui.View):
    def __init__(self, match_game, match_cog, ctx):
        super().__init__(timeout=180)  # 3 minute timeout
        self.ctx = ctx
        self.match_game = match_game
        self.match_cog = match_cog

        # Add buttons for each tile
        for r in range(match_game.rows):
            for c in range(match_game.cols):
                self.add_item(MatchButton(r, c, match_game, match_cog, self.ctx))

class Match(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.ctx = None

    @commands.command(aliases=["mat", "matchgame"])
    async def match(self, ctx, bet_amount: str = None):
        """Match Game - Match 3 of the same multiplier to win!"""
        # Check if bet is provided
        self.ctx = ctx
        if bet_amount is None:
            embed = discord.Embed(
                title=":game_die: Match Game",
                description="In Match Game, you reveal tiles to find multipliers. Match 3 of the same multiplier to win your bet × that multiplier!",
                color=0x00FFAE
            )
            embed.add_field(
                name="How to Play",
                value="1. Place a bet with `!match <amount>`\n2. Click on tiles to reveal multipliers\n3. Match 3 of the same multiplier to win\n4. The first multiplier matched determines your prize",
                inline=False
            )
            embed.add_field(
                name="Multipliers",
                value="0.2x (Low) | 0.5x (Low) | 1.25x (Medium) | 1.75x (Medium) | 2x (High) | 3x (High)",
                inline=False
            )
            return await ctx.reply(embed=embed)

        # Check for active game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Starting Match Game...",
            description="Please wait while we set up your game...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet using currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        # If processing failed, return the error
        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Extract bet information
        tokens_used = bet_info.get("tokens_used", 0)
        #credits_used = bet_info.get("credits_used", 0)
        bet_amount_value = bet_info.get("total_bet_amount", 0)
        currency_used="points"
        #currency_used = bet_info.get("currency_type", "tokens")

        # Create game
        match_game = MatchGame(bet_amount_value, ctx.author.id)
        self.ongoing_games[ctx.author.id] = match_game

        # Create game view
        view = MatchGameView(match_game, self, ctx)

        # Create initial game embed
        embed = discord.Embed(
            title=":game_die: Match Game",
            description=f"Click on tiles to reveal multipliers. Match 3 of the same multiplier to win your bet amount × that multiplier.\n\n**Bet Amount:** {bet_amount_value} {currency_used}",
            color=0x00FFAE
        )
        embed.add_field(name="Board", value="```\nClick the buttons below to reveal tiles!```", inline=False)
        embed.set_footer(text=f"Player: {ctx.author.name} | Game will timeout after 3 minutes of inactivity")

        # Delete loading message and send game
        await loading_message.delete()

        # Send buttons
        message = await ctx.reply(embed=embed, view=view)

        # Set message reference for timeout handling
        view.message = message

    async def process_game_result(self, interaction, match_game, s):
        """Process the game result when the game is over"""
        db = Users()
        user = await self.bot.fetch_user(match_game.user_id)

        # Get match result
        matched_multiplier = match_game.matched_multiplier
        winnings = match_game.get_winnings()

        # Get the currency type from the game
        currency_used = "tokens"  # Default fallback

        # Create result embed
        if matched_multiplier is not None:
            # Player matched a multiplier
            embed = discord.Embed(
                title=":trophy: Match Game Results",
                description=f"You matched the **{matched_multiplier}x** multiplier!",
                color=0x00FFAE
            )

            embed.add_field(
                name="Game Summary",
                value=f"**Bet Amount:** `{match_game.bet_amount} {currency_used}`\n**Multiplier:** {matched_multiplier}x\n**Winnings:** `{winnings} {currency_used}`",
                inline=False
            )

            # Update user balance and history
            if winnings > 0:
                db.update_balance(match_game.user_id, winnings)

                # Adjust profit ratio for house edge calculations
                profit = match_game.bet_amount - winnings
                from Cogs.utils.mongo import Servers
                dbb = Servers()
                dbb.update_server_profit(self.ctx,s, profit, game="match")


            else:
                # If they matched but didn't win anything (unlikely but possible with very low multipliers)
                pass
        else:
            # Player didn't match any multiplier
            embed = discord.Embed(
                title="❌ Match Game Over",
                description="You didn't match any multipliers.",
                color=discord.Color.red()
            )

            embed.add_field(
                name="Game Summary",
                value=f"**Bet Amount:** `{match_game.bet_amount} {currency_used}`\n**Multiplier:** None\n**Loss:** `{match_game.bet_amount} {currency_used}`",
                inline=False
            )



        # No balance field needed

        # Create a new view that reveals all tiles and adds Play Again button
        view = MatchGameView(match_game, self, self.bot.get_context(interaction.message))

        # Reveal all tiles
        for r in range(match_game.rows):
            for c in range(match_game.cols):
                match_game.reveal_tile(r, c)

        # Update all buttons to show their values
        for child in view.children:
            if isinstance(child, MatchButton):
                multiplier = match_game.board[child.game_row][child.game_col]
                child.label = f"{multiplier}x"

                # Set color based on multiplier value
                if multiplier <= 0.5:
                    child.style = discord.ButtonStyle.danger  # Red for low multipliers
                elif multiplier <= 1.75:
                    child.style = discord.ButtonStyle.primary  # Blue for medium multipliers
                else:
                    child.style = discord.ButtonStyle.success  # Green for high multipliers

                # Disable all buttons
                child.disabled = True

        # Add Play Again button
        view.add_item(PlayAgainButton(self, match_game.bet_amount, match_game.user_id))

        # Try to edit the message, but handle potential interaction errors
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            # If interaction was already responded to, try a followup
            try:
                await interaction.followup.send(embed=embed, view=view)
            except:
                # If all else fails, try to edit the original message directly
                try:
                    await interaction.message.edit(embed=embed, view=view)
                except:
                    pass
        except discord.errors.NotFound:
            # If the interaction is not found (404), edit the message directly
            try:
                if hasattr(interaction, 'message') and interaction.message:
                    await interaction.message.edit(embed=embed, view=view)
            except:
                pass
        except Exception as e:
            # Handle any other unexpected errors
            print(f"Error updating match game result: {str(e)}")
            try:
                if hasattr(interaction, 'message') and interaction.message:
                    await interaction.message.edit(embed=embed, view=view)
            except:
                pass

        # Remove from ongoing games
        if match_game.user_id in self.ongoing_games:
            del self.ongoing_games[match_game.user_id]

def setup(bot):
    bot.add_cog(Match(bot))