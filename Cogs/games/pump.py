import discord
import random
import asyncio
import time
import os
import io
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from colorama import Fore
from Cogs.utils.emojis import emoji

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, difficulty, currency_type="tokens", timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty
        self.currency_type = currency_type
        self.message = None

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True
        # Update the message with disabled buttons
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green, emoji="🎈")
    async def play_again_button(self, button, interaction):
        # Only the original player can use this button
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the view to prevent double clicks
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with the same parameters
        await self.cog.pump(self.ctx, str(self.bet_amount), self.difficulty, self.currency_type)

class PumpGameView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, difficulty, tokens_used=0, credits_used=0, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = difficulty.lower()
        self.tokens_used = tokens_used
        self.credits_used = credits_used
        self.currency_type = "credits"  # Always pay out in credits
        self.message = None
        self.current_pumps = 0
        self.max_pumps = 12
        self.game_over = False
        self.cashout_clicked = False

        # Set difficulty-specific parameters
        if self.difficulty == "easy":
            self.probability = 0.75
            self.multipliers = [1.00, 1.27, 1.69, 2.25, 3.00, 4.00, 5.34, 7.13, 9.49, 12.65, 16.87, 22.49, 29.98]
        elif self.difficulty == "medium":
            self.probability = 0.50
            self.multipliers = [1.00, 1.90, 3.80, 7.60, 15.20, 30.40, 60.80, 121.60, 243.20, 486.40, 972.80, 1945.60, 3891.20]
        elif self.difficulty == "hard":
            self.probability = 0.30
            self.multipliers = [1.00, 3.17, 10.56, 35.19, 117.28, 390.95, 1303.15, 4344.32, 14480.00, 48288.50, 161019.30, 536257.00, 1788234.00]
        elif self.difficulty == "extreme":
            self.probability = 0.15
            self.multipliers = [1.00, 6.33, 42.22, 281.48, 1876.54, 12511.60, 83333.34, 556206.00, 3707317.00, 24675324.70, 164502000.00, 1099530000.00, 7330200000.00]

        # Current multiplier (starts at 1x)
        self.current_multiplier = self.multipliers[0]

        # Add the buttons
        self.update_buttons()

    def update_buttons(self):
        """Update the buttons based on game state"""
        # Clear existing buttons
        self.clear_items()

        # If game is over, don't add any buttons
        if self.game_over:
            return

        # Add pump button
        pump_button = discord.ui.Button(
            label="Pump", 
            style=discord.ButtonStyle.danger, 
            emoji="🎈",
            custom_id="pump"
        )
        pump_button.callback = self.pump_callback
        self.add_item(pump_button)

        # Add cash out button if not on the first pump
        if self.current_pumps > 0:
            cash_out_button = discord.ui.Button(
                label="Cash Out", 
                style=discord.ButtonStyle.success, 
                emoji="💰",
                custom_id="cash_out"
            )
            cash_out_button.callback = self.cash_out_callback
            self.add_item(cash_out_button)

    def calculate_payout(self):
        """Calculate the payout based on current multiplier"""
        return round(self.bet_amount * self.current_multiplier, 2)

    def get_balloon_display(self):
        """Generate a text-based balloon representation based on current pumps"""
        # Create a visual representation of balloon size with ASCII
        if self.current_pumps == 0:
            return "🎈 Balloon is ready to be pumped!"

        # Add visual representation of pressure
        filled = "█" * self.current_pumps
        empty = "▒" * (self.max_pumps - self.current_pumps)

        # Choose color emoji based on pump count
        if self.current_pumps < 4:
            color = "🟢"
        elif self.current_pumps < 8:
            color = "🟡"
        else:
            color = "🔴"

        pressure_bar = f"{color} |{filled}{empty}| {self.current_pumps}/{self.max_pumps}"

        return pressure_bar


    async def create_embed(self, status="playing"):
        """Create game embed with current state"""
        # Format bet description
        if self.tokens_used > 0 and self.credits_used > 0:
            bet_description = f"**{self.tokens_used} tokens** + **{self.credits_used} credits**"
        elif self.tokens_used > 0:
            bet_description = f"**{self.tokens_used} tokens**"
        else:
            bet_description = f"**{self.credits_used} credits**"

        # Get balloon visual representation
        balloon_display = self.get_balloon_display()

        # First create the embed structure
        embed = None
        file = None

        # Then try to generate the image
        try:
            # Import required for BytesIO if needed
            import io

            image_buffer = await self.cog.generate_balloon_image(self.current_multiplier)
            if image_buffer:
                # Create a copy of the buffer to ensure it's open and seekable
                buffer_copy = io.BytesIO(image_buffer.getvalue())
                file = discord.File(fp=buffer_copy, filename="balloon.png")
                print("Successfully created balloon image file")
            else:
                print("Failed to generate balloon image: buffer is None")
        except Exception as e:
            print(f"Error generating image: {e}")
            import traceback
            traceback.print_exc()
            file = None

        currency = "credits"

        if status == "playing":
            embed = discord.Embed(
                title="🎈 Pump Game",
                description=f"**Keep pumping the balloon for bigger rewards, but don't let it pop!**",
                color=0xFF3366
            )
            embed.add_field(
                name="📊 Pressure",
                value=balloon_display,
                inline=False
            )
            embed.add_field(
                name="💰 Bet & Potential Win",
                value=f"**Bet:** {bet_description}\n**Multiplier:** {self.current_multiplier:.2f}x\n**Potential Win:** {self.calculate_payout():.2f} credits",
                inline=False
            )
            if self.current_pumps > 0:
                embed.set_footer(text=f"BetSync Casino • Keep pumping for bigger rewards or cash out now!")
            else:
                embed.set_footer(text=f"BetSync Casino • Pump to start!")

        elif status == "win_pump":
            embed = discord.Embed(
                title="🎈 Pump Game - Successful Pump!",
                description=f"**The balloon got bigger!**",
                color=0x00FF00
            )
            embed.add_field(
                name="📊 Pressure",
                value=balloon_display,
                inline=False
            )
            embed.add_field(
                name="💰 Bet & Potential Win",
                value=f"**Bet:** {bet_description}\n**Multiplier:** {self.current_multiplier:.2f}x\n**Potential Win:** {self.calculate_payout():.2f} credits",
                inline=False
            )
            if self.current_pumps == self.max_pumps:
                embed.set_footer(text=f"BetSync Casino • Max pumps reached! Automatic cashout!")
            else:
                embed.set_footer(text=f"BetSync Casino • Continue pumping or cash out now!")

        elif status == "lose":
            embed = discord.Embed(
                title="🎈 Pump Game - POPPED!",
                description=f"**Oh no! The balloon popped after {self.current_pumps} pumps!**\n\nBetter luck next time!",
                color=0xFF0000
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Bet:** {bet_description}\n**Lost Amount:** {self.bet_amount:.2f} credits",
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • The balloon popped!")

        elif status == "cash_out":
            payout = self.calculate_payout()
            profit = payout - self.bet_amount
            embed = discord.Embed(
                title="🎈 Pump Game - Cashed Out!",
                description=f"**Wise decision!** You've cashed out after **{self.current_pumps}/{self.max_pumps}** pumps!",
                color=0x00FF00
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Bet:** {self.bet_amount:.2f} credits\n**Multiplier:** {self.current_multiplier:.2f}x\n**Winnings:** {payout:.2f} credits\n**Profit:** {profit:.2f} credits",
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • You've secured your winnings!")

        elif status == "max_pumps":
            payout = self.calculate_payout()
            profit = payout - self.bet_amount
            embed = discord.Embed(
                title="🎈 Pump Game - Maximum Pumps!",
                description=f"**Amazing!** You've reached the maximum of **{self.max_pumps}** pumps! The balloon is at its limit!",
                color=0x00FF00
            )
            embed.add_field(
                name="💰 Game Results",
                value=f"**Bet:** {self.bet_amount:.2f} credits\n**Multiplier:** {self.current_multiplier:.2f}x\n**Winnings:** {payout:.2f} credits\n**Profit:** {profit:.2f} credits",
                inline=False
            )
            embed.set_footer(text=f"BetSync Casino • Maximum pumps achieved! Automatic cashout!")

        embed.set_author(name=f"Player: {self.ctx.author.name}", icon_url=self.ctx.author.avatar.url)
        if file:
            embed.set_image(url=f"attachment://balloon.png")
        return embed, file

    async def pump_callback(self, interaction):
        """Handle clicks on pump button"""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Check if the pump is successful based on difficulty probability
        if random.random() < self.probability:
            # Pump successful
            self.current_pumps += 1

            # Update the current multiplier
            self.current_multiplier = self.multipliers[self.current_pumps]

            # If max pumps reached, auto cash out
            if self.current_pumps >= self.max_pumps:
                self.game_over = True
                await interaction.response.defer()
                return await self.process_cashout(interaction)

            # Update buttons for next pump
            self.update_buttons()

            # Send updated embed
            embed, file = await self.create_embed(status="win_pump")

            if file:
                # Use the file directly, it's already a discord.File
                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=self)

        else:
            # Pump failed - balloon pops
            self.game_over = True
            self.clear_items()  # Remove all buttons

            # Send the game over message
            embed, file = await self.create_embed(status="lose")
            # No image for popped balloon
            if file:
                discord_file = discord.File(fp=file, filename="balloon.png")
                await interaction.response.edit_message(embed=embed, view=None, attachments=[discord_file])
            else:
                await interaction.response.edit_message(embed=embed, view=None)

            # Process the loss
            await self.process_loss()

    async def cash_out_callback(self, interaction):
        """Process player's decision to cash out"""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.game_over = True
        self.cashout_clicked = True

        # Disable all buttons
        self.clear_items()

        # Acknowledge the interaction first
        await interaction.response.defer()

        # Process the cashout
        await self.process_cashout(interaction)

    async def on_timeout(self):
        """Handle timeout"""
        if not self.game_over and self.current_pumps > 0:
            # Auto cash out if game times out and player has pumped at least once
            await self.process_cashout(None)
        elif not self.game_over:
            # Just disable buttons if no pumps yet
            self.clear_items()
            try:
                await self.message.edit(view=self)
            except:
                pass

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

    async def process_cashout(self, interaction):
        """Process cashout - update database and end game"""
        payout = self.calculate_payout()

        db = Users()
        try:
            # Update user's balance
            db.update_balance(self.ctx.author.id, payout, "credits", "$inc")

            # Create win history entry
            win_entry = {
                "type": "win",
                "game": "pump",
                "bet": self.bet_amount,
                "amount": payout,
                "multiplier": self.current_multiplier,
                "pumps": self.current_pumps,
                "difficulty": self.difficulty,
                "timestamp": int(time.time())
            }

            # Update user history and stats
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {
                    "$push": {"history": {"$each": [win_entry], "$slice": -100}},
                    "$inc": {
                        "total_played": 1,
                        "total_won": 1,
                        "total_earned": payout
                    }
                }
            )

            # Update server stats if in a guild
            if isinstance(self.ctx.channel, discord.TextChannel):
                server_db = Servers()
                server_profit = self.bet_amount - payout

                # Update server profit
                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$inc": {"profit": server_profit}}
                )

                # Add to server history
                server_bet_entry = win_entry.copy()
                server_bet_entry.update({
                    "user_id": self.ctx.author.id,
                    "user_name": self.ctx.author.name
                })

                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
                )
        except Exception as e:
            print(f"Error processing cashout: {e}")
            return False

        # Create cashout embed with appropriate status
        status = "max_pumps" if self.current_pumps >= self.max_pumps else "cash_out"
        cashout_embed, file = await self.create_embed(status=status)

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty,
            "tokens" if self.tokens_used > 0 else "credits"  # Use tokens if they were used originally
        )

        # Update the message
        if file:
            # Use the file directly, it's already a discord.File
            await self.message.edit(embed=cashout_embed, view=play_again_view, attachments=[file])
        else:
            await self.message.edit(embed=cashout_embed, view=play_again_view)
        play_again_view.message = self.message

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True

    async def process_loss(self):
        """Process loss - update database and end game"""
        db = Users()

        # Create loss history entry
        loss_entry = {
            "type": "loss",
            "game": "pump",
            "bet": self.bet_amount,
            "amount": self.bet_amount,
            "multiplier": 0,
            "pumps": self.current_pumps,
            "difficulty": self.difficulty,
            "timestamp": int(time.time())
        }

        # Update user history and stats directly in one operation
        db.collection.update_one(
            {"discord_id": self.ctx.author.id},
            {
                "$push": {"history": {"$each": [loss_entry], "$slice": -100}},
                "$inc": {
                    "total_played": 1,
                    "total_lost": 1,
                    "total_spent": self.bet_amount
                }
            }
        )

        # Update server stats if in a guild
        if isinstance(self.ctx.channel, discord.TextChannel):
            server_db = Servers()

            # Update server profit directly
            server_db.collection.update_one(
                {"server_id": self.ctx.guild.id},
                {"$inc": {"profit": self.bet_amount}}
            )

            # Add to server history
            server_bet_entry = loss_entry.copy()
            server_bet_entry.update({
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name
            })

            # Update server history directly
            server_db.collection.update_one(
                {"server_id": self.ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
            )

        # Create play again view
        play_again_view = PlayAgainView(
            self.cog, 
            self.ctx, 
            self.bet_amount, 
            self.difficulty,
            "tokens" if self.tokens_used > 0 else "credits"  # Use tokens if they were used originally
        )

        # Add play again button
        await self.message.edit(view=play_again_view)
        play_again_view.message = self.message

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True


class PumpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.balloon_asset = "assests/balloon.png" #Path to your balloon asset.  Ensure this path is correct.
        self.watermark = None  # Not using image watermark, using text instead

        try:
            # Import required modules
            from PIL import Image, ImageDraw, ImageFont

            # Try roboto font first (included in repo), fall back to arial
            try:
                self.font = ImageFont.truetype("roboto.ttf", 36)
            except:
                self.font = ImageFont.truetype("arial.ttf", 36)
        except FileNotFoundError:
            print("Warning: Font not found. Using default font.")
            self.font = None

    async def generate_balloon_image(self, multiplier):
        try:
            # Make sure we import the required modules
            import io
            from PIL import Image, ImageDraw, ImageFont

            # Create a dark blue background (similar to the image)
            bg_color = (14, 23, 35)  # Dark blue background
            bg_width, bg_height = 800, 600
            background = Image.new('RGBA', (bg_width, bg_height), bg_color)

            # Check if balloon asset exists
            import os
            if not os.path.exists(self.balloon_asset):
                print(f"Error: Balloon asset not found at {self.balloon_asset}")
                return None

            # Open and resize the balloon based on multiplier
            try:
                base_balloon = Image.open(self.balloon_asset).convert("RGBA")
            except Exception as e:
                print(f"Error opening balloon image: {e}")
                return None

            width, height = base_balloon.size
            scale_factor = min(1 + (multiplier - 1) * 0.2, 3)  # Scale up to 3x max size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)

            # Resize the balloon
            resized_balloon = base_balloon.resize((new_width, new_height), Image.LANCZOS)

            # Position the balloon in the center
            x_position = (bg_width - new_width) // 2
            y_position = (bg_height - new_height) // 2
            background.paste(resized_balloon, (x_position, y_position), resized_balloon)

            # Add multiplier text in the center of the balloon
            draw = ImageDraw.Draw(background)
            multiplier_text = f"{multiplier:.2f}x"

            # Use the proper font with drop shadow
            try:
                font = ImageFont.truetype("roboto.ttf", 60)
            except:
                font = ImageFont.load_default()

            # Calculate text position for centering
            text_bbox = draw.textbbox((0, 0), multiplier_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = (bg_width - text_width) // 2
            text_y = (bg_height - text_height) // 2

            # Draw drop shadow with increased offset for better visibility
            draw.text((text_x + 4, text_y + 4), multiplier_text, font=font, fill=(0, 0, 0, 255)) #Increased shadow darkness
            # Draw text
            draw.text((text_x, text_y), multiplier_text, font=font, fill=(255, 255, 255))

            # Add "BetSync Casino" watermark at bottom right
            watermark_text = "BetSync Casino"
            watermark_font_size = 24
            try:
                watermark_font = ImageFont.truetype("roboto.ttf", watermark_font_size)
            except:
                watermark_font = ImageFont.load_default()

            # Calculate watermark position
            watermark_bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
            watermark_width = watermark_bbox[2] - watermark_bbox[0]
            watermark_x = bg_width - watermark_width - 20
            watermark_y = bg_height - watermark_font_size - 10

            # Draw semi-transparent watermark
            draw.text((watermark_x, watermark_y), watermark_text, font=watermark_font, fill=(255, 255, 255, 128))

            # Save to BytesIO
            output = io.BytesIO()
            background.save(output, format="PNG")
            output.seek(0)
            return output

        except FileNotFoundError as e:
            print(f"Error: File not found - {e}")
            return None
        except Exception as e:
            print(f"An error occurred during image generation: {e}")
            import traceback
            traceback.print_exc()
            return None



    @commands.command(aliases=["balloon"])
    async def pump(self, ctx, bet_amount: str = None, difficulty: str = None, currency_type: str = None):
        """Play Pump - pump a balloon for increasingly higher multipliers!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🎈 How to Play Pump",
                description=(
                    "**Pump** is a game where you inflate a balloon for increasingly higher multipliers!\n\n"
                    "**Usage:** `!pump <amount> <difficulty> [currency_type]`\n"
                    "**Example:** `!pump 100 easy` or `!pump 50 hard credits`\n\n"
                    "**Difficulty Levels:**\n"
                    "- **Easy:** 75% success rate per pump\n"
                    "- **Medium:** 50% success rate per pump\n"
                    "- **Hard:** 30% success rate per pump\n"
                    "- **Extreme:** 15% success rate per pump\n\n"
                    "Each successful pump increases your multiplier. You can cash out at any time, but if the balloon pops, you lose your bet!"
                ),
                color=0xFF3366
            )
            embed.set_footer(text="BetSync Casino • Aliases: !balloon")
            return await ctx.reply(embed=embed)

        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Pump Game...",
            description="Please wait while we set up your game.",
            color=0xFF3366
        )
        loading_message = await ctx.reply(embed=loading_embed)

        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if user_data == False:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        if not difficulty or difficulty.lower() not in ["easy", "medium", "hard", "extreme"]:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Difficulty",
                description="Please choose a valid difficulty: `easy`, `medium`, `hard`, or `extreme`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        if not currency_type:
            currency_type = "tokens"
        elif currency_type.lower() in ["t", "tokens"]:
            currency_type = "tokens"
        elif currency_type.lower() in ["c", "credits"]:
            currency_type = "credits"
        else:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description="Please specify a valid currency: `tokens` or `credits`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        try:
            if isinstance(bet_amount, str) and bet_amount.lower() in ['all', 'max']:
                bet_amount_value = user_data[currency_type]
            else:
                if isinstance(bet_amount, str) and bet_amount.lower().endswith('k'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000
                elif isinstance(bet_amount, str) and bet_amount.lower().endswith('m'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000000
                else:
                    bet_amount_value = float(bet_amount)

            bet_amount_value = round(float(bet_amount_value), 2)

            if bet_amount_value <= 0:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        except ValueError:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Please enter a valid number or 'all'.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        tokens_balance = user_data.get('tokens', 0)
        credits_balance = user_data.get('credits', 0)

        tokens_used = 0
        credits_used = 0

        if currency_type == "tokens":
            if bet_amount_value <= tokens_balance:
                tokens_used = bet_amount_value
                db.update_balance(ctx.author.id, tokens_balance - tokens_used, "tokens")
            elif bet_amount_value <= tokens_balance + credits_balance:
                tokens_used = tokens_balance
                credits_used = bet_amount_value - tokens_balance
                db.update_balance(ctx.author.id, 0, "tokens")
                db.update_balance(ctx.author.id, credits_balance - credits_used, "credits")
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Funds",
                    description=f"You don't have enough funds. Your balance: **{tokens_balance:.2f} tokens** and **{credits_balance:.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:  # credits
            if bet_amount_value <= credits_balance:
                credits_used = bet_amount_value
                db.update_balance(ctx.author.id, credits_balance - credits_used, "credits")
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Funds",
                    description=f"You don't have enough credits. Your balance: **{credits_balance:.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        total_bet = tokens_used + credits_used

        game_view = PumpGameView(
            self, 
            ctx, 
            total_bet, 
            difficulty, 
            tokens_used=tokens_used,
            credits_used=credits_used,
            timeout=60  # 1 minute timeout
        )

        await loading_message.delete()

        # Create initial embed
        initial_embed, file = await game_view.create_embed(status="playing")

        if file:
            game_message = await ctx.reply(embed=initial_embed, view=game_view, file=file)
        else:
            game_message = await ctx.reply(embed=initial_embed, view=game_view)
        game_view.message = game_message

        self.ongoing_games[ctx.author.id] = {
            "game_type": "pump",
            "game_view": game_view,
            "start_time": time.time()
        }


def setup(bot):
    bot.add_cog(PumpCog(bot))