import discord
import json
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

    def create_progress_bar(self, current, maximum, length=10):
        """Create a text-based progress bar"""
        filled_length = int(length * current / maximum) if maximum > 0 else 0
        bar = '█' * filled_length + '░' * (length - filled_length)
        percent = current / maximum * 100 if maximum > 0 else 0
        return f"{bar} {percent:.1f}%"

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

        # Calculate title and XP info
        total_wagered = user_data.get("total_spent", 0)
        title, title_description = self.get_user_title(total_wagered)
        current_xp = int(user_data.get('xp', 0))
        current_level = user_data.get('level', 1)
        xp_limit = round(10 * (1 + (current_level - 1) * 0.1))

        # Get user statistics
        total_deposits_usd = user_data.get('total_deposit_amount_usd', 0)
        total_deposits = user_data.get('total_deposit_amount', 0)
        games_played = user_data.get('total_played', 0)
        games_won = user_data.get('total_won', 0)
        games_lost = user_data.get('total_lost', 0)
        total_earned = user_data.get('total_earned', 0)
        total_spent = user_data.get('total_spent', 0)
        current_balance = user_data.get('points', 0)
        primary_coin = user_data.get('primary_coin', 'BTC')
        user_rank = user_data.get('rank', 0)

        # Calculate win rate and net profit (showing only earnings to be deceiving)
        win_rate = (games_won / games_played * 100) if games_played > 0 else 0
        net_profit = total_earned  # Only show earnings, not actual profit

        # Create clean, professional embed
        embed = discord.Embed(
            title=f"👤 | {user.display_name}'s Profile",
            description=f"**{title}** • Level {current_level}",
            color=0x00FFAE
        )

        # Set user avatar as thumbnail (handle cases where user has no avatar)
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        else:
            # Use default Discord avatar or bot's avatar as fallback
            embed.set_thumbnail(url=user.default_avatar.url)

        # Create XP progress bar
        xp_progress = self.create_progress_bar(current_xp, xp_limit, length=10)

        # Account Information - Clean layout
        embed.add_field(
            name="📊 Account Status",
            value=(
                f"**Rank:** #{user_rank:,}\n"
                f"**Balance:** {current_balance:,.2f} points\n"
                f"**Primary Currency:** {primary_coin}"
            ),
            inline=True
        )

        # Financial Overview
        embed.add_field(
            name="💰 Financial Stats",
            value=(
                f"**Total Deposited:** ${total_deposits_usd:,.2f}\n"
                f"**Net Profit:** {net_profit:+,.2f} pts"
            ),
            inline=True
        )

        # Gaming Performance 
        embed.add_field(
            name="🎮 Gaming Stats",
            value=(
                f"**Games Won:** {games_won:,}\n"
                f"**Win Rate:** {win_rate:.1f}%\n"
                f"**Total Wagered:** {total_spent:,.2f} pts"
            ),
            inline=True
        )

        # Experience Progress - Full width for better display
        embed.add_field(
            name="⭐ Experience Progress",
            value=(
                f"**XP:** {current_xp:,} / {xp_limit:,}\n"
                f"```{xp_progress}```"
            ),
            inline=False
        )

        # Clean footer
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        # Delete loading message and send the profile
        await loading_message.delete()
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Profile(bot))