import discord
from discord_webhook import DiscordWebhook, DiscordEmbed
#from Cogs.utils.mongo import Users # Avoid circular import if possible
import aiohttp
import asyncio
import os
import datetime # Needed for timestamp
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
