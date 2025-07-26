
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import datetime

class HistoryView(discord.ui.View):
    def __init__(self, bot, user, history_data, author_id, category="all", page=0):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user
        self.history_data = history_data
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
        self.add_item(discord.ui.Button(label="Deposits", style=discord.ButtonStyle.primary if self.category == "deposit" else discord.ButtonStyle.secondary, custom_id="deposit"))
        self.add_item(discord.ui.Button(label="Withdrawals", style=discord.ButtonStyle.primary if self.category == "withdraw" else discord.ButtonStyle.secondary, custom_id="withdraw"))
        self.add_item(discord.ui.Button(label="Wins", style=discord.ButtonStyle.primary if self.category == "win" else discord.ButtonStyle.secondary, custom_id="win"))
        self.add_item(discord.ui.Button(label="Losses", style=discord.ButtonStyle.primary if self.category == "loss" else discord.ButtonStyle.secondary, custom_id="loss"))
        self.add_item(discord.ui.Button(label="Pushes", style=discord.ButtonStyle.primary if self.category == "push" else discord.ButtonStyle.secondary, custom_id="push"))

        # Add pagination buttons
        self.add_item(discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev", disabled=self.page == 0))
        self.add_item(discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next", disabled=self.page >= self.max_pages - 1))

    def _get_filtered_history(self, full=False):
        """Get filtered history based on the selected category"""
        if self.category == "all":
            filtered = self.history_data
        elif self.category == "deposit":
            # Handle all deposit types (btc_deposit, ltc_deposit, eth_deposit, etc.)
            filtered = [item for item in self.history_data if item.get("type", "").endswith("_deposit") or item.get("type") == "deposit"]
        elif self.category == "withdraw":
            # Handle all withdrawal types (btc_withdraw, ltc_withdraw, etc.)
            filtered = [item for item in self.history_data if item.get("type", "").endswith("_withdraw") or item.get("type") == "withdraw"]
        elif self.category == "push":
            # Handle both "push" and "draw" types for pushes
            filtered = [item for item in self.history_data if item.get("type") in ["push", "draw"]]
        else:
            filtered = [item for item in self.history_data if item.get("type") == self.category]

        # Sort by timestamp (most recent first)
        def get_timestamp(item):
            timestamp = item.get("timestamp", 0)
            if isinstance(timestamp, str):
                try:
                    # Try to parse ISO format timestamps
                    if 'T' in timestamp or 'Z' in timestamp:
                        if timestamp.endswith('Z'):
                            timestamp = timestamp[:-1] + '+00:00'
                        dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        return int(dt.timestamp())
                    elif timestamp.isdigit():
                        return int(timestamp)
                    else:
                        return 0
                except:
                    return 0
            elif isinstance(timestamp, (int, float)):
                return int(timestamp)
            else:
                return 0

        filtered.sort(key=get_timestamp, reverse=True)

        if not full:
            # Get items for current page
            start_idx = self.page * self.per_page
            end_idx = min(start_idx + self.per_page, len(filtered))
            return filtered[start_idx:end_idx]

        return filtered

    def create_embed(self):
        """Create the history embed with the filtered data"""
        filtered_data = self._get_filtered_history()

        # Prepare embed
        embed = discord.Embed(
            title=f"📜 Transaction History | {self.category.capitalize()}",
            description=f"Showing **{self.user.display_name}**'s transaction history.",
            color=0x00FFAE
        )

        if not filtered_data:
            embed.add_field(name="No History", value="No transactions found for this category.", inline=False)
        else:
            for item in filtered_data:
                timestamp = item.get("timestamp", "Unknown")
                
                # Format timestamp
                if isinstance(timestamp, (int, float)):
                    date_str = f"<t:{int(timestamp)}:R>"
                elif isinstance(timestamp, str):
                    try:
                        if 'T' in timestamp or 'Z' in timestamp:
                            if timestamp.endswith('Z'):
                                timestamp = timestamp[:-1] + '+00:00'
                            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            date_str = f"<t:{int(dt.timestamp())}:R>"
                        elif timestamp.isdigit():
                            date_str = f"<t:{int(timestamp)}:R>"
                        else:
                            date_str = timestamp
                    except:
                        date_str = "Unknown"
                else:
                    date_str = "Unknown"

                # Get amount and format it properly
                amount = item.get("amount", 0)
                try:
                    amount = float(amount)
                except:
                    amount = 0

                # Format field name and value based on transaction type
                transaction_type = item.get("type", "unknown")
                
                if transaction_type.endswith("_deposit") or transaction_type == "deposit":
                    # Handle all deposit types (btc_deposit, ltc_deposit, etc.)
                    currency = item.get("currency", "")
                    crypto_amount = item.get("amount_crypto", 0)
                    points_credited = item.get("points_credited", amount)
                    if currency and crypto_amount:
                        field_name = f"💰 {currency} Deposit • {date_str}"
                        field_value = f"Deposited **{crypto_amount:,.8f} {currency}** • Received **{points_credited:,.2f} points**"
                    else:
                        field_name = f"💰 Deposit • {date_str}"
                        field_value = f"Received **{points_credited:,.2f} points**"
                elif transaction_type.endswith("_withdraw") or transaction_type == "withdraw":
                    # Handle all withdrawal types (btc_withdraw, ltc_withdraw, etc.)
                    currency = item.get("currency", "")
                    crypto_amount = item.get("amount_crypto", 0)
                    points_cost = item.get("points_cost", amount)
                    if currency and crypto_amount:
                        field_name = f"💸 {currency} Withdrawal • {date_str}"
                        field_value = f"Withdrew **{crypto_amount:,.8f} {currency}** • Cost **{points_cost:,.2f} points**"
                    else:
                        field_name = f"💸 Withdrawal • {date_str}"
                        field_value = f"Withdrew **{points_cost:,.2f} points**"
                elif transaction_type == "win":
                    game_name = item.get("game", "Game").title()
                    bet_amount = item.get("bet", 0)
                    multiplier = item.get("multiplier", 0)
                    field_name = f"🏆 Win • {game_name} • {date_str}"
                    field_value = f"Bet **{bet_amount:,.2f} points** • Won **{amount:,.2f} points** • {multiplier}x"
                elif transaction_type == "loss":
                    game_name = item.get("game", "Game").title()
                    bet_amount = item.get("bet", amount)
                    field_name = f"❌ Loss • {game_name} • {date_str}"
                    field_value = f"Lost **{bet_amount:,.2f} points**"
                elif transaction_type == "push" or transaction_type == "draw":
                    game_name = item.get("game", "Game").title()
                    bet_amount = item.get("bet", amount)
                    field_name = f"🔄 Push • {game_name} • {date_str}"
                    field_value = f"Bet returned: **{bet_amount:,.2f} points**"
                else:
                    field_name = f"🔄 Transaction • {date_str}"
                    field_value = f"Amount: **{amount:,.2f} points**"

                embed.add_field(name=field_name, value=field_value, inline=False)

        # Add page info
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages} • BetSync Casino", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        # Set thumbnail to user's avatar
        if self.user.avatar:
            embed.set_thumbnail(url=self.user.avatar.url)
        elif self.user.default_avatar:
            embed.set_thumbnail(url=self.user.default_avatar.url)

        return embed

    async def interaction_check(self, interaction):
        """Check if the person clicking is the same as the command author"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your command. Type `!history` to view your own history.", ephemeral=True)
            return False
            
        # Get the custom_id from the interaction
        custom_id = interaction.data.get("custom_id")
        
        # Handle the different button actions
        if custom_id == "all":
            self.category = "all"
            self.page = 0
        elif custom_id == "deposit":
            self.category = "deposit"
            self.page = 0
        elif custom_id == "withdraw":
            self.category = "withdraw"
            self.page = 0
        elif custom_id == "win":
            self.category = "win"
            self.page = 0
        elif custom_id == "loss":
            self.category = "loss"
            self.page = 0
        elif custom_id == "push":
            self.category = "push"
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
        return False  # Return False to prevent default handling
        
    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for child in self.children:
            child.disabled = True

        # Try to update the message with disabled buttons
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception as e:
            print(f"Error updating message on timeout: {e}")


class History(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["transactions", "logs"])
    async def history(self, ctx, user: discord.Member = None):
        """View your transaction history with filtering by category and pagination"""
        try:
            # Send loading embed first
            loading_emoji = emoji()["loading"]
            loading_embed = discord.Embed(
                title=f"{loading_emoji} | Loading Transaction History...",
                description="Please wait while we fetch your transaction history.",
                color=0x00FFAE
            )
            loading_message = await ctx.reply(embed=loading_embed)
            
            if user is None:
                user = ctx.author

            db = Users()
            user_data = db.fetch_user(user.id)

            if user_data == False:
                embed = discord.Embed(
                    title="❌ | User Not Found",
                    description="This user doesn't have an account. Please wait for auto-registration or use `!signup`.",
                    color=0xFF0000
                )
                await loading_message.delete()
                return await ctx.reply(embed=embed)

            # Get history from user data
            history_data = user_data.get("history", [])
            
            # Ensure history_data is a list
            if not isinstance(history_data, list):
                history_data = []
                
            # Create view with buttons
            view = HistoryView(self.bot, user, history_data, ctx.author.id)

            # Send initial embed
            embed = view.create_embed()
            
            # Delete the loading message
            await loading_message.delete()
            
            # Send the history embed with buttons
            message = await ctx.reply(embed=embed, view=view)

            # Store the message for later reference in the view
            view.message = message
            
        except Exception as e:
            # Handle any errors and provide feedback to the user
            print(f"Error in history command: {e}")
            error_embed = discord.Embed(
                title="❌ | Error Fetching History",
                description="There was an error fetching your transaction history. Please try again later.",
                color=0xFF0000
            )
            
            # Try to delete the loading message if it exists
            try:
                await loading_message.delete()
            except:
                pass
                
            await ctx.reply(embed=error_embed)


def setup(bot):
    bot.add_cog(History(bot))
