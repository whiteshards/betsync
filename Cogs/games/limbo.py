import discord
import random
import asyncio
import time
import io
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class LimboGame:
    def __init__(self, cog, ctx, bet_amount, target_multiplier, user_id, rolls=None):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.target_multiplier = target_multiplier
        self.user_id = user_id
        self.tokens_used = 0
        #self.credits_used = 0
        self.running = False
        self.message = None
        self.total_profit = 0
        self.total_bets = 0
        self.history = []
        self.current_multiplier = 0
        self.roll_mode = "auto" if rolls is None else "fixed"
        self.rolls_remaining = rolls

    async def start_game(self):
        try:
            self.running = True
            db = Users()


            # Check if we should do fixed or auto mode
            if self.roll_mode == "fixed":
                # For fixed rolls, run all simulations at once without animation
                await self.run_fixed_mode_game(db)
            else:
                # Auto mode with normal animations
                await self.run_auto_mode_game(db)

        except Exception as e:
            print(f"Error in Limbo game: {e}")
            self.running = False

            # Clean up the game from ongoing_games
            if self.user_id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.user_id]

    async def run_fixed_mode_game(self, db):
        """Run fixed number of rolls without animation"""
        server_db = Servers()
        server_data = server_db.fetch_server(self.ctx.guild.id)
        original_rolls = self.rolls_remaining

        # Create initial embed to show we're calculating
        loading_embed = discord.Embed(
            title="🎮 Limbo Game",
            description=f"Running {original_rolls} rolls at {self.target_multiplier}x multiplier...",
            color=0x2B2D31
        )
        loading_embed.set_footer(text="BetSync Casino • Limbo", icon_url=self.ctx.bot.user.avatar.url)

        self.message = await self.ctx.reply(embed=loading_embed)

        # Process all the rolls at once
        wins = 0
        losses = 0
        win_entries = []
        loss_entries = []
        server_win_entries = []
        server_loss_entries = []

        current_timestamp = int(time.time())
        # First roll is already paid for in process_bet_amount
        # For subsequent rolls, calculate additional funds needed
        total_funds_needed = self.bet_amount * (self.rolls_remaining -1) if self.rolls_remaining > 1 else 0
        user_data = db.fetch_user(self.user_id)
        available_funds = user_data['points']


        if self.rolls_remaining > 1 and available_funds < total_funds_needed:
            # Calculate max rolls including the first paid roll
            max_rolls = 1 + int(available_funds / self.bet_amount)
            if max_rolls <=1:
                insufficient_embed = self.create_embed()
                insufficient_embed.title = "<:no:1344252518305234987> | Game Over - Insufficient Funds"
                insufficient_embed.description = f"You don't have enough points to place even a single bet of {self.bet_amount}."
                insufficient_embed.color = 0xFF0000
                self.message = await self.ctx.reply(embed=insufficient_embed)
                self.running = False

                # Clean up the game from ongoing_games
                if self.user_id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.user_id]
                return

            self.rolls_remaining = max_rolls

            insufficient_embed = discord.Embed(
                title="⚠️ | Insufficient Funds for All Rolls",
                description=f"You don't have enough funds for {original_rolls} rolls. Running {max_rolls} rolls instead.",
                color=0xFFA500
            )
            await self.message.edit(embed=insufficient_embed)
            await asyncio.sleep(2)  # Give user time to see the message

        # For the first bet, use the already deducted amount
        first_bet_tokens = self.tokens_used
        #first_bet_credits = self.credits_used

        # For remaining rolls, calculate additional funds needed
        remaining_rolls = self.rolls_remaining - 1  # Subtract 1 for the already deducted first bet
        if remaining_rolls > 0:
            additional_tokens_used = min(user_data['points'], self.bet_amount * remaining_rolls)
            #additional_credits_used = min(user_data['credits'], self.bet_amount * remaining_rolls - additional_tokens_used)

            # Update balances for additional rolls
            if additional_tokens_used > 0:
                db.update_balance(self.user_id, -additional_tokens_used)


            # Add to the already used amounts
            tokens_used = first_bet_tokens + additional_tokens_used
            #credits_used = first_bet_credits + additional_credits_used
        else:
            # Only one roll, so just use the amounts already deducted
            tokens_used = first_bet_tokens
            #credits_used = first_bet_credits

        # Keep track of the total funds used
        self.tokens_used = tokens_used
        #self.credits_used = credits_used
        remaining_funds = tokens_used 

        # Process all rolls
        last_roll_multiplier = 1.00
        last_roll_won = False
        all_rolls = []  # Store all results to display in history

        for i in range(self.rolls_remaining):
            # Check if we have enough funds for this roll
            if remaining_funds < self.bet_amount:
                # Stop simulation if we run out of funds
                break

            # Roll the multiplier (with 15% house edge)
            # The formula: rolled_mult = 1.0 / (1.0 - R) where R is [0, 0.85)
            r = random.random() * 0.85
            rolled_multiplier = 1.0 / (1.0 - r)
            rounded_multiplier = round(rolled_multiplier, 2)  # Round to 2 decimal places

            # Determine if user won
            won = rounded_multiplier >= self.target_multiplier
            all_rolls.append((rounded_multiplier, won))

            # Save the last roll for display
            last_roll_multiplier = rounded_multiplier
            last_roll_won = won

            # Update total stats
            self.total_bets += 1
            self.current_multiplier = rounded_multiplier

            # Deduct bet amount from remaining funds
            remaining_funds -= self.bet_amount

            # Calculate winnings
            if won:
                wins += 1
                winnings = self.bet_amount * self.target_multiplier
                self.total_profit += winnings - self.bet_amount

                # Add winnings to remaining funds
                remaining_funds += winnings

                # Add to win history
                win_entry = {
                    "type": "win",
                    "game": "limbo",
                    "amount": winnings,
                    "bet": self.bet_amount,
                    "multiplier": self.target_multiplier,
                    "rolled_multiplier": rounded_multiplier,
                    "timestamp": current_timestamp
                }
                win_entries.append(win_entry)

            else:
                losses += 1
                self.total_profit -= self.bet_amount

                # Add to loss history
                loss_entry = {
                    "type": "loss",
                    "game": "limbo",
                    "amount": self.bet_amount,
                    "bet": self.bet_amount,
                    "multiplier": 0,
                    "target_multiplier": self.target_multiplier,
                    "rolled_multiplier": rounded_multiplier,
                    "timestamp": current_timestamp
                }
                loss_entries.append(loss_entry)

        # Bulk update database
        # Credit user with total winnings
        total_winnings = (self.bet_amount * self.total_bets) + self.total_profit
        if total_winnings > 0:
            db.update_balance(self.user_id, total_winnings)



            # Calculate server profit/loss
            server_profit = losses * self.bet_amount - wins * (self.bet_amount * self.target_multiplier - self.bet_amount)
            server_db.update_server_profit(self.ctx, self.ctx.guild.id, server_profit, game="limbo")

        # Now display the final result with the last roll
        embed = self.create_embed()
        file = await self.generate_multiplier_image(last_roll_multiplier, last_roll_won)
        embed.set_image(url="attachment://limbo_result.png")

        # Create results summary embed field
        embed.add_field(
            name="Fixed Rolls Summary", 
            value=f"`Total Rolls: {self.rolls_remaining}`\n`Wins: {wins} Losses: {losses}`", 
            inline=False
        )

        await self.message.edit(embed=embed, file=file, view=LimboControlView(self, show_cashout=False))
        self.running = False

        # Clean up the game from ongoing_games
        if self.user_id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.user_id]



    async def run_auto_mode_game(self, db):
        """Run the game in auto mode with animations"""
        try:
            # Create initial embed
            embed = self.create_embed()
            file = await self.generate_multiplier_image(1.00, False)
            embed.set_image(url="attachment://limbo_result.png")

            self.message = await self.ctx.reply(embed=embed, file=file, view=LimboControlView(self))

            # Start betting loop (first bet already deducted)
            is_first_bet = True

            while self.running:
                # Only check balance after the first bet (first bet was handled by currency_helper)
                if not is_first_bet:
                    # Deduct bet amount for subsequent bets
                    user_data = db.fetch_user(self.user_id)
                    tokens_balance = user_data['points']
                    #credits_balance = user_data['credits']

                    # Determine which currency to use
                    tokens_used = 0
                    #credits_used = 0

                    # Auto determine what to use
                    if self.bet_amount <= tokens_balance:
                        tokens_used = self.bet_amount

                    else:
                        # Not enough funds to continue
                        embed = self.create_embed()
                        embed.title = "<:no:1344252518305234987> | Game Over - Insufficient Funds"
                        embed.description = f"You don't have enough funds to continue betting {self.bet_amount}.\nGame stopped."
                        embed.color = 0xFF0000
                        # Keep using the existing rolled multiplier image in the embed
                        #embed.set_image(url="attachment://limbo_result.png")
                        await self.message.edit(embed=embed, view=None)
                        self.running = False
                        break

                    # Update balances
                    if tokens_used > 0:
                        db.update_balance(self.user_id, tokens_balance - tokens_used)

                else:
                    # Use the tokens/credits that were already deducted
                    tokens_used = self.tokens_used
                    #credits_used = self.credits_used
                    is_first_bet = False  # Mark first bet as processed

                # Roll the multiplier (with 15% house edge)
                # The formula: rolled_mult = 1.0 / (1.0 - R) where R is [0, 0.85)
                r = random.random() * 0.85
                rolled_multiplier = 1.0 / (1.0 - r)
                rounded_multiplier = round(rolled_multiplier, 2)  # Round to 2 decimal places

                # Determine if user won
                won = rounded_multiplier >= self.target_multiplier

                # Update history
                self.history.insert(0, (rounded_multiplier, won))
                if len(self.history) > 10:
                    self.history.pop()

                # Update total stats
                self.total_bets += 1
                self.current_multiplier = rounded_multiplier

                # Calculate winnings
                if won:
                    winnings = self.bet_amount * self.target_multiplier
                    self.total_profit += winnings - self.bet_amount

                    # Credit the user with winnings
                    db.update_balance(self.user_id, winnings)

                    # Add to win history
                    win_entry = {
                        "type": "win",
                        "game": "limbo",
                        "amount": winnings,
                        "bet": self.bet_amount,
                        "multiplier": self.target_multiplier,
                        "rolled_multiplier": rounded_multiplier,
                        "timestamp": int(time.time())
                    }
                    #win_entries.append(win_entry) # This is auto mode, so no win_entries list

                    # Update server history
                    server_db = Servers()


                    # Update server profit (user won)
                    loss = winnings - self.bet_amount
                    server_db.update_server_profit(self.ctx, self.ctx.guild.id, -loss)
                else:
                    self.total_profit -= self.bet_amount

                    # Add to loss history
                    loss_entry = {
                        "type": "loss",
                        "game": "limbo",
                        "amount": self.bet_amount,
                        "bet": self.bet_amount,
                        "multiplier": 0,
                        "target_multiplier": self.target_multiplier,
                        "rolled_multiplier": rounded_multiplier,
                        "timestamp": int(time.time())
                    }
                    #loss_entries.append(loss_entry) # This is auto mode, so no loss_entries list

                    # Update server history
                    server_db = Servers()
                    server_data = server_db.fetch_server(self.ctx.guild.id)

                    if server_data:


                        # Update server profit (user lost)
                        server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="limbo")



                # Update display
                embed = self.create_embed()
                file = await self.generate_multiplier_image(rounded_multiplier, won)
                embed.set_image(url="attachment://limbo_result.png")

                await self.message.edit(embed=embed, file=file, view=LimboControlView(self))

                # Wait before next roll
                await asyncio.sleep(1.0)  # Normal speed for auto mode

        except Exception as e:
            print(f"Error in Limbo game: {e}")
            self.running = False

            # Clean up the game from ongoing_games
            if self.user_id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.user_id]

    def create_embed(self):
        """Create a minimalist embed displaying the game status"""
        if self.total_bets == 0:
            # Initial embed (simplified)
            embed = discord.Embed(
                title="Limbo Game",
                description="Game starting...",
                color=0x2B2D31 # Dark grey
            )
            embed.add_field(
                name="Setup",
                value=f"**Target Multiplier**: `{self.target_multiplier:.2f}x`\n**Bet Per Roll**: `{self.bet_amount}`",
                inline=False
            )
            embed.set_footer(text="BetSync Casino • Limbo", icon_url=self.ctx.bot.user.avatar.url)
            return embed

        # Regular game embed
        # Determine color based on profit/loss
        embed_color = 0x00FF00 if self.total_profit >= 0 else 0xFF0000 # Green for profit, Red for loss
        emoji = "<:yes:1355501647538815106>" if self.total_profit >= 0 else "<:no:1344252518305234987>"
        embed = discord.Embed(
            title=f"{emoji} | Limbo Game",
            description=(
                f"**Target Multiplier**: `{self.target_multiplier:.2f}x`\n"
                f"**Bet Amount**: `{self.bet_amount}`\n"
                f"**Rolled**: `{self.current_multiplier:.2f}x`"
            ),
            color=embed_color
        )

        embed.add_field(
            name="Stats",
            value=(
                f"**Total Bets**: `{self.total_bets}`\n"
                f"**Total Profit/Loss**: `{self.total_profit:,.2f}`" # Added comma formatting for profit
            ),
            inline=False
        )

        # Add history (simplified)
        if self.history:
            # Show only the multipliers, newest first
            history_text = "\n".join([f"`{mult:.2f}x`" for mult, won in self.history])
            embed.add_field(name="Results", value=history_text, inline=False)

        embed.set_footer(text="BetSync Casino • Limbo", icon_url=self.ctx.bot.user.avatar.url)
        return embed

    async def generate_multiplier_image(self, multiplier, won):
        """Generate an image showing the multiplier in BetRush style"""
        # Create a new image with dark background
        width, height = 600, 300
        background_color = (45, 60, 75)  # Dark blue-grey background

        img = Image.new('RGB', (width, height), background_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        try:
            title_font = ImageFont.truetype("roboto.ttf", 24)
            multiplier_font = ImageFont.truetype("roboto.ttf", 80)
            small_font = ImageFont.truetype("roboto.ttf", 18)
        except:
            title_font = ImageFont.load_default()
            multiplier_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Colors
        white_color = (255, 255, 255)
        grey_color = (150, 150, 150)

        # Determine multiplier color based on value and win/loss
        if multiplier >= 10.0:
            multiplier_color = (79, 172, 254)  # Blue for high multipliers
        elif multiplier >= 2.0:
            multiplier_color = (79, 172, 254)  # Blue for medium multipliers
        else:
            multiplier_color = (255, 165, 0)  # Orange for low multipliers

        # Draw "BetSync" watermark in top left
        draw.text((20, 20), "BetSync", font=title_font, fill=grey_color)

        # Draw "Target: X.XXx" in top right
        target_text = f"Target: {self.target_multiplier:.2f}x"
        target_bbox = draw.textbbox((0, 0), target_text, font=title_font)
        target_width = target_bbox[2] - target_bbox[0]
        draw.text((width - target_width - 20, 20), target_text, font=title_font, fill=grey_color)

        # Draw "CRASHED AT" text
        crashed_text = "CRASHED AT"
        crashed_bbox = draw.textbbox((0, 0), crashed_text, font=small_font)
        crashed_width = crashed_bbox[2] - crashed_bbox[0]
        draw.text(((width - crashed_width) // 2, 70), crashed_text, font=small_font, fill=grey_color)

        # Draw the main multiplier
        multiplier_text = f"{multiplier:.2f}x"
        multiplier_bbox = draw.textbbox((0, 0), multiplier_text, font=multiplier_font)
        multiplier_width = multiplier_bbox[2] - multiplier_bbox[0]
        multiplier_height = multiplier_bbox[3] - multiplier_bbox[1]

        # Center the multiplier text
        multiplier_x = (width - multiplier_width) // 2
        multiplier_y = (height - multiplier_height) // 2 - 10
        draw.text((multiplier_x, multiplier_y), multiplier_text, font=multiplier_font, fill=multiplier_color)

        # Draw progress bar
        bar_width = 400
        bar_height = 8
        bar_x = (width - bar_width) // 2
        bar_y = height - 60

        # Background bar (dark)
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], 
                      fill=(30, 40, 50))

        # Calculate progress based on multiplier vs target
        if self.target_multiplier > 0:
            progress = min(multiplier / self.target_multiplier, 1.0)
        else:
            progress = 0.5

        progress_width = int(bar_width * progress)

        # Progress bar (colored)
        if progress_width > 0:
            draw.rectangle([bar_x, bar_y, bar_x + progress_width, bar_y + bar_height], 
                          fill=multiplier_color)

        # Draw circle indicator on progress bar
        circle_x = bar_x + progress_width
        circle_y = bar_y + bar_height // 2
        circle_radius = 8
        draw.ellipse([circle_x - circle_radius, circle_y - circle_radius,
                     circle_x + circle_radius, circle_y + circle_radius], 
                    fill=white_color)

        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        return discord.File(img_bytes, filename="limbo_result.png")

    def stop_game(self):
        """Stop the game"""
        self.running = False


class LimboControlView(discord.ui.View):
    def __init__(self, game, show_cashout=True):
        super().__init__(timeout=None)
        self.game = game

        # Only add cashout button if needed
        if show_cashout:
            self.add_item(discord.ui.Button(
                label="Cash Out", 
                style=discord.ButtonStyle.success, 
                emoji="💰", 
                custom_id="cash_out_button",
                row=0
            ))
            self.children[0].callback = self.cash_out

    async def cash_out(self, interaction: discord.Interaction):
        if interaction.user.id != self.game.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        try:
            # Stop the game
            self.game.stop_game()

            # Disable buttons
            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(view=self)

            # Send final message
            final_embed = discord.Embed(
                title="💰 Limbo Game Ended",
                description=f"You cashed out with a total profit/loss of **{self.game.total_profit:.2f}**!",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=final_embed)

            # Remove from ongoing games
            if self.game.user_id in self.game.cog.ongoing_games:
                del self.game.cog.ongoing_games[self.game.user_id]

        except Exception as e:
            print(f"Error in cash out button: {e}")
            await interaction.followup.send("There was an error processing your cash out. The game has been stopped.", ephemeral=True)
            if self.game.user_id in self.game.cog.ongoing_games:
                del self.game.cog.ongoing_games[self.game.user_id]


class LimboCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["l", "crash", "cr"])
    async def limbo(self, ctx, bet_amount: str = None, target_multiplier: str = None, rolls_or_currency: str = None):
        """Play Limbo/Crash - choose a target multiplier and win if the roll is higher!"""
        if not bet_amount or not target_multiplier:
            embed = discord.Embed(
                title="🎮 How to Play Limbo/Crash",
                description=(
                    "**Limbo/Crash** is a game where you set a target multiplier. If the rolled number is higher than or equal to your target, you win!\n\n"
                    "**Usage:** `!limbo <bet_amount> <target_multiplier> [rolls]` or `!crash <bet_amount> <target_multiplier> [rolls]`\n"
                    "**Example:** `!limbo 100 1.5` or `!crash 50 2.75 10` or `!limbo 100 2 auto`\n\n"
                    "- **Lower target multipliers are easier to win but pay less**\n"
                    "- **Higher target multipliers are harder to win but pay more**\n"
                    "- **Minimum target multiplier is 1.01x**\n"
                    "- **You can specify number of rolls (up to 200) or 'auto' mode**\n"
                    "- **In auto mode, the game will continue until you cash out or run out of funds**\n"
                    "- **In fixed mode, results will be shown immediately**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if user already has an active game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Processing Limbo Game...",
            description="Please wait while we process your request...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process target multiplier
        try:
            target_multiplier_value = float(target_multiplier)

            # Validate multiplier range
            if target_multiplier_value < 1.01:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Multiplier",
                    description="Target multiplier must be at least 1.01x.",
                    color=0xFF0000
                )
                await loading_message.edit(embed=embed)
                return

            # Round to 2 decimal places
            target_multiplier_value = round(target_multiplier_value, 2)

        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Multiplier",
                description="Please enter a valid multiplier (e.g., 1.5, 2.0, etc.).",
                color=0xFF0000
            )
            await loading_message.edit(embed=embed)
            return

        # Determine if rolls_or_currency is specifying rolls or currency
        rolls = 1  # Default to one roll if no mode specified

        # Check if rolls_or_currency parameter exists
        if rolls_or_currency:
            if rolls_or_currency.lower() == "auto":
                rolls = None  # Auto mode
            elif rolls_or_currency.lower() in ['token', 'tokens', 'credit', 'credits']:
                # This is actually currency_type
                currency_type = "points"
            else:
                # Try to parse as number of rolls
                try:
                    rolls = int(rolls_or_currency)
                    if rolls <= 0:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Invalid Rolls",
                            description="Number of rolls must be greater than 0.",
                            color=0xFF0000
                        )
                        await loading_message.edit(embed=embed)
                        return
                    elif rolls > 200:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Too Many Rolls",
                            description="Maximum number of rolls is 200.",
                            color=0xFF0000
                        )
                        await loading_message.edit(embed=embed)
                        return
                except ValueError:
                    # Not a valid number, treat as currency type
                    rolls = 1
                    currency_type = "points"

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        try:
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            # Successful bet processing - extract relevant information
            tokens_used = bet_info.get("tokens_used", 0)
            #credits_used = bet_info.get("credits_used", 0)
            bet_amount_value = bet_info.get("total_bet_amount", 0)
        except Exception as e:
            print(f"Error processing bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {str(e)}")

        # Create a new game instance
        await loading_message.delete()
        game = LimboGame(self, ctx, bet_amount_value, target_multiplier_value, ctx.author.id, rolls)
        game.tokens_used = tokens_used
        #game.credits_used = credits_used

        # Store the game in ongoing games
        self.ongoing_games[ctx.author.id] = game

        # Start the game
        await game.start_game()


def setup(bot):
    bot.add_cog(LimboCog(bot))