import discord
import asyncio
import random
import os
import numpy as np
import io
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from matplotlib.collections import PatchCollection
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.currency_helper import process_bet_amount
from Cogs.utils.mongo import Users

class Plinko(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.multipliers = {
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

    # Helper function to format currency (since it's missing from currency_helper)
    def format_currency(self, amount, currency_type):
        """Format currency display"""
        if isinstance(amount, (int, float)):
            return f"{amount:.2f} {currency_type}"
        return f"{amount} {currency_type}"

    # Helper function to check funds (since it's missing from currency_helper)
    async def check_funds(self, user_id, amount, currency_type):
        """Check if a user has sufficient funds"""
        db = Users()
        user_data = db.fetch_user(user_id)

        if not user_data:
            return False, None

        if currency_type == "tokens":
            if user_data.get("tokens", 0) >= amount:
                return True, user_data
            return False, user_data
        elif currency_type == "credits":
            if user_data.get("credits", 0) >= amount:
                return True, user_data
            return False, user_data
        return False, user_data

    # Helper function to update user balance (since it's missing from currency_helper)
    async def update_user_balance(self, user_id, amount, currency_type, operation="subtract"):
        """Update user balance"""
        db = Users()
        user_data = db.fetch_user(user_id)

        if not user_data:
            return False

        if operation == "subtract":
            if currency_type == "tokens":
                db.update_user_tokens(user_id, user_data["tokens"] - amount)
            elif currency_type == "credits":
                db.update_user_credits(user_id, user_data["credits"] - amount)
        elif operation == "add":
            if currency_type == "tokens":
                db.update_user_tokens(user_id, user_data["tokens"] + amount)
            elif currency_type == "credits":
                db.update_user_credits(user_id, user_data["credits"] + amount)

        # Update stats
        if operation == "subtract":
            db.update_user_total_spent(user_id, user_data.get("total_spent", 0) + amount)
            db.update_user_total_played(user_id, user_data.get("total_played", 0) + 1)
        elif operation == "add" and amount > 0:
            db.update_user_total_earned(user_id, user_data.get("total_earned", 0) + amount)

        return True

    def simulate_plinko_drop(self, rows, risk_level):
        """Simulate a Plinko drop and return final position"""
        position = 0
        for _ in range(rows):
            # 50% chance to go left or right at each peg
            if random.random() < 0.5:
                position += 1
            else:
                position -= 1

        # Adjust position to be within valid range (0 to rows)
        final_position = rows + position
        return max(0, min(final_position, rows * 2))

    def create_plinko_image(self, rows, risk_level, drop_results):
        """Create a visualization of the Plinko game"""
        # Set up the figure and axis
        fig, ax = plt.subplots(figsize=(10, 12))

        # Background color
        ax.set_facecolor('#1a1a1a')
        fig.patch.set_facecolor('#1a1a1a')

        # Draw pegs
        pegs = []
        for row in range(rows):
            for col in range(row + 1):
                x = col * 2 - row
                y = -row
                circle = Circle((x, y), 0.3, color='#4a4a4a')
                pegs.append(circle)

        # Add pegs to the plot
        ax.add_collection(PatchCollection(pegs, match_original=True))

        # Draw paths and final positions for each drop
        colors = ['#ffffff', '#f5f542', '#42f557', '#42aef5', '#f542f5']

        for i, (final_pos, path) in enumerate(drop_results):
            color = colors[i % len(colors)]

            # Draw the path
            for j, (x, y) in enumerate(path[:-1]):
                next_x, next_y = path[j+1]
                ax.plot([x, next_x], [y, next_y], color=color, linewidth=2, alpha=0.7)

            # Draw the ball at final position
            final_x, final_y = path[-1]
            circle = Circle((final_x, final_y), 0.4, color=color)
            ax.add_patch(circle)

        # Draw multiplier buckets
        multis = self.multipliers[risk_level][f"{rows}_rows"]
        bucket_width = 1.8

        for i, multi in enumerate(multis):
            x = i * 2 - rows
            y = -rows - 1

            # Determine color based on multiplier value
            if multi >= 10:
                color = '#ff4d4d'  # Red for high multipliers
            elif multi >= 3:
                color = '#ffcc00'  # Yellow for medium multipliers
            else:
                color = '#66ff66' if multi >= 1 else '#ff6666'  # Green for >= 1, red for < 1

            rect = Rectangle((x - bucket_width/2, y - 0.5), bucket_width, 1, 
                             color=color, alpha=0.7)
            ax.add_patch(rect)

            # Add multiplier text
            ax.text(x, y, f"{multi}x", 
                    ha='center', va='center', 
                    color='white', fontsize=12, fontweight='bold')

        # Set axis limits and remove ticks
        margin = 2
        ax.set_xlim(-rows - margin, rows + margin)
        ax.set_ylim(-rows - 3, 1)
        ax.set_xticks([])
        ax.set_yticks([])

        # Add watermark
        ax.text(0, -rows/2, "BetSync", 
                ha='center', va='center', color='white', alpha=0.15,
                fontsize=40, fontweight='bold', rotation=45)

        # Add title
        title = f"PLINKO - {risk_level.replace('_', ' ').title()} Risk - {rows} Rows"
        ax.set_title(title, color='white', fontsize=16, pad=10)

        # Convert plot to image
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close()

        return buf

    def simulate_drop_path(self, rows):
        """Simulate the full path of a plinko drop"""
        path = [(0, 0)]  # Start at the top center
        position = 0

        for row in range(rows):
            # 50% chance to go left or right at each peg
            if random.random() < 0.5:
                position += 1
                x_change = 1
            else:
                position -= 1
                x_change = -1

            x = path[-1][0] + x_change
            y = path[-1][1] - 1
            path.append((x, y))

        # Final position in the bottom row
        final_position = rows + position
        final_position = max(0, min(final_position, rows * 2))

        return final_position, path

    @commands.command(name="plinko", aliases=["plk"])
    async def plinko(self, ctx, bet_amount=None, difficulty=None, rows=None, num_balls=None, currency_type=None):
        """
        Play a game of Plinko
        Usage: !plinko (plk) <bet amt> <difficulty> <rows (8-16)> <amt of balls>(optional) <currency_type> (optional)
        """
        # Show usage if no arguments provided
        if not bet_amount:
            embed = discord.Embed(
                title="Plinko Game | Usage",
                description="Drop balls on pegs and win multipliers based on where they land!",
                color=0x3498db
            )
            embed.add_field(
                name="Command Format",
                value="`!plinko <bet_amount> <difficulty> <rows> [balls] [currency]`\n"
                      "`!plk <bet_amount> <difficulty> <rows> [balls] [currency]`",
                inline=False
            )
            embed.add_field(
                name="Parameters",
                value="• `bet_amount`: Amount to bet (number or 'all')\n"
                      "• `difficulty`: 'low', 'medium', 'high'\n"
                      "• `rows`: Number of rows (8-16)\n"
                      "• `balls`: Number of balls to drop (1-5, default: 1)\n"
                      "• `currency`: 'tokens' or 'credits' (default: tokens)",
                inline=False
            )
            embed.add_field(
                name="Examples",
                value="`!plinko 100 low 8`\n"
                      "`!plk 50 medium 10 3 credits`",
                inline=False
            )
            embed.set_footer(text="BetSync Casino")
            return await ctx.reply(embed=embed)

        # Parse and validate difficulty
        if not difficulty or difficulty.lower() not in ["low", "medium", "high"]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Please choose a valid difficulty: `low`, `medium`, or `high`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        risk_level_map = {
            "low": "low_risk",
            "medium": "medium_risk",
            "high": "high_risk"
        }
        risk_level = risk_level_map[difficulty.lower()]

        # Parse and validate rows
        try:
            rows = int(rows) if rows else 8
            if rows < 8 or rows > 16:
                raise ValueError()
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Rows",
                description="Please choose a number of rows between 8 and 16.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Parse and validate number of balls
        try:
            num_balls = int(num_balls) if num_balls else 1
            if num_balls < 1 or num_balls > 5:
                raise ValueError()
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Number of Balls",
                description="Please choose between 1 and 5 balls.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Process the bet amount
        loading_message = await ctx.reply("🎮 | Processing your plinko game...")
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        bet_amount_value = bet_info["amount"]
        currency_used = bet_info["currency"]

        # Simulate the drops
        total_winnings = 0
        drop_results = []
        win_details = []

        for _ in range(num_balls):
            final_pos, path = self.simulate_drop_path(rows)
            multiplier = self.multipliers[risk_level][f"{rows}_rows"][final_pos]
            ball_win = bet_amount_value * multiplier / num_balls
            total_winnings += ball_win
            drop_results.append((final_pos, path))
            win_details.append(f"Ball landed on {multiplier}x → {ball_win:.2f}")

        # Create the game image
        image_buffer = self.create_plinko_image(rows, risk_level, drop_results)

        # Update the user's balance
        db = Users()

        # Subtract bet amount
        if currency_used == "tokens":
            db.update_user_tokens(ctx.author.id, bet_info["user_data"]["tokens"] - bet_amount_value)
        else:
            db.update_user_credits(ctx.author.id, bet_info["user_data"]["credits"] - bet_amount_value)

        # Add winnings
        if total_winnings > 0:
            if currency_used == "tokens":
                db.update_user_tokens(ctx.author.id, bet_info["user_data"]["tokens"] - bet_amount_value + total_winnings)
            else:
                db.update_user_credits(ctx.author.id, bet_info["user_data"]["credits"] - bet_amount_value + total_winnings)

        # Update stats
        db.update_user_total_spent(ctx.author.id, bet_info["user_data"].get("total_spent", 0) + bet_amount_value)
        db.update_user_total_played(ctx.author.id, bet_info["user_data"].get("total_played", 0) + 1)

        if total_winnings > bet_amount_value:
            db.update_user_total_earned(ctx.author.id, bet_info["user_data"].get("total_earned", 0) + total_winnings)
            db.update_user_total_won(ctx.author.id, bet_info["user_data"].get("total_won", 0) + 1)
            result_text = "🏆 Win!"
            color = 0x00FF00
        else:
            db.update_user_total_lost(ctx.author.id, bet_info["user_data"].get("total_lost", 0) + 1)
            result_text = "❌ Loss"
            color = 0xFF0000

        # Create result embed
        net_profit = total_winnings - bet_amount_value

        embed = discord.Embed(
            title=f"Plinko Game | {risk_level.replace('_', ' ').title()}, {rows} Rows",
            description=f"**{ctx.author.mention}'s Plinko Result**\n{result_text}",
            color=color
        )

        embed.add_field(
            name="Game Details",
            value=f"**Bet:** {bet_amount_value:.2f} {currency_used}\n"
                 f"**Balls Dropped:** {num_balls}\n"
                 f"**Total Win:** {total_winnings:.2f} {currency_used}\n"
                 f"**Net Profit:** {net_profit:.2f} {currency_used}",
            inline=False
        )

        embed.add_field(
            name="Ball Results",
            value="\n".join(win_details),
            inline=False
        )

        embed.set_footer(text="BetSync Casino")

        # Send the result with the image
        await loading_message.delete()
        await ctx.reply(embed=embed, file=discord.File(fp=image_buffer, filename="plinko.png"))

def setup(bot):
    bot.add_cog(Plinko(bot))