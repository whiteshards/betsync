# Cogs/ltc_deposit.py

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
from bitcoinlib.networks import Network # Use network name string instead
from colorama import Fore, Style # For colored print statements

from Cogs.utils.mongo import Users
from Cogs.utils.notifier import Notifier
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import get_crypto_price

# Load environment variables
load_dotenv()

LTC_XPUB = os.environ.get("LTC_XPUB")
DEPOSIT_WEBHOOK_URL = os.environ.get("DEPOSIT_WEBHOOK")
MONGO_URI = os.environ.get("MONGO") # Needed for Users() initialization if not handled globally

# Constants
LTC_CONVERSION_RATE = 0.00023  # 1 point = 0.00023 LTC
LTC_SATOSHIS = 100_000_000 # 1 LTC = 100,000,000 satoshis
REQUIRED_CONFIRMATIONS = 2
MEMPOOL_API_URL = "https://litecoinspace.org/api" # Mempool.space Litecoin API
CHECK_DEPOSIT_COOLDOWN = 15 # seconds
EMBED_TIMEOUT = 600 # 10 minutes in seconds

from PIL import Image, ImageDraw, ImageFont

# --- Helper Functions ---

def generate_qr_code(address: str, username: str):
    """Generates a styled QR code image with text."""
    # 1. Generate base QR code
    qr_data = f"litecoin:{address}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8, # Slightly smaller box size for better fit
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = qr_img.size

    # 2. Prepare fonts and text
    try:
        # Adjust font paths if necessary relative to the workspace root
        title_font = ImageFont.truetype("Helvetica-Bold.ttf", 30)
        subtitle_font = ImageFont.truetype("Helvetica.ttf", 18)
        brand_font = ImageFont.truetype("Helvetica-Bold.ttf", 36)
    except IOError:
        print(f"{Fore.YELLOW}[!] Warning: Font files not found. Using default font.{Style.RESET_ALL}")
        # Fallback to default font if specific fonts aren't found
        try:
            title_font = ImageFont.truetype("arial.ttf", 30) # Try Arial as fallback
            subtitle_font = ImageFont.truetype("arial.ttf", 18)
            brand_font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
             title_font = ImageFont.load_default()
             subtitle_font = ImageFont.load_default()
             brand_font = ImageFont.load_default()


    title_text = f"{username}'s Deposit Address" # Changed title slightly
    instruction_text = "Only send LITECOIN" # New instruction text
    brand_text = "BETSYNC"

    # 3. Calculate image dimensions and text positions using getbbox
    padding = 20
    title_bbox = title_font.getbbox(title_text)
    instruction_bbox = subtitle_font.getbbox(instruction_text) # Use subtitle font for instruction
    brand_bbox = brand_font.getbbox(brand_text)

    title_width = title_bbox[2] - title_bbox[0]
    title_height = title_bbox[3] - title_bbox[1]
    instruction_width = instruction_bbox[2] - instruction_bbox[0]
    instruction_height = instruction_bbox[3] - instruction_bbox[1]
    brand_width = brand_bbox[2] - brand_bbox[0]
    brand_height = brand_bbox[3] - brand_bbox[1]

    # Adjust total height calculation
    total_height = padding + title_height + padding // 2 + qr_height + padding // 2 + instruction_height + padding // 2 + brand_height + padding
    max_width = max(qr_width, title_width, instruction_width, brand_width)
    image_width = max_width + 2 * padding

    # 4. Create final image canvas (white background)
    final_img = Image.new('RGB', (image_width, total_height), color='white')
    draw = ImageDraw.Draw(final_img)

    # 5. Draw elements
    # Title
    title_x = (image_width - title_width) // 2
    title_y = padding
    draw.text((title_x, title_y), title_text, font=title_font, fill="black")

    # QR Code
    qr_x = (image_width - qr_width) // 2
    qr_y = title_y + title_height + padding // 2
    final_img.paste(qr_img, (qr_x, qr_y))

    # Instruction Text
    instruction_x = (image_width - instruction_width) // 2
    instruction_y = qr_y + qr_height + padding // 2
    draw.text((instruction_x, instruction_y), instruction_text, font=subtitle_font, fill="black")

    # Brand Name
    brand_x = (image_width - brand_width) // 2
    brand_y = instruction_y + instruction_height + padding // 2 # Position below instruction
    draw.text((brand_x, brand_y), brand_text, font=brand_font, fill="black")

    # 6. Save to buffer
    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# --- Deposit View ---

class DepositView(discord.ui.View):
    def __init__(self, cog_instance, user_id: int, address: str):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.cog = cog_instance
        self.user_id = user_id
        self.address = address
        self.message = None # Will be set after sending the initial message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command initiator can interact."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your deposit interface!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        """Handle view timeout."""
        if self.message:
            try:
                # Disable buttons
                for item in self.children:
                    if isinstance(item, discord.ui.Button): # Check if it's a button
                        item.disabled = True

                # Create timeout embed
                timeout_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Embed Timeout", # Specific title
                    description=f"Your deposit session for address `{self.address}` has timed out.\n\n"
                                f"Please run `!dep ltc` again if you need to check for deposits or start a new one.",
                    color=discord.Color.red()
                )
                timeout_embed.set_footer(text="BetSync Casino")
                # Remove image and view on timeout
                await self.message.edit(embed=timeout_embed, view=None, attachments=[]) # Ensure attachments=[] is here
            except discord.NotFound:
                print(f"{Fore.YELLOW}[!] Warning: Failed to edit timed-out deposit message for user {self.user_id} (message not found).{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Error editing timed-out deposit message for user {self.user_id}: {e}{Style.RESET_ALL}")
        # Remove from active views
        if self.user_id in self.cog.active_deposit_views:
            try:
                del self.cog.active_deposit_views[self.user_id]
            except KeyError:
                 pass # Already removed, potentially by another process or race condition

    @discord.ui.button(label="Check for New Deposits", style=discord.ButtonStyle.green, custom_id="check_deposit_button", emoji="🔄")
    async def check_deposit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Button to check for new deposits."""
        now = time.time()
        cooldown_key = f"{self.user_id}_check_deposit"
        last_check_time = self.cog.button_cooldowns.get(cooldown_key, 0)

        if now - last_check_time < CHECK_DEPOSIT_COOLDOWN:
            remaining = CHECK_DEPOSIT_COOLDOWN - (now - last_check_time)
            await interaction.response.send_message(f"Please wait {remaining:.1f} more seconds before checking again.", ephemeral=True)
            return

        # Check if user's primary currency is set to LTC (fetch fresh data)
        fresh_user_data = self.cog.users_db.fetch_user(self.user_id)
        if not fresh_user_data:
            await interaction.response.send_message("Error: User data not found.", ephemeral=True)
            return
            
        primary_currency = fresh_user_data.get('primary_coin', fresh_user_data.get('primary_currency', '')).upper()
        if primary_currency != 'LTC':
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Primary Currency",
                description=f"You must set your primary currency to **LTC** to claim Litecoin deposits.\n\nCurrent primary currency: **{primary_currency or 'Not Set'}**\n\nUse the balance command to change your primary currency.",
                color=discord.Color.red()
            )
            embed.set_footer(text="BetSync Casino")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.cog.button_cooldowns[cooldown_key] = now
        # Defer response immediately before the check
        await interaction.response.defer(ephemeral=True) # Defer ephemerally for pending/no_new/error

        try:
            # Check for deposits (assuming _check_for_deposits returns status and details dict)
            # The details dict should contain 'amount_crypto', 'points_credited', 'txid', 'balance_after' on success
            status, details = await self.cog._check_for_deposits(self.user_id, self.address)

            if status == "success":
                # Handle both single and multiple deposits
                deposits = details.get('deposits', [details])  # Support both formats
                total_ltc = sum(d['amount_crypto'] for d in deposits)
                
                # LTC deposits go directly to wallet.LTC - no additional balance updates needed here
                # The _check_for_deposits method already handled the wallet update

                # Update embed
                if not self.message:
                    await interaction.followup.send("Error: Could not find the original deposit message to update.", ephemeral=True)
                    return

                main_embed = self.message.embeds[0]
                main_embed.title = "<:yes:1355501647538815106> | Deposit Success"
                total_points = sum(d.get('points_credited', 0) for d in deposits)
                main_embed.description = f"<:ltc:1339343445675868191> **+{total_ltc:,.8f} LTC** (+{total_points:,.2f} points) from {len(deposits)} transaction(s)"
                main_embed.clear_fields()
                main_embed.set_image(url=None)  # Remove QR code image

                # Show each transaction
                for i, deposit in enumerate(deposits, 1):
                    txid = deposit['txid']
                    txid_short = txid[:10] + '...' if len(txid) > 10 else txid
                    explorer_url = f"https://litecoinspace.org/tx/{txid}"
                    tx_value = f"[`{txid_short}`]({explorer_url})" if txid != 'N/A' else "N/A"
                    
                    main_embed.add_field(
                        name=f"Transaction #{i}",
                        value=f"Amount: {deposit['amount_crypto']:,.8f} LTC\nTXID: {tx_value}",
                        inline=False
                    )

                # Show new balance
                updated_user = self.cog.users_db.fetch_user(self.user_id)
                ltc_balance = updated_user.get("wallet", {}).get("LTC", "N/A") if updated_user else "N/A"
                main_embed.add_field(name="New LTC Balance", value=f"<:ltc:1339343445675868191> {ltc_balance:,.8f} LTC", inline=True)
                
                # Disable check button
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "check_deposit_button":
                        item.disabled = True
                        item.style = discord.ButtonStyle.grey
                        item.label = "Checked"

                await self.message.edit(embed=main_embed, view=self, attachments=[])

                # We don't need followup.send here as we edited the main message

            elif status == "pending":
                # Add amount to pending message
                pending_amount = details.get('amount_crypto', 0)
                embed = discord.Embed(
                    title="⏳ Deposit Pending Confirmation",
                    description=(
                        f"**Address:** `{self.address}`\n"
                        f"**Amount:** {pending_amount:.8f} LTC\n"
                        f"**Confirmations:** {details['confirmations']}/{REQUIRED_CONFIRMATIONS}\n\n"
                        f"Please wait and check again when fully confirmed."
                    ),
                    color=discord.Color.orange()
                )
                embed.set_footer(text="BetSync Casino | Pending Deposit")
                await interaction.followup.send(embed=embed, ephemeral=True) # Keep pending ephemeral

            elif status == "no_new":
                embed = discord.Embed(
                    title="🔍 No New Deposits",
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"No new confirmed deposits found.\n\n"
                        f"Please ensure you sent LTC to the correct address."
                    ),
                    color=discord.Color.blue()
                )
                embed.set_footer(text="BetSync Casino")
                await interaction.followup.send(embed=embed, ephemeral=True) # Keep no_new ephemeral

            elif status == "error":
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Deposit Check Error", # Specific title
                    description=(
                        f"**Address:** `{self.address}`\n\n"
                        f"Error checking deposits:\n"
                        f"`{details['error']}`"
                    ),
                    color=discord.Color.red()
                )
                embed.set_footer(text="BetSync Casino")
                await interaction.followup.send(embed=embed, ephemeral=True) # Keep error ephemeral

        except Exception as e:
            print(f"{Fore.RED}[!] Error in check_deposit_button interaction for user {self.user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            try:
                # Use followup since we deferred
                await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)
            except discord.InteractionResponded:
                 # If followup fails after defer, try editing original response (though less likely needed now)
                 pass # Or log this specific state

    

# --- LTC Deposit Cog ---

class LtcDeposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users_db = Users()
        self.notifier = Notifier()
        self.active_deposit_views = {} # user_id: message_object
        self.button_cooldowns = {} # key: timestamp

        if not LTC_XPUB:
            print(f"{Fore.RED}[!] ERROR: LTC_XPUB not found in environment variables! LTC deposits will not work.{Style.RESET_ALL}")
        if not DEPOSIT_WEBHOOK_URL:
            print(f"{Fore.YELLOW}[!] WARNING: DEPOSIT_WEBHOOK_URL not found. Deposit notifications will not be sent.{Style.RESET_ALL}")

        # bitcoinlib handles Litecoin network by default, no need for custom network definition
        # Just ensure we use 'litecoin' as network parameter when needed
        # We might need to convert zpub to xpub or use appropriate derivation paths.
        # For now, assuming standard derivation m/0/k might work, but needs testing.

    async def _get_next_address_index(self, user_id: int) -> int:
        """Finds the next unused address index for a user."""
        # This is a simple approach. A more robust way would be to query the max index used.
        user_data = self.users_db.fetch_user(user_id)
        if user_data and 'ltc_address_index' in user_data:
            # If index exists, assume the next one is needed for a *new* address generation request.
            # However, for deposits, we usually reuse the *last* generated address.
            # Let's refine this logic in _generate_ltc_address.
            # This helper might be better suited for finding the *absolute* next index if needed elsewhere.
            # For now, we'll manage the index within _generate_ltc_address.
            return user_data.get('ltc_address_index', -1) + 1
        else:
            # If no user data or no index, start from 0.
            # Consider potential conflicts if multiple bots/processes generate addresses.
            # A dedicated counter collection in MongoDB might be safer for high concurrency.
            return 0 # Start with index 0 for the first address

    async def _generate_ltc_address(self, user_id: int) -> tuple[str | None, str | None]:
        """Generates or retrieves a unique LTC deposit address for the user."""
        user_data = self.users_db.fetch_user(user_id)

        # 1. Check if address already exists
        if user_data and user_data.get("ltc_address"):
            # Ensure the index is also stored, add if missing
            if 'ltc_address_index' not in user_data:
                 # Attempt to find index based on address (complex, avoid if possible)
                 # Or assume it's the latest if we can't find it easily.
                 # For simplicity, let's just return the address. If index is missing, generation might fail later.
                 print(f"{Fore.YELLOW}[!] User {user_id} has ltc_address but missing ltc_address_index.{Style.RESET_ALL}")
            return user_data["ltc_address"], None # Return existing address, no error

        # 2. Generate new address if none exists
        if not LTC_XPUB:
            return None, "LTC_XPUB environment variable is not configured."

        try:
            # --- Determine the globally next available index ---
            # Find the user with the highest ltc_address_index
            highest_index_user = self.users_db.collection.find_one(
                {"ltc_address_index": {"$exists": True}}, # Ensure the field exists
                sort=[("ltc_address_index", -1)] # Sort descending by index
            )

            last_global_index = -1
            if highest_index_user and 'ltc_address_index' in highest_index_user and isinstance(highest_index_user['ltc_address_index'], int):
                last_global_index = highest_index_user['ltc_address_index']

            next_index = last_global_index + 1
            print(f"{Fore.CYAN}[i] Generating address for user {user_id} using globally next index: {next_index} (Last highest global index found: {last_global_index}){Style.RESET_ALL}")
            # --- End index determination ---

            # Load the xpub key
            # Parse key first without network to avoid conflict with zpub format
            if not LTC_XPUB: # Redundant check, but safe
                 return None, "LTC_XPUB environment variable is not configured."
            print(f"{Fore.CYAN}[i] Using LTC_XPUB starting with: {LTC_XPUB[:10]}...{Style.RESET_ALL}") # Log partial key
            master_key = HDKey(LTC_XPUB)
            # Convert to Litecoin context using proper Network object
            from bitcoinlib.networks import Network
            master_key.network = Network('litecoin')

            # Use the user's specified derivation path (m/0'/index) for Native SegWit (p2wpkh)
            # Ensure the index is hardened as specified (0')
            derivation_path = f"m/0'/{next_index}" # Using user's path m/0'/i
            try:
                # Use Litecoin network context
                derived_key = master_key.subkey_for_path(derivation_path)
                address = derived_key.address() # Network already specified in HDKey
                print(f"{Fore.GREEN}[+] Derived address using user path (Native SegWit): {derivation_path}{Style.RESET_ALL}")
            except Exception as derive_err:
                 # If derivation fails, log error and fail.
                 print(f"{Fore.RED}[!] Error: Derivation failed using path ({derivation_path}): {derive_err}. Ensure LTC_XPUB is compatible with this path and p2wpkh.{Style.RESET_ALL}")
                 return None, f"Failed to derive address using path {derivation_path}: {derive_err}. Check XPUB/ZPUB compatibility."

            # Log the final derived details before saving
            print(f"{Fore.CYAN}[i] Final derived info for user {user_id}: Address={address}, Path={derivation_path}, Index={next_index}{Style.RESET_ALL}")

            # 3. Store the new address and index in the user's document
            update_data = {
                "$set": {
                    "ltc_address": address,
                    "ltc_address_index": next_index
                }
            }
            # Use upsert=True in case the user document was created but lacks these fields
            # Ensure user exists first (should be handled by on_command)
            if not user_data:
                 # This case should ideally be prevented by the bot's user registration logic
                 print(f"{Fore.RED}[!] Error: Attempted to generate address for non-existent user {user_id}. Registering user first.{Style.RESET_ALL}")
                 # You might need to call the registration logic here or handle it upstream
                 # For now, let's assume the user exists and update fails gracefully if not.
                 result = self.users_db.collection.update_one({"discord_id": user_id}, update_data)
                 if result.matched_count == 0:
                      print(f"{Fore.RED}[!] Failed to store address for user {user_id} - user document not found.{Style.RESET_ALL}")
                      return None, "User document not found to store address."
            else:
                 self.users_db.collection.update_one({"discord_id": user_id}, update_data)

            print(f"{Fore.GREEN}[+] Generated LTC address {address} (Index: {next_index}) for user {user_id}{Style.RESET_ALL}")
            return address, None

        except Exception as e:
            print(f"{Fore.RED}[!] Error generating LTC address for user {user_id}: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            # Consider logging the error to the webhook as well
            return None, f"Failed to generate address: {e}"

    async def _check_for_deposits(self, user_id: int, address: str) -> tuple[str, dict]:
        """Checks Blockstream API for confirmed deposits to the address."""
        try:
            # Fetch user data at the beginning
            user_data = self.users_db.fetch_user(user_id)
            if not user_data:
                 print(f"{Fore.RED}[!] User data not found for user {user_id} at start of deposit check.{Style.RESET_ALL}")
                 return "error", {"error": "User data not found."}

            try:
                async with aiohttp.ClientSession() as session:
                    # Get address transactions from Mempool.space
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

                    # Get current block height
                    tip_url = f"{MEMPOOL_API_URL}/blocks/tip/height"
                    async with session.get(tip_url) as tip_response:
                        if tip_response.status != 200:
                            print(f"{Fore.RED}[!] API Error ({tip_response.status}) fetching block height.{Style.RESET_ALL}")
                            return "error", {"error": f"API Error ({tip_response.status}) fetching block height."}
                        current_block_height = int(await tip_response.text())

                if not transactions:
                    return "no_new", {}
            except Exception as e:
                # Catch errors specifically from the API interaction block
                print(f"{Fore.RED}[!] Error during API check for {address}: {e}{Style.RESET_ALL}")
                # Assign default values to prevent errors later if API failed before assignment
                transactions = []
                current_block_height = -1 # Indicate failure to get block height
                # We might want to return an error here instead of continuing,
                # but let's try continuing to the main loop for now, it will likely return "no_new" or "error" later.
                # Returning error immediately might be cleaner:
                # return "error", {"error": f"API interaction failed: {str(e)}"}

            # --- Start of main processing logic ---
            # (The user_data variable is already fetched at the start of the function)

            # Get processed txids from dedicated field to prevent duplicates
            processed_txids = set(user_data.get('processed_ltc_txids', []))
            new_deposit_processed_in_this_check = False
            first_pending_tx = None

            # (The rest of the processing loop follows from here...)
            # Note: The original lines 469-475 fetching user_data again are now redundant and removed implicitly by this diff.

            # --- Re-fetch user_data inside the loop? No, use the one from the start ---
            # user_data = self.users_db.fetch_user(user_id) # Redundant
            # if not user_data: ... # Redundant check

            # --- Ensure history is a list? Already done at the start ---
            # history = user_data.get('history', []) # Redundant
            # if not isinstance(history, list): ... # Redundant check

            # --- processed_txids? Already defined ---
            # processed_txids = {entry.get('txid') ...} # Redundant

            # --- Reset flags ---
            # new_deposit_processed_in_this_check = False # Already defined
            # first_pending_tx = None # Already defined

            for tx in transactions:
                txid = tx.get('txid')
                if not txid: continue # Skip if no txid

                if txid in processed_txids:
                    continue # Skip already processed transactions

                # Check confirmation status
                status = tx.get('status', {})
                confirmed = status.get('confirmed', False)
                block_height = status.get('block_height')

                # Check outputs to find amount sent to our address *before* confirmation check
                amount_received_satoshi = 0
                for vout in tx.get('vout', []):
                    if vout.get('scriptpubkey_address') == address:
                        amount_received_satoshi += vout.get('value', 0)

                print(f"{Fore.BLUE}[API Check - {address}] TX {txid} - Amount found for address: {amount_received_satoshi} satoshis.{Style.RESET_ALL}")
                # Only proceed if this tx actually sent funds to the user's address
                if amount_received_satoshi <= 0:
                    print(f"{Fore.YELLOW}[API Check - {address}] Skipping TX {txid} - Zero or negative amount received ({amount_received_satoshi} satoshis).{Style.RESET_ALL}")
                    continue

                # Now check confirmations
                print(f"{Fore.BLUE}[API Check - {address}] TX {txid} - Confirmed: {confirmed}, Block Height: {block_height}{Style.RESET_ALL}")
                if not confirmed or not block_height:
                    print(f"{Fore.YELLOW}[API Check - {address}] Skipping TX {txid} - Not confirmed or no block height.{Style.RESET_ALL}")
                    # Store the first unconfirmed relevant transaction found
                    if not first_pending_tx:
                         first_pending_tx = {"confirmations": 0, "txid": txid, "amount_crypto": round(amount_received_satoshi / LTC_SATOSHIS, 8)} # Add amount for pending message
                    continue # Skip unconfirmed transactions for processing

                # Handle potential API failure where block height wasn't fetched
                if current_block_height == -1:
                    print(f"{Fore.RED}[!] Cannot calculate confirmations for TX {txid} because current block height fetch failed.{Style.RESET_ALL}")
                    return "error", {"error": "Failed to fetch current block height for confirmation check."}

                confirmations = (current_block_height - block_height) + 1
                print(f"{Fore.BLUE}[API Check - {address}] TX {txid} - Calculated Confirmations: {confirmations} (Current: {current_block_height}, TX Block: {block_height}){Style.RESET_ALL}")

                if confirmations < REQUIRED_CONFIRMATIONS:
                     print(f"{Fore.YELLOW}[API Check - {address}] Skipping TX {txid} - Insufficient confirmations ({confirmations}/{REQUIRED_CONFIRMATIONS}).{Style.RESET_ALL}")
                     # Store the first under-confirmed relevant transaction found
                     if not first_pending_tx or confirmations > first_pending_tx['confirmations']: # Show highest confirmation count among pending
                          first_pending_tx = {"confirmations": confirmations, "txid": txid, "amount_crypto": round(amount_received_satoshi / LTC_SATOSHIS, 8)} # Add amount for pending message
                     continue # Skip transactions without enough confirmations


                # --- Confirmed deposit found! ---
                amount_crypto = round(amount_received_satoshi / LTC_SATOSHIS, 8)
                
                # Convert LTC to points using the conversion rate
                points_to_add = amount_crypto / LTC_CONVERSION_RATE

                # --- Database Update with Atomic Duplicate Prevention ---
                balance_before_ltc = user_data.get("wallet", {}).get("LTC", 0) # Get LTC balance before
                balance_before_points = user_data.get("points", 0)

                # Use atomic operation to prevent duplicate processing
                # This will only update if the txid is NOT already in processed_ltc_txids
                update_result_wallet = self.users_db.collection.update_one(
                    {
                        "discord_id": user_id,
                        "processed_ltc_txids": {"$ne": txid}  # Only update if txid is NOT already processed
                    },
                    {
                        "$inc": {
                            "wallet.LTC": amount_crypto,
                            "points": points_to_add
                        },
                        "$addToSet": {"processed_ltc_txids": txid}  # Add txid to processed list atomically
                    }
                )
                
                if not update_result_wallet or update_result_wallet.matched_count == 0:
                     print(f"{Fore.YELLOW}[!] Transaction {txid} already processed for user {user_id} or user not found. Skipping.{Style.RESET_ALL}")
                     continue # Skip this transaction - already processed
                print(f"{Fore.GREEN}[+] Updated wallet.LTC for user {user_id} by {amount_crypto:.8f} LTC and added {points_to_add:.2f} points for txid {txid}{Style.RESET_ALL}")

                # 2. Increment total deposit amount (USD value for stats tracking)
                ltc_price = await get_crypto_price('litecoin')
                usd_value = amount_crypto * ltc_price if ltc_price else 0
                if usd_value > 0:
                    self.users_db.collection.update_one(
                        {"discord_id": user_id},
                        {"$inc": {"total_deposit_amount_usd": usd_value}}
                    )

                # 3. Add to history (crypto amount and points)
                ltc_price = await get_crypto_price('litecoin')
                usd_value = amount_crypto * ltc_price if ltc_price else None
                
                history_entry = {
                    "type": "ltc_deposit",
                    "amount_crypto": amount_crypto,
                    "points_credited": points_to_add,
                    "currency": "LTC",
                    "usd_value": usd_value,
                    "txid": txid,
                    "address": address,
                    "confirmations": confirmations,
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                }
                history_update_success = self.users_db.update_history(user_id, history_entry)
                if not history_update_success:
                     print(f"{Fore.YELLOW}[!] Failed to update history for user {user_id}, txid {txid}. Balance was updated.{Style.RESET_ALL}")
                     # Balance is already updated, log this inconsistency

                # The txid was already added to processed_ltc_txids atomically above
                # Skip wallet save to prevent duplicate history entries
                # The LTC wallet balance was already updated directly via MongoDB

                # --- Notification ---
                balance_after_ltc = balance_before_ltc + amount_crypto
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id) # Get user object for name
                    except discord.NotFound:
                         user = None # Handle case where user might have left
                username = user.name if user else f"User_{user_id}"

                if DEPOSIT_WEBHOOK_URL:
                    # Run notification in background task
                    asyncio.create_task(self.notifier.deposit_notification(
                        user_id=user_id,
                        username=username,
                        amount_crypto=amount_crypto,
                        currency="LTC",
                        points_credited=points_to_add,
                        txid=txid,
                        balance_before=balance_before_points,
                        balance_after=balance_before_points + points_to_add,
                        webhook_url=DEPOSIT_WEBHOOK_URL
                    ))

                processed_txids.add(txid) # Mark as processed for this check cycle
                new_deposit_processed_in_this_check = True
                print(f"{Fore.GREEN}[+] Processed LTC deposit for user {user_id}: {amount_crypto} LTC (direct wallet deposit), TXID: {txid}{Style.RESET_ALL}")

                # Return success details for the *first* successful deposit found in this check
                # Include points_credited for the success embed
                return "success", {
                    "amount_crypto": amount_crypto,
                    "points_credited": points_to_add,
                    "txid": txid
                }

            # --- Loop finished ---
            if new_deposit_processed_in_this_check:
                 # Should have returned success earlier, this indicates an issue
                 print(f"{Fore.YELLOW}[!] Check deposit loop finished unexpectedly after processing a deposit for user {user_id}.{Style.RESET_ALL}")
                 return "error", {"error": "Internal processing error after deposit."}
            elif first_pending_tx:
                 # No fully confirmed deposits, but found pending ones
                 return "pending", first_pending_tx
            else:
                 # No relevant transactions found (new, pending, or confirmed)
                 return "no_new", {}


        except Exception as e:
            print(f"{Fore.RED}[!] Error checking LTC deposits for address {address} (User: {user_id}): {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return "error", {"error": "An internal error occurred during check."} # Don't expose raw error to user

    async def _show_deposit_history(self, user_id: int) -> discord.Embed:
        """Fetches and formats the user's LTC deposit history."""
        user_data = self.users_db.fetch_user(user_id)
        if not user_data:
            return discord.Embed(title="Error", description="Could not fetch user data.", color=discord.Color.red())

        history = user_data.get('history', [])
        # Ensure history is a list
        if not isinstance(history, list):
             history = []

        ltc_deposits = [entry for entry in history if entry and entry.get('type') == 'ltc_deposit']
        ltc_deposits.sort(key=lambda x: x.get('timestamp', '0'), reverse=True) # Sort newest first, handle missing timestamp

        embed = discord.Embed(title=f"📜 LTC Deposit History (Last {min(len(ltc_deposits), 10)})", color=discord.Color.blue())

        if not ltc_deposits:
            embed.description = "No LTC deposit history found."
        else:
            description = ""
            for i, entry in enumerate(ltc_deposits[:10]):
                ts = entry.get('timestamp')
                dt_obj = None
                if ts:
                    try:
                        # Handle potential 'Z' suffix for UTC timezone
                        if ts.endswith('Z'):
                            ts = ts[:-1] + '+00:00'
                        dt_obj = datetime.datetime.fromisoformat(ts)
                    except ValueError:
                         print(f"{Fore.YELLOW}[!] Could not parse timestamp: {ts}{Style.RESET_ALL}")
                         dt_obj = None # Failed to parse

                # Format timestamp for display (e.g., Mar 29, 2025 14:45 UTC)
                ts_formatted = dt_obj.strftime('%b %d, %Y %H:%M UTC') if dt_obj else "N/A"
                txid_short = entry.get('txid', 'N/A')
                if len(txid_short) > 10:
                     txid_short = txid_short[:10] + '...'


                # For LTC deposits, show the LTC amount instead of points since LTC goes directly to wallet
                ltc_amount = entry.get('amount_crypto', 0)
                description += f"**{i+1}.** `{ltc_amount:.8f} LTC` (direct wallet deposit)\n" \
                               f"   TXID: `{txid_short}`\n" \
                               f"   Date: {ts_formatted}\n\n" # Add extra newline for spacing
            embed.description = description.strip() # Remove trailing newline

        embed.set_footer(text="BetSync Casino")
        return embed


    @commands.command(name="deposit_ltc", aliases=["ltcdep", "ltcdeposit"])
    async def deposit_ltc(self, ctx, currency: str = None):
        """Handles cryptocurrency deposits"""
        if not currency:
            # Show usage embed if no currency specified
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
                value="`.ltcdep`\nExample: `.ltcdep`",
                inline=False
            )
            embed.set_footer(text="BetSync Casino")
            return await ctx.reply(embed=embed)

        currency = currency.lower()
        if currency != "ltc":
            return  # Do nothing for non-LTC currencies

        user_id = ctx.author.id

        # Removed check for active deposit view to allow generating a new one.
        address, error = await self._generate_ltc_address(user_id)

        if error:
            await ctx.reply(f"<:no:1344252518305234987> Error generating address: {error}")
            return
        if not address:
             await ctx.reply("<:no:1344252518305234987> An unknown error occurred while generating the address.")
             return

        # Generate styled QR Code in thread
        try:
            qr_buffer = await asyncio.to_thread(generate_qr_code, address, ctx.author.name) # Pass address and username
            qr_file = discord.File(qr_buffer, filename="ltc_deposit_qr.png")
        except Exception as qr_err:
             print(f"{Fore.RED}[!] Failed to generate QR code for {address}: {qr_err}{Style.RESET_ALL}")
             import traceback
             traceback.print_exc() # Print full traceback for debugging
             await ctx.reply("<:no:1344252518305234987> Failed to generate QR code image.")
             return


        # Create Minimal Embed
        embed = discord.Embed(
            title="<:ltc:1339343445675868191> | Your LTC deposit address", # Updated title
            description=f"{ctx.author.mention}, deposit strictly Litecoin to the following address:",
            color=0xBFBFBF # Neutral grey color
        )
        # Add address in a code block field for easy copying
        embed.add_field(name="\u200B", value=f"```{address}```", inline=False) # \u200B is a zero-width space for an empty field name
        embed.add_field(name="Conversion Rate", value="`1 point = 0.00023 LTC`", inline=False)
        embed.set_image(url="attachment://ltc_deposit_qr.png")
        # Removed footer and timestamp for minimalism
        # embed.set_footer(text="BetSync Casino") # Optional: Add back if needed
        # embed.timestamp = datetime.datetime.utcnow()

        # Create View
        view = DepositView(self, user_id, address)

        # Send message (Only the address in the content for easy copying)
        msg_content = f"`{address}`"
        try:
            message = await ctx.reply(content=msg_content, embed=embed, file=qr_file, view=view)
            # Store active view and message
            view.message = message
            self.active_deposit_views[user_id] = message # Store message object keyed by user_id
        except Exception as send_err:
             print(f"{Fore.RED}[!] Failed to send deposit message for user {user_id}: {send_err}{Style.RESET_ALL}")
             await ctx.reply("<:no:1344252518305234987> Failed to send deposit message. Please try again.")


def setup(bot):
    # Check if LTC_XPUB is set before adding the cog
    if LTC_XPUB:
        try:
            bot.add_cog(LtcDeposit(bot))
            print(f"{Fore.GREEN}[+] Loaded Cog: {Fore.GREEN}LtcDeposit{Style.RESET_ALL}")
        except Exception as e:
             print(f"{Fore.RED}[-] Failed to load Cog: {Fore.RED}LtcDeposit{Style.RESET_ALL} - Error: {e}")
             import traceback
             traceback.print_exc()
    else:
        print(f"{Fore.RED}[-] Failed to load Cog: {Fore.RED}LtcDeposit{Style.RESET_ALL} (LTC_XPUB not set in .env)")