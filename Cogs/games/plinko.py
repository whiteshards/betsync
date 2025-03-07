
import discord
import random
import numpy as np
import time
import math
import io
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from colorama import Fore

class PlinkoDropButton(discord.ui.Button):
    def __init__(self, game):
        super().__init__(style=discord.ButtonStyle.success, label="Drop Ball", emoji="🔴")
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        # Only allow the game owner to use buttons
        if interaction.user.id != self.game.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Process the ball drop
        await self.game.drop_ball(interaction)


class PlinkoStopButton(discord.ui.Button):
    def __init__(self, game):
        super().__init__(style=discord.ButtonStyle.danger, label="Stop", emoji="🛑")
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        # Only allow the game owner to use buttons
        if interaction.user.id != self.game.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Process the stop action
        await self.game.stop_game(interaction)


class PlinkoView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        self.add_item(PlinkoDropButton(game))
        self.add_item(PlinkoStopButton(game))
    
    async def on_timeout(self):
        # Disable all buttons when timeout occurs
        for item in self.children:
            item.disabled = True
        
        # Update the message if it still exists
        if self.game.message:
            try:
                await self.game.message.edit(view=self)
                # Send a timeout message
                await self.game.ctx.send(
                    f"{self.game.ctx.author.mention}, your Plinko game has timed out! Final winnings: {self.game.total_winnings:.2f} credits."
                )
            except:
                pass  # Message may have been deleted or bot doesn't have permission

        # Clean up the game from memory
        if self.game.user_id in self.game.cog.ongoing_games:
            del self.game.cog.ongoing_games[self.game.user_id]


class PlinkoGame:
    def __init__(self, cog, ctx, bet_amount, difficulty, rows, user_id, currency_used, tokens_used, credits_used):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty.lower()
        self.rows = max(8, min(16, int(rows)))  # Ensure rows is between 8 and 16
        self.user_id = user_id
        self.currency_used = currency_used
        self.tokens_used = tokens_used 
        self.credits_used = credits_used
        self.message = None
        self.view = None
        self.total_winnings = 0
        self.num_balls_dropped = 0
        self.multiplier_values = self.get_multipliers_for_difficulty()
        
        # Set colors based on difficulty
        self.theme_colors = {
            "low": 0x00FF00,  # Green
            "medium": 0xFFA500,  # Orange
            "high": 0xFF0000   # Red
        }
        
        # Board dimensions for image generation
        self.cell_size = 40
        self.peg_radius = 5
        self.ball_radius = 8
        self.pin_spacing = self.cell_size
        self.board_width = self.pin_spacing * (self.rows + 1)
        self.board_height = self.pin_spacing * (self.rows + 2)  # Extra space for multipliers
        
        # Ball trail for animation effect
        self.ball_trails = []
        
        # Create initial board state
        self.init_board()
    
    def init_board(self):
        # Create the grid layout (this is just for visual reference)
        self.grid = []
        for row in range(self.rows):
            grid_row = []
            for col in range(row + 1):
                grid_row.append((col, row))
            self.grid.append(grid_row)
    
    def get_multipliers_for_difficulty(self):
        # Define multiplier values based on difficulty level
        if self.difficulty == "low":
            if self.rows == 8:
                return [5, 5, 2, 0.2, 0, 0.2, 2, 5, 5]
            elif self.rows == 9:
                return [8, 3, 1.4, 0.2, 0, 0, 0.2, 1.4, 3, 8]
            else:
                # For other row counts, generate appropriate multipliers
                # More rows means we need more multipliers
                num_buckets = self.rows + 1
                multipliers = []
                
                # Start with high values on the edges and decrease toward center
                for i in range(num_buckets):
                    # Calculate distance from center (normalized to 0-1)
                    center = num_buckets / 2 - 0.5
                    distance = abs(i - center) / center
                    
                    # Set multiplier based on distance (higher at edges)
                    if distance > 0.8:
                        mult = 8  # Highest at the very edges
                    elif distance > 0.6:
                        mult = 3  # High near edges
                    elif distance > 0.4:
                        mult = 1.5  # Medium
                    elif distance > 0.2:
                        mult = 0.5  # Low in middle
                    else:
                        mult = 0.2  # Lowest in very center
                    
                    multipliers.append(mult)
                
                return multipliers
                
        elif self.difficulty == "medium":
            if self.rows == 8:
                return [13, 7, 1, 0.4, 0, 0.4, 1, 7, 13]
            elif self.rows == 9:
                return [24, 4, 2, 0.4, 0, 0, 0.4, 2, 4, 24]
            else:
                # Generate medium difficulty multipliers
                num_buckets = self.rows + 1
                multipliers = []
                
                for i in range(num_buckets):
                    center = num_buckets / 2 - 0.5
                    distance = abs(i - center) / center
                    
                    if distance > 0.85:
                        mult = 24  # Very high at edges
                    elif distance > 0.7:
                        mult = 8  # High
                    elif distance > 0.5:
                        mult = 2  # Medium
                    elif distance > 0.3:
                        mult = 0.8  # Low
                    elif distance > 0.15:
                        mult = 0.4  # Very low
                    else:
                        mult = 0  # Zero in center
                    
                    multipliers.append(mult)
                
                return multipliers
                
        else:  # high difficulty
            if self.rows == 8:
                return [110, 14, 2, 0.4, 0, 0.4, 2, 14, 110]
            elif self.rows == 9:
                return [170, 8, 4, 0.7, 0, 0, 0.7, 4, 8, 170]
            else:
                # Generate high difficulty multipliers
                num_buckets = self.rows + 1
                multipliers = []
                
                for i in range(num_buckets):
                    center = num_buckets / 2 - 0.5
                    distance = abs(i - center) / center
                    
                    if distance > 0.9:
                        mult = 170  # Extremely high at edges
                    elif distance > 0.8:
                        mult = 40  # Very high near edges
                    elif distance > 0.65:
                        mult = 10  # High
                    elif distance > 0.45:
                        mult = 3  # Medium
                    elif distance > 0.25:
                        mult = 0.7  # Low
                    else:
                        mult = 0  # Zero/very low in center
                    
                    multipliers.append(mult)
                
                return multipliers
    
    def get_multiplier_colors(self):
        # Generate colors for each multiplier based on its value
        colors = []
        max_multiplier = max(self.multiplier_values)
        
        for mult in self.multiplier_values:
            if mult == 0:
                colors.append((100, 100, 100))  # Gray for zero
            elif mult < 1:
                # Shades of purple for less than 1x
                intensity = int(150 * (mult))
                colors.append((100, 50, 150 + intensity))
            elif mult <= 3:
                # Blue for small multipliers
                intensity = int(150 * (mult / 3))
                colors.append((0, 100 + intensity, 200))
            elif mult <= 10:
                # Green for medium multipliers
                intensity = int(150 * (mult / 10))
                colors.append((0, 180 + intensity, 100))
            elif mult <= 50:
                # Yellow/Orange for high multipliers
                intensity = int(150 * (mult / 50))
                colors.append((200 + intensity, 180, 0))
            else:
                # Red for very high multipliers
                intensity = min(255, int(200 + 55 * (mult / max_multiplier)))
                colors.append((intensity, 50, 50))
        
        return colors
    
    async def simulate_ball_drop(self):
        """Simulate the path of a dropped ball through the Plinko board"""
        path = []
        x_pos = self.rows / 2  # Start in the middle (0-indexed)
        
        # Add the starting position
        path.append((x_pos, 0))
        
        # Simulate the ball falling through each row
        for row in range(self.rows):
            # The ball has a 50% chance to go left or right at each peg
            # Adjust if needed for more realistic distribution
            direction = -0.5 if random.random() < 0.5 else 0.5
            x_pos += direction
            
            # Keep the ball within the bounds of the pins
            x_pos = max(0, min(row + 1, x_pos))
            
            # Add the new position to the path
            path.append((x_pos, row + 1))
        
        # The final bucket is the floor value of the final x_pos
        final_bucket = int(x_pos)
        multiplier = self.multiplier_values[final_bucket]
        win_amount = self.bet_amount * multiplier
        
        return {
            "path": path,
            "bucket": final_bucket,
            "multiplier": multiplier,
            "win_amount": win_amount
        }
    
    def generate_board_image(self, ball_path=None):
        """Generate an image of the Plinko board with the ball path"""
        # Define dimensions and create the base image
        width = self.board_width
        height = self.board_height
        
        # Create a new image with a dark background
        image = Image.new('RGBA', (width, height), (40, 40, 50, 255))
        draw = ImageDraw.Draw(image)
        
        # Load fonts
        try:
            font_path = "roboto.ttf"  # Use the font available in your system
            small_font = ImageFont.truetype(font_path, 14)
            medium_font = ImageFont.truetype(font_path, 18)
            large_font = ImageFont.truetype(font_path, 24)
        except IOError:
            # Fallback to default font if the specified font is not available
            small_font = ImageFont.load_default()
            medium_font = ImageFont.load_default()
            large_font = ImageFont.load_default()
        
        # Draw the pins
        for row in range(self.rows):
            for col in range(row + 1):
                # Calculate the x position with offset to center the pins
                x = (width / 2) + (col - row / 2) * self.pin_spacing
                y = (row + 1) * self.pin_spacing
                
                # Draw each pin as a white circle
                draw.ellipse(
                    (x - self.peg_radius, y - self.peg_radius, 
                     x + self.peg_radius, y + self.peg_radius), 
                    fill=(220, 220, 220)
                )
        
        # Draw the multiplier buckets
        bucket_width = width / len(self.multiplier_values)
        multiplier_colors = self.get_multiplier_colors()
        
        for i, mult in enumerate(self.multiplier_values):
            x1 = i * bucket_width
            x2 = (i + 1) * bucket_width
            y1 = height - self.cell_size
            y2 = height
            
            # Draw the bucket rectangle with the appropriate color
            draw.rectangle((x1, y1, x2, y2), fill=multiplier_colors[i])
            
            # Draw the multiplier text
            text_x = (x1 + x2) / 2
            text_y = (y1 + y2) / 2
            
            # Format multiplier text
            if mult >= 100:
                mult_text = f"{mult:.0f}x"
            elif mult >= 10:
                mult_text = f"{mult:.1f}x"
            else:
                mult_text = f"{mult:.1f}x"
            
            # Draw text with outline for better visibility
            text_color = (255, 255, 255)  # White text
            outline_color = (0, 0, 0)  # Black outline
            
            # Draw text shadow/outline
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text((text_x + dx, text_y + dy), mult_text, font=medium_font, fill=outline_color, anchor="mm")
            
            # Draw the main text
            draw.text((text_x, text_y), mult_text, font=medium_font, fill=text_color, anchor="mm")
        
        # Draw Betsync watermark in the middle (subtle)
        watermark_text = "BetSync"
        draw.text((width/2, height/2), watermark_text, font=large_font, fill=(255, 255, 255, 50), anchor="mm")
        
        # Draw Betsync watermark at the bottom right (more visible)
        draw.text((width - 10, height - 10), "BetSync", font=small_font, fill=(255, 255, 255, 180), anchor="rb")
        
        # Draw the ball trails if any
        for trail in self.ball_trails:
            path = trail["path"]
            bucket = trail["bucket"]
            for i in range(len(path) - 1):
                # Get the coordinates of each point in the path
                x1, y1 = path[i]
                x2, y2 = path[i + 1]
                
                # Convert to pixel coordinates
                px1 = (width / 2) + (x1 - path[0][0]) * self.pin_spacing
                py1 = (y1 + 1) * self.pin_spacing
                px2 = (width / 2) + (x2 - path[0][0]) * self.pin_spacing
                py2 = (y2 + 1) * self.pin_spacing
                
                # Draw line segment for ball trail
                draw.line((px1, py1, px2, py2), fill=(200, 200, 200, 100), width=2)
        
        # Draw the current ball path if provided
        if ball_path:
            path = ball_path["path"]
            for i in range(len(path) - 1):
                # Get the coordinates of each point in the path
                x1, y1 = path[i]
                x2, y2 = path[i + 1]
                
                # Convert to pixel coordinates
                px1 = (width / 2) + (x1 - path[0][0]) * self.pin_spacing
                py1 = (y1 + 1) * self.pin_spacing
                px2 = (width / 2) + (x2 - path[0][0]) * self.pin_spacing
                py2 = (y2 + 1) * self.pin_spacing
                
                # Draw line segment for current ball
                draw.line((px1, py1, px2, py2), fill=(255, 100, 100), width=3)
            
            # Draw the ball at its final position
            final_x, final_y = path[-1]
            ball_x = (width / 2) + (final_x - path[0][0]) * self.pin_spacing
            ball_y = (final_y + 1) * self.pin_spacing
            
            # Draw the ball as a white circle
            draw.ellipse(
                (ball_x - self.ball_radius, ball_y - self.ball_radius, 
                 ball_x + self.ball_radius, ball_y + self.ball_radius), 
                fill=(255, 255, 255)
            )
        
        # Convert the image to bytes
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes
    
    async def drop_ball(self, interaction):
        """Process a ball drop and update the game state"""
        # Simulate ball drop
        ball_result = await self.simulate_ball_drop()
        
        # Add to total winnings
        self.total_winnings += ball_result["win_amount"]
        self.num_balls_dropped += 1
        
        # Add to ball trails for display
        self.ball_trails.append(ball_result)
        # Keep only the last 5 trails to avoid clutter
        if len(self.ball_trails) > 5:
            self.ball_trails = self.ball_trails[-5:]
        
        # Generate the board image
        board_image = self.generate_board_image(ball_result)
        
        # Create an updated embed
        embed = self.create_game_embed(ball_result)
        
        # Update the message with the new embed and board image
        file = discord.File(board_image, filename="plinko.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self.view)
    
    async def stop_game(self, interaction):
        """End the game and process final results"""
        # Create a final embed
        embed = discord.Embed(
            title=f"🎮 Plinko Game Finished - {self.difficulty.capitalize()} Risk",
            description=f"Game completed with {self.num_balls_dropped} balls dropped",
            color=self.theme_colors[self.difficulty]
        )
        
        embed.add_field(
            name="Final Results",
            value=f"**Bet:** {self.bet_amount:.2f} credits\n"
                  f"**Total Winnings:** {self.total_winnings:.2f} credits\n"
                  f"**Profit/Loss:** {self.total_winnings - (self.bet_amount * self.num_balls_dropped):.2f} credits",
            inline=False
        )
        
        # Disable the buttons
        for item in self.view.children:
            item.disabled = True
        
        # Update the message
        board_image = self.generate_board_image(None)
        file = discord.File(board_image, filename="plinko.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self.view)
        
        # Process winnings
        if self.total_winnings > 0:
            # Update user balance
            db = Users()
            db.update_balance(self.user_id, self.total_winnings, "credits", "$inc")
            
            # Display confirmation message
            win_embed = discord.Embed(
                title="💰 Winnings Added!",
                description=f"**{self.total_winnings:.2f} credits** have been added to your balance.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=win_embed, ephemeral=True)
        
        # Clean up the game from memory
        if self.user_id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.user_id]
    
    def create_game_embed(self, last_drop=None):
        """Create the embed for the game display"""
        embed = discord.Embed(
            title=f"🎮 Plinko Game - {self.difficulty.capitalize()} Risk",
            description=f"Drop balls into the board and win multipliers!",
            color=self.theme_colors[self.difficulty]
        )
        
        embed.add_field(
            name="Game Info",
            value=f"**Bet:** {self.bet_amount:.2f} credits per ball\n"
                  f"**Rows:** {self.rows}\n"
                  f"**Balls Dropped:** {self.num_balls_dropped}",
            inline=True
        )
        
        embed.add_field(
            name="Winnings",
            value=f"**Total Winnings:** {self.total_winnings:.2f} credits",
            inline=True
        )
        
        if last_drop:
            embed.add_field(
                name="Last Drop",
                value=f"**Multiplier:** {last_drop['multiplier']}x\n"
                      f"**Won:** {last_drop['win_amount']:.2f} credits",
                inline=False
            )
        
        embed.set_image(url="attachment://plinko.png")
        embed.set_footer(text="BetSync Casino • Click 'Drop Ball' to drop a ball or 'Stop' to end the game")
        
        return embed


class PlinkoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
    
    @commands.command(aliases=["plk"])
    async def plinko(self, ctx, bet_amount: str = None, difficulty: str = None, rows: int = 8, currency_type: str = None):
        """Play Plinko - drop balls and win multipliers!"""
        # Show help if no arguments
        if not bet_amount or not difficulty:
            embed = discord.Embed(
                title="🎮 How to Play Plinko",
                description=(
                    "**Plinko** is a game where you drop balls into a board of pegs and win multipliers!\n\n"
                    "**Usage:** `!plinko <amount> <difficulty> [rows] [currency_type]`\n"
                    "**Example:** `!plinko 100 low 8` or `!plinko 100 high 12 tokens`\n\n"
                    "**Difficulty Levels:**\n"
                    "- **Low Risk** - Smaller multipliers, higher chance of winning\n"
                    "- **Medium Risk** - Balanced multipliers and win chances\n"
                    "- **High Risk** - Huge multipliers on the edges, but harder to win\n\n"
                    "**Rows:** Choose between 8-16 rows (more rows = more paths)\n"
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
        if difficulty.lower() not in ["low", "medium", "high"]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Please choose a valid difficulty: `low`, `medium`, or `high`",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Validate rows (ensure between 8-16)
        if not isinstance(rows, int) or rows < 8 or rows > 16:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Row Count",
                description="Rows must be between 8 and 16.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Process bet amount
        try:
            # Check if bet_amount contains 'all'
            if 'all' in bet_amount.lower() or 'max' in bet_amount.lower():
                # Get user's balance
                db = Users()
                user_data = db.fetch_user(ctx.author.id)
                if not user_data:
                    return await ctx.reply("You don't have an account. Use `!signup` to create one.")
                
                tokens = user_data.get('tokens', 0)
                credits = user_data.get('credits', 0)
                
                if currency_type and currency_type.lower() in ['token', 'tokens', 't']:
                    bet_amount = tokens
                    currency_used = "tokens"
                elif currency_type and currency_type.lower() in ['credit', 'credits', 'c']:
                    bet_amount = credits
                    currency_used = "credits"
                else:
                    # If no currency specified or invalid, use the highest balance
                    if tokens >= credits:
                        bet_amount = tokens
                        currency_used = "tokens"
                    else:
                        bet_amount = credits
                        currency_used = "credits"
            else:
                # Convert bet_amount to float
                bet_amount = float(bet_amount)
                
                # Determine currency type if not specified
                if not currency_type:
                    # Default to tokens if not specified
                    currency_used = "tokens"
                else:
                    currency_type = currency_type.lower()
                    if currency_type in ['token', 'tokens', 't']:
                        currency_used = "tokens"
                    elif currency_type in ['credit', 'credits', 'c']:
                        currency_used = "credits"
                    else:
                        # Invalid currency type
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Invalid Currency",
                            description="Please specify a valid currency: `tokens` or `credits`",
                            color=0xFF0000
                        )
                        return await ctx.reply(embed=embed)
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Please enter a valid bet amount.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Ensure positive bet
        if bet_amount <= 0:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Bet amount must be greater than 0.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if user has enough balance
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        if not user_data:
            return await ctx.reply("You don't have an account. Use `!signup` to create one.")
        
        # Get user balances
        tokens = user_data.get('tokens', 0)
        credits = user_data.get('credits', 0)
        
        # Check if user has enough of the specified currency
        if currency_used == "tokens" and tokens < bet_amount:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"You don't have enough tokens. You have {tokens:.2f} tokens.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        elif currency_used == "credits" and credits < bet_amount:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"You don't have enough credits. You have {credits:.2f} credits.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Set the tokens and credits used
        tokens_used = bet_amount if currency_used == "tokens" else 0
        credits_used = bet_amount if currency_used == "credits" else 0
        
        # Create loading message
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Creating Plinko Game...",
            description="Please wait while we set up your game.",
            color=discord.Color.blue()
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Create a new Plinko game
            game = PlinkoGame(
                self, ctx, bet_amount, difficulty, rows, 
                ctx.author.id, currency_used, tokens_used, credits_used
            )
            
            # Generate the initial board image
            board_image = game.generate_board_image()
            
            # Create the game embed
            embed = game.create_game_embed()
            
            # Create the view for the game
            game.view = PlinkoView(game)
            
            # Send the game message
            file = discord.File(board_image, filename="plinko.png")
            game.message = await ctx.reply(embed=embed, file=file, view=game.view)
            
            # Save the game in ongoing games
            self.ongoing_games[ctx.author.id] = game
            
            # Delete the loading message
            await loading_message.delete()
        except Exception as e:
            print(f"Error creating Plinko game: {e}")
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="There was an error creating your Plinko game. Please try again.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
    
    @plinko.error
    async def plinko_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Missing Arguments",
                description="Please provide all required arguments. Use `!plinko` for help.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Arguments",
                description="Please provide valid arguments. Use `!plinko` for help.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
        else:
            print(f"Plinko error: {error}")
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="An unexpected error occurred. Please try again.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(PlinkoCog(bot))
