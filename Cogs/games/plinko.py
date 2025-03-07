
import discord
from discord.ext import commands
import random
import math
import asyncio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageColor
import io
import os
import urllib.request
from Cogs.utils.currency_helper import format_currency, check_funds, update_user_balance
from Cogs.utils.mongo import Users, Servers
from random import choice

# Multiplier data for different risk levels and rows
MULTIPLIERS = {
    "low_risk": {
        "8_rows": [5.5, 2.0, 1.1, 1.0, 0.5, 1.1, 1.0, 2.0, 5.5],
        "9_rows": [5.5, 2.0, 1.6, 1.0, 0.7, 0.7, 1.0, 1.6, 2.0, 5.5],
        "10_rows": [8.8, 2.9, 1.4, 1.1, 0.9, 0.5, 0.9, 1.1, 1.4, 2.9, 8.8],
        "11_rows": [8.3, 2.9, 1.9, 1.3, 1.0, 0.7, 0.7, 1.0, 1.3, 1.9, 2.9, 8.3],
        "12_rows": [9.9, 3.0, 1.6, 1.4, 1.1, 1.0, 0.5, 1.0, 1.1, 1.4, 1.6, 3.0, 9.9],
        "13_rows": [8.0, 4.0, 2.9, 1.8, 1.2, 0.9, 0.7, 0.7, 0.9, 1.2, 1.8, 2.9, 4.0, 8.0],
        "14_rows": [7.0, 4.0, 1.8, 1.4, 1.3, 1.1, 1.0, 0.5, 1.0, 1.1, 1.3, 1.4, 1.8, 4.0, 7.0],
        "15_rows": [15.0, 8.0, 3.0, 2.0, 1.5, 1.1, 1.0, 0.7, 0.7, 1.0, 1.1, 1.5, 2.0, 3.0, 8.0, 15.0],
        "16_rows": [15.5, 9.0, 2.0, 1.4, 1.3, 1.2, 1.1, 1.0, 0.5, 1.0, 1.1, 1.2, 1.3, 1.4, 2.0, 9.0, 15.5]
    },
    "medium_risk": {
        "8_rows": [12.0, 2.9, 1.3, 0.7, 0.4, 0.7, 1.3, 2.9, 12.0],
        "9_rows": [17.0, 3.8, 1.7, 0.9, 0.5, 0.5, 0.9, 1.7, 3.8, 17.0],
        "10_rows": [20.0, 4.8, 1.9, 1.4, 0.6, 0.4, 0.6, 1.4, 1.9, 4.8, 20.0],
        "11_rows": [23.0, 5.8, 2.9, 1.7, 0.7, 0.5, 0.5, 0.7, 1.7, 2.9, 5.8, 23.0],
        "12_rows": [30.0, 10.2, 3.8, 1.9, 1.1, 0.6, 0.3, 0.6, 1.1, 1.9, 3.8, 10.2, 30.0],
        "13_rows": [40.0, 12.0, 5.7, 2.8, 1.3, 0.7, 0.4, 0.4, 0.7, 1.3, 2.8, 5.7, 12.0, 40.0],
        "14_rows": [55.0, 15.0, 6.8, 3.7, 1.9, 1.0, 0.5, 0.2, 0.5, 1.0, 1.9, 3.7, 6.8, 15.0, 55.0],
        "15_rows": [85.0, 17.0, 10.5, 5.0, 3.0, 1.3, 0.5, 0.3, 0.3, 0.5, 1.3, 3.0, 5.0, 10.5, 17.0, 85.0],
        "16_rows": [105.0, 40.0, 10.0, 4.9, 3.0, 1.5, 1.0, 0.5, 0.3, 0.5, 1.0, 1.5, 3.0, 4.9, 10.0, 40.0, 105.0]
    },
    "high_risk": {
        "8_rows": [28.0, 3.9, 1.5, 0.3, 0.2, 0.3, 1.5, 3.9, 28.0],
        "9_rows": [41.0, 6.6, 2.0, 0.6, 0.2, 0.2, 0.6, 2.0, 6.6, 41.0],
        "10_rows": [75.0, 9.5, 2.9, 0.9, 0.3, 0.2, 0.3, 0.9, 2.9, 9.5, 75.0],
        "11_rows": [110.0, 13.0, 5.1, 1.4, 0.4, 0.2, 0.2, 0.4, 1.4, 5.1, 13.0, 110.0],
        "12_rows": [165.0, 22.0, 7.9, 2.0, 0.7, 0.2, 0.2, 0.2, 0.7, 2.0, 7.9, 22.0, 165.0],
        "13_rows": [250.0, 35.0, 10.0, 3.9, 1.0, 0.2, 0.2, 0.2, 0.2, 1.0, 3.9, 10.0, 35.0, 250.0],
        "14_rows": [400.0, 52.0, 17.0, 4.9, 1.9, 0.3, 0.2, 0.2, 0.2, 0.3, 1.9, 4.9, 17.0, 52.0, 400.0],
        "15_rows": [600.0, 80.0, 25.0, 7.8, 3.0, 0.5, 0.2, 0.2, 0.2, 0.2, 0.5, 3.0, 7.8, 25.0, 80.0, 600.0],
        "16_rows": [950.0, 126.0, 24.0, 8.2, 3.8, 2.0, 0.2, 0.2, 0.2, 0.2, 0.2, 2.0, 3.8, 8.2, 24.0, 126.0, 950.0]
    }
}

# Colors for multiplier backgrounds based on value
MULTIPLIER_COLORS = {
    "very_high": (255, 20, 20, 230),    # Red for highest multipliers
    "high": (255, 165, 0, 230),         # Orange
    "medium_high": (255, 255, 0, 230),  # Yellow
    "medium": (0, 200, 0, 230),         # Green
    "low": (0, 191, 255, 230),          # Blue
    "very_low": (75, 0, 130, 230)       # Indigo for lowest multipliers
}

def get_multiplier_color(multiplier, risk_level):
    """Determine color based on multiplier value and risk level"""
    if risk_level == "low_risk":
        if multiplier >= 5.0:
            return MULTIPLIER_COLORS["very_high"]
        elif multiplier >= 2.0:
            return MULTIPLIER_COLORS["high"]
        elif multiplier >= 1.0:
            return MULTIPLIER_COLORS["medium"]
        else:
            return MULTIPLIER_COLORS["low"]
    elif risk_level == "medium_risk":
        if multiplier >= 20.0:
            return MULTIPLIER_COLORS["very_high"]
        elif multiplier >= 5.0:
            return MULTIPLIER_COLORS["high"]
        elif multiplier >= 1.0:
            return MULTIPLIER_COLORS["medium"]
        else:
            return MULTIPLIER_COLORS["low"]
    else:  # high_risk
        if multiplier >= 50.0:
            return MULTIPLIER_COLORS["very_high"]
        elif multiplier >= 10.0:
            return MULTIPLIER_COLORS["high"]
        elif multiplier >= 1.0:
            return MULTIPLIER_COLORS["medium"]
        else:
            return MULTIPLIER_COLORS["low"]

class PlinkoGame:
    def __init__(self, cog, ctx, bet_amount, difficulty, rows, num_balls=1, tokens_used=0, credits_used=0):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty
        self.rows = rows
        self.num_balls = min(num_balls, 5)  # Cap at 5 balls
        self.tokens_used = tokens_used
        self.credits_used = credits_used
        self.currency_type = "credits" if credits_used > 0 else "tokens"
        self.risk_level = f"{difficulty}_risk"
        
        # Access multipliers for this configuration
        self.multipliers = MULTIPLIERS[self.risk_level][f"{rows}_rows"]
        
        # Game state
        self.results = []
        self.paths = []
        self.image = None
        
    async def play(self):
        """Run the Plinko game simulation"""
        total_payout = 0
        total_multiplier = 0
        
        # Simulate each ball drop
        for _ in range(self.num_balls):
            # Determine final position and path
            path, final_position = self.simulate_ball_drop()
            multiplier = self.multipliers[final_position]
            
            self.paths.append(path)
            self.results.append({
                "final_position": final_position,
                "multiplier": multiplier,
                "payout": round(self.bet_amount * multiplier / self.num_balls, 2)
            })
            
            total_multiplier += multiplier
            total_payout += self.bet_amount * multiplier / self.num_balls
        
        # Generate the game image
        self.image = self.generate_game_image()
        
        # Calculate average multiplier
        avg_multiplier = total_multiplier / self.num_balls
        
        return {
            "paths": self.paths,
            "results": self.results,
            "total_payout": round(total_payout, 2),
            "avg_multiplier": round(avg_multiplier, 2)
        }
        
    def simulate_ball_drop(self):
        """Simulate a single ball drop through the plinko board"""
        # Start at center position
        position = 0
        path = [position]
        
        # For each row, determine if ball goes left (-1) or right (+1)
        for row in range(self.rows):
            # Adjust probability based on difficulty
            if self.difficulty == "low":
                # More balanced probability
                left_prob = 0.5
            elif self.difficulty == "medium":
                # Slightly biased to outsides
                distance_to_center = abs(position)
                center_pull = 0.5 - (distance_to_center * 0.05)
                left_prob = center_pull if position > 0 else 1 - center_pull
            else:  # high difficulty
                # More biased to outsides
                distance_to_center = abs(position)
                center_pull = 0.5 - (distance_to_center * 0.1)
                left_prob = center_pull if position > 0 else 1 - center_pull
            
            # Determine direction
            if random.random() < left_prob:
                position -= 1  # left
            else:
                position += 1  # right
                
            path.append(position)
        
        # Convert position to multiplier index (add rows to center at 0)
        final_index = position + self.rows
        return path, final_index
        
    def generate_game_image(self):
        """Generate an image of the Plinko game with paths and results"""
        # Constants for image dimensions and features
        WIDTH = 900
        HEIGHT = 700
        PADDING = 60
        
        # Calculate peg size and spacing based on rows
        board_width = WIDTH - (2 * PADDING)
        board_height = HEIGHT - (2 * PADDING) - 100  # Extra space for multipliers at bottom
        
        horizontal_spacing = board_width / (self.rows * 2)
        vertical_spacing = board_height / self.rows
        peg_radius = int(min(horizontal_spacing, vertical_spacing) * 0.15)
        ball_radius = int(peg_radius * 1.3)
        
        # Create image with dark background
        image = Image.new('RGBA', (WIDTH, HEIGHT), (30, 34, 39, 255))
        draw = ImageDraw.Draw(image)
        
        # Load fonts
        try:
            font_path = "arial.ttf"
            title_font = ImageFont.truetype(font_path, 32)
            multiplier_font = ImageFont.truetype(font_path, 28)
            watermark_font = ImageFont.truetype(font_path, 50)
        except:
            # Fallback to default font
            title_font = ImageFont.load_default()
            multiplier_font = ImageFont.load_default()
            watermark_font = ImageFont.load_default()
        
        # Draw title
        title = f"Plinko - {self.difficulty.capitalize()} Risk ({self.rows} rows)"
        draw.text((WIDTH//2, 30), title, fill=(255, 255, 255), font=title_font, anchor="mm")
        
        # Draw watermark (semi-transparent)
        draw.text((WIDTH//2, HEIGHT//2), "BETSYNC", fill=(255, 255, 255, 30), 
                  font=watermark_font, anchor="mm")
        
        # Draw pegs
        for row in range(self.rows + 1):
            num_pegs = row + 1
            for peg in range(num_pegs):
                # Calculate peg position
                x = PADDING + (board_width//2) - (row * horizontal_spacing//2) + (peg * horizontal_spacing)
                y = PADDING + (row * vertical_spacing)
                
                # Draw peg (white circle)
                draw.ellipse((x-peg_radius, y-peg_radius, x+peg_radius, y+peg_radius), fill=(180, 180, 180))
        
        # Draw multiplier buckets
        bucket_width = board_width / len(self.multipliers)
        bucket_height = 80
        bucket_y = HEIGHT - PADDING - bucket_height
        
        for i, mult in enumerate(self.multipliers):
            x1 = PADDING + (i * bucket_width)
            y1 = bucket_y
            x2 = x1 + bucket_width
            y2 = y1 + bucket_height
            
            # Get appropriate color for this multiplier
            color = get_multiplier_color(mult, self.risk_level)
            
            # Draw rectangle for bucket
            draw.rectangle((x1, y1, x2, y2), fill=color)
            
            # Draw multiplier text
            text_x = x1 + (bucket_width / 2)
            text_y = y1 + (bucket_height / 2)
            draw.text((text_x, text_y), f"{mult}x", fill=(255, 255, 255), font=multiplier_font, anchor="mm")
        
        # Draw ball paths
        for ball_idx, path in enumerate(self.paths):
            # Use different colors for different balls
            ball_colors = [(255, 255, 255), (220, 220, 255), (255, 220, 220), 
                         (220, 255, 220), (255, 255, 220)]
            ball_color = ball_colors[ball_idx % len(ball_colors)]
            
            for row, offset in enumerate(path):
                if row >= len(path) - 1:
                    continue
                    
                current_offset = offset
                next_offset = path[row + 1]
                
                # Calculate current and next coordinates
                x1 = PADDING + (board_width//2) - (row * horizontal_spacing//2) + (current_offset * horizontal_spacing)
                y1 = PADDING + (row * vertical_spacing)
                
                x2 = PADDING + (board_width//2) - ((row+1) * horizontal_spacing//2) + (next_offset * horizontal_spacing)
                y2 = PADDING + ((row+1) * vertical_spacing)
                
                # Draw line for path
                draw.line((x1, y1, x2, y2), fill=ball_color, width=3)
            
            # Draw final ball position
            final_row = len(path) - 1
            final_offset = path[-1]
            
            # Get x-position for bucket
            final_index = final_offset + self.rows
            bucket_x = PADDING + (final_index * bucket_width) + (bucket_width / 2)
            
            # Draw ball at final position
            draw.ellipse((bucket_x-ball_radius, bucket_y-ball_radius, 
                          bucket_x+ball_radius, bucket_y+ball_radius), 
                         fill=ball_color, outline=(0, 0, 0))
        
        # Convert to bytes for Discord
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        buffer.seek(0)
        
        return buffer

class PlinkoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["plk"])
    async def plinko(self, ctx, bet_amount: str = None, difficulty: str = None, rows: int = None, 
                    num_balls: int = 1, currency_type: str = None):
        """Play Plinko - drop balls and win multipliers based on where they land!"""
        if not bet_amount or not difficulty or not rows:
            embed = discord.Embed(
                title="🎮 How to Play Plinko",
                description=(
                    "**Plinko** is a game where you drop balls through a board of pegs and win multipliers!\n\n"
                    "**Usage:** `!plinko <amount> <difficulty> <rows> [balls] [currency_type]`\n"
                    "**Example:** `!plinko 100 low 12` or `!plinko 50 high 16 3 tokens`\n\n"
                    "**Difficulty Levels:**\n"
                    "- **Low:** Balanced payouts with moderate risk\n"
                    "- **Medium:** Higher multipliers with increased risk\n"
                    "- **High:** Extreme multipliers with high risk\n\n"
                    "**Rows:** Choose from 8-16 rows\n"
                    "**Balls:** Drop 1-5 balls at once (default: 1)\n"
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

        # Validate difficulty
        difficulty = difficulty.lower()
        if difficulty not in ["low", "medium", "high"]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Please choose from the available difficulties: `low`, `medium`, or `high`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate rows
        if not rows or not isinstance(rows, int) or rows < 8 or rows > 16:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Rows",
                description="Please choose between 8-16 rows for your Plinko game.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate number of balls
        if not isinstance(num_balls, int) or num_balls < 1 or num_balls > 5:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Number of Balls",
                description="Please choose between 1-5 balls for your Plinko game.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate and check currency
        tokens_used = 0
        credits_used = 0
        
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You need to register first. Use a command to get started.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Default to credits if not specified
        if not currency_type:
            currency_type = "credits"
        
        # Validate bet amount
        try:
            if bet_amount.lower() == "all":
                if currency_type.lower() in ["token", "tokens"]:
                    bet_amount = user_data["tokens"]
                else:
                    bet_amount = user_data["credits"]
            else:
                bet_amount = float(bet_amount)
                if bet_amount <= 0:
                    raise ValueError("Bet must be positive")
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Please enter a valid bet amount.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if user has enough currency
        currency_check = check_funds(ctx.author.id, bet_amount, currency_type)
        if not currency_check['success']:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You don't have enough {currency_type} for this bet.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Set the currency used
        if currency_type.lower() in ["token", "tokens"]:
            tokens_used = bet_amount
        else:
            credits_used = bet_amount
            
        # Check if risk level and rows combination exists
        risk_level = f"{difficulty}_risk"
        rows_key = f"{rows}_rows"
        
        if risk_level not in MULTIPLIERS or rows_key not in MULTIPLIERS[risk_level]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Configuration",
                description="The selected difficulty and rows combination is not available.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Deduct bet amount
        if currency_type.lower() in ["token", "tokens"]:
            update_user_balance(ctx.author.id, -bet_amount, 0)
        else:
            update_user_balance(ctx.author.id, 0, -bet_amount)

        # Create and store game
        self.ongoing_games[ctx.author.id] = True
        
        # Create loading message
        embed = discord.Embed(
            title="🎮 Plinko Game Starting",
            description=f"Dropping {num_balls} ball{'s' if num_balls > 1 else ''} through the Plinko board...",
            color=0x00FFAE
        )
        message = await ctx.reply(embed=embed)
        
        # Create and play game
        game = PlinkoGame(
            cog=self,
            ctx=ctx,
            bet_amount=bet_amount,
            difficulty=difficulty,
            rows=rows,
            num_balls=num_balls,
            tokens_used=tokens_used,
            credits_used=credits_used
        )
        
        try:
            # Simulate game with delay for suspense
            await asyncio.sleep(1)
            result = await game.play()
            
            # Process result
            total_payout = result["total_payout"]
            avg_multiplier = result["avg_multiplier"]
            
            # Update user balance with winnings
            if currency_type.lower() in ["token", "tokens"]:
                update_user_balance(ctx.author.id, total_payout, 0)
            else:
                update_user_balance(ctx.author.id, 0, total_payout)
            
            # Format currency
            formatted_bet = format_currency(bet_amount, currency_type)
            formatted_payout = format_currency(total_payout, currency_type)
            
            # Create individual ball results text
            ball_results = ""
            for i, ball in enumerate(result["results"]):
                ball_results += f"Ball {i+1}: {ball['multiplier']}x → {format_currency(ball['payout'], currency_type)}\n"
            
            # Create result embed
            color = 0x00FF00 if total_payout > bet_amount else 0xFF0000
            
            embed = discord.Embed(
                title=f"🎮 Plinko Results - {difficulty.capitalize()} Risk",
                description=(
                    f"**Player:** {ctx.author.mention}\n"
                    f"**Bet:** {formatted_bet}\n"
                    f"**Rows:** {rows}\n"
                    f"**Balls:** {num_balls}\n\n"
                    f"**Average Multiplier:** {avg_multiplier}x\n"
                    f"**Total Payout:** {formatted_payout}\n\n"
                    f"**Ball Results:**\n{ball_results}"
                ),
                color=color
            )
            
            # Add game image
            file = discord.File(fp=game.image, filename="plinko_game.png")
            embed.set_image(url="attachment://plinko_game.png")
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            
            await message.edit(embed=embed, attachments=[file])
            
            # Update game statistics in database
            profit = total_payout - bet_amount
            db = Users()
            
            # Update user's played games count
            update_data = {
                "$inc": {
                    "total_played": 1,
                    "total_spent": bet_amount,
                    "total_earned": total_payout
                }
            }
            
            if profit > 0:
                update_data["$inc"]["total_won"] = 1
            else:
                update_data["$inc"]["total_lost"] = 1
                
            # Record game in history
            game_data = {
                "game": "plinko",
                "bet": bet_amount,
                "payout": total_payout,
                "profit": profit,
                "currency": currency_type,
                "timestamp": discord.utils.utcnow().timestamp(),
                "metadata": {
                    "difficulty": difficulty,
                    "rows": rows,
                    "balls": num_balls,
                    "multiplier": avg_multiplier,
                }
            }
            
            update_data["$push"] = {"history": {"$each": [game_data], "$position": 0}}
            db.update_user(ctx.author.id, update_data)
            
        except Exception as e:
            # Handle any errors
            print(f"Error in Plinko game: {e}")
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="An error occurred while playing Plinko. Your bet has been refunded.",
                color=0xFF0000
            )
            
            # Refund the bet
            if currency_type.lower() in ["token", "tokens"]:
                update_user_balance(ctx.author.id, bet_amount, 0)
            else:
                update_user_balance(ctx.author.id, 0, bet_amount)
                
            await message.edit(embed=embed)
        
        finally:
            # Remove from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

def setup(bot):
    bot.add_cog(PlinkoCog(bot))
