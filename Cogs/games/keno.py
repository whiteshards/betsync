
import os
import io
import random
import discord
import asyncio
import datetime
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from colorama import Fore

# Payouts based on number of picks and hits
PAYOUTS = {
    1: {1: 3.72},
    2: {1: 1.1, 2: 15},
    3: {1: 0.5, 2: 2.7, 3: 100},
    4: {1: 0.0, 2: 1.7, 3: 12.0, 4: 900},
    5: {1: 0.0, 2: 1.2, 3: 6.0, 4: 80.0, 5: 1500.0},
    6: {1: 0.0, 2: 0.5, 3: 3.0, 4: 15.0, 5: 300.0},
    7: {1: 0.0, 2: 0.0, 3: 2.0, 4: 8.0, 5: 100.0},
    8: {1: 0.0, 2: 0.0, 3: 1.5, 4: 5.0, 5: 50.0},
    9: {1: 0.0, 2: 0.0, 3: 1.0, 4: 3.0, 5: 30.0},
    10: {1: 0.0, 2: 0.0, 3: 0.5, 4: 2.0, 5: 20.0}
}

# Win probability percentages
PROBABILITIES = {
    1: {1: 25.00},
    2: {1: 39.44, 2: 5.26},
    3: {1: 46.02, 2: 13.16, 3: 0.88},
    4: {1: 46.94, 2: 21.67, 3: 3.10, 4: 0.10},
    5: {1: 44.03, 2: 29.35, 3: 6.77, 4: 0.48, 5: 0.01},
    6: {1: 38.73, 2: 35.20, 3: 11.74, 4: 1.35, 5: 0.04},
    7: {1: 32.29, 2: 38.73, 3: 17.60, 4: 2.94, 5: 0.14},
    8: {1: 25.53, 2: 39.71, 3: 23.83, 4: 5.42, 5: 0.36},
    9: {1: 19.15, 2: 38.30, 3: 29.80, 4: 8.93, 5: 0.81},
    10: {1: 13.54, 2: 34.84, 3: 34.84, 4: 13.54, 5: 1.63}
}

class KenoView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used, timeout=120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.selected_numbers = []
        self.max_selections = 10
        self.message = None
        self.game_over = False
        
        # Add number buttons (creating a 5x4 grid for 20 numbers)
        for i in range(1, 21):
            row = (i-1) // 5
            self.add_item(KenoNumberButton(i, row))
            
        # Disable the play button initially (enable after at least one number is selected)
        self.update_play_button()
        
        # Auto-select the first number to ensure user has at least one pick
        self.selected_numbers.append(1)
        # Update the first button to show as selected
        for child in self.children:
            if isinstance(child, KenoNumberButton) and child.number == 1:
                child.style = discord.ButtonStyle.primary
                break
    
    def update_play_button(self):
        # Get the play button and update its state
        play_button = None
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "play":
                play_button = child
                break
                
        if play_button:
            play_button.disabled = len(self.selected_numbers) == 0
            
    @discord.ui.button(label="PLAY", style=discord.ButtonStyle.success, custom_id="play", row=4, disabled=True)
    async def play_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        if self.game_over:
            return await interaction.response.send_message("This game is already over!", ephemeral=True)
            
        # Disable buttons to prevent further interaction
        self.game_over = True
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(view=self)
        
        # Run the game
        await self.cog.run_keno_game(self.ctx, self, interaction.message)
        
    @discord.ui.button(label="CANCEL", style=discord.ButtonStyle.danger, custom_id="cancel", row=4)
    async def cancel_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        # Cancel the game and refund the user by adding the bet amount back
        db = Users()
        db.update_balance(self.ctx.author.id, self.bet_amount, self.currency_used, "$inc")
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(view=self)
        
        embed = discord.Embed(
            title="<:no:1344252518305234987> | Game Cancelled",
            description=f"Game cancelled. Your bet of {self.bet_amount} {self.currency_used} has been refunded.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        
        # Remove from ongoing games
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]
            
    async def on_timeout(self):
        # Handle timeout - game is considered played if user made no selections
        if not self.game_over and self.ctx.author.id in self.cog.ongoing_games:
            for child in self.children:
                child.disabled = True
                
            try:
                await self.message.edit(view=self)
                
                # If user didn't select any numbers, count it as a loss
                if len(self.selected_numbers) == 0:
                    # Record loss in database
                    db = Users()
                    
                    # Add loss to history
                    history_entry = {
                        "type": "loss",
                        "game": "keno",
                        "amount": self.bet_amount,
                        "timestamp": int(datetime.datetime.now().timestamp())
                    }
                    
                    db.collection.update_one(
                        {"discord_id": self.ctx.author.id},
                        {
                            "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                            "$inc": {"total_spent": self.bet_amount, "total_lost": 1, "total_played": 1}
                        }
                    )
                    
                    # Update server profit (positive for casino win)
                    server_db = Servers()
                    server_db.update_profit(self.ctx.guild.id, self.bet_amount)
                    
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Game Timed Out",
                        description=f"Game timed out. Your bet of {self.bet_amount} {self.currency_used} has been lost.",
                        color=discord.Color.red()
                    )
                    await self.ctx.reply(embed=embed)
                    
                else:
                    # If they selected numbers but didn't press play, run the game automatically
                    await self.cog.run_keno_game(self.ctx, self, self.message)
                    return
                    
            except Exception as e:
                print(f"Error in Keno timeout handler: {e}")
                pass
                
            # Remove from ongoing games
            del self.cog.ongoing_games[self.ctx.author.id]
            
class KenoNumberButton(discord.ui.Button):
    def __init__(self, number, row):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=str(number),
            custom_id=f"number_{number}",
            row=row
        )
        self.number = number
        
    async def callback(self, interaction):
        view = self.view
        
        if interaction.user.id != view.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        if view.game_over:
            return await interaction.response.send_message("This game is already over!", ephemeral=True)
            
        # Toggle selection
        if self.number in view.selected_numbers:
            view.selected_numbers.remove(self.number)
            self.style = discord.ButtonStyle.secondary
        else:
            # Check if maximum selections reached
            if len(view.selected_numbers) >= view.max_selections:
                return await interaction.response.send_message(f"You can select a maximum of {view.max_selections} numbers!", ephemeral=True)
                
            view.selected_numbers.append(self.number)
            self.style = discord.ButtonStyle.primary
            
        # Update the play button state
        view.update_play_button()
        
        # Update the options embed with current selections and probabilities
        embed = view.cog.create_options_embed(view.ctx.author, view.bet_amount, view.selected_numbers, view.currency_used)
        
        await interaction.response.edit_message(embed=embed, view=view)

class Keno(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        
    @commands.command(aliases=["k"])
    async def keno(self, ctx, bet_amount: str = None, currency_type: str = "tokens"):
        """
        Play a game of Keno
        
        Usage: !keno <bet amount> [currency_type]
        Example: !keno 100 tokens
        """
        # Show help if no bet amount
        if not bet_amount:
            embed = discord.Embed(
                title="🎮 How to Play Keno",
                description=(
                    "**Keno** is a lottery-style game where you select numbers and win based on matches!\n\n"
                    "**Usage:** `!keno <amount> [currency_type]`\n"
                    "**Example:** `!keno 100` or `!keno 100 tokens`\n\n"
                    "- **Select 1-10 numbers from a grid of 20**\n"
                    "- **5 winning numbers will be drawn**\n"
                    "- **Win based on how many of your picks match the draw**\n"
                    "- **Fewer selections = higher multipliers, but lower chance of big wins**\n"
                ),
                color=0x00FFAE
            )
            
            # Add paytable
            table_text = "**Picks | 1 Hit | 2 Hits | 3 Hits | 4 Hits | 5 Hits**\n"
            
            for picks in range(1, 11):
                row = f"**{picks}** | "
                for hits in range(1, 6):
                    if hits in PAYOUTS.get(picks, {}):
                        row += f"{PAYOUTS[picks][hits]}x | "
                    else:
                        row += "- | "
                table_text += row.rstrip("| ") + "\n"
                
            embed.add_field(name="📊 Payout Table", value=table_text, inline=False)
            embed.set_footer(text="BetSync Casino • Aliases: !k")
            return await ctx.reply(embed=embed)
            
        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        try:
            # Send loading message
            loading_emoji = emoji()["loading"]
            loading_embed = discord.Embed(
                title=f"{loading_emoji} | Preparing Keno Game...",
                description="Please wait while we set up your game.",
                color=0x00FFAE
            )
            loading_message = await ctx.reply(embed=loading_embed)
            
            # Import the currency helper
            from Cogs.utils.currency_helper import process_bet_amount
            
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)
            if not success:
                try:
                    await loading_message.delete()
                except:
                    pass
                return await ctx.reply(embed=error_embed)
                
            # Set up the game
            bet_amount_value = float(bet_amount)
            
            # Determine currency used
            tu = bet_info["tokens_used"]
            cu = bet_info["credits_used"]
            
            if tu > 0:
                currency_used = "tokens"
            elif cu > 0:
                currency_used = "credits"
            else:
                currency_used = "mixed/none"
                
            # Update loading message to indicate progress
            await loading_message.edit(embed=discord.Embed(
                title=f"{loading_emoji} | Setting Up Game...",
                description=f"Placing bet of {bet_amount} {currency_used}...",
                color=0x00FFAE
            ))
            
            # Create game view
            view = KenoView(self, ctx, bet_amount_value, currency_used)
            
            # Create initial embed
            initial_embed = self.create_options_embed(ctx.author, bet_amount_value, [], currency_used)
            
            # Delete loading message and start the game
            await loading_message.delete()
            
            # Send the Keno game embed
            game_message = await ctx.reply(embed=initial_embed, view=view)
            view.message = game_message
            
            # Mark game as ongoing
            self.ongoing_games[ctx.author.id] = {
                "bet_amount": bet_amount_value,
                "currency_used": currency_used,
                "view": view
            }
            
        except Exception as e:
            print(f"Keno error: {e}")
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="An error occurred while setting up the game.",
                color=0xFF0000
            )
            try:
                await loading_message.delete()
            except:
                pass
            await ctx.reply(embed=error_embed)
            
    def create_options_embed(self, user, bet_amount, selected_numbers, currency_used):
        """Creates the embed for the number selection screen"""
        num_picks = len(selected_numbers)
        
        embed = discord.Embed(
            title="🎮 Keno - Select Your Numbers",
            description=(
                f"Click on the buttons to select up to 10 numbers.\n"
                f"Press **PLAY** when you're ready to draw.\n\n"
                f"**Bet Amount:** {bet_amount} {currency_used}\n"
                f"**Numbers Selected:** {num_picks}/10"
            ),
            color=0x00FFAE
        )
        
        # Add payout info if numbers are selected
        if num_picks > 0:
            payout_text = "**Hits | Multiplier | Probability**\n"
            for hits in range(1, min(num_picks + 1, 6)):
                if hits in PAYOUTS.get(num_picks, {}):
                    multiplier = PAYOUTS[num_picks][hits]
                    probability = PROBABILITIES[num_picks][hits]
                    payout_text += f"**{hits}** | {multiplier}x | {probability}%\n"
            
            embed.add_field(name="📊 Potential Payouts", value=payout_text, inline=False)
        
        embed.set_footer(text="BetSync Casino • Select 1-10 numbers, then press PLAY")
        return embed
    
    async def generate_keno_image(self, selected_numbers, winning_numbers=None, game_over=False):
        """Generate the Keno board image"""
        # Set colors
        dark_bg = (26, 32, 44)
        tile_bg = (45, 55, 72)
        selected_color = (124, 58, 237)  # Purple
        matching_color = (0, 255, 0)    # Green for matches
        unmatched_winning_color = (255, 0, 0)  # Red for unselected winning numbers
        text_color = (255, 255, 255)
        
        # Image dimensions for 20 numbers (4x5 grid)
        width, height = 800, 600
        tile_size = 100
        margin = 20
        
        # Create image and draw object
        image = Image.new('RGB', (width, height), dark_bg)
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("arial.ttf", 42)
        except:
            font = ImageFont.load_default()
        
        # Draw grid of numbers
        for i in range(1, 21):
            row = (i-1) // 5
            col = (i-1) % 5
            
            x = margin + col * (tile_size + margin)
            y = margin + row * (tile_size + margin)
            
            # Determine tile color based on game state
            if game_over:
                if i in selected_numbers and i in winning_numbers:
                    # Matching numbers are green
                    tile_color = matching_color
                    text_col = (0, 0, 0)  # Black text on green
                elif i in winning_numbers:
                    # Winning but not selected are red
                    tile_color = unmatched_winning_color
                    text_col = text_color
                elif i in selected_numbers:
                    # Selected but not winning stays purple
                    tile_color = selected_color
                    text_col = text_color
                else:
                    # Other tiles stay default
                    tile_color = tile_bg
                    text_col = text_color
            else:
                # During selection phase
                if i in selected_numbers:
                    tile_color = selected_color
                else:
                    tile_color = tile_bg
                text_col = text_color
            
            # Draw tile
            draw.rectangle((x, y, x + tile_size, y + tile_size), fill=tile_color)
            
            # Draw number
            text_width = draw.textlength(str(i), font=font)
            text_x = x + (tile_size - text_width) // 2
            text_y = y + (tile_size - font.size) // 2 - 5  # Adjust for visual center
            
            draw.text((text_x, text_y), str(i), font=font, fill=text_col)
        
        # Save to bytes
        img_byte_array = io.BytesIO()
        image.save(img_byte_array, format="PNG")
        img_byte_array.seek(0)
        
        return img_byte_array
    
    async def run_keno_game(self, ctx, view, message):
        """Run the Keno game after numbers are selected"""
        try:
            user_id = ctx.author.id
            game_data = self.ongoing_games.get(user_id)
            
            if not game_data:
                return
                
            bet_amount = game_data["bet_amount"]
            currency_used = game_data["currency_used"]
            selected_numbers = view.selected_numbers
            num_selected = len(selected_numbers)
            
            if num_selected == 0:
                # No numbers selected, cancel game
                return
                
            # Generate winning numbers (5 random numbers from 1-20)
            all_numbers = list(range(1, 21))
            winning_numbers = random.sample(all_numbers, 5)
            
            # Find matching numbers
            matches = [num for num in selected_numbers if num in winning_numbers]
            num_matches = len(matches)
            
            # Calculate winnings
            multiplier = PAYOUTS.get(num_selected, {}).get(num_matches, 0)
            winnings = bet_amount * multiplier
            
            # Generate results image
            image_bytes = await self.generate_keno_image(selected_numbers, winning_numbers, True)
            file = discord.File(image_bytes, filename="keno_game.png")
            
            # Create results embed
            embed = discord.Embed(
                title="🎮 Keno Results",
                color=0x00FFAE
            )
            
            if num_matches > 0 and multiplier > 0:
                embed.description = (
                    f"**Congratulations!** You matched **{num_matches}** out of **{num_selected}** picks!\n\n"
                    f"**Bet:** {bet_amount} {currency_used}\n"
                    f"**Multiplier:** {multiplier}x\n"
                    f"**Win Amount:** {winnings:.2f} {currency_used}"
                )
                embed.color = discord.Color.green()
            else:
                embed.description = (
                    f"You matched **{num_matches}** out of **{num_selected}** picks.\n\n"
                    f"**Bet:** {bet_amount} {currency_used}\n"
                    f"**Result:** No win"
                )
                embed.color = discord.Color.red()
                
            embed.add_field(
                name="Your Picks",
                value=", ".join(str(n) for n in sorted(selected_numbers)),
                inline=True
            )
            
            embed.add_field(
                name="Winning Numbers",
                value=", ".join(str(n) for n in sorted(winning_numbers)),
                inline=True
            )
            
            embed.set_image(url="attachment://keno_game.png")
            embed.set_footer(text="BetSync Casino • Keno")
            
            await message.edit(embed=embed, file=file, view=view)
            
            # Update user balance and history
            db = Users()
            user_data = db.fetch_user(user_id)
            
            if not user_data:
                del self.ongoing_games[user_id]
                return
                
            # Handle win
            if num_matches > 0 and multiplier > 0:
                # Update user balance
                db.update_balance(user_id, winnings, currency_used, "$inc")
                
                # Add to user history
                history_entry = {
                    "type": "win",
                    "game": "keno",
                    "amount": winnings,
                    "timestamp": int(datetime.datetime.now().timestamp())
                }
                
                db.collection.update_one(
                    {"discord_id": user_id},
                    {
                        "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                        "$inc": {"total_earned": winnings, "total_won": 1, "total_played": 1}
                    }
                )
                
                # Update server profit (negative for casino loss)
                server_db = Servers()
                server_db.update_server_profit(ctx.guild.id, -1 * (winnings - bet_amount))
                
            else:
                # Add loss to history
                history_entry = {
                    "type": "loss",
                    "game": "keno",
                    "amount": bet_amount,
                    "timestamp": int(datetime.datetime.now().timestamp())
                }
                
                db.collection.update_one(
                    {"discord_id": user_id},
                    {
                        "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                        "$inc": {"total_spent": bet_amount, "total_lost": 1, "total_played": 1}
                    }
                )
                
                # Update server profit (positive for casino win)
                server_db = Servers()
                server_db.update_server_profit(ctx.guild.id, bet_amount)
                
            # Clean up
            del self.ongoing_games[user_id]
            
        except Exception as e:
            print(f"Error running Keno game: {e}")
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="An error occurred during the game.",
                color=0xFF0000
            )
            try:
                await message.edit(embed=embed)
            except:
                pass
                
            # Clean up
            if user_id in self.ongoing_games:
                del self.ongoing_games[user_id]

def setup(bot):
    bot.add_cog(Keno(bot))
