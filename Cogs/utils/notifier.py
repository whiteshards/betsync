import discord
from discord_webhook import DiscordWebhook, DiscordEmbed
#from Cogs.utils.mongo import Users # Avoid circular import if possible
# import aiohttp # No longer needed for this function
import asyncio
import os
import datetime # Needed for timestamp
import json # For formatting user data
from dotenv import load_dotenv

load_dotenv() # Load environment variables

class Notifier:
    """
    Utility class for sending notifications via Discord webhooks
    """

    #@staticmethod # Keep methods as instance methods if they might need self later
    async def bet_event(self, webhook_url, user_id, bet_amount):
        """
        Send a bet event notification to a webhook

        Parameters:
        - webhook_url: Discord webhook URL
        - user_id: Discord user ID
        - bet_amount: Amount bet in the transaction
        """
        from Cogs.utils.mongo import Users # Import locally to potentially avoid circular issues
        if not webhook_url:
            return False

        try:
            userd = Users()
            resp = userd.fetch_user(user_id=user_id)
            if not resp: # Handle case where user might not be found
                 print(f"Notifier: User {user_id} not found for bet_event.")
                 return False

            current_balance = resp.get("points", 0)
            primary_currency = resp.get("primary_coin", "N/A")
            wallet = resp.get("wallet", {})
            coin_balance = wallet.get(primary_currency, 0) # Use .get for safety

            # Create webhook
            webhook = DiscordWebhook(url=webhook_url, rate_limit_retry=True)

            # Create embed
            embed = DiscordEmbed(
                title="🎮 New Bet Placed",
                description="A user has placed a new bet in BetSync Casino",
                color=0x00FFAE
            )

            # User details field
            embed.add_embed_field(
                name="👤 User Details",
                value=(
                    f"**User:** <@{user_id}>\n"
                    f"**ID:** `{user_id}`"
                ),
                inline=False
            )

            # Bet and wallet details field
            embed.add_embed_field(
                name="💰 Bet Details",
                value=(
                    f"**Bet Amount:** {float(bet_amount):,.2f} points\n" # Ensure float conversion
                    f"**Balance Before:** {float(current_balance + bet_amount):,.2f} points\n" # Approx balance before
                    f"**Balance After:** {float(current_balance):,.2f} points ({coin_balance:.8f} {primary_currency})"
                ),
                inline=False
            )

            embed.set_footer(text="BetSync Casino Notification System")
            embed.set_timestamp() # Add timestamp

            # Add embed to webhook
            webhook.add_embed(embed)

            # Send webhook (async)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)
            # Check response status if needed
            return True

        except Exception as e:
            print(f"Error sending bet_event webhook notification: {e}")
            return False

    async def server_profit_update(self, server_id, server_name, profit_loss_amount, new_wallet_balance, currency):
        """
        Send a server profit update notification to a webhook

        Parameters:
        - server_id: Discord server ID
        - server_name: Name of the server
        - profit_loss_amount: The amount of profit or loss (+/-)
        - new_wallet_balance: The new wallet balance for the specific currency
        - currency: The currency type (e.g., 'BTC', 'ETH')
        """
        webhook_url = os.environ.get("PROFIT_WEBHOOK_URL")
        if not webhook_url:
            print("Error: PROFIT_WEBHOOK_URL environment variable not set.")
            return False

        try:
            # Create webhook
            webhook = DiscordWebhook(url=webhook_url, rate_limit_retry=True)

            # Determine color and title based on profit/loss
            if profit_loss_amount >= 0:
                color = 0x00FF00  # Green for profit
                title = "📈 Server Profit Update"
                change_indicator = "+"
            else:
                color = 0xFF0000  # Red for loss
                title = "📉 Server Loss Update"
                change_indicator = "" # Amount already includes negative sign

            # Create embed
            embed = DiscordEmbed(
                title=title,
                description=f"Profit/Loss recorded for server: **{server_name}**",
                color=color
            )

            # Server details field
            embed.add_embed_field(
                name="🏢 Server Details",
                value=(
                    f"**Name:** {server_name}\n"
                    f"**ID:** `{server_id}`"
                ),
                inline=False
            )

            # Profit/Loss and Wallet details field
            embed.add_embed_field(
                name="📊 Update Details",
                value=(
                    f"**Change:** {change_indicator}{profit_loss_amount:.8f} {currency}\n"
                    f"**New {currency} Balance:** {new_wallet_balance:.8f} {currency}"
                ),
                inline=False
            )

            embed.set_footer(text="BetSync Casino Server Profit Notification")
            embed.set_timestamp() # Add timestamp

            # Add embed to webhook
            webhook.add_embed(embed)

            # Send webhook (async)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)
            # Check response status if needed
            return True

        except Exception as e:
            print(f"Error sending server profit webhook notification: {e}")
            return False

    async def deposit_notification(self, user_id, username, amount_crypto, currency, points_credited, txid, balance_before, balance_after, webhook_url):
        """
        Sends a notification about a successful crypto deposit.

        Parameters:
        - user_id: Discord user ID
        - username: Discord username
        - amount_crypto: Amount deposited in crypto (e.g., 0.01 LTC)
        - currency: The crypto currency ticker (e.g., 'LTC')
        - points_credited: Amount credited in points/tokens
        - txid: Transaction ID of the deposit
        - balance_before: User's point balance before the deposit
        - balance_after: User's point balance after the deposit
        - webhook_url: The specific webhook URL for deposit notifications
        """
        if not webhook_url:
            print("Error: Deposit webhook URL not provided to deposit_notification.")
            return False

        try:
            webhook = DiscordWebhook(url=webhook_url, rate_limit_retry=True)

            embed = DiscordEmbed(
                title=f"✅ New {currency} Deposit Received",
                description=f"A deposit has been confirmed and credited.",
                color=0x00AEEF # Blue color for deposits
            )

            embed.add_embed_field(
                name="👤 User",
                value=f"{username} (`{user_id}`)",
                inline=False
            )

            embed.add_embed_field(
                name="💰 Deposit Details",
                value=(
                    f"**Amount:** {amount_crypto:.8f} {currency}\n"
                    f"**Points Credited:** {points_credited:,.2f}\n"
                    f"**TXID:** `{txid}`"
                ),
                inline=False
            )

            embed.add_embed_field(
                name="⚖️ Balance Update",
                value=(
                    f"**Before:** {balance_before:,.2f} points\n"
                    f"**After:** {balance_after:,.2f} points"
                ),
                inline=False
            )

            # Add link to block explorer (using Blockstream for LTC)
            if currency == "LTC":
                 explorer_url = f"https://blockstream.info/ltc/tx/{txid}"
                 embed.add_embed_field(name="🔗 Explorer Link", value=f"[View on Blockstream]({explorer_url})", inline=False)
            # Add other explorers if needed

            embed.set_footer(text="BetSync Casino Deposit System")
            embed.set_timestamp() # Add timestamp

            webhook.add_embed(embed)

            # Send webhook asynchronously
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)
            # Optionally check response.status_code
            return True

        except Exception as e:
            print(f"Error sending deposit webhook notification for user {user_id}, txid {txid}: {e}")
            return False

    async def send_registration_notification(self, user: discord.User | discord.Member, user_data: dict, timestamp: datetime.datetime, ctx, guild: discord.Guild):
        """
        Sends a notification when a new user registers.

        Parameters:
        - user: The discord.User or discord.Member object.
        - user_data: Dictionary containing the user's database record.
        - timestamp: The datetime object of the registration.
        - ctx: The command context. Can be None if registration is not from a command.
        - guild: The discord.Guild object where registration occurred.
        """
        webhook_url = os.getenv("REGISTER_WEBHOOK")
        if not webhook_url:
            print("Error: REGISTER_WEBHOOK environment variable not set.")
            return False

        try:
            # Format user data for embed - use json.dumps for readability
            try:
                # Attempt to serialize, converting non-serializable types to strings
                user_data_serializable = json.loads(json.dumps(user_data, default=str))
                user_data_str = json.dumps(user_data_serializable, indent=2)

                if len(user_data_str) > 1000: # Embed field value limit is 1024
                    user_data_str = user_data_str[:1000] + "\n... (truncated)"
            except Exception as json_e:
                print(f"Error formatting user_data for registration webhook: {json_e}")
                user_data_str = str(user_data) # Fallback to simple string conversion
                if len(user_data_str) > 1000:
                     user_data_str = user_data_str[:1000] + "\n... (truncated)"


            # Use DiscordEmbed from discord_webhook
            embed = DiscordEmbed(
                title="🎉 New User Registered",
                description=f"User {user.mention} (`{user.id}`) has registered.",
                color=0x00FF00 # Green color
            )

            embed.add_embed_field(name="👤 User", value=f"{user.name}#{user.discriminator}", inline=True)
            embed.add_embed_field(name="🏢 Guild", value=f"{guild.name} (`{guild.id}`)", inline=True)

            # Handle cases where ctx might not have a command (e.g., auto-registration)
            command_name = "N/A (Auto-Register?)"
            if ctx and ctx.command:
                command_name = f"`{ctx.command.qualified_name}`"
            embed.add_embed_field(name="⌨️ Command Used", value=command_name, inline=False)

            embed.add_embed_field(name="📊 Database Record", value=f"```json\n{user_data_str}\n```", inline=False)

            embed.set_footer(text="BetSync Registration Notification")
            embed.set_timestamp(timestamp) # Set timestamp using discord_webhook method
            # embed.set_thumbnail(url=user.display_avatar.url) # Optional: Add user avatar

            # Use discord_webhook library
            webhook = DiscordWebhook(url=webhook_url, username='BetSync Registration', rate_limit_retry=True)
            webhook.add_embed(embed)

            # Send webhook asynchronously using run_in_executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)

            # discord_webhook raises exceptions on failure, which are caught below.
            # We can check response status codes if needed, but basic success is assumed if no exception.
            # Example check:
            # if response and response.status_code >= 400: # Check if response exists before accessing status_code
            #     print(f"Error sending registration webhook: Status {response.status_code}, Content: {response.content}")
            #     return False

            return True

        # discord_webhook library might raise different exceptions,
        # but the generic Exception catch below should handle most network/API errors.
        # Specific exceptions from discord_webhook (like ValueError for bad URL) could be caught if needed.
        except Exception as e:
            print(f"Unexpected error sending registration webhook notification for user {user.id}: {e.__class__.__name__} - {e}")
            return False
