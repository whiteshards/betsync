
import discord
import random
import asyncio
import time
import io
import json
import math
from typing import Dict, List, Optional, Union, Tuple
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from colorama import Fore

# Multiplier tables for different risk levels and row counts
MULTIPLIER_TABLES = {
    "low_risk": {
        "8_rows": [5.5, 2.0, 1.1, 1.0, 0.5, 1.1, 1.0, 2.0, 5.5],
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

# Color themes for different risk levels
RISK_COLORS = {
    "low_risk": 0x00FFAE,  # Green
    "medium_risk": 0xFFA500,  # Orange
    "high_risk": 0xFF3366    # Red
}

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
        
        # Acknowledge the interaction immediately to prevent timeouts
        await interaction.response.defer(ephemeral=False)
        
        # Drop the ball
        await self.game.drop_ball()

    async def stop_callback(self, interaction: discord.Interaction):
        # Check if the interaction is from the game owner
        if interaction.user.id != self.game.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Acknowledge the interaction
        await interaction.response.defer(ephemeral=False)
        
        # End the game
        await self.game.end_game(interaction)
        
    async def on_timeout(self):
        """Handle view timeout - auto-end the game after timeout period"""
        if self.game.running:
            try:
                await self.game.timeout_game()
            except Exception as e:
                print(f"Error in Plinko timeout handler: {e}")

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
        """Process a single ball drop"""
        if not self.running:
            return

        db = Users()
        
        # Deduct bet amount
        db_update = db.update_balance(self.user_id, self.bet_amount, self.currency_type, "$inc", -1)
        if not db_update:
            await self.ctx.send(
                embed=discord.Embed(
                    title="❌ Insufficient Balance",
                    description=f"You don't have enough {self.currency_type} to place this bet.",
                    color=0xFF0000
                )
            )
            await self.end_game()
            return

        # Update stats
        db.collection.update_one(
            {"discord_id": self.user_id},
            {"$inc": {"total_played": 1, "total_spent": self.bet_amount}}
        )
        
        # Get server for profit tracking
        server_db = Servers()
        server = server_db.fetch_server(self.ctx.guild.id)
        
        # Simulate the ball path
        path, landing_pos = self.simulate_ball_path()
        self.ball_paths.append(path)
        
        # Calculate winnings
        multiplier = self.multiplier_table[landing_pos]
        winnings = round(self.bet_amount * multiplier, 2)
        self.ball_results.append((landing_pos, multiplier, winnings))
        self.total_winnings += winnings
        self.drops += 1
        
        # Update user balance with winnings
        if winnings > 0:
            db.update_balance(self.user_id, winnings, self.currency_type, "$inc")
            db.collection.update_one(
                {"discord_id": self.user_id},
                {"$inc": {"total_earned": winnings, "total_won": 1}}
            )
        else:
            db.collection.update_one(
                {"discord_id": self.user_id},
                {"$inc": {"total_lost": 1}}
            )
        
        # Update server profit
        profit = self.bet_amount - winnings
        if server:
            server_db.collection.update_one(
                {"server_id": self.ctx.guild.id}, 
                {"$inc": {"total_profit": profit}}
            )
        
        # Generate updated board image
        board_image = self.generate_board_image()
        file = discord.File(board_image, filename="plinko_board.png")
        
        # Create updated embed
        net_profit = self.total_winnings - (self.bet_amount * self.drops)
        profit_display = f"**+{net_profit:.2f}**" if net_profit >= 0 else f"**{net_profit:.2f}**"
        
        embed = discord.Embed(
            title=f"🎮 Plinko Game - {self.difficulty.capitalize()} Risk",
            description=(
                f"**Bet Amount:** {self.bet_amount} {self.currency_type}\n"
                f"**Rows:** {self.rows}\n"
                f"**Drops:** {self.drops}\n"
                f"**Total Winnings:** {self.total_winnings:.2f} {self.currency_type}\n"
                f"**Net Profit:** {profit_display} {self.currency_type}\n\n"
                f"**Last Drop:** {multiplier}x multiplier → {winnings:.2f} {self.currency_type}"
            ),
            color=self.color
        )
        embed.set_image(url="attachment://plinko_board.png")
        embed.set_footer(text=f"BetSync Casino • {self.ctx.author.name}'s Plinko Game")
        
        # Update the message
        await self.message.edit(embed=embed, file=file, view=self.view)
    
    def simulate_ball_path(self) -> Tuple[List[int], int]:
        """
        Simulate a ball's path through the Plinko board
        Returns the path (list of positions at each row) and final landing position
        """
        path = []
        
        # Start at the center position
        position = len(self.multiplier_table) // 2
        path.append(position)
        
        # For each row, the ball can go left or right
        for _ in range(self.rows):
            # True physics-based Plinko has roughly 50/50 chance at each peg
            # Add slight bias toward center for realism (real balls tend to center slightly)
            center_bias = 0.02 * abs(position - (len(self.multiplier_table) // 2))
            
            if random.random() < 0.5 - center_bias:
                # Go left
                if position > 0:
                    position -= 1
            else:
                # Go right
                if position < len(self.multiplier_table) - 1:
                    position += 1
                    
            path.append(position)
        
        # Return the path and final landing position
        return path, path[-1]
    
    def generate_board_image(self) -> io.BytesIO:
        """Generate a visual representation of the Plinko board"""
        # Constants for board rendering
        width = 800
        height = 1000
        peg_radius = 8
        ball_radius = 12
        multiplier_height = 80
        
        # Calculate board dimensions
        board_width = width
        board_height = height - multiplier_height
        
        # Calculate spacing
        horizontal_spacing = board_width / (len(self.multiplier_table) + 1)
        vertical_spacing = board_height / (self.rows + 2)  # +2 for top and bottom margins
        
        # Create a new image
        img = Image.new('RGBA', (width, height), (40, 44, 52, 255))  # Dark background
        draw = ImageDraw.Draw(img)

        try:
            # Try to load custom fonts
            title_font = ImageFont.truetype("roboto.ttf", 36)
            multiplier_font = ImageFont.truetype("roboto.ttf", 20)
            watermark_font = ImageFont.truetype("roboto.ttf", 36)
        except:
            # Fallback to default font if custom font fails
            title_font = ImageFont.load_default()
            multiplier_font = ImageFont.load_default()
            watermark_font = ImageFont.load_default()
            
        # Draw pegs
        for row in range(self.rows):
            num_pegs = row + 1
            start_x = (board_width - (num_pegs - 1) * horizontal_spacing) / 2
            y = vertical_spacing * (row + 1)
            
            for peg in range(num_pegs):
                x = start_x + peg * horizontal_spacing
                draw.ellipse((x - peg_radius, y - peg_radius, x + peg_radius, y + peg_radius), 
                             fill=(230, 230, 230, 255))  # White pegs
        
        # Draw multiplier buckets at the bottom
        bucket_width = horizontal_spacing * 0.9
        bucket_height = multiplier_height * 0.8
        bucket_y = board_height + (multiplier_height - bucket_height) / 2
        
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
        
        # Draw multiplier buckets
        for i, multiplier in enumerate(self.multiplier_table):
            x = horizontal_spacing * (i + 1)
            
            # Draw bucket
            bucket_color = get_multiplier_color(multiplier)
            draw.rectangle(
                (x - bucket_width/2, bucket_y, x + bucket_width/2, bucket_y + bucket_height),
                fill=bucket_color,
                outline=(255, 255, 255, 100)
            )
            
            # Draw multiplier text
            text_color = (255, 255, 255, 255)  # White text
            multiplier_text = f"{multiplier}x"
            text_bbox = draw.textbbox((0, 0), multiplier_text, font=multiplier_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = x - text_width / 2
            text_y = bucket_y + (bucket_height - text_height) / 2
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
        
        # Draw ball paths
        for path in self.ball_paths:
            prev_x = None
            prev_y = None
            
            for row, position in enumerate(path):
                # Calculate ball position
                y = vertical_spacing * (row + 1)
                
                if row == 0:
                    # First position (top of board)
                    x = board_width / 2
                else:
                    # Calculate x based on position in the bottom row
                    x = horizontal_spacing * (position + 1)
                
                # Draw line connecting previous position to current
                if prev_x is not None and prev_y is not None:
                    draw.line((prev_x, prev_y, x, y), fill=(255, 200, 200, 150), width=3)
                
                # Store current position for next iteration
                prev_x, prev_y = x, y
            
            # Draw final ball position
            if len(path) > 0:
                final_pos = path[-1]
                final_x = horizontal_spacing * (final_pos + 1)
                final_y = board_height
                
                # Draw the ball
                draw.ellipse(
                    (final_x - ball_radius, final_y - ball_radius, 
                     final_x + ball_radius, final_y + ball_radius),
                    fill=(255, 255, 255, 255),  # White ball
                    outline=(255, 0, 0, 255)   # Red outline
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
                net_profit = self.total_winnings - (self.bet_amount * self.drops)
                profit_display = f"**+{net_profit:.2f}**" if net_profit >= 0 else f"**{net_profit:.2f}**"
                
                embed = discord.Embed(
                    title=f"🎮 Plinko Game - Finished",
                    description=(
                        f"**Bet Amount:** {self.bet_amount} {self.currency_type}\n"
                        f"**Rows:** {self.rows}\n"
                        f"**Total Drops:** {self.drops}\n"
                        f"**Total Winnings:** {self.total_winnings:.2f} {self.currency_type}\n"
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
                    f"**Total Winnings:** {self.total_winnings:.2f} {self.currency_type}\n\n"
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


class PlinkoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        
    @commands.command(aliases=["plk"])
    async def plinko(self, ctx, bet_amount: str = None, difficulty: str = None, rows: int = None, currency_type: str = None):
        """Play Plinko with customizable risk and rows"""
        # Show help if no arguments
        if not bet_amount or not difficulty:
            embed = discord.Embed(
                title="🎮 How to Play Plinko",
                description=(
                    "**Plinko** is a game where you drop balls through a board full of pegs and win based on where they land!\n\n"
                    "**Usage:** `!plinko <amount> <difficulty> [rows] [currency_type]`\n"
                    "**Example:** `!plinko 100 medium 12` or `!plinko 50 high 8 tokens`\n\n"
                    "**Difficulty Levels:**\n"
                    "- **Low:** Lower risk, lower rewards\n"
                    "- **Medium:** Balanced risk and reward\n"
                    "- **High:** High risk, high potential rewards\n\n"
                    "**Rows:** Choose between 8-16 rows (default: 12)\n"
                    "**Currency:** tokens or credits (default: tokens)"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.send(embed=embed)
            
        # Validate inputs
        try:
            # Validate bet amount
            if bet_amount.lower() == "all" or bet_amount.lower() == "max":
                db = Users()
                user = db.fetch_user(ctx.author.id)
                
                if not user:
                    return await ctx.send(
                        embed=discord.Embed(
                            title="❌ User Not Found",
                            description="You need to register first. Try using some other commands first.",
                            color=0xFF0000
                        )
                    )
                
                currency = currency_type or "tokens"
                if currency.lower() not in ["tokens", "credits"]:
                    currency = "tokens"
                
                bet_amount = user.get(currency, 0)
                if bet_amount <= 0:
                    return await ctx.send(
                        embed=discord.Embed(
                            title="❌ Insufficient Balance",
                            description=f"You don't have any {currency} to bet.",
                            color=0xFF0000
                        )
                    )
            else:
                try:
                    bet_amount = float(bet_amount.replace(",", ""))
                except ValueError:
                    return await ctx.send(
                        embed=discord.Embed(
                            title="❌ Invalid Bet",
                            description="Please enter a valid number for your bet amount.",
                            color=0xFF0000
                        )
                    )
            
            # Validate rows
            if rows is None:
                rows = 12  # Default
            
            if not isinstance(rows, int) or rows < 8 or rows > 16:
                return await ctx.send(
                    embed=discord.Embed(
                        title="❌ Invalid Rows",
                        description="Please choose between 8-16 rows.",
                        color=0xFF0000
                    )
                )
                
            # Validate difficulty
            difficulty = difficulty.lower()
            if difficulty not in ["low", "medium", "high"]:
                return await ctx.send(
                    embed=discord.Embed(
                        title="❌ Invalid Difficulty",
                        description="Please choose from: low, medium, or high.",
                        color=0xFF0000
                    )
                )
                
            # Validate currency
            if currency_type is None:
                currency_type = "tokens"  # Default
            else:
                currency_type = currency_type.lower()
                if currency_type not in ["tokens", "credits"]:
                    return await ctx.send(
                        embed=discord.Embed(
                            title="❌ Invalid Currency",
                            description="Please use either tokens or credits.",
                            color=0xFF0000
                        )
                    )
                
            # Check for active game
            if ctx.author.id in self.ongoing_games:
                return await ctx.send(
                    embed=discord.Embed(
                        title="❌ Game In Progress",
                        description="You already have an active game. Please finish it first.",
                        color=0xFF0000
                    )
                )
                
            # Validate bet amount (minimum 0.01)
            if bet_amount < 0.01:
                return await ctx.send(
                    embed=discord.Embed(
                        title="❌ Invalid Bet",
                        description="Minimum bet amount is 0.01.",
                        color=0xFF0000
                    )
                )
                
            # Check user balance
            db = Users()
            user = db.fetch_user(ctx.author.id)
            
            if not user:
                return await ctx.send(
                    embed=discord.Embed(
                        title="❌ User Not Found",
                        description="You need to register first. Try using some other commands first.",
                        color=0xFF0000
                    )
                )
                
            if user.get(currency_type, 0) < bet_amount:
                return await ctx.send(
                    embed=discord.Embed(
                        title="❌ Insufficient Balance",
                        description=f"You don't have enough {currency_type} for this bet.",
                        color=0xFF0000
                    )
                )
                
            # Start the game
            game = PlinkoGame(self, ctx, bet_amount, difficulty, rows, ctx.author.id, currency_type)
            self.ongoing_games[ctx.author.id] = game
            await game.start_game()
            
        except Exception as e:
            print(f"Error in Plinko command: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)
    
    @plinko.error
    async def plinko_error(self, ctx, error):
        """Error handler for the plinko command"""
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                embed=discord.Embed(
                    title="❌ Invalid Arguments",
                    description=(
                        "Please use the correct format:\n"
                        "`!plinko <amount> <difficulty> [rows] [currency_type]`\n"
                        "Example: `!plinko 100 medium 12 tokens`"
                    ),
                    color=0xFF0000
                )
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=discord.Embed(
                    title="❌ Missing Arguments",
                    description=(
                        "You're missing required arguments.\n"
                        "Usage: `!plinko <amount> <difficulty> [rows] [currency_type]`\n"
                        "Example: `!plinko 100 medium 12 tokens`"
                    ),
                    color=0xFF0000
                )
            )
        else:
            print(f"Unhandled error in Plinko command: {error}")
            await ctx.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description=f"An unexpected error occurred. Please try again later.",
                    color=0xFF0000
                )
            )

def setup(bot):
    bot.add_cog(PlinkoCog(bot))
