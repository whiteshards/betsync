
import discord
import os
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
    
    @commands.command(name="addcash")
    async def addcash(self, ctx, user: discord.Member, amount: float, currency_type: str):
        """Add tokens or credits to a user (Admin only)
        
        Usage: !addcash @user 100 tokens
               !addcash @user 50 credits
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Validate currency type
        currency_type = currency_type.lower()
        if currency_type not in ["token", "tokens", "credit", "credits"]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description="Please specify either 'tokens' or 'credits'.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Normalize currency type
        if currency_type in ["token", "tokens"]:
            db_field = "tokens"
            display_currency = "tokens"
        else:
            db_field = "credits"
            display_currency = "credits"
        
        # Add the amount to the user's balance
        db = Users()
        user_data = db.fetch_user(user.id)
        
        # If user doesn't exist, register them
        if not user_data:
            dump = {"discord_id": user.id, "tokens": 0, "credits": 0, "history": [], 
                   "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                   "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost': 0}
            db.register_new_user(dump)
            user_data = db.fetch_user(user.id)
        
        # Update user balance
        current_amount = user_data[db_field]
        new_amount = current_amount + amount
        db.update_balance(user.id, new_amount, db_field)
        
        # Add to history
        history_entry = {
            "type": "admin_add",
            "amount": amount,
            "currency": db_field,
            "timestamp": int(discord.utils.utcnow().timestamp()),
            "admin_id": ctx.author.id
        }
        
        db.collection.update_one(
            {"discord_id": user.id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}  # Keep last 100 entries
        )
        
        # Send confirmation message
        money_emoji = emoji()["money"]
        embed = discord.Embed(
            title=f"{money_emoji} | Admin Action: Added {display_currency.capitalize()}",
            description=f"Successfully added **{amount:,.2f} {display_currency}** to {user.mention}'s balance.",
            color=0x00FFAE
        )
        embed.add_field(
            name="New Balance",
            value=f"**{new_amount:,.2f} {display_currency}**",
            inline=False
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="addadmin")
    async def addadmin(self, ctx, user: discord.Member = None):
        """Add a user as a server admin in the database (Bot Admin only)
        
        Usage: !addadmin @user
        """
        # Check if command user is in admins.txt
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
                description="Please mention a user to add as an admin.",
                color=0xFF0000
            )
            embed.add_field(
                name="Correct Usage",
                value="`!addadmin @user`",
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        # Get server data from database
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)
        
        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if user is already an admin
        server_admins = server_data.get("server_admins", [])
        if user.id in server_admins:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Already Admin",
                description=f"{user.mention} is already a server admin.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Add user to server_admins list
        server_admins.append(user.id)
        
        # Update database
        db.collection.update_one(
            {"server_id": ctx.guild.id},
            {"$set": {"server_admins": server_admins}}
        )
        
        # Send confirmation message
        embed = discord.Embed(
            title="<:checkmark:1344252974188335206> | Admin Added",
            description=f"{user.mention} has been added as a server admin.",
            color=0x00FFAE
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="viewadmins")
    async def viewadmins(self, ctx, server_id: int = None):
        """View server admins across all servers (Bot Admin only)
        
        Usage: !viewadmins [server_id]
        """
        # Check if the user is a bot admin (in admins.txt)
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to bot administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # If server_id is provided, get that server's admins
        if server_id:
            db = Servers()
            server_data = db.fetch_server(server_id)
            
            if not server_data:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Server Not Found",
                    description=f"Server with ID `{server_id}` isn't registered in our database.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
            server_name = server_data.get("server_name", f"Unknown Server ({server_id})")
            server_admins = server_data.get("server_admins", [])
            
            embed = discord.Embed(
                title=f"👑 Server Admins for {server_name}",
                description=f"Server ID: `{server_id}`",
                color=0x00FFAE
            )
            
            if not server_admins:
                embed.add_field(
                    name="No Admins",
                    value="This server has no admins configured.",
                    inline=False
                )
            else:
                admin_list = []
                for admin_id in server_admins:
                    admin_list.append(f"<@{admin_id}> (`{admin_id}`)")
                
                embed.add_field(
                    name=f"Admins ({len(server_admins)})",
                    value="\n".join(admin_list) if admin_list else "None",
                    inline=False
                )
        else:
            # If no server_id is provided, show usage
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Usage",
                description="Please specify a server ID to view its admins.",
                color=0xFF0000
            )
            embed.add_field(
                name="Correct Usage",
                value="`!viewadmins server_id`",
                inline=False
            )
            embed.add_field(
                name="Example",
                value=f"`!viewadmins {ctx.guild.id}`",
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        embed.set_footer(text=f"Requested by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="removeadmin")
    async def removeadmin(self, ctx, user: discord.Member):
        """Remove a user as a server admin from the database (Bot Admin only)
        
        Usage: !removeadmin @user
        """
        # Check if command user is in admins.txt
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Get server data from database
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)
        
        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if user is an admin
        server_admins = server_data.get("server_admins", [])
        if user.id not in server_admins:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Not An Admin",
                description=f"{user.mention} is not a server admin.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Remove user from server_admins list
        server_admins.remove(user.id)
        
        # Update database
        db.collection.update_one(
            {"server_id": ctx.guild.id},
            {"$set": {"server_admins": server_admins}}
        )
        
        # Send confirmation message
        embed = discord.Embed(
            title="<:checkmark:1344252974188335206> | Admin Removed",
            description=f"{user.mention} has been removed as a server admin.",
            color=0x00FFAE
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="listadmins")
    async def listadmins(self, ctx):
        """List all server admins (Bot Admin only)
        
        Usage: !listadmins
        """
        # Check if command user is in admins.txt
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Get server data from database
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)
        
        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Get server admins
        server_admins = server_data.get("server_admins", [])
        
        # Create embed
        embed = discord.Embed(
            title="👑 Server Admins",
            description=f"Server admins for {ctx.guild.name}",
            color=0x00FFAE
        )
        
        if not server_admins:
            embed.add_field(
                name="No Admins",
                value="This server has no admins configured.",
                inline=False
            )
        else:
            admin_list = []
            for admin_id in server_admins:
                admin = ctx.guild.get_member(admin_id)
                if admin:
                    admin_list.append(f"{admin.mention} (`{admin.id}`)")
                else:
                    admin_list.append(f"Unknown User (`{admin_id}`)")
            
            embed.add_field(
                name=f"Admins ({len(server_admins)})",
                value="\n".join(admin_list),
                inline=False
            )
        
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="fetch")
    async def fetch(self, ctx, user_input = None):
        """Fetch detailed information about a user (Bot Admin only)
        
        Usage: !fetch @user
               !fetch user_id
        """
        try:
            print(f"[DEBUG] Fetch command called by {ctx.author.id} with input: {user_input}")
            # Check if command user is an admin
            if not self.is_admin(ctx.author.id):
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Access Denied",
                    description="This command is restricted to administrators only.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
            # Check if user is provided
            if user_input is None:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Usage",
                    description="Please mention a user or provide a user ID to fetch their information.",
                    color=0xFF0000
                )
                embed.add_field(
                    name="Correct Usage",
                    value="`!fetch @user` or `!fetch user_id`",
                    inline=False
                )
                return await ctx.reply(embed=embed)
            
            # Get user from input (either a mention or ID)
            user = None
            user_id = None
            
            # Check if input is a Discord mention
            if ctx.message.mentions:
                user = ctx.message.mentions[0]
                user_id = user.id
                print(f"[DEBUG] Found mention: user={user}, user_id={user_id}")
            else:
                # Try to parse as ID
                try:
                    user_id = int(user_input.strip())
                    print(f"[DEBUG] Trying to fetch user with ID: {user_id}")
                    user = self.bot.get_user(user_id)
                    print(f"[DEBUG] Result from get_user: {user}")
                    if user is None:
                        # Try to fetch user if not in cache
                        try:
                            print(f"[DEBUG] Attempting fetch_user for {user_id}")
                            user = await self.bot.fetch_user(user_id)
                            print(f"[DEBUG] Result from fetch_user: {user}")
                        except discord.NotFound:
                            print(f"[DEBUG] User with ID {user_id} not found in Discord")
                        except Exception as e:
                            print(f"[DEBUG] Error fetching user: {str(e)}")
                except ValueError:
                    print(f"[DEBUG] Input '{user_input}' is not a valid ID")
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Input",
                        description="Please provide a valid user mention or ID.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
            
            # Get user data from database
            print(f"[DEBUG] Fetching user data from database for ID: {user_id}")
            db = Users()
            user_data = db.fetch_user(user_id)
            print(f"[DEBUG] Database result: {user_data is not None}")
            
            if not user_data:
                print(f"[DEBUG] User {user_id} not found in database")
                # Handle case where user is None
                user_id_str = f"`{user_id}`"
                user_mention = user.mention if user else user_id_str
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | User Not Found",
                    description=f"User {user_mention} isn't registered in our database.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
            # Create embed with user information
            emojis = emoji()
            
            user_mention = user.mention if user else f"`{user_id}`"
            embed = discord.Embed(
                title=f"User Information",
                description=f"Detailed information for {user_mention}",
                color=0x00FFAE
            )
            
            # User Account Info
            embed.add_field(
                name=f"User ID",
                value=f"`{user_id}`",
                inline=True
            )
            
            # Only add these fields if we have a user object
            if user:
                embed.add_field(
                    name=f"Account Created",
                    value=f"<t:{int(user.created_at.timestamp())}:R>",
                    inline=True
                )
                
                # Check if user is in guild and has joined_at attribute
                member = ctx.guild.get_member(user_id)
                if member and member.joined_at:
                    embed.add_field(
                        name=f"Server Joined",
                        value=f"<t:{int(member.joined_at.timestamp())}:R>",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f"Server Joined",
                        value="Unknown/Not in server",
                        inline=True
                    )
            else:
                embed.add_field(
                    name=f"Note",
                    value="Limited information available (user not found in Discord)",
                    inline=False
                )
            
            # Balance Information
            embed.add_field(
                name=f"Balance",
                value=(
                    f"**Tokens:** {user_data.get('tokens', 0):,.2f}\n"
                    f"**Credits:** {user_data.get('credits', 0):,.2f}"
                ),
                inline=False
            )
            
            # Transaction History
            embed.add_field(
                name=f"Deposit & Withdraw",
                value=(
                    f"**Total Deposited:** {user_data.get('total_deposit_amount', 0):,.2f}\n"
                    f"**Total Withdrawn:** {user_data.get('total_withdraw_amount', 0):,.2f}"
                ),
                inline=True
            )
            
            # Betting History
            embed.add_field(
                name=f"Betting Stats",
                value=(
                    f"**Games Played:** {user_data.get('total_played', 0):,}\n"
                    f"**Games Won:** {user_data.get('total_won', 0):,}\n"
                    f"**Games Lost:** {user_data.get('total_lost', 0):,}"
                ),
                inline=True
            )
            
            # Money Stats
            embed.add_field(
                name=f"Money Stats",
                value=(
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
                value=(
                    f"**Win Rate:** {win_rate:.2f}%\n"
                    f"**Profit/Loss:** {user_data.get('total_earned', 0) - user_data.get('total_spent', 0):,.2f}"
                ),
                inline=False
            )
            
            # Set user avatar as thumbnail if available
            if user and hasattr(user, 'avatar') and user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            
            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            await ctx.reply(embed=embed)
            print(f"[DEBUG] Successfully sent fetch response")
        except Exception as e:
            print(f"[ERROR] Error in fetch command: {str(e)}")
            try:
                error_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Error",
                    description=f"An error occurred while processing your request: ```{str(e)}```",
                    color=0xFF0000
                )
                await ctx.reply(embed=error_embed)
            except Exception as reply_error:
                print(f"[ERROR] Could not send error message: {str(reply_error)}")

def setup(bot):
    bot.add_cog(AdminCommands(bot))
