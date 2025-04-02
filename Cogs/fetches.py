import os
import requests
import discord
import json
import datetime
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users, Servers
from colorama import Fore, Back, Style

class Fetches(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_crypto_prices(self):
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,litecoin,solana,tether,dogecoin",
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"{Fore.RED}[-] {Fore.WHITE}Failed to fetch crypto prices. Status Code: {Fore.RED}{response.status_code}{Fore.WHITE}")
            return None

    def calculate_total_usd(self, user_data):
        """Calculate total USD value for a user's wallet including all cryptos"""
        prices = self.get_crypto_prices()
        if not prices:
            print(f"{Fore.RED}[-] {Fore.WHITE}Failed to get crypto prices for USD calculation{Style.RESET_ALL}")
            return 0.0

        wallet = user_data.get("wallet", {})
        total_usd = 0.0

        # Supported cryptos and their API ids
        crypto_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "LTC": "litecoin",
            "SOL": "solana",
            "USDT": "tether",
            "DOGE": "dogecoin"
        }

        for coin, amount in wallet.items():
            if coin in crypto_map:
                api_id = crypto_map[coin]
                if api_id in prices:
                    rate = 1.0 if coin == "USDT" else prices[api_id].get("usd", 0)
                    total_usd += amount * rate

        return float(f"{total_usd:.2f}")

    #@commands.command(name="rate")
    async def rate(self, ctx, amount: float = None, currency: str = None):
        bot_icon = self.bot.user.avatar.url

        if amount is None or currency is None:
            embed = discord.Embed(
                title=":bulb: How to Use `!rate`",
                description="Convert tokens/credits to cryptocurrency at real-time rates.\n\n"
                          "**Usage:** `!rate <amount> <currency>`\n"
                          "**Example:** `!rate 100 BTC`\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFFD700
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino • Live Exchange Rates", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

        currency = currency.upper()
        prices = self.get_crypto_prices()

        if not prices:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | API Error",
                description="Could not retrieve live crypto prices. Please try again later.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

        conversion_rates = {
            "BTC": prices.get("bitcoin", {}).get("usd"),
            "ETH": prices.get("ethereum", {}).get("usd"),
            "LTC": prices.get("litecoin", {}).get("usd"),
            "SOL": prices.get("solana", {}).get("usd"),
            "DOGE": prices.get("dogecoin", {}).get("usd"),
            "USDT": prices.get("tether", {}).get("usd")
        }

        if currency not in conversion_rates:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description=f"`{currency}` is not supported.\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFF0000
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

        usd_value = amount * 0.013
        converted_amount = usd_value / conversion_rates[currency]

        embed = discord.Embed(
            title=":currency_exchange: Live Currency Conversion",
            color=0x00FFAE,
            description="ㅤㅤㅤ"
        )

        embed.add_field(
            name=":moneybag: Equivalent USD Value",
            value=f"**${usd_value:,.2f}**",
            inline=False
        )

        embed.add_field(
            name=f":arrows_counterclockwise: {amount:,.2f} Tokens/Credits in {currency}",
            value=f"```ini\n[{converted_amount:.8f} {currency}]\n```",
            inline=False
        )

        embed.set_thumbnail(url=bot_icon)
        embed.set_footer(text="BetSync Casino • Live Exchange Rates", icon_url=bot_icon)

        await ctx.message.reply(embed=embed)

    #@commands.command()
    async def stats(self, ctx, user: discord.Member = None):
        user = ctx.author
        user_id = user.id
        db = Users()
        info = db.fetch_user(user_id)
        if info == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Registered", description="wait for autoregister to take place then use this command again", color=0xFF0000)
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar)
            return await ctx.message.reply(embed=embed)
        else:
            deposits = info["total_deposit_amount"]
            withdrawals = info["total_withdraw_amount"]
            games_played = info["total_played"]
            profit = info["total_earned"]
            games_won = info["total_won"]
            games_lost = info["total_lost"]
            spent = info["total_spent"]




        moneybag = emoji()["money"]
        statsemoji = emoji()["stats"]
        # Create embed
        embed = discord.Embed(title=f":star: | Stats for {user.name}", color=discord.Color.blue())
        embed.add_field(name=f"{moneybag} **Deposits:**", value=f"```{deposits} Tokens```", inline=False)
        embed.add_field(name=":outbox_tray: **Withdrawals:**", value=f"```{withdrawals} Credits```", inline=False)
        #embed.add_field(
            #name=":gift: Tips:",
            #value=f"Sent: **{tokens_tipped}** tokens, **{credits_tipped}** credits\n Received: **{tokens_received}** tokens, **{credits_received}** credits",
        #inline=False
    #)
        embed.add_field(name=":money_bag: Wagered", value=f"```{spent} Tokens```")
        embed.add_field(name=":money_with_wings: Won", value=f"```{profit} Credits```")
        #embed.add_field(
            #name=f"{statsemoji} Games:",
            #value=f":video_game: **Played: {games_played} games**\n:trophy: **Games Won: {games_won} games**\n",
            #inline=False
        #)
        #embed.add_field(name=":medal: Badges:", value=badge_text, inline=False)
        embed.set_footer(text="BetSync User Stats", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)


        await ctx.reply(embed=embed)

    # Store pending currency changes
    pending_currency_changes = {}

    # Confirmation View for currency change
    class ConfirmCurrencyView(discord.ui.View):
        def __init__(self, cog, ctx, current_coin, new_coin, current_points, new_points, current_rate, new_rate, new_usd_value, timeout=60):
            super().__init__(timeout=timeout)
            self.cog = cog
            self.ctx = ctx
            self.current_coin = current_coin
            self.new_coin = new_coin
            self.current_points = current_points
            self.new_points = new_points
            self.current_rate = current_rate
            self.new_rate = new_rate
            self.new_usd_value = new_usd_value
            self.message = None
            self.responded = False # Added responded flag

        @discord.ui.button(label="Confirm Change", style=discord.ButtonStyle.green, emoji="✅")
        async def confirm_button(self, button, interaction):
            # Only the command author can use this button
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("You cannot confirm someone else's currency change!", ephemeral=True)

            # Get the database
            db = Users()

            # Calculate how much of the current primary coin the user has based on points
            current_coin_amount = self.current_points * self.current_rate

            # Update database with new primary coin and points
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {
                    "$set": {
                        "primary_coin": self.new_coin,
                        "points": self.new_points,
                        f"wallet.{self.current_coin}": current_coin_amount
                    }
                }
            )

            # Clear pending change
            if self.ctx.author.id in self.cog.pending_currency_changes:
                del self.cog.pending_currency_changes[self.ctx.author.id]

            # Disable all buttons
            for child in self.children:
                child.disabled = True

            # Create success embed
            success_embed = discord.Embed(
                title="💱 Currency Changed Successfully",
                description=f"Your primary currency has been changed from **{self.current_coin}** to **{self.new_coin}**.",
                color=0x00FFAE  # Bright teal color
            )

            success_embed.add_field(
                name="New Balance",
                value=f"`{self.new_points:.2f} points` `({self.new_usd_value:.2f}$)`",
                inline=False
            )

            success_embed.add_field(
                name="Conversion Rate",
                value=f"`1 Point = {self.new_rate:.8f} {self.new_coin}`",
                inline=False
            )

            success_embed.set_footer(text="BetSync Casino • Currency Changed", icon_url=self.cog.bot.user.avatar.url)

            # Update original message and send confirmation
            await interaction.response.edit_message(embed=success_embed, view=self)
            self.responded = True # Set responded flag
            db.save(self.ctx.author.id)

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
        async def cancel_button(self, button, interaction):
            # Only the command author can use this button
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("You cannot cancel someone else's currency change!", ephemeral=True)

            # Clear pending change
            if self.ctx.author.id in self.cog.pending_currency_changes:
                del self.cog.pending_currency_changes[self.ctx.author.id]

            # Disable all buttons
            for child in self.children:
                child.disabled = True

            # Create cancellation embed
            cancel_embed = discord.Embed(
                title="❌ Currency Change Cancelled",
                description=f"Your currency change request has been cancelled.\nYour primary currency remains **{self.current_coin}**.",
                color=0xFF5555  # Soft red color
            )

            cancel_embed.set_footer(text="BetSync Casino • Operation Cancelled", icon_url=self.cog.bot.user.avatar.url)

            # Update message
            await interaction.response.edit_message(embed=cancel_embed, view=self)
            self.responded = True # Set responded flag

        async def on_timeout(self):
            # Clear pending change
            if self.ctx.author.id in self.cog.pending_currency_changes:
                del self.cog.pending_currency_changes[self.ctx.author.id]

            # Disable all buttons
            for child in self.children:
                child.disabled = True

            # Update message if it still exists
            if self.message and not self.responded: # Only show timeout if not responded
                try:
                    timeout_embed = discord.Embed(
                        title="⏱️ Currency Change Timed Out",
                        description="Your currency change request has expired.\nPlease try again if you still want to change your currency.",
                        color=0xAAAAAA  # Gray color
                    )
                    timeout_embed.set_footer(text="BetSync Casino • Request Expired", icon_url=self.cog.bot.user.avatar.url)
                    await self.message.edit(embed=timeout_embed, view=self)
                except:
                    pass

    @commands.command(aliases=["bal"])
    async def balance(self, ctx, param: str = None):
        """
        Show user balance with cryptocurrency conversions
        Usage: !bal [currency/user] - Sets currency or shows balance of mentioned user
        """
        user = ctx.author
        db = Users()

        # Check if a user was mentioned or ID provided
        mentioned_user = None
        if param:
            # Try to convert mention to a user
            try:
                # Extract user ID from mention format or use parameter directly
                user_id = int(''.join(filter(str.isdigit, param)))
                try:
                    mentioned_user = await self.bot.fetch_user(user_id)
                    user = mentioned_user  # Set user to mentioned user
                except:
                    # If not a valid user, assume it's a currency
                    pass
            except ValueError:
                # Not a user ID or mention, treat as currency
                pass

        # Fetch user info
        info = db.fetch_user(user.id)
        if not info:
            await ctx.reply(f"**{user.name} Does Not Have An Account.**")
            return

        # Currency chart from main.py
        crypto_values = {
            "BTC": 0.00000024,  # 1 point = 0.00000024 btc
            "LTC": 0.00023,     # 1 point = 0.00023 ltc
            "ETH": 0.000010,    # 1 point = 0.000010 eth
            "USDT": 0.0212,     # 1 point = 0.0212 usdt
            "SOL": 0.0001442    # 1 point = 0.0001442 sol
        }

        # Get current primary coin and points
        current_primary_coin = info.get("primary_coin", "BTC")
        points = info.get("points", 0)
        wallet = info.get("wallet", {
            "BTC": 0,
            "SOL": 0,
            "ETH": 0,
            "LTC": 0,
            "USDT": 0
        })

        # If it's not a user mention and param is specified, treat as currency
        currency = None
        if param and not mentioned_user:
            currency = param.upper()
            if currency not in crypto_values:
                await ctx.reply(f"**Invalid currency. Supported currencies: {', '.join(crypto_values.keys())}**")
                return

            # Check if currency is already the primary coin
            if currency == current_primary_coin:
                await ctx.reply(f"**{currency}** is already your primary currency!")
                return

            # Check if the user already has a pending currency change
            if ctx.author.id in self.pending_currency_changes:
                await ctx.reply("You already have a pending currency change. Please complete or cancel that request first.")
                return

            # Calculate how much of the current primary coin the user has based on points
            current_coin_amount = points * crypto_values[current_primary_coin]

            # Update wallet with current coin value
            wallet[current_primary_coin] = current_coin_amount

            # Set points based on new currency from wallet
            new_coin_amount = wallet.get(currency, 0)
            new_points = new_coin_amount / crypto_values[currency] if crypto_values[currency] > 0 else 0

            # Get live prices for USD values
            try:
                from Cogs.utils.crypto_utils import get_crypto_prices
                live_prices = get_crypto_prices()
            except ImportError:
                live_prices = {}

            # Calculate USD values for display
            new_coin_usd_price = 0
            if currency == "USDT":
                new_coin_usd_price = 1.0
            elif live_prices and currency.lower() in live_prices:
                new_coin_usd_price = live_prices[currency.lower()].get("usd", 0)

            new_usd_value = (new_points * crypto_values[currency]) * new_coin_usd_price if new_coin_usd_price else 0

            # Store pending change
            self.pending_currency_changes[ctx.author.id] = {
                "current_coin": current_primary_coin,
                "new_coin": currency,
                "current_points": points,
                "new_points": new_points
            }

            # Prepare emojis for display
            emoji_map = {
                "BTC": "<:btc:1339343483089063976>",
                "LTC": "<:ltc:1339343445675868191>", 
                "ETH": "<:eth:1340981832799485985>",
                "USDT": "<:usdt:1340981835563401217>",
                "SOL": "<:sol:1340981839497793556>"
            }

            current_emoji = emoji_map.get(current_primary_coin, "")
            new_emoji = emoji_map.get(currency, "")

            # Create confirmation embed
            confirm_embed = discord.Embed(
                title="💱 Currency Change Confirmation",
                description=f"You are about to change your primary currency from **{current_primary_coin}** to **{currency}**.",
                color=0x00FFAE
            )

            # Current balance
            confirm_embed.add_field(
                name="Current Balance",
                value=f"{current_emoji} `{points:.2f} points ({current_primary_coin})`",
                inline=False
            )

            # New balance after conversion
            confirm_embed.add_field(
                name="New Balance If Changed",
                value=f"{new_emoji} `{new_points:.2f} points ({currency})` `({new_usd_value:.2f}$)`",
                inline=False
            )

            # Conversion details
            confirm_embed.add_field(
                name="Conversion Details",
                value=(
                    f"**Current Rate:** `1 point = {crypto_values[current_primary_coin]:.8f} {current_primary_coin}`\n"
                    f"**New Rate:** `1 point = {crypto_values[currency]:.8f} {currency}`"
                ),
                inline=False
            )

            # Warning about price fluctuations
            confirm_embed.add_field(
                name="⚠️ Important Note",
                value="Cryptocurrency values fluctuate. Your point balance will change based on the conversion rate.",
                inline=False
            )

            confirm_embed.set_footer(text="BetSync Casino • Please Confirm Your Choice", icon_url=self.bot.user.avatar.url)

            # Create the confirmation view
            view = self.ConfirmCurrencyView(
                self,
                ctx,
                current_primary_coin,
                currency,
                points,
                new_points,
                crypto_values[current_primary_coin],
                crypto_values[currency],
                new_usd_value
            )

            # Send the confirmation message
            view.message = await ctx.reply(embed=confirm_embed, view=view)
            return

        # Get live prices using crypto utility
        try:
            from Cogs.utils.crypto_utils import get_crypto_prices
            live_prices = get_crypto_prices()
        except ImportError:
            # Fallback if crypto_utils doesn't exist
            live_prices = {}

        # Calculate USD value of points based on primary coin
        coin_value = crypto_values.get(current_primary_coin, 0)
        primary_coin_amount = points * coin_value

        # Get USD value of primary coin amount
        coin_usd_price = 0
        # Special case for USDT as it's a stablecoin pegged to $1
        if current_primary_coin == "USDT":
            coin_usd_price = 1.0  # 1 USDT = $1 USD
        elif live_prices and current_primary_coin.lower() in live_prices:
            coin_usd_price = live_prices[current_primary_coin.lower()].get("usd", 0)

        usd_value = primary_coin_amount * coin_usd_price if coin_usd_price else 0

        # Create embed
        money = emoji()["money"]
        embed = discord.Embed(title=f"{money} | {user.name}'s Balance", color=discord.Color.blue())

        # Prepare currency emojis
        emoji_map = {
            "BTC": "<:btc:1339343483089063976>",
            "LTC": "<:ltc:1339343445675868191>", 
            "ETH": "<:eth:1340981832799485985>",
            "USDT": "<:usdt:1340981835563401217>",
            "SOL": "<:sol:1340981839497793556>"
        }

        # Current primary coin balance and conversion
        primary_rate = crypto_values.get(current_primary_coin, 0)
        primary_value = points * primary_rate
        primary_emoji = emoji_map.get(current_primary_coin, "")

        # Main balance display - clean and minimalistic
        embed.add_field(
            name="Points",
            value=f"`{points:.2f}` `({usd_value:.2f}$)`",
            inline=False
        )

        # Currency info field - simplified
        embed.add_field(
            name="Primary Currency", 
            value=f"`{current_primary_coin} (1 Point => {primary_rate:.8f} {current_primary_coin})`",
            inline=False
        )

        embed.set_footer(text="Use !bal <currency> to change your primary currency and to check other currency points.", icon_url=self.bot.user.avatar.url)
        db.save(ctx.author.id)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["wa"]) # Added alias for convenience
    async def wallet(self, ctx, user: discord.Member = None):
        """Shows the user's full cryptocurrency wallet balances and total USD value."""
        target_user = user or ctx.author # Default to command author if no user is mentioned
        db = Users()

        info = db.fetch_user(target_user.id)
        if not info:
            # Use a more informative embed for non-registered users
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Not Found",
                description=f"**{target_user.mention}** does not have a BetSync account yet.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
            await ctx.reply(embed=embed)
            return

        # Fetch the wallet, providing defaults if it doesn't exist or is incomplete
        wallet_data = info.get("wallet", {})
        balances = {
            "BTC": wallet_data.get("BTC", 0),
            "LTC": wallet_data.get("LTC", 0),
            "ETH": wallet_data.get("ETH", 0),
            "USDT": wallet_data.get("USDT", 0),
            "SOL": wallet_data.get("SOL", 0),
            "DOGE": wallet_data.get("DOGE", 0) # Added DOGE based on calculate_total_usd
        }

        # Calculate total USD value
        total_usd = self.calculate_total_usd(info)

        # Prepare currency emojis (ensure consistency)
        emoji_map = {
            "BTC": "<:btc:1339343483089063976>",
            "LTC": "<:ltc:1339343445675868191>",
            "ETH": "<:eth:1340981832799485985>",
            "USDT": "<:usdt:1340981835563401217>",
            "SOL": "<:sol:1340981839497793556>",
            "DOGE": "<:doge:1344252518305234987>" # Placeholder emoji, replace if available
        }

        # Create enhanced embed
        embed = discord.Embed(
            title=f"{target_user.display_name}'s Wallet",
            color=discord.Color.blue() # Consistent color
        )
        # Set author to show user's avatar
        embed.set_author(name=target_user.name, icon_url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)

        # Add Total Value Field
        embed.add_field(
            name="💰 Total Wallet Value (USD)",
            value=f"**${total_usd:,.2f}**",
            inline=False
        )

        # Add a separator for clarity
        embed.add_field(name="\u200b", value="**Individual Balances**", inline=False) # Invisible separator field

        # Add individual balances
        balance_lines = []
        for coin, balance in balances.items():
            if balance > 0: # Only show currencies with a balance > 0
                coin_emoji = emoji_map.get(coin, "❓") # Default emoji if not found
                # Format balance to appropriate decimal places (e.g., 8 for crypto, 2 for USDT)
                decimal_places = 2 if coin == "USDT" else 8
                balance_lines.append(f"{coin_emoji} **{coin}**: `{balance:,.{decimal_places}f}`")

        if not balance_lines:
            embed.add_field(name="Empty Wallet", value="No cryptocurrency balances found.", inline=False)
        else:
            # Join balances into a single field value for better spacing control
            embed.add_field(name="Cryptocurrencies", value="\n".join(balance_lines), inline=False)

        # Updated footer
        embed.set_footer(text="BetSync Wallet | All values are approximate.", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)

        await ctx.reply(embed=embed)

    # Leaderboard Pagination View
    class LeaderboardView(discord.ui.View):
        def __init__(self, author_id, all_data, page_size=10, timeout=60):
            super().__init__(timeout=timeout)
            self.author_id = author_id
            self.all_data = all_data
            self.page_size = page_size
            self.current_page = 0
            self.total_pages = max(1, (len(all_data["users"]) + page_size - 1) // page_size)
            self.message = None
            self.scope = all_data.get("scope", "global")
            self.leaderboard_type = all_data.get("type", "stats")
            self.stat_type = all_data.get("stat_type", "wins")

            # Disable buttons if not needed
            self.update_buttons()

        def update_buttons(self):
            # Disable/enable prev/next buttons based on current page
            self.first_page_button.disabled = self.current_page == 0
            self.prev_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= self.total_pages - 1
            self.last_page_button.disabled = self.current_page >= self.total_pages - 1

        @discord.ui.button(label="<<", style=discord.ButtonStyle.gray, custom_id="first_page")
        async def first_page_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = 0
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label="<", style=discord.ButtonStyle.gray, custom_id="prev_page")
        async def prev_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = max(0, self.current_page - 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label=">", style=discord.ButtonStyle.gray, custom_id="next_page")
        async def next_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = min(self.total_pages - 1, self.current_page + 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label=">>", style=discord.ButtonStyle.gray, custom_id="last_page")
        async def last_page_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = self.total_pages - 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        def get_current_page_embed(self):
            # Get data for current page
            start_idx = self.current_page * self.page_size
            end_idx = min(start_idx + self.page_size, len(self.all_data["users"]))
            current_page_data = self.all_data["users"][start_idx:end_idx]

            # Create USD embed
            return self.create_usd_embed(current_page_data, start_idx)

        def create_usd_embed(self, users_data, start_idx):
            # Find user's position in the full leaderboard
            user_id = self.all_data.get("author_id")
            user_position = None
            user_amount = 0
            for i, user in enumerate(self.all_data["users"]):
                if user["id"] == user_id:
                    user_position = i + 1
                    user_amount = user["amount"]
                    break

            # Simplified description showing user's rank if available
\n"
        progress_bar += f"[{'■' * filled_bars}{' ' * empty_bars}] {int(progress * 100)}%\n"
        progress_bar += "```"

        embed.add_field(
            name="Level Progress",
            value=progress_bar,
            inline=False
        )

        # All ranks section
        all_ranks = ""
        for rank_name, rank_info in sorted_ranks:
            emoji = rank_info['emoji']
            level_req = rank_info['level_requirement']
            rakeback = rank_info['rakeback_percentage']

            # Highlight current rank
            if rank_name == current_rank_name:
                all_ranks += f"➤ {emoji} **{rank_name}** (Lv. {level_req}) - {rakeback}% rakeback\n"
            else:
                all_ranks += f"{emoji} {rank_name} (Lv. {level_req}) - {rakeback}% rakeback\n"

        embed.add_field(
            name="All Ranks",
            value=all_ranks,
            inline=False
        )

        # Set thumbnail to user avatar
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        embed.set_footer(text="BetSync Casino • Rank up by playing games", icon_url=self.bot.user.avatar.url)

        await ctx.reply(embed=embed)

    class RakebackButton(discord.ui.View):
        def __init__(self, cog, user_id, rakeback_amount):
            super().__init__(timeout=60)
            self.cog = cog
            self.user_id = user_id
            self.rakeback_amount = rakeback_amount

        @discord.ui.button(label="Claim Rakeback", style=discord.ButtonStyle.green, emoji="💰")
        async def claim_button(self, button, interaction):
            # Only the user who initiated can claim
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("You cannot claim someone else's rakeback!", ephemeral=True)

            # Process the claim
            db = Users()
            user_data = db.fetch_user(self.user_id)

            if not user_data:
                print(f"{Back.RED}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.RED}    ERROR    {Fore.WHITE}User data not found when claiming rakeback{Style.RESET_ALL}")
                return await interaction.response.send_message("Error: User data not found.", ephemeral=True)

            rakeback_tokens = user_data.get("rakeback_tokens", 0)

            if rakeback_tokens <= 0:
                print(f"{Back.YELLOW}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.YELLOW}    WARNING    {Fore.WHITE}Attempted to claim zero rakeback tokens{Style.RESET_ALL}")
                return await interaction.response.send_message("You don't have any rakeback tokens to claim!", ephemeral=True)

            # Log before claiming
            rn = datetime.datetime.now().strftime("%X")
            print(f"{Back.CYAN}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}Claiming {rakeback_tokens:.2f} rakeback tokens{Style.RESET_ALL}  {Fore.MAGENTA}rakeback_claim{Fore.WHITE}")

            # Update rakeback tokens to 0
            update_result = db.collection.update_one(
                {"discord_id": self.user_id},
                {"$set": {"rakeback_tokens": 0}}
            )

            # Add the rakeback tokens to user's tokens
            balance_result = db.update_balance(self.user_id, rakeback_tokens)

            # Log after claiming
            print(f"{Back.GREEN}  {Style.DIM}{self.user_id}{Style.RESET_ALL}{Back.RESET}{Fore.GREEN}    SUCCESS    {Fore.WHITE}Rakeback claimed: {rakeback_tokens:.2f} points | DB updates: {update_result.modified_count}, {balance_result}{Style.RESET_ALL}")

            # Disable the button
            for child in self.children:
                child.disabled = True
            await interaction.response.defer()
            message = await interaction.original_response()
            await message.edit(view=self)

            # Send success message with enhanced styling
            claim_embed = discord.Embed(
                title="💰 Rakeback Claimed Successfully",
                description=f"You have successfully claimed your rakeback rewards!",
                color=0x00FFAE
            )

            # Add field for claimed amount with styled box
            claim_embed.add_field(
                name="🎉 Claimed Amount",
                value=f"```ini\n[{rakeback_tokens:,.2f} points added to your balance]\n```",
                inline=False
            )

            # Add a field showing new balance
            new_balance = db.fetch_user(self.user_id).get('points', 0)
            claim_embed.add_field(
                name="💵 New points Balance",
                value=f"**{new_balance:,.2f} tokens**",
                inline=True
            )

            claim_embed.set_footer(text="BetSync Casino • Rakeback Rewards", icon_url=self.cog.bot.user.avatar.url)

            await interaction.followup.send(embed=claim_embed)

    @commands.command(name="rakeback", aliases=["rb"])
    async def rakeback(self, ctx, user: discord.Member = None):
        """View and claim your rakeback rewards"""
        if not user:
            user = ctx.author

        db = Users()
        user_data = db.fetch_user(user.id)

        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Registered",
                description="This user doesn't have an account yet. Please wait for auto-registration or use commands to interact with the bot.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get rakeback percentage from rank data
        with open('static_data/ranks.json', 'r') as f:
            rank_data = json.load(f)

        current_rank_requirement = user_data.get('rank', 0)
        rakeback_percentage = 0
        rank_name = "None"
        rank_emoji = ""

        # Find current rank and its rakeback percentage
        for name, info in rank_data.items():
            if info['level_requirement'] == current_rank_requirement:
                rakeback_percentage = info['rakeback_percentage']
                rank_name = name
                rank_emoji = info['emoji']
                break

        # Get accumulated rakeback tokens
        rakeback_tokens = user_data.get('rakeback_tokens', 0)

        # Format tokens with commas for better readability
        formatted_rakeback = f"{rakeback_tokens:,.2f}"

        # Create embed
        if user == ctx.author:
            title = f"💰 Rakeback Rewards"
        else:
            title = f"💰 {user.name}'s Rakeback Rewards"

        embed = discord.Embed(
            title=title,
            color=0x00FFAE,
            description=f"**Earn cashback rewards based on your betting activity**\nㅤㅤㅤ"
        )

        # Add a rank section with emoji and styled text
        embed.add_field(
            name="🏆 Current Rank",
            value=f"{rank_emoji} **{rank_name}**\nRakeback Rate: **{rakeback_percentage}%**",
            inline=True
        )

        # Add tokens section with styled text
        embed.add_field(
            name="💵 Available Rakeback",
            value=f"```ini\n[{formatted_rakeback} points]\n```",
            inline=True
        )

        # Add a spacer field to create 2 columns
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Create a progress-style display for claim eligibility
        if rakeback_tokens < 1:
            progress = min(rakeback_tokens, 1.0)
            bar_length = 10
            filled_bars = round(progress * bar_length)
            empty_bars = bar_length - filled_bars

            claim_status = (
                "🔒 **Claim Status: Locked**\n"
                f"Progress to claim: `{rakeback_tokens:.2f}/1.00`\n"
                f"```\n[{'■' * filled_bars}{' ' * empty_bars}] {int(progress * 100)}%\n```"
                "You need at least **1.00 rakeback points** to claim your rakeback rewards."
            )
        else:
            claim_status = (
                "✅ **Claim Status: Ready**\n"
                "Your rakeback points are ready to claim!\n"
                "Click the button below to add these tokens to your balance."
            )

        embed.add_field(
            name="📊 Claim Eligibility",
            value=claim_status,
            inline=False
        )

        # Add information on how rakeback works with improved formatting
        embed.add_field(
            name="ℹ️ About Rakeback",
            value=(
                "```\nRakeback is a loyalty reward system that returns a percentage of your bets.\n