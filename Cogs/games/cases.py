import os
import discord
import random
import time
import io
import asyncio
import aiohttp
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


    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)           
    async def play_again(self, button, interaction):
        """Handle the play again button click"""
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Get the cog instance
        cases_cog = self.bot.get_cog("CasesCog")
        if not cases_cog:
            return await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)

        # Use the same bet amount and currency
        self.ctx = await self.bot.get_context(self.message)
        self.ctx.author = interaction.user

        # Check user balance before proceeding
        #db = Users()
        #user_data = db.fetch_user(interaction.user.id)
        #if not user_data:
            #return await interaction.response.send_message("Could not fetch user data.", ephemeral=True)

        # Defer the response and update the message
        await interaction.response.defer()

        # Run the command again with the existing context
        await cases_cog.cases(self.ctx, str(self.bet_amount))


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
        """Generate an image showing the case opening result in a modern style"""
        # Set up the image dimensions - wider, less height
        width = 1200
        height = 350
        bg_color = (14, 23, 35)  # Darker blue background

        # Create the base image
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Box dimensions - wider and shorter to match reference image
        box_width = 120
        box_height = 160
        box_spacing = 20
        total_box_area = 7 * box_width + 6 * box_spacing
        start_x = (width - total_box_area) // 2
        start_y = (height - box_height) // 2 + 15  # Move cases down slightly

        # Get multiplier color based on the value
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

        # Modern box colors with variety
        base_colors = [
            (232, 32, 68),  # Red
            (0, 122, 255),  # Blue
            (20, 210, 230),  # Cyan
            (92, 105, 121),  # Gray
            (255, 69, 0),   # Orange
            (30, 144, 255),  # Light Blue
            (0, 191, 255)   # Aqua
        ]

        # Randomly shuffle the colors except for the selected case
        random.shuffle(base_colors)

        # Set the selected case color based on the multiplier pulled
        selected_case_color = get_color_for_multiplier(selected_multiplier["value"])

        # Replace the middle (selected) case color with the multiplier-based color
        box_colors = base_colors.copy()
        box_colors[3] = selected_case_color

        # Load fonts
        try:
            # Fonts for different elements
            value_font = ImageFont.truetype(self.font_path, 22) if self.font_path else ImageFont.load_default()
            tier_font = ImageFont.truetype(self.font_path, 18) if self.font_path else ImageFont.load_default()
            header_font = ImageFont.truetype(self.font_path, 28) if self.font_path else ImageFont.load_default()
            multiplier_font = ImageFont.truetype(self.font_path, 34) if self.font_path else ImageFont.load_default()
            watermark_font = ImageFont.truetype(self.font_path, 18) if self.font_path else ImageFont.load_default()
        except Exception:
            value_font = ImageFont.load_default()
            tier_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            multiplier_font = ImageFont.load_default()
            watermark_font = ImageFont.load_default()

        # Add user pull header if username is provided
        if user_name:
            header_text = f"{user_name} Pulled {selected_multiplier['name']}"
            header_size = draw.textbbox((0, 0), header_text, font=header_font)
            header_width = header_size[2] - header_size[0]
            header_x = (width - header_width) // 2
            header_y = 20  # Position at top
            draw.text((header_x, header_y), header_text, font=header_font, fill=(255, 255, 255))

            # Add larger multiplier value text right below the header
            value_text = f"{selected_multiplier['value']}x"
            value_size = draw.textbbox((0, 0), value_text, font=multiplier_font)
            value_width = value_size[2] - value_size[0]
            value_x = (width - value_width) // 2
            value_y = header_y + 40  # Position below header

            # Add glow effect around the multiplier text
            for offset_x, offset_y in [(1,1), (-1,-1), (1,-1), (-1,1), (0,1), (1,0), (-1,0), (0,-1)]:
                draw.text((value_x+offset_x, value_y+offset_y), value_text, font=multiplier_font, fill=(0, 0, 0, 150))

            # Add the multiplier text with the color matching the selected case
            multiplier_color = selected_case_color if selected_multiplier["value"] >= 1 else (255, 255, 255)
            draw.text((value_x, value_y), value_text, font=multiplier_font, fill=multiplier_color)

        # Draw the boxes in modern style - variety of designs
        for i in range(7):
            x = start_x + i * (box_width + box_spacing)
            y = start_y

            # Modern case style with rounded corners
            is_selected = (i == 3)
            box_color = box_colors[i]

            # Add slight randomization to box designs - but don't use more than one pattern
            design_variant = random.randint(1, 3)

            # Draw white outline first (3px thick)
            outline_width = 3
            draw.rounded_rectangle(
                [x-outline_width, y+10-outline_width, x+box_width+outline_width, y+box_height+outline_width], 
                radius=14, 
                fill=None, 
                outline=(255, 255, 255), 
                width=outline_width
            )

            # Draw the box with a slight 3D effect
            # Main case body
            draw.rounded_rectangle([x, y + 10, x + box_width, y + box_height], radius=14, fill=box_color)

            # Add only ONE top design based on variant (to prevent multiple lines)
            if design_variant == 1:
                # Top gem design - SIMPLIFIED to just one reflection
                # Add gem light reflection - just one simple highlight
                light_color = tuple(min(c + 40, 255) for c in box_color)
                reflection_points = [
                    (x + box_width * 0.25, y + 18),
                    (x + box_width * 0.35, y + 28),
                    (x + box_width * 0.45, y + 18)
                ]
                #draw.polygon(reflection_points, fill=light_color)

            elif design_variant == 2:
                # Horizontal stripe design - JUST ONE STRIPE
                stripe_height = 12
                stripe_y = y + 25
                stripe_color = tuple(min(c + 30, 255) for c in box_color)
                draw.rectangle([x + 10, stripe_y, x + box_width - 10, stripe_y + stripe_height], fill=stripe_color)

            else:
                # Diamond pattern on top - JUST ONE DIAMOND
                diamond_size = 20
                diamond_color = tuple(min(c + 50, 255) for c in box_color)
                diamond_x = x + box_width // 2
                diamond_y = y + 30

                diamond_points = [
                    (diamond_x, diamond_y - diamond_size//2),
                    (diamond_x + diamond_size//2, diamond_y),
                    (diamond_x, diamond_y + diamond_size//2),
                    (diamond_x - diamond_size//2, diamond_y),
                ]
                #draw.polygon(diamond_points, fill=diamond_color)

            # Draw black notch at bottom
            notch_width = box_width // 3
            notch_x = x + (box_width - notch_width) // 2
            notch_height = 15
            draw.rectangle([notch_x, y + box_height - 5, notch_x + notch_width, y + box_height + 5], fill=(20, 20, 20))

            # For all cases, add a glossy effect
            highlight_color = tuple(min(c + 80, 255) for c in box_color)
            highlight_opacity = 100  # Semi-transparent
            highlight_rect = [x + 5, y + 15, x + box_width - 5, y + 30]
            draw.rounded_rectangle(highlight_rect, radius=10, fill=(highlight_color[0], highlight_color[1], highlight_color[2], highlight_opacity))

            # If this is the selected box, add the special gem design
            if is_selected:
                # Draw gem/crystal icon in the center box to match the multiplier theme
                center_x = x + box_width // 2
                center_y = y + box_height // 3
                gem_size = 40

                # Select gem color based on multiplier value
                gem_outline_color = (220, 220, 220)
                gem_inner_color = selected_case_color
                gem_highlight_color = tuple(min(c + 70, 255) for c in selected_case_color)

                # Draw a stylized gem/crystal
                gem_points = [
                    (center_x, center_y - gem_size//2),  # Top
                    (center_x + gem_size//3, center_y - gem_size//4),  # Top right
                    (center_x + gem_size//2, center_y),  # Right
                    (center_x + gem_size//3, center_y + gem_size//4),  # Bottom right
                    (center_x, center_y + gem_size//2),  # Bottom
                    (center_x - gem_size//3, center_y + gem_size//4),  # Bottom left
                    (center_x - gem_size//2, center_y),  # Left
                    (center_x - gem_size//3, center_y - gem_size//4),  # Top left
                ]
                # Gem outline
                #draw.polygon(gem_points, fill=gem_outline_color)

                # Inner gem
                inner_gem_points = [
                    (center_x, center_y - gem_size//3),
                    (center_x + gem_size//4, center_y - gem_size//6),
                    (center_x + gem_size//3, center_y),
                    (center_x + gem_size//4, center_y + gem_size//6),
                    (center_x, center_y + gem_size//3),
                    (center_x - gem_size//4, center_y + gem_size//6),
                    (center_x - gem_size//3, center_y),
                    (center_x - gem_size//4, center_y - gem_size//6),
                ]
                #draw.polygon(inner_gem_points, fill=gem_inner_color)

                # Gem highlight
                highlight_points = [
                    (center_x - gem_size//6, center_y - gem_size//4),
                    (center_x, center_y - gem_size//6),
                    (center_x + gem_size//6, center_y - gem_size//4),
                ]
                #draw.polygon(highlight_points, fill=gem_highlight_color)

                # Add dot in center of gem matching the emoji color
                center_dot_color = selected_case_color
                if selected_multiplier["emoji"] == "💎":
                    center_dot_color = (30, 144, 255)  # Blue for diamond
                elif selected_multiplier["emoji"] == "🌟":
                    center_dot_color = (255, 215, 0)  # Gold for star
                elif selected_multiplier["emoji"] == "💀":
                    center_dot_color = (255, 0, 0)  # Red for skull

                #draw.ellipse([center_x-4, center_y-4, center_x+4, center_y+4], fill=center_dot_color)

                # Draw multiplier in a pill shape
                multiplier_text = f"{selected_multiplier['value']}x"
                multiplier_width = draw.textlength(multiplier_text, font=value_font)
                pill_width = multiplier_width + 20
                pill_height = 32
                pill_x = x + (box_width - pill_width) // 2
                pill_y = y + box_height - 50

                # Draw pill background with rounded corners
                draw.rounded_rectangle(
                    [pill_x, pill_y, pill_x + pill_width, pill_y + pill_height],
                    radius=16,
                    fill=(40, 40, 40)
                )

                # Draw multiplier text
                text_x = x + (box_width - multiplier_width) // 2
                text_y = pill_y + (pill_height - 22) // 2  # Center vertically in pill
                draw.text((text_x, text_y), multiplier_text, font=value_font, fill=(255, 255, 255))

                # Draw pointer triangle below the selected box
                triangle_size = 20
                triangle_top_x = x + box_width // 2
                triangle_top_y = y + box_height + 20

                # Draw filled triangle in the same color as the case
                triangle_points = [
                    (triangle_top_x, triangle_top_y - triangle_size),
                    (triangle_top_x - triangle_size//2, triangle_top_y),
                    (triangle_top_x + triangle_size//2, triangle_top_y)
                ]
                draw.polygon(triangle_points, fill=selected_case_color)

                # Removed the emoji above the case as requested

        # Add BetSync watermark at the bottom
        watermark_text = "BetSync Casino"
        watermark_size = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        watermark_width = watermark_size[2] - watermark_size[0]
        watermark_x = (width - watermark_width) // 2
        watermark_y = height - 25
        draw.text((watermark_x, watermark_y), watermark_text, font=watermark_font, fill=(100, 100, 100, 80))

        # Convert the image to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer

    async def send_curse_webhook(self, user, game, bet_amount, multiplier):
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
                    {"name": "Bet Amount", "value": f"{bet_amount:.2f} points", "inline": True},
                    {"name": "Multiplier at Loss", "value": f"{multiplier:.2f}x", "inline": True}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            print(f"Error sending curse webhook: {e}")

    async def generate_case_image(self, selected_multiplier):
        """Generates a case opening result image."""
        buffer = self.generate_result_image(selected_multiplier)
        return buffer

    def get_case_result(self, user_id=None):
        """Determines the result of opening a case."""
        # Check if user is cursed to lose
        curse_cog = self.bot.get_cog("AdminCurseCog")
        if curse_cog and user_id and curse_cog.is_player_cursed(user_id):
            # Force a loss by selecting from losing multipliers (< 1.0x)
            losing_multipliers = [m for m in self.multipliers if m["value"] < 1.0]
            if losing_multipliers:
                selected_multiplier = random.choice(losing_multipliers)
                return {"multiplier": selected_multiplier, "cursed": True}
        
        # Normal random result
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
        return {"multiplier": selected_multiplier, "cursed": False}


    @commands.command(aliases=["case", "crate"])
    async def cases(self, ctx, bet_amount: str = None):
        """Open a case and test your luck with different multipliers!"""
        if not bet_amount:
            embed = discord.Embed(
                title="📦 How to Play Cases",
                description=(
                    "**Cases** is a game where you open a case to win points based on multipliers!\n\n"
                    "**Usage:** `!cases <amount>`\n"
                    "**Example:** `!cases 100`\n\n"
                    "**Possible Rewards:**\n"
                    f"💎 **LEGENDARY** (23x)\n"
                    f"🌟 **EPIC** (10x)\n"
                    f"✨ **RARE** (3x)\n"
                    f"🔷 **UNCOMMON** (2x)\n"
                    f"🔹 **COMMON** (1.09x)\n"
                    f"💢 **BAD LUCK** (0.4x)\n"
                    f"💀 **TERRIBLE** (0.1x)\n\n"
                    #"**Payouts are made in credits!**"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Send loading message immediately
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Processing Case...",
            description="Please wait while we process your request...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        # If processing failed, return the error
        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Successful bet processing - extract relevant information
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        bet_amount_value = bet_info["total_bet_amount"]

        # Determine which currency was primarily used for display purposes
        currency_used ="points"

        
        currency_display = f"`{bet_amount_value} {currency_used}`"

        loading_embed.description = f"Opening case for {currency_display}..."
        await loading_message.edit(embed=loading_embed)

        # Generate the case result
        case_result = self.get_case_result(ctx.author.id)
        selected_multiplier = case_result["multiplier"]
        was_cursed = case_result.get("cursed", False)

        # Calculate winnings (paid in credits)
        win_amount = bet_amount_value * selected_multiplier["value"]
        win_amount = round(win_amount, 2)  # Round to 2 decimal places

        # Add winnings to user's credit balance
        user_won = selected_multiplier["value"] >= 1.0
        db = Users()  # Reinstantiate db to ensure we have a fresh connection
        db.update_balance(ctx.author.id, win_amount, 'credits', "$inc")

        # Handle curse system if the user was cursed
        if was_cursed:
            curse_cog = self.bot.get_cog("AdminCurseCog")
            if curse_cog:
                curse_complete = curse_cog.consume_curse(ctx.author.id)
                # Send webhook notification
                await self.send_curse_webhook(ctx.author, "cases", bet_amount_value, selected_multiplier["value"])

        # Create result image
        result_buffer = await self.generate_case_image(selected_multiplier)
        file = discord.File(result_buffer, filename="case_result.png")

        # Update server history and profit
        server_db = Servers()
        server_data = server_db.fetch_server(ctx.guild.id)

        if server_data:

            server_db.update_server_profit(ctx, ctx.guild.id, (bet_amount_value - win_amount), game="cases")



        

        db = Users() #reinstantiate db
        #db.update_history(ctx.author.id, history_entry)

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
                f"**Multiplier:** `{selected_multiplier['value']}x`\n"
                f"**Bet:** `{bet_amount_value:.2f} {currency_used}`\n"
                f"**Payout:** `{win_amount:.2f} points`\n"
                f"**Profit:** `{win_amount - bet_amount_value:.2f} points`"
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
                case_info += f"{m['emoji']} **{m['name']}** ({m['value']}x)"
            #else:
                #case_info += f"{m['emoji']} {m['name']} ({m['value']}x) - {m['chance']*100:.1f}%\n"

        result_embed.add_field(
            name="📋 Case Contents",
            value=case_info,
            inline=False
        )

        result_embed.set_footer(text=f"BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Add play again button
        play_again_view = CasesPlayAgainView(self, ctx, bet_amount_value, currency_used, self.bot)
        play_again_message = await loading_message.edit(embed=result_embed, file=image_file, view=play_again_view)
        play_again_view.message = play_again_message


def setup(bot):
    bot.add_cog(CasesCog(bot))