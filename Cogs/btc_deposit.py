# Cogs/btc_deposit.py

import discord
from discord.ext import commands, tasks
import os
import requests
import qrcode
import io
import asyncio
import datetime
import time
import aiohttp
import json
import re
from dotenv import load_dotenv
from bitcoinlib.keys import HDKey
from bitcoinlib.networks import Network
from colorama import Fore, Style

from Cogs.utils.mongo import Users
from Cogs.utils.notifier import Notifier
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import get_crypto_price

# Load environment variables
load_dotenv()

BTC_XPUB = os.environ.get("BTC_XPUB")
DEPOSIT_WEBHOOK_URL = os.environ.get("DEPOSIT_WEBHOOK")
MONGO_URI = os.environ.get("MONGO")

# Constants
BTC_CONVERSION_RATE = 0.00000024  # 1 point = 0.00000024 BTC
BTC_SATOSHIS = 100_000_000  # 1 BTC = 100,000,000 satoshis
REQUIRED_CONFIRMATIONS = 2
MEMPOOL_API_URL = "https://mempool.space/api"  # Mempool.space Bitcoin API
CHECK_DEPOSIT_COOLDOWN = 15  # seconds
EMBED_TIMEOUT = 600  # 10 minutes in seconds

from PIL import Image, ImageDraw, ImageFont

def generate_qr_code(address: str, username: str):
    """Generates a styled QR code image with text."""
    qr_data = f"bitcoin:{address}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = qr_img.size

    try:
        title_font = ImageFont.truetype("Helvetica-Bold.ttf", 30)
        subtitle_font = ImageFont.truetype("Helvetica.ttf", 18)
        brand_font = ImageFont.truetype("Helvetica-Bold.ttf", 36)
    except IOError:
        print(f"{Fore.YELLOW}[!] Warning: Font files not found. Using default font.{Style.RESET_ALL}")
        try:
            title_font = ImageFont.truetype("arial.ttf", 30)
            subtitle_font = ImageFont.truetype("arial.ttf", 18)
            brand_font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()

    title_text = f"{username}'s Deposit Address"
    instruction_text = "Only send BITCOIN"
    brand_text = "BETSYNC"

    padding = 20
    title_bbox = title_font.getbbox(title_text)
    instruction_bbox = subtitle_font.getbbox(instruction_text)
    brand_bbox = brand_font.getbbox(brand_text)

    title_width = title_bbox[2] - title_bbox[0]
    title_height = title_bbox[3] - title_bbox[1]
    instruction_width = instruction_bbox[2] - instruction_bbox[0]
    instruction_height = instruction_bbox[3] - instruction_bbox[1]
    brand_width = brand_bbox[2] - brand_bbox[0]
    brand_height = brand_bbox[3] - brand_bbox[1]

    total_height = padding + title_height + padding // 2 + qr_height + padding // 2 + instruction_height + padding // 2 + brand_height + padding
    max_width = max(qr_width, title_width, instruction_width, brand_width)
    image_width = max_width + 2 * padding

    final_img = Image.new('RGB', (image_width, total_height), color='white')
    draw = ImageDraw.Draw(final_img)

    title_x = (image_width - title_width) // 2
    title_y = padding
    draw.text((title_x, title_y), title_text, font=title_font, fill="black")

    qr_x = (image_width - qr_width) // 2
    qr_y = title_y + title_height + padding // 2
    final_img.paste(qr_img, (qr_x, qr_y))

    instruction_x = (image_width - instruction_width) // 2
    instruction_y = qr_y + qr_height + padding // 2
    draw.text((instruction_x, instruction_y), instruction_text, font=subtitle_font, fill="black")

    brand_x = (image_width - brand_width) // 2
    brand_y = instruction_y + instruction_height + padding // 2
    draw.text((brand_x, brand_y), brand_text, font=brand_font, fill="black")

    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

class DepositView(discord.ui.View):
    def __init__(self, cog_instance, user_id: int, address: str):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.cog = cog_instance
        self.user_id = user_id
        self.address = address
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your deposit interface!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True

                timeout_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Embed Timeout",
                    description=f"Your deposit session for address `{self.address}` has timed out.\n\n"
                                f"Please run `!dep btc` again if you need to check for deposits or start a new one.",
                    color=discord.Color.red()
                )
                timeout_embed.set_footer(text="BetSync Casino")
                await self.message.edit(embed=timeout_embed, view=None, attachments=[])
            except discord.NotFound:
                print(f"{Fore.YELLOW}[!] Warning: Failed to edit timed-out deposit message for user {self.user_id} (message not found).{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Error editing timed-out deposit message for user {self.user_id}: {e}{Style.RESET_ALL}")

        if self.user_id in self.cog.active_deposit_views:
            try:
                del self.cog.active_deposit_views[self.user_id]
            except KeyError:
                pass

    @discord.ui.button(label="Check for New Deposits", style=discord.ButtonStyle.green, custom_id="check_deposit_button", emoji="🔄")
    async def check_deposit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        now = time.time()
        cooldown_key = f"{self.user_id}_check_deposit"
        last_check_time = self.cog.button_cooldowns.get(cooldown_key, 0)

        if now - last_check_time < CHECK_DEPOSIT_COOLDOWN:
            remaining = CHECK_DEPOSIT_COOLDOWN - (now - last_check_time)
            await interaction.response.send_message(f"Please wait {remaining:.1f} more seconds before checking again.", ephemeral=True)
            return

        # Check if user's primary currency is set to BTC (fetch fresh data)
        fresh_user_data = self.cog.users_db.fetch_user(self.user_id)
        if not fresh_user_data:
            await interaction.response.send_message("Error: User data not found.", ephemeral=True)
            return
            
        primary_currency = fresh_user_data.get('primary_coin', fresh_user_data.get('primary_currency', '')).upper()
        if primary_currency != 'BTC':
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Primary Currency",
                description=f"You must set your primary currency to **BTC** to claim Bitcoin deposits.\n\nCurrent primary currency: **{primary_currency or 'Not Set'}**\n\nUse the balance command to change your primary currency.",
                color=discord.Color.red()
            )
            embed.set_footer(text="BetSync Casino")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.cog.button_cooldowns[cooldown_key] = now
        await interaction.response.defer(ephemeral=True)

        try:
            status, details = await self.cog._check_for_deposits(self.user_id, self.address)

            if status == "success":
                deposits = details.get('deposits', [details])
                total_btc = sum(d['amount_crypto'] for d in deposits)

                for deposit in deposits:
                    btc_price = await get_crypto_price('bitcoin')
                    usd_value = deposit['amount_crypto'] * btc_price if btc_price else None

                    history_entry = {
                        "type": "btc_deposit",
                        "amount_crypto": deposit['amount_crypto'],
                        "currency": "BTC",
                        "usd_value": usd_value,
                        "txid": deposit['txid'],
                        "address": self.address,
                        "confirmations": deposit.get('confirmations', REQUIRED_CONFIRMATIONS),
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                    }
                    self.cog.users_db.update_history(self.user_id, history_entry)

                    if usd_value:
                        self.cog.users_db.collection.update_one(
                            {"discord_id": self.user_id},
                            {"$inc": {"total_deposit_amount_usd": usd_value}}
                        )

                if not self.message:
                    await interaction.followup.send("Error: Could not find the original deposit message to update.", ephemeral=True)
                    return

                main_embed = self.message.embeds[0]
                main_embed.title = "<:yes:1355501647538815106> | Deposit Success"
                main_embed.description = f"<:btc:1339343483089063976> **+{total_btc:,.8f} BTC** from {len(deposits)} transaction(s)"
                main_embed.clear_fields()
                main_embed.set_image(url=None)  # Remove QR code image

                for i, deposit in enumerate(deposits, 1):
                    txid = deposit['txid']
                    txid_short = txid[:10] + '...' if len(txid) > 10 else txid
                    explorer_url = f"https://mempool.space/tx/{txid}"
                    tx_value = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"

                    main_embed.add_field(
                        name=f"Transaction #{i}",
                        value=f"Amount: {deposit['amount_crypto']:,.8f} BTC\nTXID: {tx_value}",
                        inline=False
                    )

                updated_user = self.cog.users_db.fetch_user(self.user_id)
                btc_balance = updated_user.get("wallet", {}).get("BTC", "N/A") if updated_user else "N/A"
                main_embed.add_field(name="New BTC Balance", value=f"<:btc:1339343483089063976> {btc_balance:,.8f} BTC", inline=True)

                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "check_deposit_button":
                        item.disabled = True
                        item.style = discord.ButtonStyle.grey
                        item.label = "Checked"

                await self.message.edit(embed=main_embed, view=self, attachments=[])

            elif status == "pending":
                pending_amount = details.get('amount_crypto', 0)
                embed = discord.Embed(
                    title="⏳ Deposit Pending Confirmation",
                    description=(
                        f"**Address:** `{self.address}`\n"
                        f"**Amount:** {pending_amount:.8f} BTC\n"
                        f"**Confirmations:** {details['confirmations']}/{REQUIRED_CONFIRMATIONS}\n\n"
                        f"Please wait and check again when fully confirmed."
                    ),
                    color=discord.Color.orange()
                )
                embed.set_footer(text="BetSync Casino | Pending Deposit")
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif status == "no_new":
                embed = discord.Embed(
                    title="🔍 No New Deposits",
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"No new confirmed deposits found.\n\n"
                        f"Please ensure you sent BTC to the correct address."
                    ),
                    color=discord.Color.blue()
                )
                embed.set_footer(text="BetSync Casino")
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif status == "error":
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Deposit Check Error",
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"Error checking deposits:\n"
                        f"`{details['error']}`"
                    ),
                    color=discord.Color.red()
                )
                embed.set_footer(text="BetSync Casino")
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"{Fore.RED}[!] Error in check_deposit_button interaction for user {self.user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)
            except discord.InteractionResponded:
                pass

    @discord.ui.button(label="History", style=discord.ButtonStyle.grey, custom_id="deposit_history_button", emoji="📜")
    async def deposit_history_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        history_embed = await self.cog._show_deposit_history(self.user_id)
        await interaction.followup.send(embed=history_embed, ephemeral=True)

class BtcDeposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.notifier = Notifier()
        self.active_deposit_views = {}
        self.button_cooldowns = {}

        if not BTC_XPUB:
            print(f"{Fore.RED}[!] ERROR: BTC_XPUB not found in environment variables! BTC deposits will not work.{Style.RESET_ALL}")
        if not DEPOSIT_WEBHOOK_URL:
            print(f"{Fore.YELLOW}[!] WARNING: DEPOSIT_WEBHOOK_URL not found. Deposit notifications will not be sent.{Style.RESET_ALL}")

    async def _get_next_address_index(self, user_id: int) -> int:
        user_data = self.users_db.fetch_user(user_id)
        if user_data and 'btc_address_index' in user_data:
            return user_data.get('btc_address_index', -1) + 1
        else:
            return 0

    async def _generate_btc_address(self, user_id: int) -> tuple[str | None, str | None]:
        user_data = self.users_db.fetch_user(user_id)

        if user_data and user_data.get("btc_address"):
            if 'btc_address_index' not in user_data:
                print(f"{Fore.YELLOW}[!] User {user_id} has btc_address but missing btc_address_index.{Style.RESET_ALL}")
            return user_data["btc_address"], None

        if not BTC_XPUB:
            return None, "BTC_XPUB environment variable is not configured."

        try:
            highest_index_user = self.users_db.collection.find_one(
                {"btc_address_index": {"$exists": True}},
                sort=[("btc_address_index", -1)]
            )

            last_global_index = -1
            if highest_index_user and 'btc_address_index' in highest_index_user and isinstance(highest_index_user['btc_address_index'], int):
                last_global_index = highest_index_user['btc_address_index']

            next_index = last_global_index + 1
            print(f"{Fore.CYAN}[i] Generating address for user {user_id} using globally next index: {next_index} (Last highest global index found: {last_global_index}){Style.RESET_ALL}")

            if not BTC_XPUB:
                return None, "BTC_XPUB environment variable is not configured."
            print(f"{Fore.CYAN}[i] Using BTC_XPUB starting with: {BTC_XPUB[:10]}...{Style.RESET_ALL}")
            master_key = HDKey(BTC_XPUB)
            master_key.network = Network('bitcoin')

            derivation_path = f"m/0h/{next_index}"
            try:
                derived_key = master_key.subkey_for_path(derivation_path)
                address = derived_key.address()
                print(f"{Fore.GREEN}[+] Derived address using user path (Native SegWit): {derivation_path}{Style.RESET_ALL}")
            except Exception as derive_err:
                print(f"{Fore.RED}[!] Error: Derivation failed using path ({derivation_path}): {derive_err}. Ensure BTC_XPUB is compatible with this path and p2wpkh.{Style.RESET_ALL}")
                return None, f"Failed to derive address using path {derivation_path}: {derive_err}. Check XPUB compatibility."

            print(f"{Fore.CYAN}[i] Final derived info for user {user_id}: Address={address}, Path={derivation_path}, Index={next_index}{Style.RESET_ALL}")

            update_data = {
                "$set": {
                    "btc_address": address,
                    "btc_address_index": next_index
                }
            }

            if not user_data:
                result = self.users_db.collection.update_one({"discord_id": user_id}, update_data)
                if result.matched_count == 0:
                    print(f"{Fore.RED}[!] Failed to store address for user {user_id} - user document not found.{Style.RESET_ALL}")
                    return None, "User document not found to store address."
            else:
                self.users_db.collection.update_one({"discord_id": user_id}, update_data)

            print(f"{Fore.GREEN}[+] Generated BTC address {address} (Index: {next_index}) for user {user_id}{Style.RESET_ALL}")
            return address, None

        except Exception as e:
            print(f"{Fore.RED}[!] Error generating BTC address for user {user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return None, f"Failed to generate address: {e}"

    async def _check_for_deposits(self, user_id: int, address: str) -> tuple[str, dict]:
        try:
            user_data = self.users_db.fetch_user(user_id)
            if not user_data:
                print(f"{Fore.RED}[!] User data not found for user {user_id} at start of deposit check.{Style.RESET_ALL}")
                return "error", {"error": "User data not found."}

            try:
                async with aiohttp.ClientSession() as session:
                    txs_url = f"{MEMPOOL_API_URL}/address/{address}/txs"
                    async with session.get(txs_url) as response:
                        if response.status != 200:
                            print(f"{Fore.RED}[!] Mempool API Error ({response.status}) fetching transactions for {address}. Response: {await response.text()}{Style.RESET_ALL}")
                            return "error", {"error": f"API Error ({response.status}) fetching transactions."}

                        try:
                            transactions = await response.json()
                        except Exception as e:
                            print(f"{Fore.RED}[!] Error parsing transactions for {address}: {e}{Style.RESET_ALL}")
                            return "error", {"error": "Failed to parse transaction data"}

                    tip_url = f"{MEMPOOL_API_URL}/blocks/tip/height"
                    async with session.get(tip_url) as tip_response:
                        if tip_response.status != 200:
                            print(f"{Fore.RED}[!] API Error ({tip_response.status}) fetching block height.{Style.RESET_ALL}")
                            return "error", {"error": f"API Error ({tip_response.status}) fetching block height."}
                        current_block_height = int(await tip_response.text())

                if not transactions:
                    return "no_new", {}
            except Exception as e:
                transactions = []
                current_block_height = -1

            # Get processed txids from dedicated field to prevent duplicates
            processed_txids = set(user_data.get('processed_btc_txids', []))
            new_deposit_processed_in_this_check = False
            first_pending_tx = None

            for tx in transactions:
                txid = tx.get('txid')
                if not txid:
                    continue

                if txid in processed_txids:
                    continue

                status = tx.get('status', {})
                confirmed = status.get('confirmed', False)
                block_height = status.get('block_height')

                amount_received_satoshi = 0
                for vout in tx.get('vout', []):
                    if vout.get('scriptpubkey_address') == address:
                        amount_received_satoshi += vout.get('value', 0)

                print(f"{Fore.BLUE}[API Check - {address}] TX {txid} - Amount found for address: {amount_received_satoshi} satoshis.{Style.RESET_ALL}")
                if amount_received_satoshi <= 0:
                    print(f"{Fore.YELLOW}[API Check - {address}] Skipping TX {txid} - Zero or negative amount received ({amount_received_satoshi} satoshis).{Style.RESET_ALL}")
                    continue

                print(f"{Fore.BLUE}[API Check - {address}] TX {txid} - Confirmed: {confirmed}, Block Height: {block_height}{Style.RESET_ALL}")
                if not confirmed or not block_height:
                    print(f"{Fore.YELLOW}[API Check - {address}] Skipping TX {txid} - Not confirmed or no block height.{Style.RESET_ALL}")
                    if not first_pending_tx:
                        first_pending_tx = {"confirmations": 0, "txid": txid, "amount_crypto": round(amount_received_satoshi / BTC_SATOSHIS, 8)}
                    continue

                if current_block_height == -1:
                    print(f"{Fore.RED}[!] Cannot calculate confirmations for TX {txid} because current block height fetch failed.{Style.RESET_ALL}")
                    return "error", {"error": "Failed to fetch current block height for confirmation check."}

                confirmations = (current_block_height - block_height) + 1
                print(f"{Fore.BLUE}[API Check - {address}] TX {txid} - Calculated Confirmations: {confirmations} (Current: {current_block_height}, TX Block: {block_height}){Style.RESET_ALL}")

                if confirmations < REQUIRED_CONFIRMATIONS:
                    print(f"{Fore.YELLOW}[API Check - {address}] Skipping TX {txid} - Insufficient confirmations ({confirmations}/{REQUIRED_CONFIRMATIONS}).{Style.RESET_ALL}")
                    if not first_pending_tx or confirmations > first_pending_tx['confirmations']:
                        first_pending_tx = {"confirmations": confirmations, "txid": txid, "amount_crypto": round(amount_received_satoshi / BTC_SATOSHIS, 8)}
                    continue

                amount_crypto = round(amount_received_satoshi / BTC_SATOSHIS, 8)
                
                # Convert BTC to points using the conversion rate
                points_to_add = amount_crypto / BTC_CONVERSION_RATE

                balance_before_btc = user_data.get("wallet", {}).get("BTC", 0)
                balance_before_points = user_data.get("points", 0)

                # Use atomic operation to prevent duplicate processing
                # This will only update if the txid is NOT already in processed_btc_txids
                update_result_wallet = self.users_db.collection.update_one(
                    {
                        "discord_id": user_id,
                        "processed_btc_txids": {"$ne": txid}  # Only update if txid is NOT already processed
                    },
                    {
                        "$inc": {
                            "wallet.BTC": amount_crypto,
                            "points": points_to_add
                        },
                        "$addToSet": {"processed_btc_txids": txid}  # Add txid to processed list atomically
                    }
                )
                
                if not update_result_wallet or update_result_wallet.matched_count == 0:
                    print(f"{Fore.YELLOW}[!] Transaction {txid} already processed for user {user_id} or user not found. Skipping.{Style.RESET_ALL}")
                    continue # Skip this transaction - already processed
                print(f"{Fore.GREEN}[+] Updated wallet.BTC for user {user_id} by {amount_crypto:.8f} BTC and added {points_to_add:.2f} points for txid {txid}{Style.RESET_ALL}")

                history_entry = {
                    "type": "btc_deposit",
                    "amount_crypto": amount_crypto,
                    "points_credited": points_to_add,
                    "currency": "BTC",
                    "txid": txid,
                    "address": address,
                    "confirmations": confirmations,
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                }
                history_update_success = self.users_db.update_history(user_id, history_entry)
                if not history_update_success:
                    print(f"{Fore.YELLOW}[!] Failed to update history for user {user_id}, txid {txid}. Balance was updated.{Style.RESET_ALL}")

                # The txid was already added to processed_btc_txids atomically above
                await asyncio.to_thread(self.users_db.save, user_id)

                balance_after_btc = balance_before_btc + amount_crypto
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        user = None
                username = user.name if user else f"User_{user_id}"

                if DEPOSIT_WEBHOOK_URL:
                    asyncio.create_task(self.notifier.deposit_notification(
                        user_id=user_id,
                        username=username,
                        amount_crypto=amount_crypto,
                        currency="BTC",
                        points_credited=points_to_add,
                        txid=txid,
                        balance_before=balance_before_points,
                        balance_after=balance_before_points + points_to_add,
                        webhook_url=DEPOSIT_WEBHOOK_URL
                    ))

                processed_txids.add(txid)
                new_deposit_processed_in_this_check = True
                print(f"{Fore.GREEN}[+] Processed BTC deposit for user {user_id}: {amount_crypto} BTC, TXID: {txid}{Style.RESET_ALL}")

                return "success", {
                    "amount_crypto": amount_crypto,
                    "txid": txid
                }

            if new_deposit_processed_in_this_check:
                print(f"{Fore.YELLOW}[!] Check deposit loop finished unexpectedly after processing a deposit for user {user_id}.{Style.RESET_ALL}")
                return "error", {"error": "Internal processing error after deposit."}
            elif first_pending_tx:
                return "pending", first_pending_tx
            else:
                return "no_new", {}

        except Exception as e:
            print(f"{Fore.RED}[!] Error checking BTC deposits for address {address} (User: {user_id}): {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return "error", {"error": "An internal error occurred during check."}

    async def _show_deposit_history(self, user_id: int) -> discord.Embed:
        user_data = self.users_db.fetch_user(user_id)
        if not user_data:
            return discord.Embed(title="Error", description="Could not fetch user data.", color=discord.Color.red())

        history = user_data.get('history', [])
        if not isinstance(history, list):
            history = []

        btc_deposits = [entry for entry in history if entry and entry.get('type') == 'btc_deposit']
        btc_deposits.sort(key=lambda x: x.get('timestamp', '0'), reverse=True)

        embed = discord.Embed(title=f"📜 BTC Deposit History (Last {min(len(btc_deposits), 10)})", color=discord.Color.blue())

        if not btc_deposits:
            embed.description = "No BTC deposit history found."
        else:
            description = ""
            for i, entry in enumerate(btc_deposits[:10], 1):
                ts = entry.get('timestamp')
                dt_obj = None
                if ts:
                    try:
                        if ts.endswith('Z'):
                            ts = ts[:-1] + '+00:00'
                        dt_obj = datetime.datetime.fromisoformat(ts)
                    except ValueError:
                        print(f"{Fore.YELLOW}[!] Could not parse timestamp: {ts}{Style.RESET_ALL}")
                        dt_obj = None

                ts_formatted = dt_obj.strftime('%b %d, %Y %H:%M UTC') if dt_obj else "N/A"
                txid_short = entry.get('txid', 'N/A')
                if len(txid_short) > 10:
                    txid_short = txid_short[:10] + '...'

                points = entry.get('points_credited', entry.get('points', 0))
                description += f"**{i+1}.** `{entry.get('amount_crypto', 0):.8f} BTC` (+{points:,.0f} points)\n" \
                               f"   TXID: `{txid_short}`\n" \
                               f"   Date: {ts_formatted}\n\n"
            embed.description = description.strip()

        embed.set_footer(text="BetSync Casino")
        return embed

    @commands.command(name="deposit_btc", aliases=["btcdep", "btcdeposit"])
    async def deposit_btc(self, ctx, currency: str = None):
        if not currency:
            embed = discord.Embed(
                title="<:wallet:1339343483089063976> Cryptocurrency Deposits",
                description="Deposit supported cryptocurrencies to receive points",
                color=0x00FFAE
            )
            embed.add_field(
                name="Supported Cryptocurrencies",
                value=(
                    "<:btc:1339343483089063976> BTC\n"
                    "<:ltc:1339343445675868191> LTC\n"
                    "<:eth:1340981832799485985> ETH\n"
                    "<:usdt:1340981835563401217> USDT\n"
                    "<:sol:1340981839497793556> SOL"
                ),
                inline=True
            )
            embed.add_field(
                name="Conversion Rates",
                value=(
                    "1 point = 0.00000024 BTC\n"
                    "1 point = 0.00023 LTC\n"
                    "1 point = 0.000010 ETH\n"
                    "1 point = 0.0212 USDT\n"
                    "1 point = 0.0001442 SOL"
                ),
                inline=True
            )
            embed.add_field(
                name="Usage",
                value="`.dep <currency>`\nExamples: `.dep btc` or `.dep ltc`",
                inline=False
            )
            embed.set_footer(text="BetSync Casino")
            return await ctx.reply(embed=embed)

        currency = currency.lower() if currency else None
        if currency != "btc":
            # Only show BTC deposit interface if currency is explicitly "btc"
            if currency:
                return
            # Show general deposit menu if no currency specified

        user_id = ctx.author.id
        address, error = await self._generate_btc_address(user_id)

        if error:
            await ctx.reply(f"<:no:1344252518305234987> Error generating address: {error}")
            return
        if not address:
            await ctx.reply("<:no:1344252518305234987> An unknown error occurred while generating the address.")
            return

        try:
            qr_buffer = await asyncio.to_thread(generate_qr_code, address, ctx.author.name)
            qr_file = discord.File(qr_buffer, filename="btc_deposit_qr.png")
        except Exception as qr_err:
            print(f"{Fore.RED}[!] Failed to generate QR code for {address}: {qr_err}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            await ctx.reply("<:no:1344252518305234987> Failed to generate QR code image.")
            return

        embed = discord.Embed(
            title="<:btc:1339343483089063976> | Your BTC deposit address",
            description=f"{ctx.author.mention}, deposit strictly Bitcoin to the following address:",
            color=0xBFBFBF
        )
        embed.add_field(name="\u200B", value=f"```{address}```", inline=False)
        embed.add_field(name="Conversion Rate", value="`1 point = 0.00000024 BTC`", inline=False)
        embed.set_image(url="attachment://btc_deposit_qr.png")

        view = DepositView(self, user_id, address)

        msg_content = f"`{address}`"
        try:
            message = await ctx.reply(content=msg_content, embed=embed, file=qr_file, view=view)
            view.message = message
            self.active_deposit_views[user_id] = message
        except Exception as send_err:
            print(f"{Fore.RED}[!] Failed to send deposit message for user {user_id}: {send_err}{Style.RESET_ALL}")
            await ctx.reply("<:no:1344252518305234987> Failed to send deposit message. Please try again.")

def setup(bot):
    if BTC_XPUB:
        try:
            bot.add_cog(BtcDeposit(bot))
            print(f"{Fore.GREEN}[+] Loaded Cog: {Fore.GREEN}BtcDeposit{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[-] Failed to load Cog: {Fore.RED}BtcDeposit{Style.RESET_ALL} - Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"{Fore.RED}[-] Failed to load Cog: {Fore.RED}BtcDeposit{Style.RESET_ALL} (BTC_XPUB not set in .env)")