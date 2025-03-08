import discord
import random
import io
import time
from typing import List, Tuple
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from Cogs.utils.mongo import Users, Servers
import datetime
from io import BytesIO

# Define multiplier tables from the provided data
MULTIPLIER_TABLES = {
    "low_risk": {
        "8_rows": [5.5, 2.0, 1.1, 1.0, 0.5, 1.0, 1.1, 2.0, 5.5],
        "9_rows": [5.5, 2, 1.6, 1.0, 0.7, 0.7, 1.0, 1.6, 2.0, 5.5],
        "10_rows": [8.8, 2.9, 1.4, 1.1, 0.9, 0.5, 0.9, 1.1, 1.4, 2.9, 8.8],
        "11_rows": [8.3, 2.9, 1.9, 1.3, 1.0, 0.7, 0.7, 1.0, 1.3, 1.9, 2.9, 8.3],
        "12_rows": [9.9, 3, 1.6, 1.4, 1.1, 1.0, 0.5, 1.0, 1.1, 1.4, 1.6, 3, 9.9],
        "13_rows": [8, 4, 2.9, 1.8, 1.2, 0.9, 0.7, 0.7, 0.9, 1.2, 1.8, 2.9, 4, 8],
        "14_rows": [7, 4, 1.8, 1.4, 1.3, 1.1, 1.0, 0.5, 1.0, 1.1, 1.3, 1.4, 1.8, 4, 7],
        "15_rows": [15, 8, 3, 2, 1.5, 1.1, 1.0, 0.7, 0.7, 1.0, 1.1, 1.5, 2, 3, 8, 15],
        "16_rows": [15.5, 9, 2, 1.4, 1.3, 1.2, 1.1, 1.0, 0.5, 1.0, 1.1, 1.2, 1.3, 1.4, 2, 9, 15.5]
    },
    "medium_risk": {
        "8_rows": [12, 2.9, 1.3, 0.7, 0.4, 0.7, 1.3, 2.9, 12],
        "9_rows": [17, 3.8, 1.7, 0.9, 0.5, 0.5, 0.9, 1.7, 3.8, 17],
        "10_rows": [20, 4.8, 1.9, 1.4, 0.6, 0.4, 0.6, 1.4, 1.9, 4.8, 20],
        "11_rows": [23, 5.8, 2.9, 1.7, 0.7, 0.5, 0.5, 0.7, 1.7, 2.9, 5.8, 23],
        "12_rows": [30, 10.2, 3.8, 1.9, 1.1, 0.6, 0.3, 0.6, 1.1, 1.9, 3.8, 10.2, 30],
        "13_rows": [40, 12, 5.7, 2.8, 1.3, 0.7, 0.4, 0.4, 0.7, 1.3, 2.8, 5.7, 12, 40],
        "14_rows": [55.0, 15, 6.8, 3.7, 1.9, 1.0, 0.5, 0.2, 0.5, 1.0, 1.9, 3.7, 6.8, 15, 55],
        "15_rows": [85, 17, 10.5, 5, 3, 1.3, 0.5, 0.3, 0.3, 0.5, 1.3, 3, 5, 10.5, 17, 85],
        "16_rows": [105, 40, 10, 4.9, 3, 1.5, 1.0, 0.5, 0.3, 0.5, 1.0, 1.5, 3, 4.9, 10, 40, 105]
    },
    "high_risk": {
        "8_rows": [28, 3.9, 1.5, 0.3, 0.2, 0.3, 1.5, 3.9, 28],
        "9_rows": [41, 6.6, 2.0, 0.6, 0.2, 0.2, 0.6, 2.0, 6.6, 41],
        "10_rows": [75, 9.5, 2.9, 0.9, 0.3, 0.2, 0.3, 0.9, 2.9, 9.5, 75],
        "11_rows": [110, 13, 5.1, 1.4, 0.4, 0.2, 0.2, 0.4, 1.4, 5.1, 13, 110],
        "12_rows": [165, 22, 7.9, 2.0, 0.7, 0.2, 0.2, 0.2, 0.7, 2.0, 7.9, 22, 165],
        "13_rows": [250, 35, 10, 3.9, 1, 0.2, 0.2, 0.2, 0.2, 1, 3.9, 10, 35, 250],
        "14_rows": [400, 52, 17, 4.9, 1.9, 0.3, 0.2, 0.2, 0.2, 0.3, 1.9, 4.9, 17, 52, 400],
        "15_rows": [600, 80, 25, 7.8, 3, 0.5, 0.2, 0.2, 0.2, 0.2, 0.5, 3, 7.8, 25, 80, 600],
        "16_rows": [950.0, 126, 24, 8.2, 3.8, 2.0, 0.2, 0.2, 0.2, 0.2, 0.2, 2.0, 3.8, 8.2, 24, 126, 950.0]
    }
}

# Define risk colors for visual distinction
RISK_COLORS = {
    "low_risk": 0x00AA00,  # Green
    "medium_risk": 0xFFAA00,  # Orange
    "high_risk": 0xFF0000   # Red
}

class PlinkoGame:
    def __init__(self, cog, ctx, bet_amount, difficulty, rows, user_id, currency_type):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty
        self.rows = rows
        self.user_id = user_id
        self.currency_type = currency_type
        self.running = False
        self.message = None
        self.view = None
        self.total_winnings = 0
        self.drops = 0
        self.ball_paths = []
        self.ball_results = []
        self.win_amount = 0
        self.server_id = ctx.guild.id

        # Set colors based on difficulty
        if difficulty == "low":
            self.color = RISK_COLORS["low_risk"]
            self.multiplier_table = MULTIPLIER_TABLES["low_risk"][f"{rows}_rows"]
        elif difficulty == "medium":
            self.color = RISK_COLORS["medium_risk"]
            self.multiplier_table = MULTIPLIER_TABLES["medium_risk"][f"{rows}_rows"]
        else:  # high
            self.color = RISK_COLORS["high_risk"]
            self.multiplier_table = MULTIPLIER_TABLES["high_risk"][f"{rows}_rows"]

    async def start_game(self):
        """Initialize and start the Plinko game"""
        try:
            self.running = True
            self.view = PlinkoView(self)

            # Create initial game embed
            embed = discord.Embed(
                title=f"🎮 Plinko Game - {self.difficulty.capitalize()} Risk",
                description=(
                    f"**Bet Amount:** {self.bet_amount} {self.currency_type}\n"
                    f"**Rows:** {self.rows}\n"
                    f"**Drops:** 0\n"
                    f"**Total Winnings:** 0 {self.currency_type}\n\n"
                    "Click **Drop Ball** to start playing!"
                ),
                color=self.color
            )

            # Generate initial board image
            board_image = self.generate_board_image()
            file = discord.File(board_image, filename="plinko_board.png")
            embed.set_image(url="attachment://plinko_board.png")
            embed.set_footer(text=f"BetSync Casino • {self.ctx.author.name}'s Plinko Game")

            # Send the initial message
            self.message = await self.ctx.send(embed=embed, file=file, view=self.view)

        except Exception as e:
            print(f"Error starting Plinko game: {e}")
            self.running = False
            await self.ctx.send(f"Error starting the game: {e}")

    async def drop_ball(self):
        """Drop a ball and update the game state"""
        try:
            # Increase drop counter
            self.drops += 1

            # Clear previous ball path if any
            if self.ball_paths:
                # Keep only the most recent path
                self.ball_paths = []

            # Simulate the ball path and landing
            path, landing_pos = self.simulate_ball_path()

            # Store the path for rendering
            self.ball_paths.append(path)

            # Get multiplier based on landing position
            multiplier = self.multiplier_table[landing_pos]
            win_for_this_ball = self.bet_amount * multiplier
            self.win_amount += win_for_this_ball

            # Update database for the user's balance
            db = Users()
            # Correct way to use update_balance for deduction:
            # For $inc operation, we pass the negative amount directly
            db_update = db.update_balance(self.user_id, -self.bet_amount, self.currency_type, "$inc")

            # Update database for the win amount if applicable
            if multiplier > 0:
                win_update = db.update_balance(self.user_id, win_for_this_ball, self.currency_type, "$inc")

            # Add to history
            total_profit = self.win_amount - (self.drops * self.bet_amount)

            history_entry = {
                "game": "plinko",
                "timestamp": datetime.datetime.now(),
                "bet_amount": self.bet_amount,
                "win_amount": self.win_amount,
                "profit": total_profit,
                "details": {
                    "difficulty": self.difficulty,
                    "rows": self.rows,
                    "balls_dropped": self.drops,
                    "multipliers": [self.multiplier_table[p[-1]] for p in self.ball_paths]
                }
            }

            db.update_history(self.user_id, history_entry)

            # Also update server history
            servers_db = Servers()
            servers_db.update_history(self.server_id, history_entry)

            # Update server profit
            server_profit = -total_profit  # Server profits when player loses
            servers_db.update_server_profit(self.server_id, server_profit)

            # Update the embed with the new ball drop
            await self.update_game_embed()

        except Exception as e:
            print(f"Error in drop_ball: {e}")

    async def update_game_embed(self):
        """Update the game embed with the latest information"""
        try:
            net_profit = self.win_amount - (self.bet_amount * self.drops)
            profit_display = f"**+{net_profit:.2f}**" if net_profit >= 0 else f"**{net_profit:.2f}**"

            embed = discord.Embed(
                title=f"🎮 Plinko Game - {self.difficulty.capitalize()} Risk",
                description=(
                    f"**Bet Amount:** {self.bet_amount} {self.currency_type}\n"
                    f"**Rows:** {self.rows}\n"
                    f"**Drops:** {self.drops}\n"
                    f"**Total Winnings:** {self.win_amount:.2f} {self.currency_type}\n"
                    f"**Net Profit:** {profit_display} {self.currency_type}\n\n"
                    f"**Last Drop:** {self.multiplier_table[self.ball_paths[-1][-1]]}x multiplier → {self.bet_amount * self.multiplier_table[self.ball_paths[-1][-1]]:.2f} {self.currency_type}"
                ),
                color=self.color
            )
            board_image = self.generate_board_image()
            file = discord.File(board_image, filename="plinko_board.png")
            embed.set_image(url="attachment://plinko_board.png")
            embed.set_footer(text=f"BetSync Casino • {self.ctx.author.name}'s Plinko Game")

            await self.message.edit(embed=embed, file=file, view=self.view)
        except Exception as e:
            print(f"Error updating Plinko embed: {e}")


    def simulate_ball_path(self) -> Tuple[List[int], int]:
        """Simulate a ball's path through the Plinko board"""
        path = []
        num_slots = len(self.multiplier_table)
        actual_rows = self.rows + 2  # User rows + 2 as per requirement

        # Start randomly at one of the 2 gaps at the top
        position = random.randint(0, 1)
        path.append(position)

        # Track the current position as we move down through the rows
        current_position = position

        # For each row after the first, determine path based on pegs
        for row in range(1, actual_rows):
            # Each row has row+1 pegs, creating row+2 possible positions
            # When the ball hits a peg, it has a 50/50 chance to go left or right

            # Slight center bias for realism (real physics has this tendency)
            center = (row + 2) / 2
            center_bias = 0.03 * abs(current_position - center)

            if random.random() < 0.5 - center_bias:
                # Ball goes left
                current_position = current_position
            else:
                # Ball goes right
                current_position = current_position + 1

            # Make sure we don't go out of bounds
            current_position = max(0, min(current_position, row + 1))

            # Add this position to our path
            path.append(current_position)

        # The final position maps to the multiplier index
        # For the last row, there are num_slots possible positions
        # Need to map from range [0, actual_rows] to [0, num_slots-1]
        final_row_positions = actual_rows + 1

        # Scale the position to match the multiplier table indices
        scaled_position = int(current_position * (num_slots - 1) / (final_row_positions - 1) + 0.5)
        final_pos = max(0, min(scaled_position, num_slots - 1))

        # Replace the last position with the scaled position for correct display
        path[-1] = final_pos

        return path, final_pos

    def generate_board_image(self):
        """Generate a visual representation of the Plinko board"""
        try:
            num_slots = len(self.multiplier_table)
            actual_rows = self.rows + 2  # User rows + 2 as per

            # Increase image size for better visibility, especially for 16 rows
            board_width = max(800, 50 * num_slots)
            board_height = max(800, 100 + 50 * actual_rows)

            # Create a larger image with a black background
            board_image = Image.new("RGBA", (board_width, board_height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(board_image)

            # Calculate peg positions
            peg_radius = 5
            peg_spacing_x = board_width / (num_slots + 1)
            peg_spacing_y = (board_height - 100) / (actual_rows + 1)

            # Draw pegs
            for row in range(actual_rows):
                offset = peg_spacing_x / 2 if row % 2 else 0
                num_pegs = num_slots if row % 2 else num_slots + 1

                for col in range(num_pegs):
                    x = offset + peg_spacing_x * (col + 1)
                    y = 50 + peg_spacing_y * (row + 1)
                    draw.ellipse(
                        [(x - peg_radius, y - peg_radius), (x + peg_radius, y + peg_radius)],
                        fill=(200, 200, 200)
                    )

            # Draw buckets with multipliers at the bottom
            bucket_width = peg_spacing_x
            bucket_height = 60
            bucket_y = board_height - bucket_height

            # Load font for multiplier text
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()

            # Draw buckets with enhanced multiplier visibility
            for i, multiplier in enumerate(self.multiplier_table):
                x = peg_spacing_x * (i + 1)

                # Bucket color based on multiplier value
                if multiplier >= 10:
                    color = (255, 215, 0)  # Gold for high multipliers
                elif multiplier >= 5:
                    color = (255, 165, 0)  # Orange for medium-high multipliers
                elif multiplier >= 2:
                    color = (0, 191, 255)  # Light blue for medium multipliers
                elif multiplier >= 1:
                    color = (50, 205, 50)  # Green for low multipliers
                else:
                    color = (169, 169, 169)  # Grey for multipliers < 1

                # Draw the bucket with some spacing
                draw.rectangle(
                    [(x - bucket_width/2 + 2, bucket_y), (x + bucket_width/2 - 2, board_height)],
                    fill=color
                )

                # Prepare multiplier text with enhanced visibility
                text = f"{multiplier}x"
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                text_x = x - text_width / 2
                text_y = bucket_y + (bucket_height - text_height) / 2

                # Draw text outline (black border)
                for offset_x, offset_y in [(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
                    draw.text(
                        (text_x + offset_x, text_y + offset_y),
                        text,
                        font=font,
                        fill=(0, 0, 0)  # Black outline
                    )

                # Draw the actual text
                draw.text(
                    (text_x, text_y),
                    text,
                    font=font,
                    fill=(255, 255, 255)  # White text
                )

            # Draw ball paths if any
            if self.ball_paths:
                last_path = self.ball_paths[-1]

                # Draw the path
                for i in range(len(last_path) - 1):
                    row = i
                    col = last_path[i]
                    next_col = last_path[i + 1]

                    # Calculate current position
                    offset_current = peg_spacing_x / 2 if row % 2 else 0
                    x1 = offset_current + peg_spacing_x * (col + 1)
                    y1 = 50 + peg_spacing_y * (row + 1)

                    # Calculate next position
                    offset_next = peg_spacing_x / 2 if (row + 1) % 2 else 0
                    x2 = offset_next + peg_spacing_x * (next_col + 1)
                    y2 = 50 + peg_spacing_y * (row + 2)

                    # Draw line segment of path
                    draw.line([(x1, y1), (x2, y2)], fill=(255, 0, 0), width=3)

                # Draw red circle at final position
                final_row = len(last_path) - 1
                final_col = last_path[-1]
                final_x = peg_spacing_x * (final_col + 1)
                final_y = bucket_y + bucket_height / 2

                draw.ellipse(
                    [(final_x - 10, final_y - 10), (final_x + 10, final_y + 10)],
                    fill=(255, 0, 0)
                )

            # Convert to BytesIO for discord attachment
            buffer = BytesIO()
            board_image.save(buffer, "PNG")
            buffer.seek(0)
            return buffer

        except Exception as e:
            print(f"Error generating Plinko board image: {e}")
            # Return a fallback image or raise the exception
            fallback = BytesIO()
            Image.new("RGB", (500, 500), (30, 30, 30)).save(fallback, "PNG")
            fallback.seek(0)
            return fallback

    async def end_game(self, interaction=None):
        """End the Plinko game normally"""
        if not self.running:
            return

        self.running = False

        # Disable buttons
        for child in self.view.children:
            child.disabled = True

        try:
            # Final update to the message
            if self.message:
                net_profit = self.win_amount - (self.bet_amount * self.drops)
                profit_display = f"**+{net_profit:.2f}**" if net_profit >= 0 else f"**{net_profit:.2f}**"

                embed = discord.Embed(
                    title=f"🎮 Plinko Game - Finished",
                    description=(
                        f"**Bet Amount:** {self.bet_amount} {self.currency_type}\n"
                        f"**Rows:** {self.rows}\n"
                        f"**Total Drops:** {self.drops}\n"
                        f"**Total Winnings:** {self.win_amount:.2f} {self.currency_type}\n"
                        f"**Net Profit:** {profit_display} {self.currency_type}\n\n"
                        "Thanks for playing Plinko!"
                    ),
                    color=self.color
                )

                board_image = self.generate_board_image()
                file = discord.File(board_image, filename="plinko_board.png")
                embed.set_image(url="attachment://plinko_board.png")
                embed.set_footer(text=f"BetSync Casino • Game Finished")

                await self.message.edit(embed=embed, file=file, view=self.view)
        except Exception as e:
            print(f"Error ending Plinko game: {e}")

        # Clean up
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

    async def timeout_game(self):
        """Handle game timeout"""
        if not self.running:
            return

        self.running = False

        try:
            # Final timeout message
            embed = discord.Embed(
                title=f"🎮 Plinko Game - Timed Out",
                description=(
                    f"**Bet Amount:** {self.bet_amount} {self.currency_type}\n"
                    f"**Rows:** {self.rows}\n"
                    f"**Total Drops:** {self.drops}\n"
                    f"**Total Winnings:** {self.win_amount:.2f} {self.currency_type}\n\n"
                    "Game timed out due to inactivity."
                ),
                color=discord.Color.dark_gray()
            )

            # Disable all buttons
            for child in self.view.children:
                child.disabled = True

            board_image = self.generate_board_image()
            file = discord.File(board_image, filename="plinko_board.png")
            embed.set_image(url="attachment://plinko_board.png")
            embed.set_footer(text=f"BetSync Casino • Game Timed Out")

            await self.message.edit(embed=embed, file=file, view=self.view)
        except Exception as e:
            print(f"Error handling Plinko timeout: {e}")

        # Clean up
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]


class PlinkoView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        self.drop_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Drop Ball",
            emoji="🔴",
            custom_id="drop_ball"
        )
        self.drop_button.callback = self.drop_callback
        self.add_item(self.drop_button)

        self.stop_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Stop",
            emoji="🛑",
            custom_id="stop_game"
        )
        self.stop_button.callback = self.stop_callback
        self.add_item(self.stop_button)

        # Add a cooldown to prevent spam
        self.last_drop_time = 0
        self.cooldown = 1.5  # 1.5 seconds cooldown between drops

    async def drop_callback(self, interaction: discord.Interaction):
        try:
            # Check if the interaction is from the game owner
            if interaction.user.id != self.game.user_id:
                return await interaction.response.send_message("This is not your game!", ephemeral=True)

            # Check for cooldown
            current_time = time.time()
            if current_time - self.last_drop_time < self.cooldown:
                remaining = round(self.cooldown - (current_time - self.last_drop_time), 1)
                return await interaction.response.send_message(
                    f"Please wait {remaining} seconds before dropping another ball.", 
                    ephemeral=True
                )

            self.last_drop_time = current_time

            # Disable buttons during ball drop to prevent spam
            self.drop_button.disabled = True
            self.stop_button.disabled = True

            # Update the view with disabled buttons first
            await interaction.response.edit_message(view=self)

            # Drop the ball
            await self.game.drop_ball()

            # Re-enable buttons after drop is complete
            self.drop_button.disabled = False
            self.stop_button.disabled = False

            # Update the view with enabled buttons
            await self.game.message.edit(view=self)
        except Exception as e:
            print(f"Error in drop_callback: {e}")
            # Re-enable buttons if there's an error
            self.drop_button.disabled = False
            self.stop_button.disabled = False
            try:
                await self.game.message.edit(view=self)
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            except:
                # If we can't edit the original message, try to send a new one
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)

    async def stop_callback(self, interaction: discord.Interaction):
        try:
            # Check if the interaction is from the game owner
            if interaction.user.id != self.game.user_id:
                return await interaction.response.send_message("This is not your game!", ephemeral=True)

            # Acknowledge the interaction
            await interaction.response.defer(ephemeral=False)

            # End the game
            await self.game.end_game(interaction)
        except Exception as e:
            print(f"Error in stop_callback: {e}")
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def on_timeout(self):
        """Handle view timeout - auto-end the game after timeout period"""
        if self.game.running:
            try:
                await self.game.timeout_game()
            except Exception as e:
                print(f"Error in Plinko timeout handler: {e}")


class Plinko(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}  # Store ongoing games for each user

    @commands.command(aliases=["plk"])
    async def plinko(self, ctx, bet_amount: str = None, difficulty: str = None, rows: str = None, currency_type: str = "tokens"):
        """
        Play a game of Plinko

        Usage: !plinko <bet amount> <difficulty> <rows> <currency_type>
        Example: !plinko 10 medium 12 tokens

        Difficulty: low, medium, high
        Rows: 8-16
        Currency: tokens, credits
        """
        # Check if user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="❌ Game Already Running",
                description="You already have an ongoing Plinko game. Please finish it before starting a new one.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Import currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Handle missing parameters
        if bet_amount is None:
            embed = discord.Embed(
                title="📊 How to Play Plinko",
                description=(
                    "**Plinko** is a game where a ball falls through pegs and lands in one of several prize buckets!\n\n"
                    "**Usage:** `!plinko <bet amount> <difficulty> <rows> [currency_type]`\n"
                    "**Example:** `!plinko 100 medium 12` or `!plinko all high 16 credits`\n\n"
                    "**Difficulty:**\n"
                    "- `low`: Lower risk, smaller payouts\n"
                    "- `medium`: Balanced risk and reward\n"
                    "- `high`: Higher risk, bigger potential payouts\n\n"
                    "**Rows:** Choose between 8-16 rows\n"
                    "**Currency:** tokens (default) or credits"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Create loading embed
        loading_embed = discord.Embed(
            title="🎮 Setting up Plinko...",
            description="Processing your bet...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        try:
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            # Successful bet processing - extract relevant information
            tokens_used = bet_info.get("tokens_used", 0)
            credits_used = bet_info.get("credits_used", 0)
            bet_amount_value = bet_info.get("total_bet_amount", 0)
            currency_used = bet_info.get("currency_type", "tokens")  # Default to tokens if not specified

            # Update bet_amount with the processed value
            bet_amount = bet_amount_value

            await loading_message.delete()  # Delete loading message after processing
        except Exception as e:
            await loading_message.delete()
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while processing your bet: {str(e)}",
                color=0xFF0000
            )
            return await ctx.reply(embed=error_embed)

        # Validate difficulty
        if difficulty is None or difficulty.lower() not in ["low", "medium", "high"]:
            embed = discord.Embed(
                title="❌ Invalid Difficulty",
                description="Please choose a valid difficulty: low, medium, or high.",
                color=0xFF0000
            )
            embed.add_field(
                name="Usage",
                value="!plinko <bet amount> <difficulty> <rows> <currency_type>",
                inline=False
            )
            return await ctx.reply(embed=embed)

        # Normalize difficulty
        difficulty = difficulty.lower()

        # Validate rows
        try:
            rows = int(rows)
            if rows < 8 or rows > 16:
                raise ValueError()
        except:
            embed = discord.Embed(
                title="❌ Invalid Rows",
                description="Please choose a number of rows between 8 and 16.",
                color=0xFF0000
            )
            embed.add_field(
                name="Usage",
                value="!plinko <bet amount> <difficulty> <rows> <currency_type>",
                inline=False
            )
            return await ctx.reply(embed=embed)

        # Create and start the game
        try:
            # Create the game
            game = PlinkoGame(
                cog=self,
                ctx=ctx,
                bet_amount=bet_amount,
                difficulty=difficulty,
                rows=rows,
                user_id=ctx.author.id,
                currency_type=currency_used
            )

            # Store the game
            self.ongoing_games[ctx.author.id] = game

            # Start the game
            await game.start_game()

        except Exception as e:
            print(f"Error creating Plinko game: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while creating the game: {e}",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)

    @plinko.error
    async def plinko_error(self, ctx, error):
        """Handle errors for the plinko command"""
        if isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Argument",
                description="Please provide valid arguments for the command.",
                color=0xFF0000
            )
            embed.add_field(
                name="Usage",
                value="!plinko <bet amount> <difficulty> <rows> <currency_type>",
                inline=False
            )
            embed.add_field(
                name="Example",
                value="!plinko 10 medium 12 tokens",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {error}",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Plinko(bot))