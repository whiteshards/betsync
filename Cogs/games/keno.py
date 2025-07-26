# Implementing curse lose mechanics and webhook functionality for the Keno game.
import os
import io
import random
import discord
import asyncio
import datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from colorama import Fore
import time
import aiohttp

# Payouts based on number of picks and hits
PAYOUTS = {
    1: {1: 3.72},
    2: {1: 1, 2: 10},
    3: {1: 0.5, 2: 1.5, 3: 25},
    4: {1: 0.0, 2: 1.35, 3: 10.0, 4: 100},
    5: {1: 0.0, 2: 0.0, 3: 3, 4: 50.0, 5: 100.0},
    6: {1: 0.0, 2: 0.5, 3: 3.0, 4: 12.0, 5: 300.0},
    7: {1: 0.0, 2: 0.0, 3: 2.0, 4: 8.0, 5: 100.0},
    8: {1: 0.0, 2: 0.0, 3: 1.5, 4: 5.0, 5: 50.0},
    9: {1: 0.0, 2: 0.0, 3: 1.0, 4: 3.0, 5: 30.0},
    10: {1: 0.0, 2: 0.0, 3: 0.5, 4: 2.0, 5: 20.0}
}

def generate_paytable_image():
    """Generate a visually appealing payout table image"""
    # Image dimensions and settings - larger size for better fit
    width, height = 1000, 700
    bg_color = (25, 25, 25)  # Dark background
    header_color = (40, 40, 40)  # Slightly lighter for header
    cell_color = (34, 34, 34)
    alt_cell_color = (30, 30, 30)
    highlight_color = (128, 0, 255)  # Purple for highlights
    text_color = (255, 255, 255)

    # Create image and draw object
    image = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    try:
        # Try to load fonts - better sizes for readability
        title_font = ImageFont.truetype("arial.ttf", 42)
        header_font = ImageFont.truetype("arial.ttf", 24)
        cell_font = ImageFont.truetype("arial.ttf", 22)
        subtitle_font = ImageFont.truetype("arial.ttf", 20)
    except:
        # Fallback fonts
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    # Draw title
    title = "BETSYNC CASINO"
    title_width = draw.textlength(title, font=title_font)
    draw.text(((width - title_width) // 2, 30), title, font=title_font, fill=highlight_color)

    # Draw subtitle
    subtitle = "Payout Table"
    subtitle_width = draw.textlength(subtitle, font=subtitle_font)
    draw.text(((width - subtitle_width) // 2, 85), subtitle, font=subtitle_font, fill=text_color)

    # Table layout - better margins for breathing room
    table_margin = 100  # Increased margin for breathing room
    start_y = 130
    table_width = width - (2 * table_margin)
    rows = 11  # Header + 10 rows
    cols = 11  # First column is for picks, then 0-10 hits

    cell_width = table_width // cols
    cell_height = 42  # Slightly larger cells

    # Draw table background and grid
    table_height = cell_height * rows
    # Draw rounded rectangle for table background
    draw.rectangle(
        (table_margin - 2, start_y - 2, width - table_margin + 2, start_y + table_height + 2),
        fill=(50, 50, 50),
        outline=(90, 90, 90),
        width=2
    )

    # Draw header row
    header_labels = ["Picks", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    for col in range(cols):
        # Headers for columns
        x = table_margin + (col * cell_width)
        y = start_y
        draw.rectangle((x, y, x + cell_width, y + cell_height), fill=header_color)

        # Draw text
        text = header_labels[col]
        text_width = draw.textlength(text, font=header_font)
        text_x = x + (cell_width - text_width) // 2
        text_y = y + ((cell_height - header_font.getbbox(text)[3]) // 2)  # Better centering
        draw.text((text_x, text_y), text, font=header_font, fill=highlight_color)

    # Draw data rows
    for row in range(1, 11):  # 1-10 picks
        # First column shows number of picks
        x = table_margin
        y = start_y + (row * cell_height)

        # Alternate row colors
        row_bg_color = alt_cell_color if row % 2 == 0 else cell_color

        draw.rectangle((x, y, x + cell_width, y + cell_height), fill=row_bg_color)

        # Draw pick number
        text = str(row)
        text_width = draw.textlength(text, font=cell_font)
        text_x = x + (cell_width - text_width) // 2
        text_y = y + ((cell_height - cell_font.getbbox(text)[3]) // 2)  # Better centering
        draw.text((text_x, text_y), text, font=cell_font, fill=text_color)

        # Draw multipliers for each hit possibility
        for col in range(1, 11):  # 0-10 hits
            x = table_margin + (col * cell_width)

            draw.rectangle((x, y, x + cell_width, y + cell_height), fill=row_bg_color)

            # Get multiplier value
            hits = col - 1  # Adjust: 1st column is 0 hits, 2nd is 1 hit...
            multiplier = PAYOUTS.get(row, {}).get(hits, 0)

            # Format multiplier text
            if multiplier == 0:
                text = "0x"
                text_color_cell = (100, 100, 100)  # Gray for zero
            else:
                text = f"{multiplier}x"
                # Use purple color scheme
                if multiplier > 50:
                    text_color_cell = (191, 0, 255)  # Bright purple for high values
                elif multiplier > 10:
                    text_color_cell = (147, 112, 219)  # Medium purple for medium values
                else:
                    text_color_cell = text_color

            text_width = draw.textlength(text, font=cell_font)
            text_x = x + (cell_width - text_width) // 2
            text_y = y + ((cell_height - cell_font.getbbox(text)[3]) // 2)  # Better centering
            draw.text((text_x, text_y), text, font=cell_font, fill=text_color_cell)
    """
    # Draw footer
    footer_text = "Powered by BetSync Casino | The best Discord casino"
    footer_width = draw.textlength(footer_text, font=subtitle_font)
    #draw.text(
        ((width - footer_width) // 2, start_y + table_height + 25),
        footer_text,
        font=subtitle_font,
        fill=(170, 170, 170)
    )
   """ 
    # Save to bytes
    img_byte_array = io.BytesIO()
    image.save(img_byte_array, format="PNG")
    img_byte_array.seek(0)

    return img_byte_array

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
    def __init__(self, cog, ctx, bet_amount, timeout=120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = "points"
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
        #self.selected_numbers.append(1)
        # No auto-select by default, but keep the first button on standby
        # Let users make their own selections

    def update_play_button(self):
        # Get the play button and update its state
        play_button = None
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "play":
                play_button = child
                break

        if play_button:
            # Always enable play button - if no numbers are selected, one will be randomly chosen
            play_button.disabled = False

    @discord.ui.button(label="PLAY", style=discord.ButtonStyle.success, custom_id="play", row=4, disabled=False)
    async def play_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.game_over:
            return await interaction.response.send_message("This game is already over!", ephemeral=True)
        await interaction.response.defer()
        # Disable buttons to prevent further interaction
        self.game_over = True
        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

        # Run the game
        await self.cog.run_keno_game(self.ctx, self, interaction.message)

    @discord.ui.button(label="CANCEL", style=discord.ButtonStyle.danger, custom_id="cancel", row=4)
    async def cancel_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Cancel the game and refund the user by adding the bet amount back
        await interaction.response.defer()
        db = Users()
        db.update_balance(self.ctx.author.id, self.bet_amount)

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

        embed = discord.Embed(
            title="<:no:1344252518305234987> | Game Cancelled",
            description=f"Game cancelled. Your bet of `{self.bet_amount} points` has been refunded.",
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


                    # Update server profit (positive for casino win)
                    server_db = Servers()
                    server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="keno")

                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Game Timed Out",
                        description=f"Game timed out. Your bet of `{self.bet_amount} {self.currency_used}` has been lost.",
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
            # Use blurple color which is closer to purple than primary blue
            self.style = discord.ButtonStyle.blurple

        # Update the play button state
        view.update_play_button()

        # Update the options embed with current selections and probabilities
        embed = view.cog.create_options_embed(view.ctx.author, view.bet_amount, view.selected_numbers, view.currency_used)

        # Generate paytable image for the current selection
        if view.selected_numbers:
            paytable_bytes = view.cog.create_mini_paytable_for_selections(len(view.selected_numbers))
            paytable_file = discord.File(paytable_bytes, filename="keno_paytable_selection.png")
            await interaction.response.edit_message(embed=embed, file=paytable_file, view=view)
        else:
            # No selections, don't include paytable
            await interaction.response.edit_message(embed=embed, view=view)

import datetime
import io
from PIL import Image, ImageDraw, ImageFont
import random

# Define payouts for different selections and hits
PAYOUTS = {
    1: {1: 3.72},
    2: {1: 1, 2: 10},
    3: {1: 0.5, 2: 1.5, 3: 25},
    4: {1: 0.0, 2: 1.35, 3: 10.0, 4: 100},
    5: {1: 0.0, 2: 0.0, 3: 3, 4: 50.0, 5: 100.0},
    6: {1: 0.0, 2: 0.5, 3: 3.0, 4: 12.0, 5: 300.0},
    7: {1: 0.0, 2: 0.0, 3: 2.0, 4: 8.0, 5: 100.0},
    8: {1: 0.0, 2: 0.0, 3: 1.5, 4: 5.0, 5: 50.0},
    9: {1: 0.0, 2: 0.0, 3: 1.0, 4: 3.0, 5: 30.0},
    10: {1: 0.0, 2: 0.0, 3: 0.5, 4: 2.0, 5: 20.0}
}

# Probability percentages for different picks and hits
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

class Keno(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["k"])
    async def keno(self, ctx, bet_amount: str = None):
        """
        Play a game of Keno

        Usage: !keno <bet amount> [currency_type]
        Example: !keno 100 tokens
        """
        # Show help if no bet amount
        if not bet_amount:
            # Generate paytable image
            paytable_image = generate_paytable_image()
            paytable_file = discord.File(paytable_image, filename="keno_paytable.png")

            embed = discord.Embed(
                title="🎮 How to Play Keno",
                description=(
                    "**Keno** is a lottery-style game where you select numbers and win based on matches!\n\n"
                    "**Usage:** `!keno <amount>`\n"
                    "**Example:** `!keno 100`\n\n"
                    "- **Select 1-10 numbers from a grid of 20**\n"
                    "- **5 winning numbers will be drawn**\n"
                    "- **Win based on how many of your picks match the draw**\n"
                    "- **Fewer selections = higher multipliers, but lower chance of big wins**\n"
                ),
                color=0x00FFAE
            )

            # Set the paytable image
            embed.set_image(url="attachment://keno_paytable.png")
            embed.set_footer(text="BetSync Casino • Aliases: !k")
            return await ctx.reply(embed=embed, file=paytable_file)

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
            #loading_emoji = emoji()["loading"]
            loading_embed = discord.Embed(
                title=f"Preparing Keno Game...",
                description="Please wait while we set up your game.",
                color=0x00FFAE
            )
            loading_message = await ctx.reply(embed=loading_embed)

            # Import the currency helper
            from Cogs.utils.currency_helper import process_bet_amount

            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)
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
            #cu = bet_info["credits_used"]

            currency_used = "points"

            # Update loading message to indicate progress
            await loading_message.edit(embed=discord.Embed(
                title=f"Setting Up Game...",
                description=f"Placing bet of `{bet_amount} points...`",
                color=0x00FFAE
            ))

            # Create game view
            view = KenoView(self, ctx, bet_amount_value)

            # Create initial embed
            initial_embed = self.create_options_embed(ctx.author, bet_amount_value, [1], currency_used)

            # Generate initial paytable image for selected number
            paytable_bytes = self.create_mini_paytable_for_selections(1)
            paytable_file = discord.File(paytable_bytes, filename="keno_paytable_selection.png")

            # Delete loading message and start the game
            await loading_message.delete()

            # Send the Keno game embed with paytable image
            game_message = await ctx.reply(embed=initial_embed, file=paytable_file, view=view)
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
                f"**Bet Amount:** `{bet_amount} {currency_used}`\n"
                f"**Numbers Selected:** {num_picks}/10"
            ),
            color=0x00FFAE
        )

        # Add payout info if numbers are selected
        if num_picks > 0:
            # Create a highlight-only mini paytable image for the selected number of picks
            paytable_bytes = self.create_mini_paytable_for_selections(num_picks)

            # Set the footer text
            probability_text = ""
            for hits in range(1, min(num_picks + 1, 6)):
                if hits in PROBABILITIES.get(num_picks, {}):
                    probability = PROBABILITIES[num_picks][hits]
                    probability_text += f"**{hits} Hit:** {probability}% chance\n"

            if probability_text:
                embed.add_field(name="Win Chances", value=probability_text, inline=False)

            # The image will be attached by the caller function
            embed.set_image(url="attachment://keno_paytable_selection.png")

        embed.set_footer(text="BetSync Casino • Select 1-10 numbers, then press PLAY")
        return embed

    def create_mini_paytable_for_selections(self, num_picks):
        """Create a mini paytable image focused on the selected number of picks"""
        # Image dimensions and settings - better size with more breathing room
        width, height = 600, 200  # Larger dimensions for better fit
        bg_color = (25, 25, 25)  # Dark background
        header_color = (40, 40, 40) 
        cell_color = (34, 34, 34)
        highlight_color = (128, 0, 255)  # Purple for highlights
        text_color = (255, 255, 255)
        accent_color = (147, 51, 234)  # Purple accent color

        # Create image and draw object
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        try:
            # Try to load fonts - better sizing
            title_font = ImageFont.truetype("arial.ttf", 24)  # Larger title font
            header_font = ImageFont.truetype("arial.ttf", 20)
            cell_font = ImageFont.truetype("arial.ttf", 20)
        except:
            # Fallback fonts
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            cell_font = ImageFont.load_default()

        # Draw title
        title = f"PAYOUTS FOR {num_picks} PICKS"
        title_width = draw.textlength(title, font=title_font)
        draw.text(((width - title_width) // 2, 20), title, font=title_font, fill=highlight_color)

        # Table layout - better margins
        table_margin = 50  # Increased margin for breathing room
        start_y = 60
        table_width = width - (2 * table_margin)

        # Determine number of columns (hits)
        max_hits = min(num_picks, 5)  # Maximum 5 hits
        cols = max_hits + 1  # Hits columns + 1 for label column

        cell_width = table_width // cols
        cell_height = 50  # Slightly larger cells

        # Draw header row
        header_labels = ["Picks"] + [f"{i} Hit{'' if i == 1 else 's'}" for i in range(1, max_hits + 1)]

        for col in range(cols):
            x = table_margin + (col * cell_width)
            y = start_y

            # Draw header cell with rounded corners
            draw.rectangle((x, y, x + cell_width, y + cell_height), fill=header_color)

            # Draw header text with better centering
            text = header_labels[col]
            text_width = draw.textlength(text, font=header_font)
            text_x = x + (cell_width - text_width) // 2

            # Better vertical centering using font metrics
            text_bbox = header_font.getbbox(text)
            text_height = text_bbox[3] - text_bbox[1]
            text_y = y + ((cell_height - text_height) // 2)

            draw.text((text_x, text_y), text, font=header_font, fill=highlight_color)

        # Draw data row - just the selected number of picks
        # First column (picks)
        x = table_margin
        y = start_y + cell_height

        # Draw cell with accent color to highlight
        draw.rectangle((x, y, x + cell_width, y + cell_height), fill=accent_color)

        # Draw pick number with better centering
        text = str(num_picks)
        text_width = draw.textlength(text, font=cell_font)
        text_bbox = cell_font.getbbox(text)
        text_height = text_bbox[3] - text_bbox[1]

        text_x = x + (cell_width - text_width) // 2
        text_y = y + ((cell_height - text_height) // 2)

        draw.text((text_x, text_y), text, font=cell_font, fill=(255, 255, 255))  # White text on purple

        # Draw multipliers for each hit
        for col in range(1, cols):
            hits = col  # First data column is 1 hit
            x = table_margin + (col * cell_width)

            # Get multiplier
            multiplier = PAYOUTS.get(num_picks, {}).get(hits, 0)

            # Draw cell
            draw.rectangle((x, y, x + cell_width, y + cell_height), fill=cell_color)

            # Format multiplier text
            if multiplier == 0:
                text = "-"
                text_color_cell = (100, 100, 100)  # Gray
            else:
                text = f"{multiplier}x"
                # Use purple color scheme for higher values
                if multiplier > 100:
                    text_