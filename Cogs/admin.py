
import discord
import os
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import io
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers, ProfitData, ServerProfit
from Cogs.utils.emojis import emoji

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_ids = self.load_admin_ids()
        self.blacklisted_ids = self.load_blacklisted_ids()
        
        # Set default matplotlib style
        plt.style.use('dark_background')
    
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
        
    def load_blacklisted_ids(self):
        """Load blacklisted IDs from blacklist.txt file"""
        blacklisted_ids = []
        try:
            with open("blacklist.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        blacklisted_ids.append(int(line))
        except Exception as e:
            print(f"Error loading blacklisted IDs: {e}")
        return blacklisted_ids
        
    def save_blacklisted_ids(self):
        """Save blacklisted IDs to blacklist.txt file"""
        try:
            with open("blacklist.txt", "w") as f:
                for user_id in self.blacklisted_ids:
                    f.write(f"{user_id}\n")
            return True
        except Exception as e:
            print(f"Error saving blacklisted IDs: {e}")
            return False
    
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
                
    @commands.command(name="blacklist")
    async def blacklist(self, ctx, user: discord.User = None):
        """Blacklist a user from using the bot (Bot Admin only)
        
        Usage: !blacklist @user
               !blacklist user_id
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
                description="Please mention a user or provide a user ID to blacklist.",
                color=0xFF0000
            )
            embed.add_field(
                name="Correct Usage",
                value="`!blacklist @user`\n`!blacklist user_id`",
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        # Check if user is already blacklisted
        if user.id in self.blacklisted_ids:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Already Blacklisted",
                description=f"{user.mention} is already blacklisted.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if user is an admin (prevent blacklisting admins)
        if self.is_admin(user.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Cannot Blacklist Admin",
                description=f"You cannot blacklist an administrator.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Add user to blacklisted_ids
        self.blacklisted_ids.append(user.id)
        
        # Save to blacklist.txt
        success = self.save_blacklisted_ids()
        
        if not success:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to save the blacklist. Please check the logs.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Send confirmation message
        embed = discord.Embed(
            title="🚫 | User Blacklisted",
            description=f"{user.mention} has been blacklisted from using the bot.",
            color=0x00FFAE
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="unblacklist")
    async def unblacklist(self, ctx, user: discord.User = None):
        """Remove a user from the blacklist (Bot Admin only)
        
        Usage: !unblacklist @user
               !unblacklist user_id
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
                description="Please mention a user or provide a user ID to remove from the blacklist.",
                color=0xFF0000
            )
            embed.add_field(
                name="Correct Usage",
                value="`!unblacklist @user`\n`!unblacklist user_id`",
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        # Check if user is blacklisted
        if user.id not in self.blacklisted_ids:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Not Blacklisted",
                description=f"{user.mention} is not in the blacklist.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Remove user from blacklisted_ids
        self.blacklisted_ids.remove(user.id)
        
        # Save to blacklist.txt
        success = self.save_blacklisted_ids()
        
        if not success:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to save the blacklist. Please check the logs.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Send confirmation message
        embed = discord.Embed(
            title="✅ | User Unblacklisted",
            description=f"{user.mention} has been removed from the blacklist.",
            color=0x00FFAE
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    @commands.command(name="viewblacklist")
    async def viewblacklist(self, ctx):
        """View all blacklisted users (Bot Admin only)
        
        Usage: !viewblacklist
        """
        # Check if command user is in admins.txt
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Create embed
        embed = discord.Embed(
            title="🚫 Blacklisted Users",
            description="Users who are blacklisted from using the bot",
            color=0x00FFAE
        )
        
        if not self.blacklisted_ids:
            embed.add_field(
                name="No Blacklisted Users",
                value="There are currently no blacklisted users.",
                inline=False
            )
        else:
            blacklist_entries = []
            for user_id in self.blacklisted_ids:
                try:
                    user = await self.bot.fetch_user(user_id)
                    blacklist_entries.append(f"{user.mention} (`{user.id}`)")
                except:
                    blacklist_entries.append(f"Unknown User (`{user_id}`)")
            
            # Split into chunks if there are many entries
            chunks = [blacklist_entries[i:i+15] for i in range(0, len(blacklist_entries), 15)]
            
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name=f"Blacklisted Users {i+1}" if len(chunks) > 1 else "Blacklisted Users",
                    value="\n".join(chunk),
                    inline=False
                )
        
        embed.set_footer(text=f"Requested by: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)
        
    async def generate_profit_graph(self, view_type="daily"):
        """Generate a profit graph based on the time frame"""
        # Get profit data from MongoDB
        profit_db = ProfitData()
        profit_data = profit_db.get_profit_data()
        
        if not profit_data:
            raise ValueError("No profit data available")
        
        # Prepare data based on view type
        dates = []
        profits = []
        cumulative_profits = []
        total_profit = 0
        
        # Set time frame data
        if view_type == "daily":
            # Get last 30 days
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(days=30)
            
            # Create a date range for the last 30 days
            date_range = {}
            current_date = start_date
            while current_date <= end_date:
                date_range[current_date] = 0
                current_date += datetime.timedelta(days=1)
            
            # Fill in available data
            for item in profit_data:
                date_str = item.get("date")
                # Convert string date to datetime.date if needed
                if isinstance(date_str, str):
                    try:
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                elif isinstance(date_str, datetime.date):
                    date = date_str
                else:
                    continue
                
                if start_date <= date <= end_date:
                    date_range[date] = item.get("total_profit", 0)
            
            # Convert to lists
            for date, profit in sorted(date_range.items()):
                dates.append(date)
                profits.append(profit * 0.0212)  # Convert tokens to USD (1 token = 0.0212$)
                total_profit += profit
                cumulative_profits.append(total_profit * 0.0212)  # Convert tokens to USD
            
            x_label = "Day"
            title = "Daily Profit (Last 30 Days)"
            
        elif view_type == "monthly":
            # Group by month
            monthly_data = {}
            
            for item in profit_data:
                date_str = item.get("date")
                # Convert string date to datetime.date if needed
                if isinstance(date_str, str):
                    try:
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                elif isinstance(date_str, datetime.date):
                    date = date_str
                else:
                    continue
                
                # Create a key for year-month
                month_key = datetime.date(date.year, date.month, 1)
                    
                if month_key not in monthly_data:
                    monthly_data[month_key] = 0
                    
                monthly_data[month_key] += item.get("total_profit", 0)
            
            # Sort by date and convert to lists
            for date, profit in sorted(monthly_data.items()):
                dates.append(date)
                profits.append(profit * 0.0212)  # Convert tokens to USD
                total_profit += profit
                cumulative_profits.append(total_profit * 0.0212)  # Convert tokens to USD
            
            x_label = "Month"
            title = "Monthly Profit"
            
        else:  # all_time
            # Group by date (keep all records, but ensure they're sorted)
            all_data = {}
            
            for item in profit_data:
                date_str = item.get("date")
                # Convert string date to datetime.date if needed
                if isinstance(date_str, str):
                    try:
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                elif isinstance(date_str, datetime.date):
                    date = date_str
                else:
                    continue
                
                if date not in all_data:
                    all_data[date] = 0
                    
                    all_data[date] += item.get("total_profit", 0)
            
            # Sort by date and convert to lists
            for date, profit in sorted(all_data.items()):
                dates.append(date)
                profits.append(profit * 0.0212)  # Convert tokens to USD
                total_profit += profit
                cumulative_profits.append(total_profit * 0.0212)  # Convert tokens to USD
            
            x_label = "Date"
            title = "All-Time Profit"
        
        # Create the plot with a modern gray background
        fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
        fig.patch.set_facecolor('#2B2D31')  # Modern dark gray for outer background
        ax.set_facecolor('#36393F')  # Slightly lighter gray for plot area
        
        # Plot the profit trend with a nice gradient fill
        if cumulative_profits:
            # Create gradient fill
            line, = ax.plot(dates, cumulative_profits, color='#00FFAE', linewidth=2.5, marker='', zorder=3)
            
            # Fill area under the curve with gradient
            ax.fill_between(dates, cumulative_profits, color='#00FFAE', alpha=0.2)
            
            # Get the highest value for annotation
            max_idx = np.argmax(cumulative_profits)
            max_date = dates[max_idx]
            max_value = cumulative_profits[max_idx]
            
            # Add a dot marker at the highest value with annotation
            ax.plot(max_date, max_value, 'o', color='white', markersize=8, zorder=4)
            
            # Add a "tooltip" annotation with black background
            bbox_props = dict(boxstyle="round,pad=0.5", facecolor='black', alpha=0.8, edgecolor='gray')
            cumulative_text = f"{max_date.strftime('%d %b %Y')}\nCumulative: ${max_value:,.2f}"
            ax.annotate(cumulative_text, 
                        (max_date, max_value),
                        xytext=(10, 10),
                        textcoords="offset points",
                        bbox=bbox_props,
                        color='white',
                        zorder=5)
            
            # Format the y-axis with dollar signs
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
            
            # Format x-axis dates
            if view_type == "daily":
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
            elif view_type == "monthly":
                ax.xaxis.set_major_locator(mdates.MonthLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            else:
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
                
            # Customize grid
            ax.grid(True, linestyle='--', alpha=0.3, zorder=1)
            
            # Add labels and title with white text
            ax.set_xlabel(x_label, color='white', fontsize=12)
            ax.set_ylabel('Profit (USD)', color='white', fontsize=12)
            
            # Calculate total profit and growth percentage
            first_value = cumulative_profits[0] if cumulative_profits else 0
            last_value = cumulative_profits[-1] if cumulative_profits else 0
            growth_pct = ((last_value - first_value) / first_value * 100) if first_value > 0 else 0
            
            # Title with accumulated amount and growth percentage
            title_text = f"Total Revenue\n${last_value:,.2f}"
            growth_text = f"+{growth_pct:.2f}%" if growth_pct >= 0 else f"{growth_pct:.2f}%"
            
            # Set the main title with Helvetica font
            from matplotlib.font_manager import FontProperties
            try:
                # Try to load Helvetica font
                helvetica_font = FontProperties(fname="Helvetica-Bold.ttf")
                ax.set_title(title_text, size=32, color='white', pad=20, fontproperties=helvetica_font)
            except:
                # Fallback to default font if Helvetica.ttf cannot be loaded
                print("Could not load Helvetica font, using default")
                ax.set_title(title_text, fontsize=20, color='white', pad=20)
            
            # Add the growth percentage text with color based on value
            text_color = '#4CAF50' if growth_pct >= 0 else '#FF5252'
            #fig.text(0.15, 0.86, growth_text, fontsize=12, color=text_color)
            
            # Add the time period text
            #fig.text(0.15, 0.82, f"• {title}", fontsize=10, color='white', alpha=0.7)
            
            # Style the axes and ticks
            ax.tick_params(colors='white', which='both')
            for spine in ax.spines.values():
                spine.set_edgecolor('#555555')
            
            # Add BetSync watermark
            plt.figtext(0.5, 0.01, "BetSync Casino", fontsize=10, color='white', alpha=0.4, ha='center')
            
            # Adjust layout for better padding
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            # Add a subtle shadow effect for the frame
            # This is done by adding a rectangle patch with a gradient alpha
            from matplotlib.patches import Rectangle
            shadow = Rectangle((0, 0), 1, 1, transform=fig.transFigure, 
                              facecolor='black', alpha=0.2, zorder=-1)
            fig.patches.append(shadow)
            
            # Save to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor=fig.get_facecolor())
            buf.seek(0)
            
            # Create Discord file and embed
            file = discord.File(buf, filename="profit_graph.png")
            
            embed = discord.Embed(
                title=f"BetSync Casino {title}", 
                description=f"**Total Revenue:** ${last_value:,.2f}",
                color=0x2B2D31
            )
            
            # Add growth information
            growth_indicator = "📈" if growth_pct >= 0 else "📉"
            embed.add_field(
                name=f"{growth_indicator} Growth",
                value=f"**{growth_text}** during this period",
                inline=True
            )
            
            # Add average daily profit
            if len(cumulative_profits) > 1:
                avg_daily = last_value / len(cumulative_profits)
                embed.add_field(
                    name="💰 Average",
                    value=f"**${avg_daily:,.2f}** per {x_label.lower()}",
                    inline=True
                )
            
            embed.set_image(url="attachment://profit_graph.png")
            embed.set_footer(text="Click the buttons below to change the time period")
            
            # Close the figure to prevent memory leaks
            plt.close(fig)
            
            return embed, file
        else:
            # If no data available
            embed = discord.Embed(
                title="No Profit Data Available",
                description="There is no profit data available for the selected time period.",
                color=0xFF0000
            )
            
            # Create empty plot for attachment
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor=fig.get_facecolor())
            buf.seek(0)
            file = discord.File(buf, filename="no_data.png")
            
            # Close the figure to prevent memory leaks
            plt.close(fig)
            
            return embed, file
    
    async def generate_server_profit_data(self, date=None, page=0, servers_per_page=20):
        """Generate a server profit graph and data for the specified date"""
        # Get server profit data from MongoDB
        server_profit_db = ServerProfit()
        
        # Default to today if no date provided
        if date is None:
            date = datetime.datetime.now().date().strftime("%Y-%m-%d")
            
        # Get all server profits for the date
        server_profits = server_profit_db.get_all_server_profits(date)
        
        if not server_profits:
            raise ValueError(f"No server profit data available for {date}")
        
        # Sort servers by profit (highest to lowest)
        server_profits.sort(key=lambda x: x.get("profit", 0), reverse=True)
        
        # Calculate total and average
        total_profit = sum(server.get("profit", 0) for server in server_profits)
        avg_profit = total_profit / len(server_profits) if server_profits else 0
        
        # Calculate USD equivalents (based on the rate seen in the code: 1 token = 0.0212 USD)
        total_profit_usd = total_profit * 0.0212
        avg_profit_usd = avg_profit * 0.0212
        
        # Create the plot with a modern gray background
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [2, 1]}, dpi=100)
        fig.patch.set_facecolor('#2B2D31')  # Dark gray for outer background
        
        # Prepare data for the current page
        start_idx = page * servers_per_page
        end_idx = min(start_idx + servers_per_page, len(server_profits))
        current_page_servers = server_profits[start_idx:end_idx]
        
        # Prepare data for top 10 bar chart
        top_servers = server_profits[:10]  # Get top 10 servers
        server_names = [s.get("server_name", f"Server {s.get('server_id')}")[:15] for s in top_servers]
        profits = [s.get("profit", 0) for s in top_servers]
        
        # Create bar chart for top 10 servers
        ax1.set_facecolor('#36393F')  # Slightly lighter gray for plot area
        bars = ax1.bar(server_names, profits, color='#00FFAE', alpha=0.8)
        
        # Add profit values on top of bars
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 5,
                    f'{height:,.0f}',
                    ha='center', va='bottom', color='white', fontsize=9)
        
        # Format the axes
        ax1.set_xlabel("Server", color='white', fontsize=12)
        ax1.set_ylabel("Profit (Tokens)", color='white', fontsize=12)
        ax1.set_title(f"Top 10 Server Profits - {date}", color='white', fontsize=16, pad=20)
        
        # Rotate x-axis labels for better readability
        plt.setp(ax1.get_xticklabels(), rotation=45, ha='right', fontsize=9)
        
        # Style the axes and ticks
        ax1.tick_params(colors='white', which='both')
        for spine in ax1.spines.values():
            spine.set_edgecolor('#555555')
        
        # Add grid lines for readability
        ax1.grid(True, linestyle='--', alpha=0.3, zorder=0)
        
        # Create pie chart showing proportion of total profit
        if len(top_servers) > 0:
            # Get data for pie chart (top 5 servers plus "Others")
            top_5_servers = server_profits[:5]
            top_5_profits = [s.get("profit", 0) for s in top_5_servers]
            top_5_names = [s.get("server_name", f"Server {s.get('server_id')}")[:15] for s in top_5_servers]
            
            other_profit = total_profit - sum(top_5_profits)
            
            if other_profit > 0:
                pie_data = top_5_profits + [other_profit]
                pie_labels = top_5_names + ["Others"]
            else:
                pie_data = top_5_profits
                pie_labels = top_5_names
            
            # Create custom colormap
            colors = ['#00FFAE', '#00D6A4', '#00AE9E', '#00867A', '#005E55', '#3A3A3A']
            
            # Create pie chart - convert pie_data to integers to avoid 'wedge sizes x must be an integer value' error
            ax2.set_facecolor('#36393F')
            # Round float values to integers for pie chart
            integer_pie_data = [int(value) for value in pie_data]
            
            # Initialize wedges as empty list
            wedges = []
            
            # Only create pie chart if there are non-zero values
            if sum(integer_pie_data) > 0:
                pie_results = ax2.pie(
                    integer_pie_data, 
                    labels=None, 
                    autopct='%1.1f%%',
                    startangle=90, 
                    colors=colors,
                    wedgeprops={'width': 0.5, 'edgecolor': '#2B2D31', 'linewidth': 1}
                )
                
                # Unpack pie chart results
                wedges, texts, autotexts = pie_results
                
                # Style the pie chart text - only when autotexts is defined
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontsize(9)
            else:
                # If no data, just show empty plot
                ax2.text(0.5, 0.5, "No profit data", ha='center', va='center', color='white', fontsize=14)
            
            # Add legend with percentage and absolute values, only if there are wedges
            if wedges:
                legend_labels = [f"{label} ({pie_data[i]/total_profit*100:.1f}%)" for i, label in enumerate(pie_labels)]
                ax2.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1, 0.5), frameon=False, labelcolor='white')
            
            ax2.set_title("Profit Distribution", color='white', fontsize=14, pad=20)
        
        # Add BetSync watermark
        plt.figtext(0.5, 0.01, "BetSync Casino", fontsize=10, color='white', alpha=0.4, ha='center')
        
        # Adjust layout for better padding
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor())
        buf.seek(0)
        
        # Close the figure to prevent memory leaks
        plt.close(fig)
        
        # Create Discord file
        file = discord.File(buf, filename="server_profit_graph.png")
        
        # Create embed with relevant information
        embed = discord.Embed(
            title=f"Server Profits - {date}",
            description=f"Showing data for {len(server_profits)} servers",
            color=0x2B2D31
        )
        
        # Add summary statistics
        embed.add_field(
            name="Total Profit",
            value=f"**{total_profit:,.2f}** tokens\n(${total_profit_usd:,.2f})",
            inline=True
        )
        
        embed.add_field(
            name="Average Per Server",
            value=f"**{avg_profit:,.2f}** tokens\n(${avg_profit_usd:,.2f})",
            inline=True
        )
        
        embed.add_field(
            name="Top Server",
            value=f"**{server_profits[0].get('server_name', 'Unknown')}**\n{server_profits[0].get('profit', 0):,.2f} tokens",
            inline=True
        )
        
        # Add server rankings for current page
        server_list = []
        for i, server in enumerate(current_page_servers, start=start_idx + 1):
            server_name = server.get("server_name", f"Server {server.get('server_id')}")
            profit = server.get("profit", 0)
            profit_usd = profit * 0.0212
            server_list.append(f"**{i}. {server_name}** - {profit:,.2f} tokens (${profit_usd:,.2f})")
        
        if server_list:
            embed.add_field(
                name=f"Server Rankings (Page {page + 1})",
                value="\n".join(server_list),
                inline=False
            )
        
        embed.set_image(url="attachment://server_profit_graph.png")
        embed.set_footer(text=f"Page {page + 1}/{(len(server_profits) + servers_per_page - 1) // servers_per_page}")
        
        return embed, file
    
    @commands.command(name="sp", aliases=["serverprofit"])
    async def server_profit(self, ctx, date=None):
        """Display server profit data with rankings and visualization
        
        Usage: !sp [YYYY-MM-DD]
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Use today's date if none provided
        if date is None:
            date = datetime.datetime.now().date().strftime("%Y-%m-%d")
        else:
            # Validate date format
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Date Format",
                    description="Please use the format YYYY-MM-DD (e.g., 2023-12-31)",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Generating Server Profit Data",
            description="Please wait while we generate the server profit report...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Generate the server profit data
            embed, file = await self.generate_server_profit_data(date)
            
            # Create the view with pagination buttons
            view = ServerProfitView(self, ctx.author.id, date=date)
            
            # Edit the loading message with the data
            await loading_message.edit(embed=embed, file=file, view=view)
            
        except ValueError as e:
            # Handle no data available
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | No Data Available",
                description=f"{str(e)}",
                color=0xFF0000
            )
            await loading_message.edit(embed=error_embed)
        except Exception as e:
            # Handle any other errors
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while generating the server profit data: ```{str(e)}```",
                color=0xFF0000
            )
            await loading_message.edit(embed=error_embed)
    
    @commands.command(name="tp")
    async def total_profit(self, ctx, view_type: str = "daily"):
        """Display total profit graph with daily/monthly/all-time views
        
        Usage: !tp
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Normalize view type
        view_type = view_type.lower()
        if view_type not in ["daily", "monthly", "all_time"]:
            view_type = "daily"
        
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Generating Profit Graph",
            description="Please wait while we generate the profit chart...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Generate the profit graph
            embed, file = await self.generate_profit_graph(view_type)
            
            # Create the view with buttons for different time frames
            view = TotalProfitView(self, ctx.author.id)
            
            # Edit the loading message with the graph
            await loading_message.edit(embed=embed, file=file, view=view)
            
        except Exception as e:
            # Handle any errors
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while generating the profit graph: ```{str(e)}```",
                color=0xFF0000
            )
            await loading_message.edit(embed=error_embed)
    
    @commands.command(name="game_np", aliases=["gnp"])
    async def game_np(self, ctx, game: str = None):
        """Check how much all games or a specific game is performing
        
        Usage: !game_np [game_name]
               Example games: limbo, blackjack, cases
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Get the database instance
        db = Servers()
        
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Retrieving Game Performance Data",
            description="Please wait while we fetch the statistics...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            if game:
                # Get stats for a specific game
                game = game.lower()  # Normalize game name
                game_data = db.get_np(game)
                
                if not game_data:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Game Not Found",
                        description=f"No data found for game '{game}'. Check the spelling or try without specifying a game.",
                        color=0xFF0000
                    )
                    return await loading_message.edit(embed=embed)
                
                # Create embed for single game
                money_emoji = emoji()["money"]
                embed = discord.Embed(
                    title=f"{money_emoji} | Game Performance: {game.capitalize()}",
                    description=f"Performance statistics for {game.capitalize()}",
                    color=0x00FFAE
                )
                
                # Add game stats
                profit = game_data.get("total_profit", 0)
                embed.add_field(
                    name="Total Profit",
                    value=f"**{profit:,.2f}** tokens",
                    inline=True
                )
                
                # Calculate rough USD equivalent (example rate from context)
                usd_equivalent = profit * 0.0212  # Based on the rate seen in server.py
                embed.add_field(
                    name="USD Equivalent (Est.)",
                    value=f"**${usd_equivalent:,.2f}**",
                    inline=True
                )
                
                # Add server share if applicable
                server_share = profit * (30/100)  # Based on the rate seen in server.py
                embed.add_field(
                    name="Server Share (30%)",
                    value=f"**{server_share:,.2f}** tokens",
                    inline=True
                )
                
            else:
                # Get stats for all games
                # Create the main embed
                money_emoji = emoji()["money"]
                embed = discord.Embed(
                    title=f"{money_emoji} | Game Performance Overview",
                    description="Performance statistics for all games",
                    color=0x00FFAE
                )
                
                # Get general stats first
                #overall_data = db.get_np()
                #if overall_data:
                    ##l = 0
                    #or i in overall_data:
                        #l += i.get("total_profit", 0)
                    #embed.add_field(
                        #name="Total Casino Profit",
                        #value=f"**{l:,.2f}** tokens",
                        #nline=False
                    #)
                
                # Get individual game stats
                game_list = ["limbo", "blackjack", "cases", "tower", "progressivecf", "hilo", "plinko", "keno", "crash", "crosstheroad", "dice", "poker", "coinflip", "mines", "hilo", "penalty", "pump", "race", "wheel", "baccarat"]
                game_stats = []
                
                for game_name in game_list:
                    game_data = db.get_np(game_name)
                    if game_data:
                        profit = game_data.get("total_profit", 0)
                        game_stats.append((game_name, profit))
                
                # Sort games by profit (highest to lowest)
                game_stats.sort(key=lambda x: x[1], reverse=True)
                
                # Add top performing games field
                if game_stats:
                    performance_text = ""
                    for i, (game_name, profit) in enumerate(game_stats):
                        performance_text += f"**{i+1}.** {game_name.capitalize()}: **{profit:,.2f}** tokens\n"
                    
                    embed.add_field(
                        name="Game Performance (Ranked)",
                        value=performance_text,
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Game Performance",
                        value="No game performance data available.",
                        inline=False
                    )
            
            # Add help text
            embed.set_footer(text="Use !game_np [game_name] to view stats for a specific game", icon_url=ctx.bot.user.avatar.url)
            
            # Edit loading message with the stats
            await loading_message.edit(embed=embed)
            
        except Exception as e:
            # Handle any errors
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while retrieving game statistics: ```{str(e)}```",
                color=0xFF0000
            )
            await loading_message.edit(embed=error_embed)

class TimeFrameButton(discord.ui.Button):
    def __init__(self, view_type, label, style, custom_id):
        super().__init__(style=style, label=label, custom_id=custom_id)
        self.view_type = view_type
    
    async def callback(self, interaction: discord.Interaction):
        # Only allow the original command author to use buttons
        if interaction.user.id != self.view.author_id:
            return await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
        
        # Update the view with the selected time frame
        await self.view.update_graph(interaction, self.view_type)

class TotalProfitView(discord.ui.View):
    def __init__(self, cog, author_id):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id
        
        # Add buttons for different time periods
        self.add_item(TimeFrameButton("daily", "Daily", discord.ButtonStyle.primary, "daily"))
        self.add_item(TimeFrameButton("monthly", "Monthly", discord.ButtonStyle.secondary, "monthly"))
        self.add_item(TimeFrameButton("all_time", "All Time", discord.ButtonStyle.success, "all_time"))
    
    async def update_graph(self, interaction, view_type):
        """Update the graph based on the selected time frame"""
        try:
            # Generate the appropriate graph
            embed, file = await self.cog.generate_profit_graph(view_type)
            
            # Update the message with the new graph
            await interaction.response.edit_message(embed=embed, file=file, view=self)
        except Exception as e:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while generating the graph: `{str(e)}`",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class ServerProfitView(discord.ui.View):
    def __init__(self, cog, author_id, page=0, date=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id
        self.page = page
        self.servers_per_page = 20
        self.date = date if date else datetime.datetime.now().date().strftime("%Y-%m-%d")
        
        # Add pagination buttons
        self.add_item(discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="prev", disabled=page == 0))
        self.add_item(discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next"))
    
    async def interaction_check(self, interaction):
        """Check if the person clicking is the same as the command author"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use these controls.", ephemeral=True)
            return False
            
        # Handle the button click
        await self.button_callback(interaction)
        return False  # Return False to prevent the default handling
    
    async def button_callback(self, interaction):
        """Handle button interactions"""
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "prev" and self.page > 0:
            self.page -= 1
        elif custom_id == "next":
            self.page += 1
            
        # Update buttons
        for child in self.children:
            if child.custom_id == "prev":
                child.disabled = self.page == 0
        
        # Generate new embed and file
        embed, file = await self.cog.generate_server_profit_data(self.date, self.page, self.servers_per_page)
        
        # Update the message
        await interaction.response.edit_message(embed=embed, file=file, view=self)


def setup(bot):
    bot.add_cog(AdminCommands(bot))
