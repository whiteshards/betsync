
import discord
import json
import os
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Load titles from static_data/titles.json
        with open('static_data/titles.json', 'r') as f:
            self.titles_data = json.load(f)

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
        
        # Calculate total wagered (total_spent in database)
        total_wagered = user_data.get("total_spent", 0)
        
        # Get user's title based on amount wagered
        title, title_description = self.get_user_title(total_wagered)
        
        # Create the profile embed
        embed = discord.Embed(
            title=f"{emojis.get('profile', '👤')} User Profile",
            color=0x00FFAE
        )
        
        # Set user avatar as thumbnail if they have one
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        # User information with title
        embed.add_field(
            name="User Info",
            value=f"**Name:** {user.name}\n**ID:** {user.id}\n**Title:** {title}",
            inline=False
        )
        
        # Title description
        embed.add_field(
            name="Title Description",
            value=title_description or "No description available",
            inline=False
        )
        
        # Balance information
        embed.add_field(
            name="Balance",
            value=f"**Tokens:** {user_data.get('tokens', 0):,.2f}\n**Credits:** {user_data.get('credits', 0):,.2f}",
            inline=True
        )
        
        # User statistics
        embed.add_field(
            name=f"User Statistics",
            value=(
                f"**Total Wagered:** {total_wagered:,.2f}\n"
                f"**Total Deposited:** {user_data.get('total_deposit_amount', 0):,.2f}\n"
                f"**Total Withdrawn:** {user_data.get('total_withdraw_amount', 0):,.2f}\n"
                f"**Games Played:** {user_data.get('total_played', 0):,}\n"
                f"**Games Won:** {user_data.get('total_won', 0):,}\n"
                f"**Games Lost:** {user_data.get('total_lost', 0):,}\n"
                f"**Total Spent:** {user_data.get('total_spent', 0):,.2f}\n"
                f"**Total Earned:** {user_data.get('total_earned', 0):,.2f}"
            ),
            inline=True
        )
        
        # Win Rate Calculation
        total_played = user_data.get('total_played', 0)
        win_rate = (user_data.get('total_won', 0) / total_played * 100) if total_played > 0 else 0
        
        embed.add_field(
            name=f"Performance",
            value=f"**Win Rate:** {win_rate:.2f}%",
            inline=False
        )
        
        # Set footer
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        # Delete loading message and send the profile
        await loading_message.delete()
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Profile(bot))
