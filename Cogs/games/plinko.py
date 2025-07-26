# Applying the changes to incorporate the curse mechanic into the Plinko game and include necessary imports and functions.
import discord
import random
import asyncio
import time
import os
import aiohttp
from discord.ext import commands
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
    def __init__(self, cog, ctx, bet_amount, difficulty, rows, user_id):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty
        self.rows = rows
        self.user_id = user_id
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
                    f"**Bet Amount:** {self.bet_amount} points\n"
                    f"**Rows:** {self.rows}\n"
                    f"**Drops:** 0\n"
                    f"**Total Winnings:** 0 points\n\n"
                    "Click **Drop Ball** to start playing!"
                ),
                color=self.color
            )

            # Generate initial board image
            board_image = self.generate_board_image()
            file = discord.File(board_image, filename="plinko_board.png")
            embed.set_image(url="attachment://plinko_board.png")
            embed.set_footer(text=f"BetSync Casino • {self.ctx.author.name}'s Plinko Game")

            # Send the initial message as a reply to the user's command
            self.message = await self.ctx.reply(embed=embed, file=file, view=self.view, mention_author=True)

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

            # Check for curse before calculating path
            curse_cog = self.cog.bot.get_cog('AdminCurseCog')
            forced_loss = False

            if curse_cog and curse_cog.is_player_cursed(self.ctx.author.id):
                # Force loss for cursed players - ensure ball lands in lowest multiplier slot
                forced_loss = True
                curse_cog.consume_curse(self.ctx.author.id)
                await self.send_curse_webhook(self.ctx.author, "plinko", self.bet_amount)

            # Calculate the ball's path
            if forced_loss:
                # Force the ball to land in the lowest multiplier slot (usually 0 or edges)
                path, landing_pos = self.calculate_forced_loss_path()
            else:
                path, landing_pos = self.simulate_ball_path()

            # Store the path for rendering
            self.ball_paths.append(path)

            # Get multiplier based on landing position
            multiplier = self.multiplier_table[landing_pos]
            win_for_this_ball = self.bet_amount * multiplier
            self.win_amount += win_for_this_ball

            # Update database for the user's balance
            db = Users()
            user_data = db.fetch_user(self.user_id)

            # Points will be deducted only when ball is dropped and multiplier > 0
            points_used = self.bet_amount

            # Update database - deduct points and add winnings if applicable
            if multiplier > 0:
                db_update = db.update_balance(self.user_id, -points_used, "points", "$inc")
                win_update = db.update_balance(self.user_id, win_for_this_ball, "points", "$inc")

            # Add to history
            total_profit = self.win_amount - (self.drops * self.bet_amount)

            # Determine entry type based on profit
            entry_type = "win" if total_profit > 0 else "loss" if total_profit < 0 else "push"

            history_entry = {
                "type": entry_type,
                "game": "plinko",
                "timestamp": int(time.time()),
                "amount": self.win_amount if entry_type == "win" else self.bet_amount,
                "bet": self.bet_amount,
                "multiplier": self.multiplier_table[self.ball_paths[-1][-1]],
                "profit": total_profit,
                "details": {
                    "difficulty": self.difficulty,
                    "rows": self.rows,
                    "balls_dropped": self.drops,
                    "multipliers": [self.multiplier_table[p[-1]] for p in self.ball_paths],
                    "points_used": points_used
                }
            }

            db.update_history(self.user_id, history_entry)

            # Also update server history
            servers_db = Servers()
            server_history_entry = history_entry.copy()
            server_history_entry.update({
                "user_id": self.user_id,
                "user_name": self.ctx.author.name
            })
            servers_db.update_history(self.server_id, server_history_entry)

            # Update server profit
            server_profit = -total_profit  # Server profits when player loses
            servers_db.update_server_profit(self.ctx, self.server_id, server_profit, "plinko")

            # Update the embed with the new ball drop
            await self.update_game_embed(game_over=forced_loss)

        except Exception as e:
            print(f"Error in drop_ball: {e}")

    async def update_game_embed(self, game_over=False):
        """Update the game embed with the latest information"""
        try:
            net_profit = self.win_amount - (self.bet_amount * self.drops)
            profit_display = f"**+{net_profit:.2f}**" if net_profit >= 0 else f"**{net_profit:.2f}**"

            embed = discord.Embed(
                title=f"🎮 Plinko Game - {self.difficulty.capitalize()} Risk",
                description=(
                    f"**Bet Amount:** {self.bet_amount} points\n"
                    f"**Rows:** {self.rows}\n"
                    f"**Drops:** {self.drops}\n"
                    f"**Total Winnings:** {self.win_amount:.2f} points\n"
                    f"**Net Profit:** {profit_display} points\n\n"
                    f"**Last Drop:** {self.multiplier_table[self.ball_paths[-1][-1]]}x multiplier → {self.bet_amount * self.multiplier_table[self.ball_paths[-1][-1]]:.2f} points"
                ),
                color=self.color
            )
            board_image = self.generate_board_image(game_over=game_over)
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

    def calculate_forced_loss_path(self) -> Tuple[List[int], int]:
        """Calculate a path that forces the ball to land in the lowest multiplier slot"""
        path = []
        num_slots = len(self.multiplier_table)
        actual_rows = self.rows + 2  # User rows + 2 as per requirement

        # Start randomly at one of the 2 gaps at the top
        position = random.randint(0, 1)
        path.append(position)

        # Track the current position as we move down through the rows
        current_position = position

        # Determine the target edge (left or right) based on the lowest multiplier
        lowest_multiplier_index = self.multiplier_table.index(min(self.multiplier_table))
        target_side = 0 if lowest_multiplier_index < num_slots / 2 else actual_rows - 1

        # For each row after the first, determine path based on pegs
        for row in range(1, actual_rows):
            # Each row has row+1 pegs, creating row+2 possible positions
            # When the ball hits a peg, it has a 50/50 chance to go left or right

            # Move towards the target edge
            if target_side == 0:  # Move left
                current_position = max(0, current_position - 1)
            else:  # Move right
                current_position = min(row + 1, current_position + 1)

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

    async def send_curse_webhook(self, user, game, bet_amount):
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
                    {"name": "Bet Amount", "value": f"{bet_amount:.2f} points", "inline": True}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            }

            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            print(f"Error sending curse webhook: {e}")

    def generate_board_image(self, game_over=False) -> io.BytesIO:
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
                        f"**Bet Amount:** {self.bet_amount} points\n"
                        f"**Rows:** {self.rows}\n"
                        f"**Total Drops:** {self.drops}\n"
                        f"**Total Winnings:** {self.win_amount:.2f} points\n\n"
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
                    f"**Bet Amount:** {self.bet_amount} points\n"
                    f"**Rows:** {self.rows}\n"
                    f"**Total Drops:** {self.drops}\n"
                    f"**Total Winnings:** {self.win_amount:.2f} points\n\n"
                    "Game timed out due to inactivity."
                ),
                color=discord.Color.dark_gray()
            )

            # Disable all buttons
            for child in self.view.children: