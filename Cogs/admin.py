
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
        
        # Add command check for blacklisted users
        self.bot.add_check(self.check_blacklist)

    async def check_blacklist(self, ctx):
        """Check if user is blacklisted before command execution"""
        if ctx.author.id in self.blacklisted_ids:
            # Don't send embed if the command is blacklist/unblacklist
            if ctx.command.name not in ['blacklist', 'unblacklist']:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Blacklisted",
                    description="You have been blacklisted from using this bot.",
                    color=0xFF0000
                )
                await ctx.reply(embed=embed)
            return False
        return True
    
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
    async def addcash(self, ctx, user: discord.Member, amount: float):
        """Add or remove points from a user (Admin only)
        
        Usage: 
        - To add: !addcash @user 100
        - To remove: !addcash @user -100
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Get the user's current balance
        db = Users()
        user_data = db.fetch_user(user.id)
        
        # If user doesn't exist, register them
        if not user_data:
            dump = {"discord_id": user.id, "points": 0, "history": [], 
                   "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                   "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost': 0,
                   "primary_coin": "BTC", "wallet": {"BTC": 0, "SOL": 0, "ETH": 0, "LTC": 0, "USDT": 0}}
            db.register_new_user(dump)
            user_data = db.fetch_user(user.id)
        
        # Get current balance and primary coin
        current_points = user_data.get("points", 0)
        primary_coin = user_data.get("primary_coin", "BTC")
        
        # Update user balance (add or subtract based on amount sign)
        new_balance = current_points + amount
        
        # Prevent negative balance
        if new_balance < 0:
            new_balance = 0
            
        # Update points balance
        db.update_balance(user.id, new_balance, "points", "$set")
        
        # Also update the wallet for the primary coin
        crypto_values = {
            "BTC": 0.00000024,   # 1 point = 0.00000024 btc
            "LTC": 0.00023,      # 1 point = 0.00023 ltc
            "ETH": 0.000010,     # 1 point = 0.000010 eth
            "USDT": 0.0212,      # 1 point = 0.0212 usdt
            "SOL": 0.0001442     # 1 point = 0.0001442 sol
        }
        
        # Calculate crypto amount for wallet update
        crypto_amount = new_balance * crypto_values[primary_coin]
        
        # Update wallet
        db.collection.update_one(
            {"discord_id": user.id},
            {"$set": {f"wallet.{primary_coin}": crypto_amount}}
        )
        
        # Create response embed
        action = "added to" if amount > 0 else "removed from"
        embed = discord.Embed(
            title=f"💰 Cash {action.split()[0].title()}!",
            description=f"{abs(amount):.2f} points have been {action} {user.mention}'s balance.\nNew balance: {new_balance:.2f} points",
            color=0x00FF00 if amount > 0 else 0xFF9900
        )
        await ctx.reply(embed=embed)
        
        # Add to history
        history_entry = {
            "type": "admin_add",
            "amount": amount,
            "currency": "points",
            "timestamp": int(discord.utils.utcnow().timestamp()),
            "admin_id": ctx.author.id
        }
        
        db.collection.update_one(
            {"discord_id": user.id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}  # Keep last 100 entries
        )
        
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
                    #print(f"[DEBUG] Trying to fetch user with ID: {user_id}")
                    user = self.bot.get_user(user_id)
                    #print(f"[DEBUG] Result from get_user: {user}")
                    if user is None:
                        # Try to fetch user if not in cache
                        try:
                            #print(f"[DEBUG] Attempting fetch_user for {user_id}")
                            user = await self.bot.fetch_user(user_id)
                            #print(f"[DEBUG] Result from fetch_user: {user}")
                        except discord.NotFound:
                            print(f"[DEBUG] User with ID {user_id} not found in Discord")
                        except Exception as e:
                            print(f"[DEBUG] Error fetching user: {str(e)}")
                except ValueError:
                    #print(f"[DEBUG] Input '{user_input}' is not a valid ID")
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Input",
                        description="Please provide a valid user mention or ID.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
            
            # Get user data from database
            #print(f"[DEBUG] Fetching user data from database for ID: {user_id}")
            db = Users()
            user_data = db.fetch_user(user_id)
            #print(f"[DEBUG] Database result: {user_data is not None}")
            
            if not user_data:
                #print(f"[DEBUG] User {user_id} not found in database")
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
                title=f":mag: User Information",
                description=f"Basic information for {user_mention}",
                color=0x00FFAE
            )
            
            # User Account Info - Minimalistic
            basic_info = f"**ID:** `{user_id}`"
            
            # Only add these fields if we have a user object
            if user:
                basic_info += f"\n**Created:** <t:{int(user.created_at.timestamp())}:R>"
                
                # Check if user is in guild and has joined_at attribute
                member = ctx.guild.get_member(user_id)
                if member and member.joined_at:
                    basic_info += f"\n**Joined:** <t:{int(member.joined_at.timestamp())}:R>"
            
            embed.add_field(
                name=f"Account Details",
                value=basic_info,
                inline=False
            )
            
            # Points and Primary Currency - Minimalistic
            points = user_data.get('points', 0)
            primary_coin = user_data.get('primary_coin', 'BTC')
            
            embed.add_field(
                name="Balance",
                value=f"**Points:** {points:,.2f}\n**Currency:** {primary_coin}",
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
            
            
            
            # Win Rate Calculation
            # Set user avatar as thumbnail if available
            if user and hasattr(user, 'avatar') and user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            
            embed.set_footer(text=f"Admin lookup by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
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
    
    @commands.command(name="leave")
    async def leave_server(self, ctx, server_id: int = None):
        """Make the bot leave a specified server and delete its data (Admin only)
        
        Usage: !leave server_id
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Check if server ID is provided
        if server_id is None:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Missing Server ID",
                description="Please provide a server ID to leave.",
                color=0xFF0000
            )
            embed.add_field(
                name="Usage",
                value="`!leave server_id`",
                inline=False
            )
            return await ctx.reply(embed=embed)
            
        # Get the server
        server = self.bot.get_guild(server_id)
        
        # Check if server exists in the database
        db = Servers()
        server_data = db.fetch_server(server_id)
        
        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description=f"Server with ID `{server_id}` is not in the database.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Confirm before leaving
        confirm_embed = discord.Embed(
            title="⚠️ | Confirm Server Leave",
            description=f"Are you sure you want to leave the server:\n\n**{server_data.get('server_name', f'Unknown Server ({server_id})')}** (`{server_id}`)?",
            color=0xFFA500
        )
        confirm_embed.add_field(
            name="Warning",
            value="This will delete all server data from the database!",
            inline=False
        )
        confirm_embed.set_footer(text="Reply with 'yes' within 30 seconds to confirm.")
        
        confirm_message = await ctx.reply(embed=confirm_embed)
        
        # Wait for confirmation
        try:
            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() == 'yes'
                
            await self.bot.wait_for('message', check=check, timeout=30.0)
            
            # Leave the server and delete data
            success = db.collection.delete_one({"server_id": server_id})
            
            # Create final embed
            if success.deleted_count > 0:
                # Leave the server if it's accessible
                server_name = server_data.get('server_name', f"Unknown Server ({server_id})")
                leave_successful = False
                
                if server:
                    try:
                        await server.leave()
                        leave_successful = True
                    except Exception as e:
                        print(f"Error leaving server: {e}")
                
                embed = discord.Embed(
                    title="<:checkmark:1344252974188335206> | Server Left",
                    description=f"Successfully removed **{server_name}** (`{server_id}`) from the database.",
                    color=0x00FFAE
                )
                
                if leave_successful:
                    embed.add_field(
                        name="Server Status",
                        value="Successfully left the server.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Server Status",
                        value="Could not leave the server. The bot may not be in this server anymore or lacks permissions.",
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Error",
                    description=f"Failed to remove server from database. Please try again.",
                    color=0xFF0000
                )
                
            await ctx.reply(embed=embed)
            
        except asyncio.TimeoutError:
            # User didn't confirm in time
            timeout_embed = discord.Embed(
                title="❌ | Operation Cancelled",
                description="Server leave operation cancelled due to timeout.",
                color=0xFF0000
            )
            await confirm_message.edit(embed=timeout_embed)
    
    @commands.command(name="uptime")
    async def uptime(self, ctx):
        """Show bot uptime and system information (Admin only)
        
        Usage: !uptime
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        try:
            import psutil
            import platform
            from datetime import datetime

            # Get bot uptime
            current_time = datetime.utcnow()
            delta_uptime = current_time - datetime.fromtimestamp(psutil.boot_time())
            hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)

            # Get CPU info
            cpu_info = platform.processor() or "N/A"
            cpu_cores = psutil.cpu_count(logical=False)
            cpu_threads = psutil.cpu_count()
            cpu_usage = psutil.cpu_percent(interval=1)

            # Get RAM info
            ram = psutil.virtual_memory()
            ram_total = ram.total / (1024**3)  # Convert to GB
            ram_used = ram.used / (1024**3)
            ram_percent = ram.percent

            # Get disk info
            disk = psutil.disk_usage('/')
            disk_total = disk.total / (1024**3)  # Convert to GB
            disk_used = disk.used / (1024**3)
            disk_percent = disk.percent

            # Create embed
            embed = discord.Embed(
                title="🖥️ System Information",
                description="Current system status and specifications",
                color=0x00FFAE,
                timestamp=current_time
            )

            # Uptime field
            uptime_str = f"```{days}d {hours}h {minutes}m {seconds}s```"
            embed.add_field(
                name="⏰ Bot Uptime",
                value=uptime_str,
                inline=False
            )

            # System info field
            sys_info = f"```\nOS: {platform.system()} {platform.release()}\n"
            sys_info += f"Machine: {platform.machine()}\n"
            sys_info += f"Hostname: {platform.node()}```"
            embed.add_field(
                name="🔧 System",
                value=sys_info,
                inline=False
            )

            # CPU info field
            cpu_info = f"```\nProcessor: {cpu_info}\n"
            cpu_info += f"Cores: {cpu_cores} (Physical) / {cpu_threads} (Logical)\n"
            cpu_info += f"Usage: {cpu_usage}%```"
            embed.add_field(
                name="⚡ CPU",
                value=cpu_info,
                inline=False
            )

            # Memory info field
            ram_info = f"```\nTotal: {ram_total:.2f} GB\n"
            ram_info += f"Used: {ram_used:.2f} GB\n"
            ram_info += f"Usage: {ram_percent}%```"
            embed.add_field(
                name="📝 Memory",
                value=ram_info,
                inline=False
            )

            # Disk info field
            disk_info = f"```\nTotal: {disk_total:.2f} GB\n"
            disk_info += f"Used: {disk_used:.2f} GB\n"
            disk_info += f"Usage: {disk_percent}%```"
            embed.add_field(
                name="💾 Disk",
                value=disk_info,
                inline=False
            )

            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.reply(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while fetching system information: ```{str(e)}```",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)
            
    @commands.command(name="adminpanel", aliases=["ap"])
    async def adminpanel(self, ctx, page: int = 1):
        """Display all available admin commands with pagination (Admin only)
        
        Usage: !adminpanel [page]
        """
        try:
            # Check if command user is an admin
            if not self.is_admin(ctx.author.id):
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Access Denied",
                    description="This command is restricted to administrators only.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
                
            # Commands per page
            commands_per_page = 7
                
            # Add admin commands from AdminCommands cog
            admin_commands = [
                ("addcash", "Add tokens or credits to a user's balance", "!addcash @user 100 tokens"),
                ("addadmin", "Add a user as a server admin", "!addadmin @user"),
                ("viewadmins", "View server admins across all servers", "!viewadmins server_id"),
                ("removeadmin", "Remove a user as a server admin", "!removeadmin @user"),
                ("listadmins", "List all server admins for current server", "!listadmins"),
                ("fetch", "Fetch detailed information about a user", "!fetch @user"),
                ("blacklist", "Blacklist a user from using the bot", "!blacklist @user"),
                ("unblacklist", "Remove a user from the blacklist", "!unblacklist @user"),
                ("viewblacklist", "View all blacklisted users", "!viewblacklist"),
                ("lose", "Curse a player to lose their next few games", "!lose @user 5"),
                ("removecurse", "Remove loss curse from a player", "!removecurse @user"),
                ("viewcurses", "View all cursed players", "!viewcurses"),
                ("manageinvites", "Manage user invite counts", "!manageinvites add @user 5"),
                ("leave", "Make the bot leave a server and delete its data", "!leave server_id"),
                ("uptime", "Show bot uptime and system information", "!uptime"),
                ("sp", "Display server profit data with rankings", "!sp [YYYY-MM-DD]"),
                ("tp", "Display total profit graph", "!tp [daily/monthly/all_time]"),
                ("game_np", "Check game performance statistics", "!game_np [game_name]"),
                ("cleardb", "Clear database collections selectively", "!cleardb [all]"),
                ("adminpanel", "Show this admin panel", "!adminpanel [page]")
            ]
            
            # Add server admin commands from ServersCog
            server_admin_commands = [
                ("serverstats", "View server statistics", "!serverstats"),
                ("airdrop", "Create a token/credit airdrop for users", "!airdrop amount [t/c] [duration]")
            ]
            
            # Calculate total pages required
            total_admin_pages = (len(admin_commands) + commands_per_page - 1) // commands_per_page
            total_pages = total_admin_pages + ((len(server_admin_commands) + commands_per_page - 1) // commands_per_page)
            
            # Validate page number
            if page < 1:
                page = 1
            if page > total_pages:
                page = total_pages
                
            # Create embed
            embed = discord.Embed(
                title="👑 Admin Panel - Available Commands",
                description=f"List of all available administrator commands (Page {page}/{total_pages})",
                color=0x00FFAE
            )
            
            # Determine which commands to show based on page
            if page <= total_admin_pages:
                # Show admin commands
                start_idx = (page - 1) * commands_per_page
                end_idx = min(start_idx + commands_per_page, len(admin_commands))
                
                admin_commands_text = ""
                for i in range(start_idx, end_idx):
                    cmd, desc, usage = admin_commands[i]
                    admin_commands_text += f"**!{cmd}** - {desc}\n`{usage}`\n\n"
                
                embed.add_field(
                    name="Admin Commands",
                    value=admin_commands_text,
                    inline=False
                )
                
                # Add navigation instructions
                embed.add_field(
                    name="Navigation",
                    value=f"Use `!adminpanel [page]` to navigate between pages.",
                    inline=False
                )
            else:
                # Show server admin commands
                server_page = page - total_admin_pages
                start_idx = (server_page - 1) * commands_per_page
                end_idx = min(start_idx + commands_per_page, len(server_admin_commands))
                
                server_commands_text = ""
                for i in range(start_idx, end_idx):
                    cmd, desc, usage = server_admin_commands[i]
                    server_commands_text += f"**!{cmd}** - {desc}\n`{usage}`\n\n"
                
                embed.add_field(
                    name="Server Admin Commands",
                    value=server_commands_text,
                    inline=False
                )
                
                # Add navigation instructions
                embed.add_field(
                    name="Navigation",
                    value=f"Use `!adminpanel [page]` to navigate between pages.",
                    inline=False
                )
            
            embed.set_footer(text=f"Page {page}/{total_pages} • Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            # Create view with navigation buttons
            view = AdminPanelPaginator(self, ctx.author.id, page, total_pages, commands_per_page)
            
            # Send the embed with buttons
            response = await ctx.reply(embed=embed, view=view)
            view.message = response
            
        except Exception as e:
            # Log the error and send a fallback message if the embed fails
            print(f"Error in adminpanel command: {str(e)}")
            await ctx.reply(f"⚠️ Error displaying admin panel: {str(e)}\nPlease contact the developer.")

    async def generate_server_profit_data(self, date=None, page=0, servers_per_page=20):
        """Generate server profit data for the specified date"""
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
        
        # Calculate USD equivalents (based on the rate: 1 token = 0.0212 USD)
        total_profit_usd = total_profit * 0.0212
        avg_profit_usd = avg_profit * 0.0212
        
        # Prepare data for the current page
        start_idx = page * servers_per_page
        end_idx = min(start_idx + servers_per_page, len(server_profits))
        current_page_servers = server_profits[start_idx:end_idx]
        
        # Count positive and negative servers
        positive_servers = len([s for s in server_profits if s.get("profit", 0) > 0])
        negative_servers = len([s for s in server_profits if s.get("profit", 0) < 0])
        zero_servers = len([s for s in server_profits if s.get("profit", 0) == 0])
        
        # Calculate the total positive profit (for profit distribution)
        total_positive_profit = sum(max(0, s.get("profit", 0)) for s in server_profits)
        
        # Create a clean, concise embed
        embed = discord.Embed(
            title=f"Server Profits | {date}",
            description=f"Performance data across {len(server_profits):,} servers",
            color=0x00FFAE
        )
        
        # Consolidate all stats into a single field with backticks for values
        stats_text = (
            f"**Total Profit:** `{total_profit:,.2f}` tokens (`${total_profit_usd:,.2f}`)\n"
            f"**Average Per Server:** `{avg_profit:,.2f}` tokens (`${avg_profit_usd:,.2f}`)\n"
            f"**Server Distribution:**\n"
            f"Profitable: `{positive_servers}` servers\n"
            f"Unprofitable: `{negative_servers}` servers\n"
            f"Neutral: `{zero_servers}` servers\n\n"
        )
        
        # Add profit distribution info if available
        if total_positive_profit > 0:
            # Calculate top 5 servers contribution
            top5_servers = server_profits[:5]
            top5_sum = sum(max(0, s.get("profit", 0)) for s in top5_servers)
            top5_percent = (top5_sum / total_positive_profit) * 100 if total_positive_profit > 0 else 0
            others_percent = 100 - top5_percent
            
            stats_text += (
                f"**Profit Distribution:**\n"
                f"Top 5 Servers: `{top5_percent:.1f}%` (`{top5_sum:,.2f}` tokens)\n"
                f"Other Servers: `{others_percent:.1f}%` (`{total_positive_profit - top5_sum:,.2f}` tokens)\n"
            )
        
        # Add the consolidated stats field
        embed.add_field(
            name="Server Statistics",
            value=stats_text,
            inline=False
        )
        
        # Add server rankings in a single field with cleaner formatting
        if current_page_servers:
            rankings_text = ""
            for i, server in enumerate(current_page_servers, start=start_idx + 1):
                server_name = server.get("server_name", f"Server {server.get('server_id')}")
                profit = server.get("profit", 0)
                profit_usd = profit * 0.0212
                
                # Simplified ranking format
                rankings_text += f"`#{i}` **{server_name}** — `{profit:,.2f}` tokens"
                if abs(profit) >= 1000:
                    rankings_text += f" (`${profit_usd:,.2f}`)"
                rankings_text += "\n"
            
            embed.add_field(
                name=f"Server Rankings (Page {page + 1})",
                value=rankings_text,
                inline=False
            )
        
        # Add custom footer with pagination info
        total_pages = (len(server_profits) + servers_per_page - 1) // servers_per_page
        embed.set_footer(
            text=f"BetSync Casino | Page {page + 1}/{total_pages} | Data for {date}"
        )
        
        return embed, None  # Return None for file since we're not using images anymore
    
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
            embed, _ = await self.generate_server_profit_data(date)
            
            # Create the view with pagination buttons
            view = ServerProfitView(self, ctx.author.id, date=date)
            
            # Edit the loading message with the data
            await loading_message.edit(embed=embed, view=view)
            
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
    
    @commands.command(name="cleardb")
    async def cleardb(self, ctx, target: str = None):
        """Clear database collections (Bot Admin only)
        
        Usage: !cleardb - Shows dropdown menu to select what to clear
               !cleardb all - Clears everything immediately
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # If 'all' is specified, clear everything immediately
        if target and target.lower() == "all":
            # Create confirmation embed
            confirm_embed = discord.Embed(
                title="⚠️ | FINAL WARNING - CLEAR ALL DATA",
                description="**YOU ARE ABOUT TO DELETE ALL DATABASE DATA**\n\nThis action will permanently remove:\n• All user accounts and balances\n• All server configurations\n• All profit tracking data\n• All game statistics\n• Everything in the database\n\n**THIS CANNOT BE UNDONE!**",
                color=0xFF0000
            )
            confirm_embed.add_field(
                name="🔒 Confirmation Required",
                value="Type `CONFIRM DELETE ALL` within 30 seconds to proceed.\nType anything else to cancel.",
                inline=False
            )
            
            await ctx.reply(embed=confirm_embed)
            
            # Wait for confirmation
            try:
                def check(message):
                    return message.author == ctx.author and message.channel == ctx.channel
                    
                response = await self.bot.wait_for('message', check=check, timeout=30.0)
                
                if response.content.strip() == "CONFIRM DELETE ALL":
                    await self.execute_cleardb_all(ctx)
                else:
                    cancel_embed = discord.Embed(
                        title="❌ | Operation Cancelled",
                        description="Database clear operation was cancelled.",
                        color=0x00FFAE
                    )
                    await ctx.reply(embed=cancel_embed)
                    
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ | Operation Timed Out",
                    description="Database clear operation was cancelled due to timeout.",
                    color=0xFF0000
                )
                await ctx.reply(embed=timeout_embed)
        
        else:
            # Show dropdown menu for selective clearing
            embed = discord.Embed(
                title="🗂️ | Database Clear Options",
                description="Select what data you want to clear from the database.\n\n**⚠️ Warning: These operations are irreversible!**",
                color=0xFFA500
            )
            embed.add_field(
                name="Available Options",
                value="• **Users Data** - All user accounts and balances\n• **Servers Data** - All server configurations\n• **Profit Data** - Daily profit tracking\n• **Server Profit** - Server-specific profits\n• **Net Profit** - Game statistics\n• **Everything** - Complete database wipe",
                inline=False
            )
            embed.set_footer(text="Use the dropdown below to select what to clear")
            
            # Create view with dropdown
            view = ClearDBView(self, ctx.author.id)
            message = await ctx.reply(embed=embed, view=view)
            view.message = message
    
    async def execute_cleardb(self, interaction, target):
        """Execute the database clearing operation"""
        from pymongo import MongoClient
        import os
        
        # Connect to MongoDB
        mongodb = MongoClient(os.environ["MONGO"])
        db = mongodb["BetSync"]
        
        try:
            if target == "users":
                result = db["users"].delete_many({})
                embed = discord.Embed(
                    title="✅ | Users Data Cleared",
                    description=f"Successfully deleted {result.deleted_count} user records.",
                    color=0x00FFAE
                )
                
            elif target == "servers":
                result = db["servers"].delete_many({})
                embed = discord.Embed(
                    title="✅ | Servers Data Cleared",
                    description=f"Successfully deleted {result.deleted_count} server records.",
                    color=0x00FFAE
                )
                
            elif target == "profit_data":
                result = db["profit_data"].delete_many({})
                embed = discord.Embed(
                    title="✅ | Profit Data Cleared",
                    description=f"Successfully deleted {result.deleted_count} profit records.",
                    color=0x00FFAE
                )
                
            elif target == "server_profit":
                result = db["server_profit"].delete_many({})
                embed = discord.Embed(
                    title="✅ | Server Profit Data Cleared",
                    description=f"Successfully deleted {result.deleted_count} server profit records.",
                    color=0x00FFAE
                )
                
            elif target == "net_profit":
                result = db["net_profit"].delete_many({})
                embed = discord.Embed(
                    title="✅ | Net Profit Data Cleared",
                    description=f"Successfully deleted {result.deleted_count} net profit records.",
                    color=0x00FFAE
                )
                
            elif target == "referrals":
                referral_result = db["referrals"].delete_many({})
                invite_cache_result = db["invite_cache"].delete_many({})
                total_deleted = referral_result.deleted_count + invite_cache_result.deleted_count
                embed = discord.Embed(
                    title="✅ | Referral Data Cleared",
                    description=f"Successfully deleted {total_deleted} referral records ({referral_result.deleted_count} referrals + {invite_cache_result.deleted_count} invite cache).",
                    color=0x00FFAE
                )
                
            elif target == "everything":
                # Create final confirmation for everything
                confirm_embed = discord.Embed(
                    title="⚠️ | FINAL CONFIRMATION - DELETE ALL",
                    description="**YOU ARE ABOUT TO DELETE EVERYTHING IN THE DATABASE**\n\nThis will permanently remove ALL data across ALL collections.\n\n**THIS CANNOT BE UNDONE!**",
                    color=0xFF0000
                )
                confirm_embed.add_field(
                    name="🔒 Final Confirmation",
                    value="Click the 'CONFIRM DELETE ALL' button below to proceed.\nThis interaction will expire in 30 seconds.",
                    inline=False
                )
                
                # Create confirmation button
                view = FinalConfirmationView(self, interaction.user.id)
                await interaction.response.edit_message(embed=confirm_embed, view=view)
                return
                
            embed.set_footer(text=f"Operation performed by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Database Error",
                description=f"An error occurred while clearing the database:\n```{str(e)}```",
                color=0xFF0000
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
    
    async def execute_cleardb_all(self, ctx):
        """Execute complete database wipe"""
        from pymongo import MongoClient
        import os
        
        # Connect to MongoDB
        mongodb = MongoClient(os.environ["MONGO"])
        db = mongodb["BetSync"]
        
        try:
            # Get all collections
            collections = db.list_collection_names()
            total_deleted = 0
            
            # Delete from each collection
            for collection_name in collections:
                result = db[collection_name].delete_many({})
                total_deleted += result.deleted_count
            
            embed = discord.Embed(
                title="💥 | DATABASE COMPLETELY WIPED",
                description=f"**All data has been permanently deleted**\n\nCollections cleared: {len(collections)}\nTotal records deleted: {total_deleted}",
                color=0xFF0000
            )
            embed.add_field(
                name="Collections Cleared",
                value=", ".join(collections) if collections else "None",
                inline=False
            )
            embed.set_footer(text=f"Operation performed by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Database Error",
                description=f"An error occurred while wiping the database:\n```{str(e)}```",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)

class FinalConfirmationView(discord.ui.View):
    def __init__(self, cog, author_id):
        super().__init__(timeout=30)
        self.cog = cog
        self.author_id = author_id
        
    @discord.ui.button(label="CONFIRM DELETE ALL", style=discord.ButtonStyle.danger, emoji="💥")
    async def confirm_delete_all(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this button.", ephemeral=True)
            return
        
        # Execute complete database wipe
        from pymongo import MongoClient
        import os
        
        # Connect to MongoDB
        mongodb = MongoClient(os.environ["MONGO"])
        db = mongodb["BetSync"]
        
        try:
            # Get all collections
            collections = db.list_collection_names()
            total_deleted = 0
            
            # Delete from each collection
            for collection_name in collections:
                result = db[collection_name].delete_many({})
                total_deleted += result.deleted_count
            
            embed = discord.Embed(
                title="💥 | DATABASE COMPLETELY WIPED",
                description=f"**All data has been permanently deleted**\n\nCollections cleared: {len(collections)}\nTotal records deleted: {total_deleted}",
                color=0xFF0000
            )
            embed.add_field(
                name="Collections Cleared",
                value=", ".join(collections) if collections else "None",
                inline=False
            )
            embed.set_footer(text=f"Operation performed by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Database Error",
                description=f"An error occurred while wiping the database:\n```{str(e)}```",
                color=0xFF0000
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_operation(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this button.", ephemeral=True)
            return
        
        cancel_embed = discord.Embed(
            title="❌ | Operation Cancelled",
            description="Database clear operation was cancelled.",
            color=0x00FFAE
        )
        await interaction.response.edit_message(embed=cancel_embed, view=None)

    

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
                game_list = ["limbo", "blackjack", "cases", "tower", "progressivecf", "plinko", "keno", "crash", "crosstheroad", "dice", "poker", "coinflip", "mines", "hilo", "penalty", "pump", "race", "wheel", "baccarat"]
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

class ClearDBDropdown(discord.ui.Select):
    def __init__(self, cog, author_id):
        self.cog = cog
        self.author_id = author_id
        
        options = [
            discord.SelectOption(
                label="Clear All Users Data",
                description="Remove all user accounts and their data",
                value="users",
                emoji="👥"
            ),
            discord.SelectOption(
                label="Clear All Servers Data", 
                description="Remove all server configurations and data",
                value="servers",
                emoji="🏢"
            ),
            discord.SelectOption(
                label="Clear Profit Data",
                description="Remove all profit tracking data",
                value="profit_data",
                emoji="💰"
            ),
            discord.SelectOption(
                label="Clear Server Profit Data",
                description="Remove server-specific profit records",
                value="server_profit",
                emoji="📊"
            ),
            discord.SelectOption(
                label="Clear Net Profit Data",
                description="Remove game net profit statistics",
                value="net_profit",
                emoji="🎮"
            ),
            discord.SelectOption(
                label="Clear Referral Data",
                description="Remove all referral tracking data",
                value="referrals",
                emoji="🎯"
            ),
            discord.SelectOption(
                label="⚠️ CLEAR EVERYTHING ⚠️",
                description="DELETE ALL DATABASE COLLECTIONS - IRREVERSIBLE",
                value="everything",
                emoji="💥"
            )
        ]
        
        super().__init__(
            placeholder="Select what data to clear...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this dropdown.", ephemeral=True)
            return
        
        await self.cog.execute_cleardb(interaction, self.values[0])

class ClearDBView(discord.ui.View):
    def __init__(self, cog, author_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.author_id = author_id
        self.add_item(ClearDBDropdown(cog, author_id))
    
    async def on_timeout(self):
        # Disable all items when timeout occurs
        for item in self.children:
            item.disabled = True
        
        # Try to edit the message to show it's expired
        try:
            embed = discord.Embed(
                title="⏰ | Command Expired",
                description="The cleardb command has expired. Please run the command again if needed.",
                color=0xFF0000
            )
            await self.message.edit(embed=embed, view=self)
        except:
            pass

class AdminPanelPaginator(discord.ui.View):
    def __init__(self, cog, author_id, current_page, total_pages, commands_per_page):
        super().__init__(timeout=60)
        self.cog = cog
        self.author_id = author_id
        self.current_page = current_page
        self.total_pages = total_pages
        self.commands_per_page = commands_per_page
        self.message = None
        
        # Add pagination buttons
        self.add_item(discord.ui.Button(label="First", style=discord.ButtonStyle.secondary, custom_id="first", disabled=current_page==1))
        self.add_item(discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev", disabled=current_page==1))
        self.add_item(discord.ui.Button(label=f"{current_page}/{total_pages}", style=discord.ButtonStyle.gray, custom_id="page", disabled=True))
        self.add_item(discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, custom_id="next", disabled=current_page==total_pages))
        self.add_item(discord.ui.Button(label="Last", style=discord.ButtonStyle.secondary, custom_id="last", disabled=current_page==total_pages))
    
    async def interaction_check(self, interaction):
        """Verify the user interacting is the command author"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this admin panel navigation.", ephemeral=True)
            return False
            
        # Handle the button click
        await self.handle_pagination(interaction)
        return False  # Return False to prevent the default handling
    
    async def handle_pagination(self, interaction):
        """Handle pagination button interactions"""
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "first":
            new_page = 1
        elif custom_id == "prev":
            new_page = max(1, self.current_page - 1)
        elif custom_id == "next":
            new_page = min(self.total_pages, self.current_page + 1)
        elif custom_id == "last":
            new_page = self.total_pages
        else:
            return
            
        # Execute the adminpanel command with the new page
        await interaction.response.defer()
        
        # Calculate which commands to show
        admin_commands = [
            ("addcash", "Add tokens or credits to a user's balance", "!addcash @user 100 tokens"),
            ("addadmin", "Add a user as a server admin", "!addadmin @user"),
            ("viewadmins", "View server admins across all servers", "!viewadmins server_id"),
            ("removeadmin", "Remove a user as a server admin", "!removeadmin @user"),
            ("listadmins", "List all server admins for current server", "!listadmins"),
            ("fetch", "Fetch detailed information about a user", "!fetch @user"),
            ("blacklist", "Blacklist a user from using the bot", "!blacklist @user"),
            ("unblacklist", "Remove a user from the blacklist", "!unblacklist @user"),
            ("viewblacklist", "View all blacklisted users", "!viewblacklist"),
            ("manageinvites", "Manage user invite counts", "!manageinvites add @user 5"),
            ("leave", "Make the bot leave a server and delete its data", "!leave server_id"),
            ("uptime", "Show bot uptime and system information", "!uptime"),
            ("sp", "Display server profit data with rankings", "!sp [YYYY-MM-DD]"),
            ("tp", "Display total profit graph", "!tp [daily/monthly/all_time]"),
            ("game_np", "Check game performance statistics", "!game_np [game_name]"),
            ("cleardb", "Clear database collections selectively", "!cleardb [all]"),
            ("adminpanel", "Show this admin panel", "!adminpanel [page]")
        ]
        
        server_admin_commands = [
            ("serverstats", "View server statistics", "!serverstats"),
            ("airdrop", "Create a token/credit airdrop for users", "!airdrop amount [t/c] [duration]")
        ]
        
        # Calculate total pages
        total_admin_pages = (len(admin_commands) + self.commands_per_page - 1) // self.commands_per_page
        
        # Create embed
        embed = discord.Embed(
            title="👑 Admin Panel - Available Commands",
            description=f"List of all available administrator commands (Page {new_page}/{self.total_pages})",
            color=0x00FFAE
        )
        
        # Determine which commands to show based on page
        if new_page <= total_admin_pages:
            # Show admin commands
            start_idx = (new_page - 1) * self.commands_per_page
            end_idx = min(start_idx + self.commands_per_page, len(admin_commands))
            
            commands_text = ""
            for i in range(start_idx, end_idx):
                cmd, desc, usage = admin_commands[i]
                commands_text += f"**!{cmd}** - {desc}\n`{usage}`\n\n"
            
            embed.add_field(
                name="Admin Commands",
                value=commands_text,
                inline=False
            )
        else:
            # Show server admin commands
            server_page = new_page - total_admin_pages
            start_idx = (server_page - 1) * self.commands_per_page
            end_idx = min(start_idx + self.commands_per_page, len(server_admin_commands))
            
            commands_text = ""
            for i in range(start_idx, end_idx):
                cmd, desc, usage = server_admin_commands[i]
                commands_text += f"**!{cmd}** - {desc}\n`{usage}`\n\n"
            
            embed.add_field(
                name="Server Admin Commands",
                value=commands_text,
                inline=False
            )
        
        # Add navigation instructions
        embed.add_field(
            name="Navigation",
            value=f"Use the buttons below or `!adminpanel [page]` to navigate between pages.",
            inline=False
        )
        
        # Update footer
        embed.set_footer(text=f"Page {new_page}/{self.total_pages} • Requested by {interaction.user.name}", 
                         icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        
        # Create new view with updated buttons
        new_view = AdminPanelPaginator(self.cog, self.author_id, new_page, self.total_pages, self.commands_per_page)
        
        # Edit the message
        await interaction.message.edit(embed=embed, view=new_view)
        new_view.message = interaction.message

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
        self.add_item(discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, custom_id="next"))
        self.add_item(discord.ui.Button(label="Refresh", style=discord.ButtonStyle.success, custom_id="refresh"))
    
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
        elif custom_id == "refresh":
            # Just refresh the current page
            pass
            
        # Update buttons
        for child in self.children:
            if child.custom_id == "prev":
                child.disabled = self.page == 0
        
        # Generate new embed
        embed, _ = await self.cog.generate_server_profit_data(self.date, self.page, self.servers_per_page)
        
        # Update the message
        await interaction.response.edit_message(embed=embed, view=self)


def setup(bot):
    bot.add_cog(AdminCommands(bot))
