import discord
import random
import io
import time
from typing import List, Tuple
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from Cogs.utils.mongo import Users, Servers
import datetime

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
        "16_rows": [950, 126, 24, 8.2, 3.8, 2.0, 0.2, 0.2, 0.2, 0.2, 0.2, 2.0, 3.8, 8.2, 24, 126, 950]
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
                    f"**Total Winnings:** 0 credits\n\n"
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
                win_update = db.update_balance(self.user_id, win_for_this_ball, "credits", "$inc")

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
                    f"**Total Winnings:** {self.win_amount:.2f} credits\n"
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
        """Simulate a ball's path through the Plinko board - optimized version"""
        num_slots = len(self.multiplier_table)
        actual_rows = self.rows + 2  # User rows + 2 as per requirement
        
        # Faster algorithm: only calculate the final position
        # This is much quicker than simulating each step
        
        # For display, we'll generate a simplified path
        # Choose a final landing position with distribution
        # that's triangular (more likely to land in the middle)
        weights = []
        for i in range(num_slots):
            # Distance from center (0 to 1 scale)
            center_idx = (num_slots - 1) / 2
            distance = abs(i - center_idx) / center_idx
            # Weight is higher for center positions
            weight = 1.0 - (distance * 0.5)  # Adjust 0.5 to control center bias
            weights.append(weight)
            
        # Normalize weights to sum to 1
        total = sum(weights)
        weights = [w/total for w in weights]
        
        # Choose landing position based on weights
        final_pos = random.choices(range(num_slots), weights=weights)[0]
        
        # Create a simplified path for visualization
        # We'll just interpolate a few points from start to finish
        path = []
        
        # Start randomly at one of the 2 gaps at the top
        start_pos = random.randint(0, 1)
        path.append(start_pos)
        
        # Generate a few intermediate points for visual effect
        # Just enough to show movement without costly simulation
        steps = min(5, actual_rows-1)  # Limit number of steps for efficiency
        for i in range(1, steps):
            row_position = i * (actual_rows / steps)
            # Calculate position that gradually moves toward final position
            progress = i / steps
            interpolated_pos = int(start_pos + progress * (final_pos - start_pos))
            # Add some randomness to make path look natural
            jitter = random.uniform(-0.5, 0.5) * (1 - progress)
            pos = max(0, min(round(interpolated_pos + jitter), num_slots - 1))
            path.append(pos)
            
        # Add final position
        path.append(final_pos)
        
        return path, final_pos

    def generate_board_image(self) -> io.BytesIO:
        """Generate a visual representation of the Plinko board"""
        # Constants for board rendering - Adjust size based on row count
        width = 1100 if self.rows >= 16 else 900 if self.rows >= 13 else 800
        height = 1300 if self.rows >= 16 else 1100 if self.rows >= 13 else 1000
        peg_radius = 6 if self.rows >= 16 else 7 if self.rows >= 13 else 8  # Smaller pegs for larger boards
        ball_radius = 12
        multiplier_height = 100 if self.rows >= 16 else 80  # Taller multiplier area for more rows

        # Calculate board dimensions
        board_width = width
        board_height = height - multiplier_height

        # Create a new image
        img = Image.new('RGBA', (width, height), (40, 44, 52, 255))  # Dark background
        draw = ImageDraw.Draw(img)

        try:
            # Try to load custom fonts
            title_font = ImageFont.truetype("roboto.ttf", 36)
            multiplier_font = ImageFont.truetype("roboto.ttf", 22 if self.rows >= 16 else 20)  # Slightly larger font for 16+ rows
            watermark_font = ImageFont.truetype("roboto.ttf", 36)
        except:
            # Fallback to default font if custom font fails
            title_font = ImageFont.load_default()
            multiplier_font = ImageFont.load_default()
            watermark_font = ImageFont.load_default()

        # Calculate the actual display rows (user_rows + 2)
        actual_rows = self.rows + 2

        # The number of slots/gaps at the bottom should be actual_rows - 1
        # This ensures we have one more multiplier than the user-specified rows
        num_slots = len(self.multiplier_table)
        horizontal_spacing = board_width / (num_slots + 1)

        # Calculate vertical spacing with appropriate margins
        vertical_spacing = board_height / (actual_rows + 1)  # +1 for margins

        # Draw pegs - Start with 2 gaps at top (1 peg), increasing as we go down
        for row in range(actual_rows):
            # First row has 1 peg (2 gaps), then each row adds 1 more peg
            num_pegs = row + 1

            # Calculate starting x position to center the pegs
            start_x = (board_width - (num_pegs - 1) * horizontal_spacing) / 2
            y = vertical_spacing * (row + 1)  # Proper spacing from top

            for peg in range(num_pegs):
                x = start_x + peg * horizontal_spacing
                draw.ellipse((x - peg_radius, y - peg_radius, x + peg_radius, y + peg_radius), 
                             fill=(230, 230, 230, 255))  # White pegs

        # Draw multiplier buckets at the bottom - one for each multiplier
        bucket_width = horizontal_spacing * 0.9
        bucket_height = multiplier_height * 0.8

        # Position buckets just below the last row of pegs
        bucket_y = vertical_spacing * (actual_rows + 0.5)

        # Color mapping for multipliers
        def get_multiplier_color(multiplier):
            if multiplier >= 10:
                return (255, 0, 102, 255)  # Bright pink for high multipliers
            elif multiplier >= 3:
                return (255, 165, 0, 255)  # Orange for medium multipliers
            elif multiplier >= 1:
                return (0, 191, 255, 255)  # Blue for neutral multipliers
            else:
                return (158, 158, 158, 255)  # Grey for low multipliers

        # Draw multiplier buckets - there should be num_slots buckets
        for i, multiplier in enumerate(self.multiplier_table):
            x = horizontal_spacing * (i + 1)

            # Adjust bucket width for more spacing between buckets when there are many slots
            bucket_width_adjusted = bucket_width * (0.85 if self.rows >= 16 else 0.9)

            # Draw bucket with slightly better spacing
            bucket_color = get_multiplier_color(multiplier)
            draw.rectangle(
                (x - bucket_width_adjusted/2, bucket_y, x + bucket_width_adjusted/2, bucket_y + bucket_height),
                fill=bucket_color,
                outline=(255, 255, 255, 150)  # Slightly more visible outline
            )

            # Draw multiplier text with black outline for better visibility
            text_color = (255, 255, 255, 255)  # White text
            multiplier_text = f"{multiplier}x"
            text_bbox = draw.textbbox((0, 0), multiplier_text, font=multiplier_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = x - text_width / 2
            text_y = bucket_y + (bucket_height - text_height) / 2

            # Draw text outline (thin black border) by drawing the text multiple times with small offsets
            outline_color = (0, 0, 0, 255)  # Black outline
            outline_thickness = 1

            # Draw outline by offsetting text in 4 directions
            for dx, dy in [(outline_thickness, 0), (-outline_thickness, 0), (0, outline_thickness), (0, -outline_thickness)]:
                draw.text((text_x + dx, text_y + dy), multiplier_text, font=multiplier_font, fill=outline_color)

            # Draw the main text on top
            draw.text((text_x, text_y), multiplier_text, font=multiplier_font, fill=text_color)

        # Add subtle BetSync watermark in the middle
        watermark_text = "BetSync"
        watermark_bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        watermark_width = watermark_bbox[2] - watermark_bbox[0]
        watermark_x = (width - watermark_width) / 2
        watermark_y = board_height / 2 - 20
        draw.text((watermark_x, watermark_y), watermark_text, font=watermark_font, fill=(255, 255, 255, 40))

        # Add more visible BetSync watermark at the bottom right
        bottom_watermark = "BetSync"
        bottom_watermark_bbox = draw.textbbox((0, 0), bottom_watermark, font=multiplier_font)
        bottom_watermark_width = bottom_watermark_bbox[2] - bottom_watermark_bbox[0]
        bottom_watermark_x = width - bottom_watermark_width - 10
        bottom_watermark_y = height - 25
        draw.text((bottom_watermark_x, bottom_watermark_y), bottom_watermark, 
                  font=multiplier_font, fill=(255, 255, 255, 180))

        # Draw only the most recent ball
        if self.ball_paths and len(self.ball_paths[-1]) > 0:
            final_pos = self.ball_paths[-1][-1]
            # Align with the multiplier buckets
            final_x = horizontal_spacing * (final_pos + 1)
            final_y = bucket_y - ball_radius

            # Draw the ball
            draw.ellipse(
                (final_x - ball_radius, final_y - ball_radius, 
                 final_x + ball_radius, final_y + ball_radius),
                fill=(255, 255, 255, 255),  # White ball
                outline=(255, 0, 0, 255)    # Red outline
            )

        # Save to a BytesIO object
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        return img_buffer

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
                        f"**Total Winnings:** {self.win_amount:.2f} credits\n\n"
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
        finally:
            # Always clean up, regardless of whether the edit succeeded
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
                    f"**Total Winnings:** {self.win_amount:.2f} credits\n\n"
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
        finally:
            # Always clean up, regardless of whether the edit succeeded
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]


class PlinkoView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        # Add drop ball button
        self.drop_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Drop Ball",
            emoji="🔴",
            custom_id="drop_ball"
        )
        self.drop_button.callback = self.drop_callback
        self.add_item(self.drop_button)

        # Stop button - initially disabled until first drop
        self.stop_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Stop",
            emoji="🛑",
            custom_id="stop_game",
            disabled=True  # Disabled until first drop
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

            # Check if user has enough balance for another bet
            db = Users()
            user_data = db.fetch_user(self.game.user_id)
            user_balance = user_data.get(self.game.currency_type, 0)

            if user_balance < self.game.bet_amount:
                # Not enough balance for another drop
                error_embed = discord.Embed(
                    title="❌ Insufficient Balance",
                    description=f"You don't have enough {self.game.currency_type} for another ball drop!",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True, delete_after=5)

                # End the game and clean up since player can't continue
                if self.game.ctx.author.id in self.game.cog.ongoing_games:
                    del self.game.cog.ongoing_games[self.game.ctx.author.id]
                
                # Update message to show game is over
                game_over_embed = discord.Embed(
                    title=f"🎮 Plinko Game - Ended",
                    description=(
                        f"**Bet Amount:** {self.game.bet_amount} {self.game.currency_type}\n"
                        f"**Rows:** {self.game.rows}\n"
                        f"**Total Drops:** {self.game.drops}\n"
                        f"**Total Winnings:** {self.game.win_amount:.2f} credits\n\n"
                        f"Game ended due to insufficient balance."
                    ),
                    color=discord.Color.red()
                )
                
                # Mark the game as not running
                self.game.running = False
                
                # Disable all buttons
                for child in self.children:
                    child.disabled = True
                
                board_image = self.game.generate_board_image()
                file = discord.File(board_image, filename="plinko_board.png")
                game_over_embed.set_image(url="attachment://plinko_board.png")
                game_over_embed.set_footer(text=f"BetSync Casino • Game Ended")
                
                await self.game.message.edit(embed=game_over_embed, file=file, view=self)
                return

            # Drop the ball
            await self.game.drop_ball()

            # Re-enable buttons after drop is complete
            self.drop_button.disabled = False
            self.stop_button.disabled = False

            # Enable stop button after the first drop
            if self.game.drops >= 1:
                self.stop_button.disabled = False
                await self.game.message.edit(view=self)

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
        if ctx.author.id in self.ongoing_games and self.ongoing_games[ctx.author.id].running:
            embed = discord.Embed(
                title="❌ Game Already Running",
                description="You already have an ongoing Plinko game. Please finish it before starting a new one.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        # Clean up any existing game that might be in a bad state
        elif ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

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

        # Normalize currency type to lowercase
        if currency_type:
            currency_type = currency_type.lower()
            if currency_type not in ["tokens", "credits"]:
                embed = discord.Embed(
                    title="❌ Invalid Currency",
                    description="Currency type must be either 'tokens' or 'credits'.",
                    color=0xFF0000
                )
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