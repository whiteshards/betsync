
import discord
import asyncio
import time
import random
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class AirdropButton(discord.ui.Button):
    def __init__(self, airdrop_data):
        super().__init__(style=discord.ButtonStyle.success, label="Join Airdrop", emoji="<:checkmark:1344252974188335206>")
        self.airdrop_data = airdrop_data
        self.participants = set()  # Store participant IDs
        
    async def callback(self, interaction: discord.Interaction):
        # Prevent multiple entries
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("You've already joined this airdrop!", ephemeral=True)
            
        # Add user to participants
        self.participants.add(interaction.user.id)
        self.airdrop_data["participants"].append(interaction.user.id)
        
        # Register user if needed
        db = Users()
        if db.fetch_user(interaction.user.id) == False:
            dump = {"discord_id": interaction.user.id, "tokens": 0, "credits": 0, "history": [], 
                   "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                   "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost': 0}
            db.register_new_user(dump)
        
        # Update participant count on the embed
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            1, 
            name="👥 Participants", 
            value=f"**{len(self.participants)}** users have joined"
        )
        
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("You've joined the airdrop! Wait for it to end to receive your share.", ephemeral=True)

class AirdropView(discord.ui.View):
    def __init__(self, airdrop_data):
        super().__init__(timeout=airdrop_data["duration"])
        self.airdrop_data = airdrop_data
        self.add_item(AirdropButton(airdrop_data))
    
    async def on_timeout(self):
        # Disable the button when the airdrop ends
        for item in self.children:
            item.disabled = True
        
        # Message will be edited in the airdrop_end_handler

class ServerBetHistoryView(discord.ui.View):
    def __init__(self, author_id, server_bet_history, timeout=60):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.history = server_bet_history
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = max(1, (len(server_bet_history) + self.items_per_page - 1) // self.items_per_page)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️", disabled=True)
    async def previous_button(self, button, interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("You cannot use these controls.", ephemeral=True)
            
        self.current_page = max(0, self.current_page - 1)
        
        # Enable/disable buttons based on current page
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1
        
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_button(self, button, interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("You cannot use these controls.", ephemeral=True)
            
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        
        # Enable/disable buttons based on current page
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1
        
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def get_embed(self):
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.history))
        
        embed = discord.Embed(
            title="🎮 Server Bet History",
            description=f"Page {self.current_page + 1}/{self.total_pages}",
            color=0x00FFAE
        )
        
        if len(self.history) == 0:
            embed.add_field(name="No History", value="This server has no bet history.", inline=False)
            return embed
            
        for i in range(start_idx, end_idx):
            bet = self.history[i]
            timestamp = bet.get("timestamp", 0)
            formatted_time = f"<t:{timestamp}:R>"
            
            # Format based on bet type
            game_type = bet.get("game", "Unknown")
            user_name = bet.get("user_name", "Unknown User")
            
            if bet.get("type") == "win":
                bet_amount = bet.get("bet", 0)
                winnings = bet.get("amount", 0)
                multiplier = bet.get("multiplier", 1)
                
                value = (
                    f"**User:** {user_name}\n"
                    f"**Game:** {game_type}\n"
                    f"**Bet:** {bet_amount}\n"
                    f"**Multiplier:** {multiplier}x\n"
                    f"**Winnings:** {winnings}\n"
                    f"**When:** {formatted_time}"
                )
                
                embed.add_field(
                    name=f"🏆 Win #{i+1}",
                    value=value,
                    inline=False
                )
            else:
                bet_amount = bet.get("bet", 0)
                multiplier = bet.get("multiplier", 0)
                
                value = (
                    f"**User:** {user_name}\n"
                    f"**Game:** {game_type}\n"
                    f"**Bet:** {bet_amount}\n"
                    f"**Multiplier:** {multiplier}x\n"
                    f"**When:** {formatted_time}"
                )
                
                embed.add_field(
                    name=f"💔 Loss #{i+1}",
                    value=value,
                    inline=False
                )
        
        embed.set_footer(text="BetSync Casino • Server Stats")
        return embed

class ServersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_airdrops = {}  # Store active airdrops

    @commands.command(aliases=["ss"])
    async def serverstats(self, ctx):
        """View server stats (Server Admins and Bot Admins only)
        
        Usage: !serverstats
        """
        # Check if user is authorized (in admins.txt or server_admins)
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)
        
        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        # Check if user is a server admin or in admins.txt
        server_admins = server_data.get("server_admins", [])
        
        # Load admin IDs from admins.txt
        admin_ids = []
        try:
            with open("admins.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        admin_ids.append(int(line))
        except Exception as e:
            print(f"Error loading admin IDs: {e}")
        
        # Check if user is authorized
        if ctx.author.id not in admin_ids and ctx.author.id not in server_admins:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to server administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        total_profit = server_data["total_profit"]
        giveaway_channel = server_data["giveaway_channel"]

        embed = discord.Embed(title=f":stars: Server Stats for {ctx.guild.name}", color=0x00FFAE)
        money = emoji()["money"]
        embed.add_field(name=f"{money} Total Profit", value=f"```{round(total_profit, 2)} Tokens (~{round((total_profit * 0.0212), 2)} $)```")
        embed.add_field(name=f"{money} Server's Cut Of The Profits", value=f"```{round((total_profit * (32/100)), 2)} Tokens (~{round((total_profit * 0.0212) * (25/100), 2)} $)```")
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        await ctx.reply(embed=embed)
        
    #@commands.command(aliases=["sbh"])
    async def serverbethistory(self, ctx):
        """View the server's bet history with pagination"""
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)
        
        if not server_data:
            return await ctx.reply("This server hasn't been registered yet.")
        
        server_bet_history = server_data.get("server_bet_history", [])
        
        # Reverse the list to show newest first
        server_bet_history.reverse()
        
        # Create and send the paginated view
        view = ServerBetHistoryView(ctx.author.id, server_bet_history)
        await ctx.reply(embed=view.get_embed(), view=view)
        
    @commands.command(aliases=["ad", "gw", "giveaway"])
    async def airdrop(self, ctx, amount=None, currency_type=None, duration=None):
        """
        Create an airdrop to distribute tokens or credits to participants
        Usage: !airdrop <amount> [t/c] [duration_in_seconds]
        """
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Creating Airdrop...",
            description="Please wait while we process your request.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Check if user already has an active airdrop
        if ctx.author.id in self.active_airdrops:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Active Airdrop",
                description="You already have an active airdrop. Please wait for it to finish.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Show usage if arguments are missing
        if amount is None:
            await loading_message.delete()
            return await self.show_airdrop_usage(ctx)
        
        # Get user data from database
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description="You need an account to create an airdrop. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Parse amount
        try:
            # Handle 'all' or 'max' amount
            if amount.lower() in ['all', 'max']:
                tokens_balance = user_data['tokens']
                credits_balance = user_data['credits']
                
                # Determine which currency to use if not specified
                if currency_type is None:
                    # Use tokens if available, otherwise credits
                    if tokens_balance > 0:
                        amount_value = tokens_balance
                        currency_type = 't'
                    elif credits_balance > 0:
                        amount_value = credits_balance
                        currency_type = 'c'
                    else:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Funds",
                            description="You don't have any tokens or credits to airdrop.",
                            color=0xFF0000
                        )
                        await loading_message.delete()
                        return await ctx.reply(embed=embed)
                elif currency_type.lower() in ['t', 'token', 'tokens']:
                    amount_value = tokens_balance
                    currency_type = 't'
                elif currency_type.lower() in ['c', 'credit', 'credits']:
                    amount_value = credits_balance
                    currency_type = 'c'
                else:
                    # If currency_type is not a valid currency, it might be duration
                    if duration is None:
                        try:
                            duration = int(currency_type)
                            currency_type = None
                            if tokens_balance > 0:
                                amount_value = tokens_balance
                                currency_type = 't'
                            elif credits_balance > 0:
                                amount_value = credits_balance
                                currency_type = 'c'
                            else:
                                embed = discord.Embed(
                                    title="<:no:1344252518305234987> | Insufficient Funds",
                                    description="You don't have any tokens or credits to airdrop.",
                                    color=0xFF0000
                                )
                                await loading_message.delete()
                                return await ctx.reply(embed=embed)
                        except ValueError:
                            await loading_message.delete()
                            return await self.show_airdrop_usage(ctx)
                    else:
                        await loading_message.delete()
                        return await self.show_airdrop_usage(ctx)
            else:
                # Check if amount has 'k' or 'm' suffix
                if amount.lower().endswith('k'):
                    amount_value = float(amount[:-1]) * 1000
                elif amount.lower().endswith('m'):
                    amount_value = float(amount[:-1]) * 1000000
                else:
                    amount_value = float(amount)
        except ValueError:
            await loading_message.delete()
            return await self.show_airdrop_usage(ctx)
            
        # Ensure amount is positive
        if amount_value <= 0:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Airdrop amount must be greater than 0.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Parse currency if provided
        if currency_type is None:
            # Default: use tokens if available, otherwise credits
            tokens_balance = user_data['tokens']
            if tokens_balance >= amount_value:
                currency_type = 't'
            else:
                currency_type = 'c'
        
        # Normalize currency type
        if currency_type.lower() in ['t', 'token', 'tokens']:
            db_field = 'tokens'
            display_currency = 'tokens'
        elif currency_type.lower() in ['c', 'credit', 'credits']:
            db_field = 'credits'
            display_currency = 'credits'
        else:
            # If currency_type is not a valid currency, it might be duration
            if duration is None:
                try:
                    duration = int(currency_type)
                    # Use tokens if available, otherwise credits
                    tokens_balance = user_data['tokens']
                    if tokens_balance >= amount_value:
                        db_field = 'tokens'
                        display_currency = 'tokens'
                    else:
                        db_field = 'credits'
                        display_currency = 'credits'
                except ValueError:
                    await loading_message.delete()
                    return await self.show_airdrop_usage(ctx)
            else:
                await loading_message.delete()
                return await self.show_airdrop_usage(ctx)
        
        # Check if user has enough balance
        user_balance = user_data.get(db_field, 0)
        if user_balance < amount_value:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You don't have enough {display_currency} for this airdrop. Your balance: **{user_balance:.2f} {display_currency}**\nRequired: **{amount_value:.2f} {display_currency}**",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Parse duration if provided
        if duration is None:
            # Default: 60 seconds
            duration_value = 60
        else:
            try:
                duration_value = int(duration)
                # Cap at 10 minutes (600 seconds)
                duration_value = min(duration_value, 600)
                # Minimum of 10 seconds
                duration_value = max(duration_value, 10)
            except ValueError:
                await loading_message.delete()
                return await self.show_airdrop_usage(ctx)
        
        # Apply service fee (1.5%)
        service_fee = amount_value * 0.015
        airdrop_amount = amount_value - service_fee
        
        # Deduct from user's balance
        new_balance = user_balance - amount_value
        db.update_balance(ctx.author.id, new_balance, db_field)
        
        # Create airdrop data
        airdrop_data = {
            "author_id": ctx.author.id,
            "author_name": ctx.author.name,
            "amount": airdrop_amount,
            "currency": db_field,
            "display_currency": display_currency,
            "duration": duration_value,
            "participants": [],
            "start_time": int(time.time())
        }
        
        # Store active airdrop
        self.active_airdrops[ctx.author.id] = airdrop_data
        
        # Create embed for airdrop
        embed = discord.Embed(
            title="🎁 Airdrop Started!",
            description=f"{ctx.author.mention} is giving away **{airdrop_amount:.2f} {display_currency}**!",
            color=0x00FFAE
        )
        
        # Calculate end time
        end_time = airdrop_data["start_time"] + duration_value
        
        embed.add_field(
            name="⏱️ Time Remaining",
            value=f"Ends <t:{end_time}:R>",
            inline=False
        )
        
        embed.add_field(
            name="👥 Participants",
            value="**0** users have joined",
            inline=False
        )
        
        embed.add_field(
            name="💎 How to Join",
            value="Click the button below to join the airdrop!",
            inline=False
        )
        
        embed.set_footer(text=f"BetSync Casino • Service Fee: {service_fee:.2f} {display_currency} (1.5%)")
        
        # Create view with join button
        view = AirdropView(airdrop_data)
        
        # Delete loading message
        await loading_message.delete()
        
        # Send airdrop message
        airdrop_message = await ctx.send(embed=embed, view=view)
        
        # Schedule airdrop end handler
        self.bot.loop.create_task(
            self.airdrop_end_handler(ctx, airdrop_message, airdrop_data)
        )
        
        # Send confirmation to airdrop creator
        try:
            confirm_embed = discord.Embed(
                title="<:checkmark:1344252974188335206> | Airdrop Created",
                description=(
                    f"Your airdrop of **{airdrop_amount:.2f} {display_currency}** has been created!\n"
                    f"Service fee: **{service_fee:.2f} {display_currency}** (1.5%)\n"
                    f"Duration: **{duration_value} seconds**"
                ),
                color=0x00FF00
            )
            await ctx.author.send(embed=confirm_embed)
        except discord.Forbidden:
            # If we can't DM the user, just continue silently
            pass
        
    async def show_airdrop_usage(self, ctx):
        """Show airdrop command usage information"""
        embed = discord.Embed(
            title="<:no:1344252518305234987> | Invalid Airdrop Format",
            description="Please use the correct format for the airdrop command.",
            color=0xFF0000
        )
        embed.add_field(
            name=":bulb: Correct Usage",
            value=(
                "**Format:** `!airdrop <amount> [currency] [duration]`\n\n"
                "**Examples:**\n"
                "• `!airdrop 100` - Airdrop 100 tokens for 60 seconds\n"
                "• `!airdrop 50 t 300` - Airdrop 50 tokens for 300 seconds\n"
                "• `!airdrop 200 c 120` - Airdrop 200 credits for 120 seconds\n"
                "• `!airdrop all` - Airdrop all your tokens for 60 seconds\n"
                "• `!airdrop max c 180` - Airdrop all your credits for 180 seconds"
            ),
            inline=False
        )
        embed.add_field(
            name=":game_die: Parameters",
            value=(
                "• `amount`: Number or 'all'/'max'\n"
                "• `currency`: 't' for tokens, 'c' for credits (optional)\n"
                "• `duration`: Time in seconds, max 600 (optional)"
            ),
            inline=False
        )
        embed.set_footer(text="BetSync Casino • Aliases: !ad, !gw, !giveaway")
        await ctx.reply(embed=embed)
        
    async def airdrop_end_handler(self, ctx, message, airdrop_data):
        """Handle airdrop end after duration expires"""
        try:
            # Wait for duration
            await asyncio.sleep(airdrop_data["duration"])
            
            # Get final participants
            participants = airdrop_data["participants"]
            participant_count = len(participants)
            
            # Update embed with results
            embed = discord.Embed(
                title="🎁 Airdrop Ended!",
                color=0x00FFAE
            )
            
            if participant_count == 0:
                # No participants - refund the creator (minus fee)
                db = Users()
                creator_data = db.fetch_user(airdrop_data["author_id"])
                if creator_data:
                    current_balance = creator_data.get(airdrop_data["currency"], 0)
                    new_balance = current_balance + airdrop_data["amount"]
                    db.update_balance(airdrop_data["author_id"], new_balance, airdrop_data["currency"])
                    
                    embed.description = f"No one joined the airdrop. The amount has been refunded to {airdrop_data['author_name']}."
                    
                    # Notify creator
                    creator = self.bot.get_user(airdrop_data["author_id"])
                    if creator:
                        try:
                            refund_embed = discord.Embed(
                                title="💰 Airdrop Refund",
                                description=f"Your airdrop had no participants and has been refunded.\nRefunded: **{airdrop_data['amount']:.2f} {airdrop_data['display_currency']}**",
                                color=0x00FFAE
                            )
                            await creator.send(embed=refund_embed)
                        except discord.Forbidden:
                            # Can't DM the user, just continue
                            pass
            else:
                # Calculate share for each participant
                share_amount = airdrop_data["amount"] / participant_count
                share_amount = round(share_amount, 2)  # Round to 2 decimal places
                
                embed.description = (
                    f"Airdrop by {airdrop_data['author_name']} has ended!\n"
                    f"**{participant_count}** participants received **{share_amount:.2f} {airdrop_data['display_currency']}** each."
                )
                
                # Distribute shares to participants
                db = Users()
                participants_notified = 0
                
                for participant_id in participants:
                    participant_data = db.fetch_user(participant_id)
                    if participant_data:
                        # Update participant balance
                        current_balance = participant_data.get(airdrop_data["currency"], 0)
                        new_balance = current_balance + share_amount
                        db.update_balance(participant_id, new_balance, airdrop_data["currency"])
                        
                        # Add to history
                        history_entry = {
                            "type": "airdrop",
                            "amount": share_amount,
                            "currency": airdrop_data["currency"],
                            "from_id": airdrop_data["author_id"],
                            "from_name": airdrop_data["author_name"],
                            "timestamp": int(time.time())
                        }
                        db.collection.update_one(
                            {"discord_id": participant_id},
                            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                        )
                        
                        # Notify participant
                        participant = self.bot.get_user(participant_id)
                        if participant:
                            try:
                                notify_embed = discord.Embed(
                                    title="🎁 Airdrop Received!",
                                    description=(
                                        f"You received **{share_amount:.2f} {airdrop_data['display_currency']}** from "
                                        f"{airdrop_data['author_name']}'s airdrop!"
                                    ),
                                    color=0x00FFAE
                                )
                                await participant.send(embed=notify_embed)
                                participants_notified += 1
                            except discord.Forbidden:
                                # Can't DM the user, just continue
                                pass
                
                # Add notification stats to embed
                if participants_notified < participant_count:
                    embed.add_field(
                        name="📣 Notifications",
                        value=f"**{participants_notified}** out of **{participant_count}** participants were notified via DM.",
                        inline=False
                    )
            
            # Update the original message
            embed.set_footer(text="BetSync Casino • Airdrop Completed")
            
            # Disable buttons
            try:
                for child in message.components:
                    for item in child.children:
                        item.disabled = True
                
                await message.edit(embed=embed, components=message.components)
            except:
                # If we can't update components, try a new view
                view = discord.ui.View()
                for item in view.children:
                    item.disabled = True
                
                await message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"Error in airdrop_end_handler: {e}")
            # Try to send an error message
            try:
                error_embed = discord.Embed(
                    title="❌ Airdrop Error",
                    description="There was an error processing the airdrop. Participants may not have received their rewards.",
                    color=0xFF0000
                )
                await message.edit(embed=error_embed)
            except:
                pass
        finally:
            # Always remove from active airdrops
            if airdrop_data["author_id"] in self.active_airdrops:
                del self.active_airdrops[airdrop_data["author_id"]]

def setup(bot):
    bot.add_cog(ServersCog(bot))


import discord
import os
import time
from discord.ext import commands
from Cogs.utils.mongo import Servers, Users
from Cogs.utils.emojis import emoji

class ServerBetHistoryView(discord.ui.View):
    def __init__(self, bot, server_data, author_id, category="all", page=0):
        super().__init__(timeout=120)
        self.bot = bot
        self.server_data = server_data
        self.server_bet_history = server_data.get("server_bet_history", [])
        self.author_id = author_id
        self.category = category
        self.page = page
        self.per_page = 10
        self.max_pages = 0
        self.message = None

        # Calculate the initial max pages
        self._calculate_max_pages()

        # Add the buttons to the view
        self._update_buttons()

    def _calculate_max_pages(self):
        """Calculate the maximum number of pages for the current category"""
        filtered = self._get_filtered_history(full=True)
        self.max_pages = max(1, (len(filtered) + self.per_page - 1) // self.per_page)

    def _update_buttons(self):
        """Update all buttons in the view based on current state"""
        self.clear_items()

        # Add category buttons
        self.add_item(discord.ui.Button(label="All", style=discord.ButtonStyle.primary if self.category == "all" else discord.ButtonStyle.secondary, custom_id="all"))
        self.add_item(discord.ui.Button(label="Wins", style=discord.ButtonStyle.primary if self.category == "win" else discord.ButtonStyle.secondary, custom_id="win"))
        self.add_item(discord.ui.Button(label="Losses", style=discord.ButtonStyle.primary if self.category == "loss" else discord.ButtonStyle.secondary, custom_id="loss"))

        # Add pagination buttons
        self.add_item(discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev", disabled=self.page == 0))
        self.add_item(discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next", disabled=self.page >= self.max_pages - 1))

    def _get_filtered_history(self, full=False):
        """Get filtered history based on the selected category

        Args:
            full: If True, return all items in category, otherwise return just current page items
        """
        if self.category == "all":
            filtered = self.server_bet_history
        else:
            filtered = [item for item in self.server_bet_history if item.get("type") == self.category]

        # Sort by timestamp (most recent first)
        filtered.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        # Limit to items per page if not requesting full list
        if not full:
            # Get items for current page
            start_idx = self.page * self.per_page
            end_idx = min(start_idx + self.per_page, len(filtered))
            return filtered[start_idx:end_idx]

        return filtered

    def create_embed(self):
        """Create the server bet history embed with the filtered data"""
        filtered_data = self._get_filtered_history()
        server_name = self.server_data.get("server_name", "Unknown Server")

        # Prepare embed
        embed = discord.Embed(
            title=f":chart_with_upwards_trend: Server Bet History | {self.category.capitalize()}",
            description=f"Showing bet history for **{server_name}**.",
            color=0x00FFAE
        )

        if not filtered_data:
            embed.add_field(name="No History", value="No bets found for this category.", inline=False)
        else:
            for item in filtered_data:
                timestamp = item.get("timestamp", "Unknown")
                if isinstance(timestamp, (int, float)):
                    # Convert timestamp to readable date
                    date_str = f"<t:{int(timestamp)}:R>"
                else:
                    date_str = timestamp

                user_id = item.get("user_id", "Unknown")
                user_name = item.get("user_name", "Unknown User")
                
                # Format field name and value based on transaction type
                if item.get("type") == "win":
                    field_name = f"🏆 Win • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"User: **{user_name}** (<@{user_id}>)\n"
                    field_value += f"Bet: **{item.get('bet', 0):,.2f}**\n"
                    field_value += f"Won: **{item.get('amount', 0):,.2f} credits**\n"
                    field_value += f"Multiplier: **{item.get('multiplier', 1.0):,.2f}x**"
                elif item.get("type") == "loss":
                    field_name = f"❌ Loss • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"User: **{user_name}** (<@{user_id}>)\n"
                    field_value += f"Lost: **{item.get('amount', 0):,.2f}**\n"
                    if "multiplier" in item:
                        field_value += f"Multiplier: **{item.get('multiplier', 1.0):,.2f}x**"
                else:
                    field_name = f"🎮 Game • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"User: **{user_name}** (<@{user_id}>)\n"
                    field_value += f"Amount: **{item.get('amount', 0):,.2f}**"

                embed.add_field(name=field_name, value=field_value, inline=False)

        # Add page info
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages} • BetSync Casino", icon_url=self.bot.user.avatar.url)

        return embed

    async def interaction_check(self, interaction):
        """Check if the person clicking is the same as the command author"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your command. You can use `!serverbets` to view the server history.", ephemeral=True)
            return False

        # Handle the button click
        await self.button_callback(interaction)
        return False  # Return False to prevent the default handling

    async def button_callback(self, interaction):
        """Handle button interactions"""
        custom_id = interaction.data.get("custom_id")

        if custom_id == "all":
            self.category = "all"
            self.page = 0
        elif custom_id == "win":
            self.category = "win"
            self.page = 0
        elif custom_id == "loss":
            self.category = "loss"
            self.page = 0
        elif custom_id == "prev":
            if self.page > 0:
                self.page -= 1
        elif custom_id == "next":
            if self.page < self.max_pages - 1:
                self.page += 1

        # Recalculate max pages
        self._calculate_max_pages()

        # Update buttons
        self._update_buttons()

        # Update the message
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for child in self.children:
            child.disabled = True

        # Try to update the message with disabled buttons
        try:
            await self.message.edit(view=self)
        except:
            pass


class ServersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ss"])
    async def serverstats(self, ctx):
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        total_profit = server_data["total_profit"]
        server_admins = server_data["server_admins"]
        giveaway_channel = server_data["giveaway_channel"]

        #if count(server_admins) == 0: server_admins = None

        #if giveaway_channel == None: giveaway_channel = "Not Set"

        embed = discord.Embed(title=f":stars: Server Stats for {ctx.guild.name}", color=0x00FFAE)
        money = emoji()["money"]
        embed.add_field(name=f"{money} Total Profit", value=f"```{round(total_profit, 2)} Tokens (~{round((total_profit * 0.0212), 2)} $)```")
        embed.add_field(name=f"{money} Server's Cut Of The Profits", value=f"```{round((total_profit * (32/100)), 2)} Tokens (~{round((total_profit * 0.0212) * (25/100), 2)} $)```")
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        await ctx.reply(embed=embed)
        
    @commands.command(aliases=["ad", "gw", "giveaway"])
    async def airdrop(self, ctx, amount=None, currency_type=None, duration=None):
        """
        Create an airdrop to distribute tokens or credits to participants
        Usage: !airdrop <amount> [t/c] [duration_in_seconds]
        """
        # If no arguments provided or incorrectly formatted, show usage
        if amount is None:
            embed = discord.Embed(
                title="🎁 Airdrop Command",
                description="Create an airdrop to distribute tokens or credits to other server members!",
                color=0x00FFAE
            )
            
            embed.add_field(
                name="📝 Usage",
                value="`!airdrop <amount> [currency] [duration]`",
                inline=False
            )
            
            embed.add_field(
                name="📊 Parameters",
                value=(
                    "• `amount`: The amount to airdrop or 'all'/'max'\n"
                    "• `currency`: 't' for tokens, 'c' for credits (optional)\n"
                    "• `duration`: Duration in seconds (10-600), default: 60"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 Examples",
                value=(
                    "• `!airdrop 100` - Airdrop 100 tokens for 60 seconds\n"
                    "• `!airdrop 50 t 300` - Airdrop 50 tokens for 5 minutes\n"
                    "• `!airdrop 200 c 120` - Airdrop 200 credits for 2 minutes\n"
                    "• `!airdrop all` - Airdrop all your tokens\n"
                    "• `!airdrop max c` - Airdrop all your credits"
                ),
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ Notes",
                value=(
                    "• A 1.5% service fee is applied to all airdrops\n"
                    "• The amount is evenly distributed among participants\n"
                    "• If no one joins, your amount will be refunded (minus fee)"
                ),
                inline=False
            )
            
            embed.set_footer(text="BetSync Casino • Aliases: !ad, !gw, !giveaway")
            
            await ctx.reply(embed=embed)
            return
            
        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Creating Airdrop...",
            description="Please wait while we process your request.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Check if user already has an active airdrop
        if hasattr(self, 'active_airdrops') and ctx.author.id in self.active_airdrops:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Active Airdrop",
                description="You already have an active airdrop. Please wait for it to finish.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Initialize active_airdrops dict if not already exists
        if not hasattr(self, 'active_airdrops'):
            self.active_airdrops = {}
        
        # Get user data from database
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description="You need an account to create an airdrop. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Parse amount
        try:
            # Handle 'all' or 'max' bet
            if amount.lower() in ['all', 'max']:
                tokens_balance = user_data['tokens']
                credits_balance = user_data['credits']
                
                # Determine which currency to use if not specified
                if currency_type is None:
                    # Use tokens if available, otherwise credits
                    if tokens_balance > 0:
                        amount_value = tokens_balance
                        currency_type = 't'
                    elif credits_balance > 0:
                        amount_value = credits_balance
                        currency_type = 'c'
                    else:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Funds",
                            description="You don't have any tokens or credits to airdrop.",
                            color=0xFF0000
                        )
                        await loading_message.delete()
                        return await ctx.reply(embed=embed)
                elif currency_type.lower() in ['t', 'token', 'tokens']:
                    amount_value = tokens_balance
                    currency_type = 't'
                elif currency_type.lower() in ['c', 'credit', 'credits']:
                    amount_value = credits_balance
                    currency_type = 'c'
                else:
                    # If currency_type is not a valid currency, it might be duration
                    if duration is None:
                        try:
                            duration = int(currency_type)
                            currency_type = None
                            if tokens_balance > 0:
                                amount_value = tokens_balance
                                currency_type = 't'
                            elif credits_balance > 0:
                                amount_value = credits_balance
                                currency_type = 'c'
                            else:
                                embed = discord.Embed(
                                    title="<:no:1344252518305234987> | Insufficient Funds",
                                    description="You don't have any tokens or credits to airdrop.",
                                    color=0xFF0000
                                )
                                await loading_message.delete()
                                return await ctx.reply(embed=embed)
                        except ValueError:
                            await loading_message.delete()
                            return await self.show_airdrop_usage(ctx)
                    else:
                        await loading_message.delete()
                        return await self.show_airdrop_usage(ctx)
            else:
                # Check if amount has 'k' or 'm' suffix
                if amount.lower().endswith('k'):
                    amount_value = float(amount[:-1]) * 1000
                elif amount.lower().endswith('m'):
                    amount_value = float(amount[:-1]) * 1000000
                else:
                    amount_value = float(amount)
        except ValueError:
            await loading_message.delete()
            return await self.show_airdrop_usage(ctx)
            
        # Ensure amount is positive
        if amount_value <= 0:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Airdrop amount must be greater than 0.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Parse currency if provided
        if currency_type is None:
            # Default: use tokens if available, otherwise credits
            tokens_balance = user_data['tokens']
            if tokens_balance >= amount_value:
                currency_type = 't'
            else:
                currency_type = 'c'
        
        # Normalize currency type
        if currency_type.lower() in ['t', 'token', 'tokens']:
            db_field = 'tokens'
            display_currency = 'tokens'
        elif currency_type.lower() in ['c', 'credit', 'credits']:
            db_field = 'credits'
            display_currency = 'credits'
        else:
            # If currency_type is not a valid currency, it might be duration
            if duration is None:
                try:
                    duration = int(currency_type)
                    # Use tokens if available, otherwise credits
                    tokens_balance = user_data['tokens']
                    if tokens_balance >= amount_value:
                        db_field = 'tokens'
                        display_currency = 'tokens'
                    else:
                        db_field = 'credits'
                        display_currency = 'credits'
                except ValueError:
                    await loading_message.delete()
                    return await self.show_airdrop_usage(ctx)
            else:
                await loading_message.delete()
                return await self.show_airdrop_usage(ctx)
        
        # Check if user has enough balance
        user_balance = user_data.get(db_field, 0)
        if user_balance < amount_value:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You don't have enough {display_currency} for this airdrop. Your balance: **{user_balance:.2f} {display_currency}**\nRequired: **{amount_value:.2f} {display_currency}**",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)
            
        # Parse duration if provided
        if duration is None:
            # Default: 60 seconds
            duration_value = 60
        else:
            try:
                duration_value = int(duration)
                # Cap at 10 minutes (600 seconds)
                duration_value = min(duration_value, 600)
                # Minimum of 10 seconds
                duration_value = max(duration_value, 10)
            except ValueError:
                await loading_message.delete()
                return await self.show_airdrop_usage(ctx)
        
        # Apply service fee (1.5%)
        service_fee = amount_value * 0.015
        airdrop_amount = amount_value - service_fee
        
        # Deduct from user's balance
        new_balance = user_balance - amount_value
        db.update_balance(ctx.author.id, new_balance, db_field)
        
        # Create airdrop data
        airdrop_data = {
            "author_id": ctx.author.id,
            "author_name": ctx.author.name,
            "amount": airdrop_amount,
            "currency": db_field,
            "display_currency": display_currency,
            "duration": duration_value,
            "participants": [],
            "start_time": int(time.time())
        }
        
        # Store active airdrop
        self.active_airdrops[ctx.author.id] = airdrop_data
        
        # Create embed for airdrop
        embed = discord.Embed(
            title="🎁 Airdrop Started!",
            description=f"{ctx.author.mention} is giving away **{airdrop_amount:.2f} {display_currency}**!",
            color=0x00FFAE
        )
        
        # Calculate end time
        end_time = airdrop_data["start_time"] + duration_value
        
        embed.add_field(
            name="⏱️ Time Remaining",
            value=f"Ends <t:{end_time}:R>",
            inline=False
        )
        
        embed.add_field(
            name="👥 Participants",
            value="**0** users have joined",
            inline=False
        )
        
        embed.add_field(
            name="💎 How to Join",
            value="Click the button below to join the airdrop!",
            inline=False
        )
        
        embed.set_footer(text=f"BetSync Casino • Service Fee: {service_fee:.2f} {display_currency} (1.5%)")
        
        # Create view with join button
        view = AirdropView(airdrop_data)
        
        # Delete loading message
        await loading_message.delete()
        
        # Send airdrop message
        airdrop_message = await ctx.send(embed=embed, view=view)
        
        # Schedule airdrop end handler
        self.bot.loop.create_task(
            self.airdrop_end_handler(ctx, airdrop_message, airdrop_data)
        )
        
        # Send confirmation to airdrop creator
        try:
            confirm_embed = discord.Embed(
                title="<:checkmark:1344252974188335206> | Airdrop Created",
                description=(
                    f"Your airdrop of **{airdrop_amount:.2f} {display_currency}** has been created!\n"
                    f"Service fee: **{service_fee:.2f} {display_currency}** (1.5%)\n"
                    f"Duration: **{duration_value} seconds**"
                ),
                color=0x00FF00
            )
            await ctx.author.send(embed=confirm_embed)
        except discord.Forbidden:
            # If we can't DM the user, just continue silently
            pass
        
    async def show_airdrop_usage(self, ctx):
        """Show airdrop command usage information"""
        embed = discord.Embed(
            title="<:no:1344252518305234987> | Invalid Airdrop Format",
            description="Please use the correct format for the airdrop command.",
            color=0xFF0000
        )
        embed.add_field(
            name=":bulb: Correct Usage",
            value=(
                "**Format:** `!airdrop <amount> [currency] [duration]`\n\n"
                "**Examples:**\n"
                "• `!airdrop 100` - Airdrop 100 tokens for 60 seconds\n"
                "• `!airdrop 50 t 300` - Airdrop 50 tokens for 300 seconds\n"
                "• `!airdrop 200 c 120` - Airdrop 200 credits for 120 seconds\n"
                "• `!airdrop all` - Airdrop all your tokens for 60 seconds\n"
                "• `!airdrop max c 180` - Airdrop all your credits for 180 seconds"
            ),
            inline=False
        )
        embed.add_field(
            name=":game_die: Parameters",
            value=(
                "• `amount`: Number or 'all'/'max'\n"
                "• `currency`: 't' for tokens, 'c' for credits (optional)\n"
                "• `duration`: Time in seconds, max 600 (optional)"
            ),
            inline=False
        )
        embed.set_footer(text="BetSync Casino • Aliases: !ad, !gw, !giveaway")
        await ctx.reply(embed=embed)
        
    async def airdrop_end_handler(self, ctx, message, airdrop_data):
        """Handle airdrop end after duration expires"""
        try:
            # Wait for duration
            await asyncio.sleep(airdrop_data["duration"])
            
            # Get final participants
            participants = airdrop_data["participants"]
            participant_count = len(participants)
            
            # Update embed with results
            embed = discord.Embed(
                title="🎁 Airdrop Ended!",
                color=0x00FFAE
            )
            
            if participant_count == 0:
                # No participants - refund the creator (minus fee)
                db = Users()
                creator_data = db.fetch_user(airdrop_data["author_id"])
                if creator_data:
                    current_balance = creator_data.get(airdrop_data["currency"], 0)
                    new_balance = current_balance + airdrop_data["amount"]
                    db.update_balance(airdrop_data["author_id"], new_balance, airdrop_data["currency"])
                    
                    embed.description = f"No one joined the airdrop. The amount has been refunded to {airdrop_data['author_name']}."
                    
                    # Notify creator
                    creator = self.bot.get_user(airdrop_data["author_id"])
                    if creator:
                        try:
                            refund_embed = discord.Embed(
                                title="💰 Airdrop Refund",
                                description=f"Your airdrop had no participants and has been refunded.\nRefunded: **{airdrop_data['amount']:.2f} {airdrop_data['display_currency']}**",
                                color=0x00FFAE
                            )
                            await creator.send(embed=refund_embed)
                        except discord.Forbidden:
                            # Can't DM the user, just continue
                            pass
            else:
                # Calculate share for each participant
                share_amount = airdrop_data["amount"] / participant_count
                share_amount = round(share_amount, 2)  # Round to 2 decimal places
                
                embed.description = (
                    f"Airdrop by {airdrop_data['author_name']} has ended!\n"
                    f"**{participant_count}** participants received **{share_amount:.2f} {airdrop_data['display_currency']}** each."
                )
                
                # Distribute shares to participants
                db = Users()
                participants_notified = 0
                
                for participant_id in participants:
                    participant_data = db.fetch_user(participant_id)
                    if participant_data:
                        # Update participant balance
                        current_balance = participant_data.get(airdrop_data["currency"], 0)
                        new_balance = current_balance + share_amount
                        db.update_balance(participant_id, new_balance, airdrop_data["currency"])
                        
                        # Add to history
                        history_entry = {
                            "type": "airdrop",
                            "amount": share_amount,
                            "currency": airdrop_data["currency"],
                            "from_id": airdrop_data["author_id"],
                            "from_name": airdrop_data["author_name"],
                            "timestamp": int(time.time())
                        }
                        db.collection.update_one(
                            {"discord_id": participant_id},
                            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                        )
                        
                        # Notify participant
                        participant = self.bot.get_user(participant_id)
                        if participant:
                            try:
                                notify_embed = discord.Embed(
                                    title="🎁 Airdrop Received!",
                                    description=(
                                        f"You received **{share_amount:.2f} {airdrop_data['display_currency']}** from "
                                        f"{airdrop_data['author_name']}'s airdrop!"
                                    ),
                                    color=0x00FFAE
                                )
                                await participant.send(embed=notify_embed)
                                participants_notified += 1
                            except discord.Forbidden:
                                # Can't DM the user, just continue
                                pass
                
                # Add notification stats to embed
                if participants_notified < participant_count:
                    embed.add_field(
                        name="📣 Notifications",
                        value=f"**{participants_notified}** out of **{participant_count}** participants were notified via DM.",
                        inline=False
                    )
            
            # Update the original message
            embed.set_footer(text="BetSync Casino • Airdrop Completed")
            
            # Disable buttons
            try:
                for item in message.view.children:
                    item.disabled = True
                await message.edit(embed=embed, view=message.view)
            except:
                # If we can't update components, try a new view
                view = discord.ui.View()
                for item in view.children:
                    item.disabled = True
                
                await message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"Error in airdrop_end_handler: {e}")
            # Try to send an error message
            try:
                error_embed = discord.Embed(
                    title="❌ Airdrop Error",
                    description="There was an error processing the airdrop. Participants may not have received their rewards.",
                    color=0xFF0000
                )
                await message.edit(embed=error_embed)
            except:
                pass
        finally:
            # Always remove from active airdrops
            if airdrop_data["author_id"] in self.active_airdrops:
                del self.active_airdrops[airdrop_data["author_id"]]
                
    @commands.command(aliases=["serverbets", "serverhistory", "sbets", "sb"])
    async def serverbethistory(self, ctx):
        """View server's bet history with filtering by category and pagination"""
        # Send loading embed first
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Loading Server Bet History...",
            description="Please wait while we fetch the server's bet history.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if server_data == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact an administrator.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)

        # Create view with buttons
        view = ServerBetHistoryView(self.bot, server_data, ctx.author.id)

        # Send initial embed
        embed = view.create_embed()
        
        # Delete the loading message
        await loading_message.delete()
        
        message = await ctx.reply(embed=embed, view=view)

        # Store the message for later reference in the view
        view.message = message
        
    @commands.command(aliases=["serversetup", "configure"])
    async def setup(self, ctx):
        """Set up server-specific prefixes and whitelisted channels (Server Admins only)
        
        Usage: !setup
        """
        # Check if DMs are enabled
        try:
            # Attempt to send a test message to check if DMs are open
            test_dm = await ctx.author.send("Setting up your server configuration...")
        except discord.Forbidden:
            # DMs are disabled
            embed = discord.Embed(
                title="<:no:1344252518305234987> | DMs Disabled",
                description="Please enable direct messages from server members to use this command.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Delete the test message
        await test_dm.delete()
            
        # Send acknowledgment message in the channel
        ack_embed = discord.Embed(
            title="<:checkmark:1344252974188335206> | Setup Process Started",
            description="I've sent you a direct message to configure your server!",
            color=0x00FF00
        )
        await ctx.reply(embed=ack_embed)
        
        # Check if user is authorized (server admin or bot admin)
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)
        
        if not server_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact the developer.",
                color=0xFF0000
            )
            return await ctx.author.send(embed=embed)
            
        # Load admin IDs from admins.txt
        admin_ids = []
        try:
            with open("admins.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        admin_ids.append(int(line))
        except Exception as e:
            print(f"Error loading admin IDs: {e}")
        
        # Get server admins from database
        server_admins = server_data.get("server_admins", [])
        
        # Check if user is authorized
        if ctx.author.id not in admin_ids and ctx.author.id not in server_admins:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to server administrators only.",
                color=0xFF0000
            )
            return await ctx.author.send(embed=embed)
        
        # Get current configurations
        current_prefixes = server_data.get("server_prefixes", [])
        current_channels = server_data.get("whitelisted_channels", [])
        
        # Create welcome embed
        embed = discord.Embed(
            title=f"⚙️ Server Setup: {ctx.guild.name}",
            description="Configure your server settings for BetSync Casino below.",
            color=0x00FFAE
        )
        
        # Format current prefixes
        prefix_str = "None configured (using default prefixes: `!`, `.`)"
        if current_prefixes:
            prefix_str = ", ".join([f"`{p}`" for p in current_prefixes])
        
        embed.add_field(
            name="🏷️ Custom Prefixes",
            value=f"Current prefixes: {prefix_str}\n\nType `add prefix [prefix]` to add a prefix.\nType `remove prefix [prefix]` to remove a prefix.",
            inline=False
        )
        
        # Format current channels
        channel_str = "None configured (bot works in all channels)"
        if current_channels:
            channel_mentions = []
            for channel_id in current_channels:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    channel_mentions.append(f"<#{channel_id}>")
                else:
                    channel_mentions.append(f"Unknown Channel ({channel_id})")
            channel_str = ", ".join(channel_mentions)
        
        embed.add_field(
            name="📝 Whitelisted Channels",
            value=f"Current channels: {channel_str}\n\nType `add channel #channel` or `add channel [channel_id]` to add a channel.\nType `remove channel #channel` or `remove channel [channel_id]` to remove a channel.",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Notes",
            value="• Commands will only work in whitelisted channels if any are set\n• Channel mentions must be valid Discord channel mentions\n• Type `done` when you're finished configuring",
            inline=False
        )
        
        embed.set_footer(text="BetSync Casino • Server Setup")
        
        # Send the embed to DM
        await ctx.author.send(embed=embed)
        
        # Start interaction loop
        while True:
            try:
                # Wait for user response
                response = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author.id == ctx.author.id and m.guild is None,
                    timeout=300  # 5 minutes timeout
                )
                
                cmd = response.content.lower().strip()
                
                # Check if user wants to exit
                if cmd == "done" or cmd == "exit" or cmd == "quit":
                    final_embed = discord.Embed(
                        title="<:checkmark:1344252974188335206> | Setup Complete",
                        description="Your server configuration has been saved!",
                        color=0x00FF00
                    )
                    await ctx.author.send(embed=final_embed)
                    break
                
                # Process commands
                if cmd.startswith("add prefix "):
                    prefix = cmd[11:].strip()
                    if not prefix:
                        await ctx.author.send("❌ | Prefix cannot be empty.")
                        continue
                    
                    if prefix in current_prefixes:
                        await ctx.author.send(f"❌ | Prefix `{prefix}` is already added.")
                        continue
                    
                    # Update database
                    current_prefixes.append(prefix)
                    db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {"$set": {"server_prefixes": current_prefixes}}
                    )
                    
                    # Update bot prefixes for this guild
                    for command in self.bot.commands:
                        if not hasattr(command, 'guild_prefixes'):
                            command.guild_prefixes = {}
                        command.guild_prefixes[ctx.guild.id] = current_prefixes
                    
                    await ctx.author.send(f"✅ | Added prefix: `{prefix}`")
                
                elif cmd.startswith("remove prefix "):
                    prefix = cmd[14:].strip()
                    if not prefix:
                        await ctx.author.send("❌ | Please specify a prefix to remove.")
                        continue
                    
                    if prefix not in current_prefixes:
                        await ctx.author.send(f"❌ | Prefix `{prefix}` is not in the list.")
                        continue
                    
                    # Update database
                    current_prefixes.remove(prefix)
                    db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {"$set": {"server_prefixes": current_prefixes}}
                    )
                    
                    # Update bot prefixes for this guild
                    for command in self.bot.commands:
                        if hasattr(command, 'guild_prefixes') and ctx.guild.id in command.guild_prefixes:
                            command.guild_prefixes[ctx.guild.id] = current_prefixes
                    
                    await ctx.author.send(f"✅ | Removed prefix: `{prefix}`")
                
                elif cmd.startswith("add channel "):
                    try:
                        # First check if there's a channel mention
                        if response.channel_mentions:
                            channel = response.channel_mentions[0]
                            channel_id = channel.id
                            channel_name = channel.mention
                        else:
                            # Try to get channel ID from the message
                            channel_id_str = cmd[11:].strip()
                            
                            # Handle potential <#id> format manually
                            if channel_id_str.startswith("<#") and channel_id_str.endswith(">"):
                                channel_id_str = channel_id_str[2:-1]
                                
                            try:
                                channel_id = int(channel_id_str)
                                # Try to get the channel object
                                channel = self.bot.get_channel(channel_id)
                                
                                if not channel:
                                    # Channel might exist but bot can't see it
                                    channel_name = f"Channel (ID: {channel_id})"
                                else:
                                    channel_name = channel.mention
                                    # Verify channel is in the server
                                    if channel.guild.id != ctx.guild.id:
                                        await ctx.author.send("❌ | The channel must be in your server.")
                                        continue
                            except ValueError:
                                await ctx.author.send("❌ | Please provide a valid channel ID or mention.")
                                continue
                        
                        # Check if channel is already in the whitelist
                        if channel_id in current_channels:
                            await ctx.author.send(f"❌ | Channel {channel_name} is already whitelisted.")
                            continue
                        
                        # Update database
                        current_channels.append(channel_id)
                        db.collection.update_one(
                            {"server_id": ctx.guild.id},
                            {"$set": {"whitelisted_channels": current_channels}}
                        )
                        
                        await ctx.author.send(f"✅ | Added whitelisted channel: {channel_name}")
                    except Exception as e:
                        await ctx.author.send(f"❌ | Error adding channel: {str(e)}")
                
                elif cmd.startswith("remove channel "):
                    try:
                        # First check if there's a channel mention
                        if response.channel_mentions:
                            channel = response.channel_mentions[0]
                            channel_id = channel.id
                            channel_name = channel.mention
                        else:
                            # Try to get channel ID from the message
                            channel_id_str = cmd[14:].strip()
                            
                            # Handle potential <#id> format manually
                            if channel_id_str.startswith("<#") and channel_id_str.endswith(">"):
                                channel_id_str = channel_id_str[2:-1]
                            
                            try:
                                channel_id = int(channel_id_str)
                                # Try to get the channel object
                                channel = self.bot.get_channel(channel_id)
                                
                                if not channel:
                                    # Channel might exist but bot can't see it
                                    channel_name = f"Channel (ID: {channel_id})"
                                else:
                                    channel_name = channel.mention
                            except ValueError:
                                await ctx.author.send("❌ | Please provide a valid channel ID or mention.")
                                continue
                        
                        # Check if channel is in the whitelist
                        if channel_id not in current_channels:
                            await ctx.author.send(f"❌ | Channel {channel_name} is not in the whitelist.")
                            continue
                        
                        # Update database
                        current_channels.remove(channel_id)
                        db.collection.update_one(
                            {"server_id": ctx.guild.id},
                            {"$set": {"whitelisted_channels": current_channels}}
                        )
                        
                        await ctx.author.send(f"✅ | Removed whitelisted channel: {channel_name}")
                    except Exception as e:
                        await ctx.author.send(f"❌ | Error removing channel: {str(e)}")
                
                else:
                    await ctx.author.send("❌ | Unknown command. Type `add prefix [prefix]`, `remove prefix [prefix]`, `add channel #channel`, `remove channel #channel`, or `done`.")
            
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏱️ Setup Timed Out",
                    description="The setup process has been automatically closed due to inactivity.",
                    color=0xFF9900
                )
                await ctx.author.send(embed=timeout_embed)
                break
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
                    color=0xFF0000
                )
                await ctx.author.send(embed=error_embed)
                break


def setup(bot):
    bot.add_cog(ServersCog(bot))
