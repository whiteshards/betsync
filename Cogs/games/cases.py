import discord
import random
import asyncio
import io
from PIL import Image, ImageDraw, ImageFont
import os
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class CasesPlayAgainView(discord.ui.View):
    """View with a Play Again button that shows after a game ends"""
    def __init__(self, cog, ctx, bet_amount, currency_used, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None
        self.original_author = ctx.author  # Store the original author explicitly

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, button, interaction):
        # Check if the person clicking is the original player
        if interaction.user.id != self.original_author.id:
            return await interaction.response.send_message("Only the original player can use this button!", ephemeral=True)

        # Disable the button after click
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with same bet amount
        await self.cog.cases(self.ctx, str(self.bet_amount), self.currency_used)


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
                draw.polygon(reflection_points, fill=light_color)
                
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
                draw.polygon(diamond_points, fill=diamond_color)
            
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
                draw.polygon(gem_points, fill=gem_outline_color)
                
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
                draw.polygon(inner_gem_points, fill=gem_inner_color)
                
                # Gem highlight
                highlight_points = [
                    (center_x - gem_size//6, center_y - gem_size//4),
                    (center_x, center_y - gem_size//6),
                    (center_x + gem_size//6, center_y - gem_size//4),
                ]
                draw.polygon(highlight_points, fill=gem_highlight_color)
                
                # Add dot in center of gem matching the emoji color
                center_dot_color = selected_case_color
                if selected_multiplier["emoji"] == "💎":
                    center_dot_color = (30, 144, 255)  # Blue for diamond
                elif selected_multiplier["emoji"] == "🌟":
                    center_dot_color = (255, 215, 0)  # Gold for star
                elif selected_multiplier["emoji"] == "💀":
                    center_dot_color = (255, 0, 0)  # Red for skull
                
                draw.ellipse([center_x-4, center_y-4, center_x+4, center_y+4], fill=center_dot_color)
                
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
            title=f"{loading_emoji} Opening Case...",
            description="Processing your bet...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Get user's balance
        author = ctx.author
        db = Users()
        user_data = db.fetch_user(author.id)
        tokens_balance = user_data.get('tokens', 0)
        credits_balance = user_data.get('credits', 0)

        # Process bet amount and currency
        try:
            # Handle all/max bet amount
            if isinstance(bet_amount, str) and bet_amount.lower() in ["all", "max"]:
                if currency_type:
                    if currency_type.lower() in ["tokens", "t"]:
                        bet_amount = tokens_balance
                        currency_used = "tokens"
                    elif currency_type.lower() in ["credits", "c"]:
                        bet_amount = credits_balance
                        currency_used = "credits"
                    else:
                        return await ctx.reply("Invalid currency type. Use 'tokens' or 'credits'.")
                else:
                    # If no currency specified with all/max, use the currency with higher balance
                    if tokens_balance >= credits_balance:
                        bet_amount = tokens_balance
                        currency_used = "tokens"
                    else:
                        bet_amount = credits_balance
                        currency_used = "credits"
            else:
                # Handle numeric bet amount
                try:
                    bet_amount = float(bet_amount)
                    if bet_amount <= 0:
                        return await ctx.reply("Bet amount must be positive!")
                except ValueError:
                    return await ctx.reply("Invalid bet amount! Please enter a valid number.")

                # Handle currency selection
                if currency_type:
                    if currency_type.lower() in ["tokens", "t"]:
                        currency_used = "tokens"
                    elif currency_type.lower() in ["credits", "c"]:
                        currency_used = "credits"
                    else:
                        return await ctx.reply("Invalid currency type. Use 'tokens' or 'credits'.")
                else:
                    # Default to tokens if no currency specified
                    currency_used = "tokens"

            # Validate user has enough balance
            if currency_used == "tokens" and tokens_balance < bet_amount:
                return await ctx.reply(f"You don't have enough tokens! Your balance: {tokens_balance:.2f} tokens")
            elif currency_used == "credits" and credits_balance < bet_amount:
                return await ctx.reply(f"You don't have enough credits! Your balance: {credits_balance:.2f} credits")

            # Deduct the bet amount
            db.update_balance(author.id, -bet_amount, currency_used, "$inc")
            
            # Update loading message with bet information
            loading_embed.description = f"Bet: **{bet_amount:.2f} {currency_used}**"
            await loading_message.edit(embed=loading_embed)

        except Exception as e:
            await loading_message.delete()
            return await ctx.reply(f"An error occurred: {str(e)}")

        # Create a clean spinning animation
        animation_embed = discord.Embed(
            title="📦 Case Opening",
            description=f"Bet: **{bet_amount:.2f} {currency_used}**",
            color=0x00FFAE
        )

        # Determine result first to avoid sticking issues
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
            
        # Spinning reel animation - properly aligned and fixed
        for i in range(8):  # 8 spins for animation
            # Create a clean display of spinning items
            shuffled_items = self.multipliers.copy()
            random.shuffle(shuffled_items)
            
            # Make sure the animation shows the actual result at the end
            if i == 7:  # On last spin, make sure middle item is the result
                center_idx = -1
                for idx, item in enumerate(shuffled_items):
                    if item["value"] == selected_multiplier["value"] and item["name"] == selected_multiplier["name"]:
                        center_idx = idx
                        break
                
                # If found, swap to make it the middle item
                if center_idx != -1 and center_idx != 1:
                    shuffled_items[center_idx], shuffled_items[1] = shuffled_items[1], shuffled_items[center_idx]
                # If not found (unlikely), replace middle item directly
                elif center_idx == -1:
                    shuffled_items[1] = selected_multiplier

            reel = ""
            for j in range(3):
                item = shuffled_items[j]
                if j == 1:
                    # Center item highlighted with consistent alignment
                    reel += f"▶️ {item['emoji']} **{item['name']}** ({item['value']}x) ◀️\n"
                else:
                    # Consistent padding for non-selected items for better alignment
                    reel += f"   {item['emoji']} {item['name']} ({item['value']}x)\n"

            animation_embed.description = f"Bet: **{bet_amount:.2f} {currency_used}**\n\n{reel}"
            
            try:
                await loading_message.edit(embed=animation_embed)
                await asyncio.sleep(0.08 if i < 6 else 0.12)  # Even faster animation with slight slowdown at end
            except Exception as e:
                print(f"Error in animation: {e}")
                # If edit fails, continue to next frame
                continue

        # Calculate winnings
        win_amount = bet_amount * selected_multiplier["value"]
        user_won = selected_multiplier["value"] > 1.0

        # Update MongoDB
        # Update gameplay statistics
        db.collection.update_one(
            {"discord_id": author.id},
            {"$inc": {
                "total_played": 1,
                "total_won": 1 if user_won else 0,
                "total_lost": 0 if user_won else 1,
                "total_spent": bet_amount,
                "total_earned": win_amount if user_won else 0
            }}
        )

        # Add to user's credits - always payout in credits
        db.update_balance(author.id, win_amount, "credits", "$inc")

        # Update server profit statistics if in a server
        if hasattr(ctx, 'guild') and ctx.guild:
            server_db = Servers()
            server_profit = bet_amount - win_amount
            server_db.update_server_profit(ctx.guild.id, server_profit)

            # Add game to server history
            history_entry = {
                "game": "cases",
                "user_id": author.id,
                "username": author.name,
                "bet_amount": bet_amount,
                "currency": currency_used,
                "result": "win" if user_won else "loss",
                "multiplier": selected_multiplier["value"],
                "profit": server_profit,
                "timestamp": int(discord.utils.utcnow().timestamp())
            }
            server_db.update_history(ctx.guild.id, history_entry)

        # Add game to user history
        history_entry = {
            "game": "cases",
            "bet_amount": bet_amount,
            "currency": currency_used,
            "result": "win" if user_won else "loss",
            "multiplier": selected_multiplier["value"],
            "win_amount": win_amount,
            "timestamp": int(discord.utils.utcnow().timestamp())
        }
        db.update_history(author.id, history_entry)

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
        image_buffer = self.generate_result_image(selected_multiplier, author.name)
        image_file = discord.File(image_buffer, filename="case_result.png")
        
        # Create a simplified and clean result embed
        result_embed = discord.Embed(
            title=f"{selected_multiplier['emoji']} {selected_multiplier['name']} {selected_multiplier['emoji']}",
            description=(
                f"**Multiplier: {selected_multiplier['value']}x**\n"
                f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                f"**Payout:** {win_amount:.2f} credits\n"
                f"**Profit:** {win_amount - bet_amount:.2f} credits"
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
                case_info += f"➡️ {m['emoji']} **{m['name']}** ({m['value']}x) - {m['chance']*100:.1f}% ⬅️\n"
            else:
                case_info += f"{m['emoji']} {m['name']} ({m['value']}x) - {m['chance']*100:.1f}%\n"

        result_embed.add_field(
            name="📋 Case Contents",
            value=case_info,
            inline=False
        )

        result_embed.set_footer(text=f"BetSync Casino • {currency_used.capitalize()} bet: {bet_amount:.2f}", icon_url=self.bot.user.avatar.url)

        # Add play again button
        play_again_view = CasesPlayAgainView(self, ctx, bet_amount, currency_used)
        play_again_message = await loading_message.edit(embed=result_embed, file=image_file, view=play_again_view)
        play_again_view.message = play_again_message

def setup(bot):
    bot.add_cog(CasesCog(bot))