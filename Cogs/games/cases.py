import os
import discord
import random
import time
import io
import asyncio
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class CasesPlayAgainView(discord.ui.View):
    """View with a Play Again button that shows after a game ends"""
    def __init__(self, cog, ctx, bet_amount, currency_used, bot, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.bot = bot
        self.currency_used = currency_used
        self.message = None
        self.original_author = ctx.author  # Store the original author explicitly
        self.author_id = ctx.author.id #Added this line
        
    def disable_all_buttons(self):
        """Disable all buttons in the view"""
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def on_timeout(self):
        """Handle timeout by disabling all buttons"""
        self.disable_all_buttons()
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
                
    async def play_again(self, button, interaction):
        """Handle the play again button click"""
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Get the cog instance
        cases_cog = self.bot.get_cog("CasesCog")
        if not cases_cog:
            return await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)

        # Use the same bet amount and currency
        ctx = await self.bot.get_context(self.message)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Send a loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Processing Case...",
            description="Please wait while we process your request...",
            color=0x00FFAE
        )
        await interaction.response.defer()
        loading_message = await interaction.followup.send(embed=loading_embed)

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(self.ctx, str(self.bet_amount), self.currency_used, loading_message)

        # If processing failed, return the error
        if not success:
            return await interaction.followup.send(embed=error_embed, ephemeral=True)

        # Disable buttons on original message
        self.disable_all_buttons()
        await self.message.edit(view=self)

        # Run the command again
        await cases_cog.cases(ctx, str(self.bet_amount), self.currency_used)


class CasesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Define case multipliers and their chances based on provided image
        self.multipliers = [
            {"value": 23.0, "chance": 0.01, "emoji": "💎", "name": "LEGENDARY", "color": (255, 215, 0)},
            {"value": 10.0, "chance": 0.02, "emoji": "🌟", "name": "EPIC", "color": (148, 0, 211)},
            {"value": 3.0, "chance": 0.04, "emoji": "✨", "name": "RARE", "color": (255, 69, 0)},
            {"value": 2.0, "chance": 0.07, "emoji": "🔷", "name": "UNCOMMON", "color": (30, 144, 255)},
            {"value": 1.09, "chance": 0.10, "emoji": "🔹", "name": "COMMON", "color": (0, 191, 255)},
            {"value": 0.4, "chance": 0.35, "emoji": "💢", "name": "BAD LUCK", "color": (128, 128, 128)},
            {"value": 0.1, "chance": 0.41, "emoji": "💀", "name": "TERRIBLE", "color": (255, 0, 0)}
        ]

        # Validate that probabilities sum to 1
        total_prob = sum(item["chance"] for item in self.multipliers)
        if abs(total_prob - 1.0) > 0.001:  # Allow small floating-point error
            print(f"Warning: Case probabilities sum to {total_prob}, not 1.0")

        # Font path
        self.font_path = "roboto.ttf"
        if not os.path.exists(self.font_path):
            print(f"Warning: Font file {self.font_path} not found, using default font")
            self.font_path = None

    def generate_result_image(self, selected_multiplier, user_name=None):
        """Generate a simple image showing a single case with the result"""
        # Set up the image dimensions
        width = 800
        height = 400
        bg_color = (14, 23, 35)  # Dark blue background

        # Create the base image
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Load the open-box image
        try:
            case_img = Image.open("assests/open-box.png").convert("RGBA")
            # Resize the case image to fit well in our canvas
            case_size = 200
            case_img = case_img.resize((case_size, case_size), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"Error loading case image: {e}")
            # Create a simple box as fallback
            case_img = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
            draw_case = ImageDraw.Draw(case_img)
            draw_case.rectangle([10, 10, 190, 190], outline=(255, 255, 255), width=5)
            draw_case.rectangle([40, 40, 160, 160], fill=(100, 100, 100))

        # Get color based on multiplier value
        def get_color_for_multiplier(mult_value):
            if mult_value >= 10:  # Epic/Legendary
                return (255, 0, 68)  # Red
            elif mult_value >= 3:  # Rare
                return (255, 69, 0)  # Orange
            elif mult_value >= 2:  # Uncommon
                return (30, 144, 255)  # Blue
            elif mult_value >= 1:  # Common
                return (0, 191, 255)  # Light Blue
            elif mult_value >= 0.4:  # Bad Luck
                return (92, 105, 121)  # Gray
            else:  # Terrible
                return (80, 80, 80)  # Dark Gray

        # Get multiplier color
        multiplier_color = get_color_for_multiplier(selected_multiplier["value"])

        # Load fonts
        try:
            # Fonts for different elements
            header_font = ImageFont.truetype(self.font_path, 36) if self.font_path else ImageFont.load_default()
            multiplier_font = ImageFont.truetype(self.font_path, 48) if self.font_path else ImageFont.load_default()
            watermark_font = ImageFont.truetype(self.font_path, 18) if self.font_path else ImageFont.load_default()
        except Exception:
            header_font = ImageFont.load_default()
            multiplier_font = ImageFont.load_default()
            watermark_font = ImageFont.load_default()

        # Position the case in the center
        case_x = (width - case_img.width) // 2
        case_y = (height - case_img.height) // 2 - 20  # Move up slightly to make room for text

        # Paste the case image onto our background
        img.paste(case_img, (case_x, case_y), case_img if case_img.mode == 'RGBA' else None)

        # Draw the result text below the case
        result_text = f"{selected_multiplier['name']} {selected_multiplier['value']}x"
        result_bbox = draw.textbbox((0, 0), result_text, font=multiplier_font)
        result_width = result_bbox[2] - result_bbox[0]
        result_x = (width - result_width) // 2
        result_y = case_y + case_img.height + 20  # Position below the case

        # Add a subtle glow effect for the text
        for offset_x, offset_y in [(1,1), (-1,-1), (1,-1), (-1,1), (0,1), (1,0), (-1,0), (0,-1)]:
            draw.text((result_x+offset_x, result_y+offset_y), result_text, font=multiplier_font, fill=(0, 0, 0, 150))

        # Draw the main text in the appropriate color
        draw.text((result_x, result_y), result_text, font=multiplier_font, fill=multiplier_color)

        # Add BetSync watermark at the bottom
        watermark_text = "BetSync Casino"
        watermark_bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        watermark_width = watermark_bbox[2] - watermark_bbox[0]
        watermark_x = (width - watermark_width) // 2
        watermark_y = height - 30
        draw.text((watermark_x, watermark_y), watermark_text, font=watermark_font, fill=(100, 100, 100))

        # Convert the image to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer

    async def generate_case_image(self, selected_multiplier):
        """Generates a case opening result image."""
        buffer = self.generate_result_image(selected_multiplier)
        return buffer

    def get_case_result(self):
        """Determines the result of opening a case."""
        random_value = random.random()
        cumulative_prob = 0
        selected_multiplier = None

        for multiplier in self.multipliers:
            cumulative_prob += multiplier["chance"]
            if random_value <= cumulative_prob:
                selected_multiplier = multiplier
                break

        if not selected_multiplier:  # Fallback in case of floating-point issues
            selected_multiplier = self.multipliers[-1]
        return {"multiplier": selected_multiplier}


    @commands.command(aliases=["case", "crate"])
    async def cases(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Open a case and test your luck with different multipliers!"""
        if not bet_amount:
            embed = discord.Embed(
                title="📦 How to Play Cases",
                description=(
                    "**Cases** is a game where you open a case to win credits based on multipliers!\n\n"
                    "**Usage:** `!cases <amount> [currency_type]`\n"
                    "**Example:** `!cases 100` or `!cases 100 tokens`\n\n"
                    "**Possible Rewards:**\n"
                    f"💎 **LEGENDARY** (23x) - 1% chance\n"
                    f"🌟 **EPIC** (10x) - 2% chance\n"
                    f"✨ **RARE** (3x) - 4% chance\n"
                    f"🔷 **UNCOMMON** (2x) - 7% chance\n"
                    f"🔹 **COMMON** (1.09x) - 10% chance\n"
                    f"💢 **BAD LUCK** (0.4x) - 35% chance\n"
                    f"💀 **TERRIBLE** (0.1x) - 41% chance\n\n"
                    "**Payouts are made in credits!**"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Send loading message immediately
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Processing Case...",
            description="Please wait while we process your request...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

        # If processing failed, return the error
        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Successful bet processing - extract relevant information
        tokens_used = bet_info["tokens_used"]
        credits_used = bet_info["credits_used"]
        bet_amount_value = bet_info["total_bet_amount"]

        # Determine which currency was primarily used for display purposes
        if tokens_used > 0 and credits_used > 0:
            currency_used = "mixed"
        elif tokens_used > 0:
            currency_used = "tokens"
        else:
            currency_used = "credits"

        # Update the loading message to show bet details
        if currency_used == "mixed":
            currency_display = f"{tokens_used} tokens and {credits_used} credits"
        else:
            currency_display = f"{bet_amount_value} {currency_used}"

        loading_embed.description = f"Opening case for {currency_display}..."
        await loading_message.edit(embed=loading_embed)

        # Generate the case result
        case_result = self.get_case_result()
        selected_multiplier = case_result["multiplier"]

        # Calculate winnings (paid in credits)
        win_amount = bet_amount_value * selected_multiplier["value"]
        win_amount = round(win_amount, 2)  # Round to 2 decimal places

        # Add winnings to user's credit balance
        user_won = selected_multiplier["value"] >= 1.0
        if user_won:
            db = Users()  # Reinstantiate db to ensure we have a fresh connection
            db.update_balance(ctx.author.id, win_amount, 'credits', "$inc")

        # Create result image
        result_buffer = await self.generate_case_image(selected_multiplier)
        file = discord.File(result_buffer, filename="case_result.png")

        # Update server history and profit
        server_db = Servers()
        server_data = server_db.fetch_server(ctx.guild.id)

        if server_data:
            # Calculate server profit
            if tokens_used > 0:
                # For tokens used, the server profit is the token amount
                server_profit = tokens_used

                # If credits were also used, add their contribution to profit minus any winnings
                if credits_used > 0:
                    if user_won:
                        # Only subtract winnings from the credits portion
                        credits_portion = min(credits_used, win_amount)
                        server_profit += (credits_used - credits_portion)
                    else:
                        server_profit += credits_used
            else:
                # If only credits were used, profit is the bet minus any winnings
                server_profit = bet_amount_value - win_amount if user_won else bet_amount_value

            server_db.update_server_profit(ctx.guild.id, server_profit)

            # Add to server history
            history_entry = {
                "type": "case",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "amount": bet_amount_value,
                "currency": "mixed" if tokens_used > 0 and credits_used > 0 else ("tokens" if tokens_used > 0 else "credits"),
                "multiplier": selected_multiplier["value"],
                "win_amount": win_amount,
                "timestamp": int(time.time())
            }
            server_db.update_history(ctx.guild.id, history_entry)

        # Add game to user history
        history_entry = {
            "game": "cases",
            "bet_amount": bet_amount_value,
            "currency": currency_used,
            "result": "win" if user_won else "loss",
            "multiplier": selected_multiplier["value"],
            "win_amount": win_amount,
            "timestamp": int(time.time())
        }
        db = Users() #reinstantiate db
        db.update_history(ctx.author.id, history_entry)

        # Set color based on result tier
        if selected_multiplier["value"] >= 10:  # Legendary/Epic
            color = 0xFFD700  # Gold
        elif selected_multiplier["value"] >= 2:  # Rare/Uncommon
            color = 0x00FF00  # Green
        elif selected_multiplier["value"] >= 1:  # Common
            color = 0x00AAFF  # Blue
        else:  # Bad luck / Terrible
            color = 0xFF0000  # Red

        # Generate the result image with user's name
        image_buffer = await self.generate_case_image(selected_multiplier)
        image_file = discord.File(image_buffer, filename="case_result.png")

        # Create a simplified and clean result embed
        result_embed = discord.Embed(
            title=f"Case Opening",
            description=(
                f"**Multiplier: {selected_multiplier['value']}x**\n"
                f"**Bet:** {bet_amount_value:.2f} {currency_used}\n"
                f"**Payout:** {win_amount:.2f} credits\n"
                f"**Profit:** {win_amount - bet_amount_value:.2f} credits"
            ),
            color=color
        )

        # Set the image in the embed
        result_embed.set_image(url="attachment://case_result.png")

        # Add multiplier info in a clean format
        case_info = ""
        for m in sorted(self.multipliers, key=lambda x: x["value"], reverse=True):
            # Highlight the result
            if m["value"] == selected_multiplier["value"]:
                case_info += f"{m['emoji']} **{m['name']}** ({m['value']}x)\n"
            #else:
                #case_info += f"{m['emoji']} {m['name']} ({m['value']}x) - {m['chance']*100:.1f}%\n"

        result_embed.add_field(
            name="📋 Case Contents",
            value=case_info,
            inline=False
        )

        result_embed.set_footer(text=f"BetSync Casino • {currency_used.capitalize()} bet: {bet_amount_value:.2f}", icon_url=self.bot.user.avatar.url)

        # Add play again button
        play_again_view = CasesPlayAgainView(self, ctx, bet_amount_value, currency_used, self.bot)
        play_again_message = await loading_message.edit(embed=result_embed, file=image_file, view=play_again_view)
        play_again_view.message = play_again_message


def setup(bot):
    bot.add_cog(CasesCog(bot))