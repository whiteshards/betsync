
import discord
import json
import os
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from PIL import Image, ImageDraw, ImageFont
import io

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load titles from static_data/titles.json
        with open('static_data/titles.json', 'r') as f:
            self.titles_data = json.load(f)
        
        # Load fonts
        self.title_font = ImageFont.truetype("arial.ttf", 24)
        self.subtitle_font = ImageFont.truetype("arial.ttf", 20)
        self.regular_font = ImageFont.truetype("arial.ttf", 16)
        self.small_font = ImageFont.truetype("arial.ttf", 14)

    def get_user_title(self, total_wagered):
        """Determine user's title based on total amount wagered"""
        titles = self.titles_data.get("titles", {})
        current_title = "Beginner"  # Default title
        
        # Find the highest title threshold the user has reached
        for title, data in titles.items():
            if total_wagered >= data.get("wagered", 0):
                if titles.get(current_title, {}).get("wagered", 0) <= data.get("wagered", 0):
                    current_title = title
        
        return current_title, titles.get(current_title, {}).get("description", "")

    def generate_profile_image(self, user, user_data):
        """Generate profile image with user stats"""
        # Create a dark background image (960x600)
        width, height = 960, 500  # Reduced height since we removed top section
        image = Image.new('RGB', (width, height), (18, 18, 18))
        draw = ImageDraw.Draw(image)
        
        # Draw checkerboard pattern in the background (subtle)
        square_size = 40
        for y in range(0, height, square_size):
            for x in range(0, width, square_size):
                if (x // square_size + y // square_size) % 2 == 0:
                    draw.rectangle([x, y, x + square_size, y + square_size], fill=(25, 25, 25))
        
        # Calculate total wagered
        total_wagered = user_data.get("total_spent", 0)
        
        # Get user's title
        title, title_description = self.get_user_title(total_wagered)
        
        # Calculate XP info
        current_xp = user_data.get('xp', 0)
        current_level = user_data.get('level', 1)
        xp_limit = round(10 * (1 + (current_level - 1) * 0.1))
        
        # Calculate win rate
        total_played = user_data.get('total_played', 0)
        win_rate = (user_data.get('total_won', 0) / total_played * 100) if total_played > 0 else 0
        
        # Center coordinates for the layout
        center_x = width // 2
        
        # Draw sections
        left_x = 100
        right_x = width - 100
        section_y = 50  # Adjusted to start higher since we removed top section
        section_height = 250
        
        # Left section - User Info
        draw.rectangle([left_x - 50, section_y - 20, center_x - 20, section_y + section_height], 
                       fill=(30, 30, 30), outline=(40, 40, 40))
        draw.text((left_x, section_y), "User Information", fill=(200, 200, 200), font=self.subtitle_font)
        
        # Right section - Casino Stats
        draw.rectangle([center_x + 20, section_y - 20, right_x + 50, section_y + section_height], 
                       fill=(30, 30, 30), outline=(40, 40, 40))
        draw.text((center_x + 70, section_y), "Casino Statistics", fill=(200, 200, 200), font=self.subtitle_font)
        
        # User information details
        details_y = section_y + 40
        line_height = 34
        
        # Left section details
        draw.text((left_x, details_y), "Title:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((left_x + 200, details_y), f"{title}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((left_x, details_y + line_height), "Level:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((left_x + 200, details_y + line_height), f"{current_level}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((left_x, details_y + line_height * 2), "XP:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((left_x + 200, details_y + line_height * 2), f"{current_xp}/{xp_limit}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((left_x, details_y + line_height * 3), "Rank:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((left_x + 200, details_y + line_height * 3), f"{user_data.get('rank', 0)}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((left_x, details_y + line_height * 4), "Tokens:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((left_x + 200, details_y + line_height * 4), f"{round(user_data.get('tokens', 0), 2):.2f}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((left_x, details_y + line_height * 5), "Credits:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((left_x + 200, details_y + line_height * 5), f"{round(user_data.get('credits', 0), 2):.2f}", fill=(255, 255, 255), font=self.regular_font)
        
        # Right section details
        right_left_x = center_x + 70
        
        draw.text((right_left_x, details_y), "Total Wagered:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((right_left_x + 200, details_y), f"{round(total_wagered, 2):.2f}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((right_left_x, details_y + line_height), "Total Deposited:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((right_left_x + 200, details_y + line_height), f"{round(user_data.get('total_deposit_amount', 0), 2):.2f}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((right_left_x, details_y + line_height * 2), "Total Withdrawn:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((right_left_x + 200, details_y + line_height * 2), f"{round(user_data.get('total_withdraw_amount', 0), 2):.2f}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((right_left_x, details_y + line_height * 3), "Games Played:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((right_left_x + 200, details_y + line_height * 3), f"{user_data.get('total_played', 0)}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((right_left_x, details_y + line_height * 4), "Games Won:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((right_left_x + 200, details_y + line_height * 4), f"{user_data.get('total_won', 0)}", fill=(255, 255, 255), font=self.regular_font)
        
        draw.text((right_left_x, details_y + line_height * 5), "Win Rate:", fill=(150, 150, 150), font=self.regular_font)
        draw.text((right_left_x + 200, details_y + line_height * 5), f"{win_rate:.2f}%", fill=(255, 255, 255), font=self.regular_font)
        
        # Footer section
        footer_y = section_y + section_height + 20
        draw.text((center_x, footer_y), "BetSync Casino", fill=(150, 150, 150), font=self.small_font, anchor="mt")
        
        # Save image to bytes buffer
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer

    @commands.command(aliases=["prof"])
    async def profile(self, ctx, user: discord.Member = None):
        """View your or another user's profile with stats and title"""
        # Get emojis
        emojis = emoji()
        loading_emoji = emojis["loading"]
        
        # Send loading message
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Loading Profile...",
            description="Please wait while we fetch the profile data.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # If no user is specified, use the command author
        if user is None:
            user = ctx.author
        
        # Fetch user data from database
        db = Users()
        user_data = db.fetch_user(user.id)
        
        if user_data == False:
            # User not found in database
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="This user doesn't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
        
        # Generate profile image
        image_buffer = self.generate_profile_image(user, user_data)
        
        # Calculate title and XP info
        total_wagered = user_data.get("total_spent", 0)
        title, title_description = self.get_user_title(total_wagered)
        current_xp = user_data.get('xp', 0)
        current_level = user_data.get('level', 1)
        xp_limit = round(10 * (1 + (current_level - 1) * 0.1))
        
        # Calculate win rate
        total_played = user_data.get('total_played', 0)
        win_rate = (user_data.get('total_won', 0) / total_played * 100) if total_played > 0 else 0
        
        # Create embed with user information
        embed = discord.Embed(
            title=f"<:member_hexagon:1347561410837876786> User Profile",
            description=f"**{user.name}'s Casino Profile**",
            color=0x00FFAE
        )
        
        # Add image to embed first (to ensure it appears centered)
        file = discord.File(fp=image_buffer, filename="profile.png")
        embed.set_image(url="attachment://profile.png")
        
        # Add user information field
        embed.add_field(
            name="User Information",
            value=(
                f"**Username:** {user.name}\n"
                f"**User ID:** {user.id}\n"
                #f"**Title:** {title}\n"
                #f"**Level:** {current_level}\n"
                #f"**XP:** {current_xp}/{xp_limit}\n"
                #f"**Rank:** {user_data.get('rank', 0)}"
            ),
            inline=True
        )
        
        # Add balance information field
        #embed.add_field(
            #name="Balance",
            #value=(
                #f"**Tokens:** {user_data.get('tokens', 0):.2f}\n"
                #f"**Credits:** {user_data.get('credits', 0):.2f}"
            #),
            #inline=True
        #)
        
        # Set user avatar as thumbnail if available
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        # Set footer
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        # Delete loading message and send the profile
        await loading_message.delete()
        await ctx.reply(embed=embed, file=file)

def setup(bot):
    bot.add_cog(Profile(bot))
