import discord
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class AdminCurseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cursed_players = {}  # {user_id: remaining_losses}
        self.admin_ids = self.load_admin_ids()

    def load_admin_ids(self):
        """Load admin IDs from admins.txt file"""
        admin_ids = []
        try:
            with open("admins.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        admin_ids.append(int(line))
        except Exception as e:
            print(f"Error loading admin IDs: {e}")
        return admin_ids

    def is_admin(self, user_id):
        """Check if a user ID is in the admin list"""
        return user_id in self.admin_ids

    @commands.command(name="lose")
    async def lose_command(self, ctx, user: discord.User = None, games: int = 1):
        """Curse a player to lose their next few games (Admin only)

        Usage: !lose @user [number_of_games]
               !lose user_id [number_of_games]
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if user is provided
        if user is None:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Usage",
                description="Please mention a user or provide a user ID to curse.",
                color=0xFF0000
            )
            embed.add_field(
                name="Correct Usage",
                value="`!lose @user [games]`\n`!lose user_id [games]`\n\nExample: `!lose @user 5` (makes them lose next 5 games)",
                inline=False
            )
            return await ctx.reply(embed=embed)

        # Validate games parameter
        if games < 1 or games > 50:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Number",
                description="Number of games must be between 1 and 50.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if user is an admin (prevent cursing admins)
        if self.is_admin(user.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Cannot Curse Admin",
                description="You cannot curse an administrator.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Add or update curse
        if user.id in self.cursed_players:
            self.cursed_players[user.id] += games
        else:
            self.cursed_players[user.id] = games

        # Send confirmation message
        embed = discord.Embed(
            title="💀 | Player Cursed with Losses",
            description=f"{user.mention} has been cursed to lose their next **{games}** games!\n\nTotal remaining losses: **{self.cursed_players[user.id]}**",
            color=0x8B0000
        )
        embed.set_footer(text=f"Cursed by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

    @commands.command(name="removecurse", aliases=["uncurse"])
    async def remove_curse(self, ctx, user: discord.User = None):
        """Remove loss curse from a player (Admin only)

        Usage: !removecurse @user
               !removecurse user_id
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if user is provided
        if user is None:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Usage",
                description="Please mention a user or provide a user ID to remove curse from.",
                color=0xFF0000
            )
            embed.add_field(
                name="Correct Usage",
                value="`!removecurse @user`\n`!removecurse user_id`",
                inline=False
            )
            return await ctx.reply(embed=embed)

        if user.id not in self.cursed_players:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Not Cursed",
                description=f"{user.mention} is not cursed with losses.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Remove curse
        if user.id in self.cursed_players:
            del self.cursed_players[user.id]
            removed = True
            # Sync with game cogs
            self.sync_cursed_players()
        else:
            removed = False

        # Send confirmation message
        embed = discord.Embed(
            title="✨ | Curse Removed",
            description=f"Loss curse has been removed from {user.mention}.\n\nThey had **{remaining_losses}** losses remaining.",
            color=0x00FFAE
        )
        embed.set_footer(text=f"Curse removed by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

    @commands.command(name="viewcurses", aliases=["curses"])
    async def view_curses(self, ctx):
        """View all cursed players (Admin only)

        Usage: !viewcurses
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Create embed
        embed = discord.Embed(
            title="💀 Cursed Players",
            description="Players who are cursed to lose games",
            color=0x8B0000
        )

        if not self.cursed_players:
            embed.add_field(
                name="No Cursed Players",
                value="There are currently no cursed players.",
                inline=False
            )
        else:
            curse_entries = []
            for user_id, remaining_losses in self.cursed_players.items():
                try:
                    user = await self.bot.fetch_user(user_id)
                    curse_entries.append(f"{user.mention} - **{remaining_losses}** losses remaining")
                except:
                    curse_entries.append(f"Unknown User (`{user_id}`) - **{remaining_losses}** losses remaining")

            # Split into chunks if there are many entries
            chunks = [curse_entries[i:i+15] for i in range(0, len(curse_entries), 15)]

            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name=f"Cursed Players {i+1}" if len(chunks) > 1 else "Cursed Players",
                    value="\n".join(chunk),
                    inline=False
                )

        embed.set_footer(text=f"Requested by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.reply(embed=embed)

    def is_player_cursed(self, user_id):
        """Check if a player is cursed to lose"""
        return user_id in self.cursed_players and self.cursed_players[user_id] > 0

    def consume_curse(self, user_id):
        """Consume one curse from a player (call this when they lose a game)"""
        if user_id in self.cursed_players:
            self.cursed_players[user_id] -= 1
            if self.cursed_players[user_id] <= 0:
                del self.cursed_players[user_id]
                return True  # Curse is now complete
        return False  # Still has more losses to go

    def force_loss(self, user_id):
        """Force a loss for a cursed player and consume the curse"""
        if self.is_player_cursed(user_id):
            curse_complete = self.consume_curse(user_id)
            return True, curse_complete
        return False, False

    def sync_cursed_players(self):
        """Sync cursed_players with game cogs"""
        for cog_name, cog in self.bot.cogs.items():
            if hasattr(cog, 'cursed_players'):
                cog.cursed_players = self.cursed_players

def setup(bot):
    bot.add_cog(AdminCurseCog(bot))