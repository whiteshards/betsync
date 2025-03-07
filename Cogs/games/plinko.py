
import discord
import random
import asyncio
import io
import time
import math
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import numpy as np
import os

class PlinkoButton(discord.ui.Button):
    def __init__(self, row, column, label, style, disabled=False, custom_id=None, multiplier=None):
        super().__init__(label=label, style=style, disabled=disabled, custom_id=custom_id)
        self.row = row
        self.column = column
        self.multiplier = multiplier

class PlinkoDropButton(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, difficulty, rows, currency_type, tokens_used=0, credits_used=0, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty.lower()
        self.rows = rows
        self.currency_type = currency_type
        self.tokens_used = tokens_used
        self.credits_used = credits_used
        self.message = None
        self.total_winnings = 0
        self.balls_dropped = 0
        self.dropped = False
        self.multipliers = self.get_multipliers()
        
    def get_multipliers(self):
        # Define multipliers for each difficulty and row count
        multipliers = {
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
        return multipliers[self.difficulty][f"{self.rows}_rows"]

    def get_difficulty_color(self):
        colors = {
            "low_risk": 0x00FFAE,  # Light blue/teal
            "medium_risk": 0xFFA500,  # Orange
            "high_risk": 0xFF3333,  # Red
        }
        return colors.get(self.difficulty, 0x00FFAE)

    @discord.ui.button(label="Drop", style=discord.ButtonStyle.primary, emoji="🔽", custom_id="drop_button")
    async def drop_button(self, button, interaction):
        # Ensure only the game owner can use the buttons
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)
        
        # Update this interaction for future edits
        await interaction.response.defer()
        
        # Get the database and deduct the bet amount
        db = Users()
        
        # Deduct the bet from the appropriate currency
        if self.currency_type == "tokens":
            current_balance = db.fetch_user_value(self.ctx.author.id, "tokens")
            if current_balance < self.bet_amount:
                return await interaction.followup.send("You don't have enough tokens!", ephemeral=True)
            db.update_balance(self.ctx.author.id, -self.bet_amount, "tokens", "$inc")
            self.tokens_used += self.bet_amount
        else:
            current_balance = db.fetch_user_value(self.ctx.author.id, "credits")
            if current_balance < self.bet_amount:
                return await interaction.followup.send("You don't have enough credits!", ephemeral=True)
            db.update_balance(self.ctx.author.id, -self.bet_amount, "credits", "$inc")
            self.credits_used += self.bet_amount
        
        # Update game stats in the database
        db.collection.update_one(
            {"discord_id": self.ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": self.bet_amount}}
        )
        
        # Simulate the ball drop
        path, landed_index, multiplier = self.simulate_plinko_drop()
        
        # Calculate winnings
        win_amount = self.bet_amount * multiplier
        self.total_winnings += win_amount
        
        # Generate the image
        image_buffer = await self.generate_plinko_image(path, landed_index)
        
        # Update stats based on win/loss
        if win_amount > self.bet_amount:
            # Win
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {"$inc": {"total_won": 1, "total_earned": win_amount}}
            )
        else:
            # Loss
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {"$inc": {"total_lost": 1}}
            )
        
        # Credit the winnings
        if self.currency_type == "tokens":
            db.update_balance(self.ctx.author.id, win_amount, "tokens", "$inc")
        else:
            db.update_balance(self.ctx.author.id, win_amount, "credits", "$inc")
        
        # Update the server profit/loss
        server_profit = self.bet_amount - win_amount
        db_server = Servers()
        db_server.update_server_profit(self.ctx.guild.id, server_profit)
        
        # Add to bet history
        bet_record = {
            "user_id": self.ctx.author.id,
            "username": self.ctx.author.name,
            "bet_amount": self.bet_amount,
            "currency_type": self.currency_type,
            "game_type": "plinko",
            "difficulty": self.difficulty,
            "rows": self.rows,
            "multiplier": multiplier,
            "win_amount": win_amount,
            "timestamp": int(time.time())
        }
        db_server.add_bet_to_history(self.ctx.guild.id, bet_record)
        
        # Increment ball count
        self.balls_dropped += 1
        
        # Create updated embed
        embed = discord.Embed(
            title=f"🎮 Plinko Game • {self.difficulty.capitalize()} Risk • {self.rows} Rows",
            description=(
                f"**Bet:** {self.bet_amount:,.2f} {self.currency_type.capitalize()}\n"
                f"**Multiplier:** {multiplier}x\n"
                f"**Win:** {win_amount:,.2f} {self.currency_type.capitalize()}\n"
                f"**Ball #{self.balls_dropped} landed at position:** {landed_index + 1}/{len(self.multipliers)}\n"
                f"**Total Winnings:** {self.total_winnings:,.2f} {self.currency_type.capitalize()}"
            ),
            color=self.get_difficulty_color()
        )
        
        embed.set_footer(text=f"BetSync Casino • {self.ctx.author.name}'s Plinko Game")
        file = discord.File(fp=image_buffer, filename="plinko.png")
        embed.set_image(url="attachment://plinko.png")
        
        # Update the message
        await self.message.edit(embed=embed, file=file, view=self)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="stop_button")
    async def stop_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)
        
        await interaction.response.defer()
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
            
        # Create the final embed
        embed = discord.Embed(
            title=f"🎮 Plinko Game Finished • {self.difficulty.capitalize()} Risk",
            description=(
                f"**Total Bet:** {self.bet_amount * self.balls_dropped:,.2f} {self.currency_type.capitalize()}\n"
                f"**Balls Dropped:** {self.balls_dropped}\n"
                f"**Total Winnings:** {self.total_winnings:,.2f} {self.currency_type.capitalize()}\n"
                f"**Net Profit:** {self.total_winnings - (self.bet_amount * self.balls_dropped):,.2f} {self.currency_type.capitalize()}"
            ),
            color=self.get_difficulty_color()
        )
        
        if self.balls_dropped > 0:
            embed.set_footer(text=f"BetSync Casino • {self.ctx.author.name}'s Plinko Game • Game Over")
            await self.message.edit(embed=embed, view=self)
        else:
            # If they never dropped a ball, refund their cooldown
            cmd = self.cog.bot.get_command('plinko')
            if cmd and cmd._buckets and cmd._buckets._cooldown:
                ctx = await self.cog.bot.get_context(self.ctx.message)
                if ctx:
                    bucket = cmd._buckets.get_bucket(ctx.message)
                    if bucket:
                        bucket.reset()
            
            embed.title = "🎮 Plinko Game Cancelled"
            embed.description = "Game has been cancelled without dropping any balls."
            await self.message.edit(embed=embed, view=self)
        
        # Remove from active games
        if self.ctx.author.id in self.cog.active_games:
            del self.cog.active_games[self.ctx.author.id]

    def simulate_plinko_drop(self):
        """Simulate a ball dropping through the Plinko board"""
        # Path array to track left/right decisions
        path = []
        
        # Current position (start in the middle)
        position = 0
        
        # For each row, decide if ball goes left or right
        for i in range(self.rows):
            # Randomize the direction (0 = left, 1 = right)
            # Higher probability to go toward center for balanced distribution
            if position < 0:
                # If on left side, more likely to go right (toward center)
                direction = random.choices([0, 1], weights=[40, 60])[0]
            elif position > 0:
                # If on right side, more likely to go left (toward center)
                direction = random.choices([0, 1], weights=[60, 40])[0]
            else:
                # If in center, equal chance
                direction = random.randint(0, 1)
            
            path.append(direction)
            
            # Update position: -1 for left, +1 for right
            position += (1 if direction == 1 else -1)
        
        # Calculate final landing position (index in multipliers array)
        # Convert from position (-rows..+rows) to index (0..multipliers-1)
        landing_index = (position + self.rows) // 2
        
        # Ensure it's within bounds
        max_index = len(self.multipliers) - 1
        landing_index = max(0, min(landing_index, max_index))
        
        # Get the multiplier at this position
        multiplier = self.multipliers[landing_index]
        
        return path, landing_index, multiplier

    async def generate_plinko_image(self, path, landed_index):
        """Generate a visual representation of the Plinko board with the ball's path"""
        # Set up colors based on difficulty
        colors = {
            "low_risk": (0, 255, 174),     # Light blue/teal
            "medium_risk": (255, 165, 0),  # Orange
            "high_risk": (255, 51, 51)     # Red
        }
        
        difficulty_color = colors.get(self.difficulty, (0, 255, 174))
        
        # Image dimensions
        peg_radius = 6
        cell_size = 50
        padding = 20
        
        # Calculate board width and height based on rows
        num_buckets = len(self.multipliers)
        max_pegs_in_row = num_buckets - 1
        board_width = (max_pegs_in_row + 1) * cell_size + 2 * padding
        board_height = (self.rows + 2) * cell_size + 2 * padding  # +2 for multiplier display and ball drop start
        
        # Create a new image with a dark background
        image = Image.new('RGBA', (board_width, board_height), (40, 40, 50, 255))
        draw = ImageDraw.Draw(image)
        
        # Try to load the font, use default if not available
        try:
            font = ImageFont.truetype("roboto.ttf", 18)
            small_font = ImageFont.truetype("roboto.ttf", 14)
            watermark_font = ImageFont.truetype("roboto.ttf", 24)
        except IOError:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
            watermark_font = font
            
        # Draw multiplier buckets at the bottom
        bucket_width = cell_size
        bucket_height = cell_size // 2
        
        for i, multiplier in enumerate(self.multipliers):
            # Calculate position
            x = padding + i * bucket_width
            y = board_height - bucket_height - padding // 2
            
            # Choose color based on multiplier value
            if multiplier >= 10:
                color = (255, 215, 0)  # Gold for high multipliers
            elif multiplier >= 2:
                color = (255, 165, 0)  # Orange for medium multipliers
            elif multiplier >= 1:
                color = (0, 200, 0)    # Green for breaking even
            else:
                color = (200, 0, 0)    # Red for losing
                
            # Draw bucket with rounded rectangle
            bucket_rect = [(x, y), (x + bucket_width, y + bucket_height)]
            draw.rectangle(bucket_rect, fill=color, outline=(255, 255, 255), width=1)
            
            # Draw multiplier text
            text = f"{multiplier}x"
            text_bbox = draw.textbbox((0, 0), text, font=small_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = x + (bucket_width - text_width) // 2
            text_y = y + (bucket_height - text_height) // 2
            draw.text((text_x, text_y), text, fill=(255, 255, 255), font=small_font)
            
            # Highlight the landing bucket
            if i == landed_index:
                highlight_outline = [(x - 2, y - 2), (x + bucket_width + 2, y + bucket_height + 2)]
                draw.rectangle(highlight_outline, outline=(255, 255, 255), width=2)
        
        # Draw pegs
        for row in range(self.rows):
            num_pegs = row + 1
            row_width = num_pegs * cell_size
            start_x = (board_width - row_width) // 2 + cell_size // 2
            
            for col in range(num_pegs):
                x = start_x + col * cell_size
                y = padding + (row + 1) * cell_size  # +1 to leave room at top for ball drop
                
                # Draw peg as a white circle
                draw.ellipse([(x - peg_radius, y - peg_radius), 
                              (x + peg_radius, y + peg_radius)], 
                             fill=(255, 255, 255))
        
        # Draw the ball's path
        if path:
            # Start position (middle top)
            ball_x = board_width // 2
            ball_y = padding + cell_size // 2
            ball_radius = 10
            
            # Draw starting position
            draw.ellipse([(ball_x - ball_radius, ball_y - ball_radius), 
                          (ball_x + ball_radius, ball_y + ball_radius)], 
                         fill=(255, 255, 255))
            
            # Track the ball's path
            for row, direction in enumerate(path):
                num_pegs = row + 1
                row_width = num_pegs * cell_size
                row_start_x = (board_width - row_width) // 2 + cell_size // 2
                
                # Calculate next position
                if direction == 1:  # Right
                    next_x = ball_x + cell_size // 2
                else:  # Left
                    next_x = ball_x - cell_size // 2
                    
                next_y = ball_y + cell_size
                
                # Draw line from current to next position
                draw.line([(ball_x, ball_y), (next_x, next_y)], fill=(255, 255, 255), width=2)
                
                # Update ball position
                ball_x = next_x
                ball_y = next_y
                
                # Draw ball at new position
                draw.ellipse([(ball_x - ball_radius, ball_y - ball_radius), 
                              (ball_x + ball_radius, ball_y + ball_radius)], 
                             fill=(255, 255, 255))
            
            # Draw line to final bucket
            bucket_x = padding + landed_index * bucket_width + bucket_width // 2
            bucket_y = board_height - bucket_height - padding // 2
            draw.line([(ball_x, ball_y), (bucket_x, bucket_y - ball_radius)], fill=(255, 255, 255), width=2)
            
            # Final ball position in bucket
            draw.ellipse([(bucket_x - ball_radius, bucket_y - ball_radius), 
                          (bucket_x + ball_radius, bucket_y + ball_radius)], 
                         fill=(255, 255, 255))
        
        # Add a subtle watermark in the middle
        watermark_text = "BetSync"
        watermark_bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        watermark_width = watermark_bbox[2] - watermark_bbox[0]
        watermark_height = watermark_bbox[3] - watermark_bbox[1]
        watermark_x = (board_width - watermark_width) // 2
        watermark_y = (board_height - watermark_height) // 2
        draw.text((watermark_x, watermark_y), watermark_text, fill=(255, 255, 255, 64), font=watermark_font)
        
        # Add a more visible watermark at bottom right
        watermark_text = "BetSync"
        watermark_bbox = draw.textbbox((0, 0), watermark_text, font=small_font)
        watermark_width = watermark_bbox[2] - watermark_bbox[0]
        watermark_x = board_width - watermark_width - 10
        watermark_y = board_height - 20
        draw.text((watermark_x, watermark_y), watermark_text, fill=(255, 255, 255, 128), font=small_font)
        
        # Save the image to a bytes buffer
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        
        return image_buffer

class PlinkoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.command(aliases=["plk"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def plinko(self, ctx, bet_amount=None, difficulty=None, rows=None, currency_type=None):
        """
        Play Plinko! Drop balls and win multipliers.
        Usage: !plinko <bet amount> <difficulty> <rows> [currency_type]
        Example: !plinko 100 medium 12 tokens
        """
        # Show usage if no arguments provided
        if bet_amount is None or difficulty is None or rows is None:
            embed = discord.Embed(
                title="🎮 How to Play Plinko",
                description=(
                    "**Plinko** is a game where balls bounce off pegs and land in buckets with different multipliers!\n\n"
                    "**Usage:** `!plinko <bet amount> <difficulty> <rows> [currency_type]`\n"
                    "**Example:** `!plinko 100 medium 12 tokens`\n\n"
                    "**Difficulty Levels:**\n"
                    "• **Low Risk** - Lower variance, more consistent wins\n"
                    "• **Medium Risk** - Balanced risk and reward\n"
                    "• **High Risk** - High volatility, chance for massive wins\n\n"
                    "**Rows:** Choose between 8-16 rows (more rows = more bounces)\n"
                    "**Currency:** tokens (default) or credits"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !plk")
            return await ctx.reply(embed=embed)
        
        # Check if user already has an active game
        if ctx.author.id in self.active_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing Plinko game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Default currency to tokens if not specified
        if currency_type is None:
            currency_type = "tokens"
        else:
            currency_type = currency_type.lower()
            if currency_type not in ["tokens", "credits"]:
                currency_type = "tokens"
        
        # Validate difficulty
        difficulty = difficulty.lower()
        if difficulty not in ["low", "medium", "high"]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Please choose from: low, medium, high",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Validate rows
        try:
            rows = int(rows)
            if rows < 8 or rows > 16:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Row Count",
                    description="Please choose between 8 and 16 rows.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Row Count",
                description="Please enter a valid number between 8 and 16.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Plinko Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Process bet amount using currency_helper
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)
        
        # If processing failed, return
        if not success:
            return
        
        # Extract processed bet information
        bet_amount = bet_info["amount"]
        tokens_used = bet_info["tokens_used"] if "tokens_used" in bet_info else 0
        credits_used = bet_info["credits_used"] if "credits_used" in bet_info else 0
        currency_type = bet_info["currency_type"]
        
        # Create difficulty-based colors
        difficulty_colors = {
            "low": 0x00FFAE,     # Light blue/teal
            "medium": 0xFFA500,  # Orange
            "high": 0xFF3333     # Red
        }
        
        # Create initial embed
        embed = discord.Embed(
            title=f"🎮 Plinko Game • {difficulty.capitalize()} Risk • {rows} Rows",
            description=(
                f"**Bet:** {bet_amount:,.2f} {currency_type.capitalize()}\n"
                f"**Risk Level:** {difficulty.capitalize()}\n"
                f"**Rows:** {rows}\n\n"
                f"Click the **Drop** button to start dropping balls!\n"
                f"Click **Stop** when you want to finish."
            ),
            color=difficulty_colors.get(difficulty, 0x00FFAE)
        )
        
        embed.set_footer(text=f"BetSync Casino • {ctx.author.name}'s Plinko Game")
        
        # Create basic plinko board display for initial message
        view = PlinkoDropButton(
            self, ctx, bet_amount, difficulty, rows, currency_type, 
            tokens_used=tokens_used, credits_used=credits_used
        )
        
        # Generate an empty plinko board image (no ball path yet)
        empty_board = await view.generate_plinko_image([], -1)
        file = discord.File(fp=empty_board, filename="plinko.png")
        embed.set_image(url="attachment://plinko.png")
        
        # Delete loading message and send the game
        await loading_message.delete()
        view.message = await ctx.reply(embed=embed, file=file, view=view)
        
        # Add to active games
        self.active_games[ctx.author.id] = view

    @plinko.before_invoke
    async def before_plinko(self, ctx):
        # Ensure user is registered
        db = Users()
        if db.fetch_user(ctx.author.id) == False:
            dump = {
                "discord_id": ctx.author.id,
                "tokens": 0,
                "credits": 0,
                "history": [],
                "total_deposit_amount": 0,
                "total_withdraw_amount": 0,
                "total_spent": 0,
                "total_earned": 0,
                "total_played": 0,
                "total_won": 0,
                "total_lost": 0
            }
            db.register_new_user(dump)

def setup(bot):
    bot.add_cog(PlinkoCog(bot))
