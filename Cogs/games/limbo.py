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
        self.credits_used = 0
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

            # Update stats for first bet
            db.collection.update_one(
                {"discord_id": self.user_id},
                {"$inc": {"total_played": 1, "total_spent": self.bet_amount}}
            )

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
        total_funds_needed = self.bet_amount * original_rolls
        user_data = db.fetch_user(self.user_id)
        available_funds = user_data['tokens'] + user_data['credits']

        if available_funds < total_funds_needed:
            max_rolls = int(available_funds / self.bet_amount)
            if max_rolls <= 0:
                insufficient_embed = self.create_embed()
                insufficient_embed.title = "<:no:1344252518305234987> | Game Over - Insufficient Funds"
                insufficient_embed.description = f"You don't have enough funds to place even a single bet of {self.bet_amount}."
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

        # Calculate how much to deduct from tokens vs credits
        tokens_used = min(user_data['tokens'], self.bet_amount * self.rolls_remaining)
        credits_used = min(user_data['credits'], self.bet_amount * self.rolls_remaining - tokens_used)

        # Update balances
        if tokens_used > 0:
            db.update_balance(self.user_id, user_data['tokens'] - tokens_used, "tokens")

        if credits_used > 0:
            db.update_balance(self.user_id, user_data['credits'] - credits_used, "credits")

        # Keep track of the total funds used
        self.tokens_used = tokens_used
        self.credits_used = credits_used
        remaining_funds = tokens_used + credits_used

        # Process all rolls
        last_roll_multiplier = 1.00
        last_roll_won = False
        all_rolls = []  # Store all results to display in history

        for i in range(self.rolls_remaining):
            # Check if we have enough funds for this roll
            if remaining_funds < self.bet_amount:
                # Stop simulation if we run out of funds
                break

            # Roll the multiplier (with 4% house edge)
            # The formula: rolled_mult = 1.0 / (1.0 - R) where R is [0, 0.96)
            r = random.random() * 0.96
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
                win_entries.append({
                    "type": "win",
                    "game": "limbo",
                    "bet": self.bet_amount,
                    "amount": winnings,
                    "multiplier": self.target_multiplier,
                    "timestamp": current_timestamp + i
                })

                if server_data:
                    server_win_entries.append({
                        "type": "win",
                        "game": "limbo",
                        "user_id": self.user_id,
                        "user_name": self.ctx.author.name,
                        "bet": self.bet_amount,
                        "amount": winnings,
                        "multiplier": self.target_multiplier,
                        "timestamp": current_timestamp + i
                    })
            else:
                losses += 1
                self.total_profit -= self.bet_amount

                # Add to loss history
                loss_entries.append({
                    "type": "loss",
                    "game": "limbo",
                    "bet": self.bet_amount,
                    "amount": self.bet_amount,
                    "timestamp": current_timestamp + i
                })

                if server_data:
                    server_loss_entries.append({
                        "type": "loss",
                        "game": "limbo",
                        "user_id": self.user_id,
                        "user_name": self.ctx.author.name,
                        "bet": self.bet_amount,
                        "timestamp": current_timestamp + i
                    })

        # Update history from newest to oldest (last 10)
        self.history = all_rolls[:10] if len(all_rolls) <= 10 else all_rolls[-10:]
        self.history.reverse()  # Make most recent first

        # Bulk update database
        # Credit user with total winnings
        total_winnings = wins * self.bet_amount * self.target_multiplier
        if total_winnings > 0:
            db.update_balance(self.user_id, total_winnings, "credits", "$inc")

        # Update user history and stats
        if win_entries:
            db.collection.update_one(
                {"discord_id": self.user_id},
                {"$push": {"history": {"$each": win_entries, "$slice": -100}}}
            )

        if loss_entries:
            db.collection.update_one(
                {"discord_id": self.user_id},
                {"$push": {"history": {"$each": loss_entries, "$slice": -100}}}
            )

        # Update user stats with win/loss counts
        db.collection.update_one(
            {"discord_id": self.user_id},
            {"$inc": {
                "total_won": wins,
                "total_lost": losses,
                "total_earned": total_winnings
            }}
        )

        # Update server history and profit
        if server_data:
            if server_win_entries:
                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": server_win_entries, "$slice": -100}}}
                )

            if server_loss_entries:
                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": server_loss_entries, "$slice": -100}}}
                )

            # Calculate server profit/loss
            server_profit = losses * self.bet_amount - wins * (self.bet_amount * self.target_multiplier - self.bet_amount)
            server_db.update_server_profit(self.ctx.guild.id, server_profit)

        # Now display the final result with the last roll
        embed = self.create_embed()
        file = await self.generate_multiplier_image(last_roll_multiplier, last_roll_won)
        embed.set_image(url="attachment://limbo_result.png")

        # Create results summary embed field
        embed.add_field(
            name="Fixed Rolls Summary", 
            value=f"Total Rolls: **{self.rolls_remaining}**\nWins: **{wins}**\nLosses: **{losses}**\nWin Rate: **{(wins/self.rolls_remaining)*100:.1f}%**", 
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

            # Start betting loop
            while self.running:
                # Deduct bet amount
                user_data = db.fetch_user(self.user_id)
                tokens_balance = user_data['tokens']
                credits_balance = user_data['credits']

                # Determine which currency to use
                tokens_used = 0
                credits_used = 0

                # Auto determine what to use
                if self.bet_amount <= tokens_balance:
                    tokens_used = self.bet_amount
                elif self.bet_amount <= credits_balance:
                    credits_used = self.bet_amount
                elif self.bet_amount <= tokens_balance + credits_balance:
                    # Use all tokens and some credits
                    tokens_used = tokens_balance
                    credits_used = self.bet_amount - tokens_balance
                else:
                    # Not enough funds to continue
                    embed = self.create_embed()
                    embed.title = "<:no:1344252518305234987> | Game Over - Insufficient Funds"
                    embed.description = f"You don't have enough funds to continue betting {self.bet_amount}.\nGame stopped."
                    embed.color = 0xFF0000
                    # Keep using the existing rolled multiplier image in the embed
                    embed.set_image(url="attachment://limbo_result.png")
                    await self.message.edit(embed=embed, view=None)
                    self.running = False
                    break

                # Update balances
                if tokens_used > 0:
                    db.update_balance(self.user_id, tokens_balance - tokens_used, "tokens")

                if credits_used > 0:
                    db.update_balance(self.user_id, credits_balance - credits_used, "credits")

                # Roll the multiplier (with 4% house edge)
                # The formula: rolled_mult = 1.0 / (1.0 - R) where R is [0, 0.96)
                r = random.random() * 0.96
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
                    db.update_balance(self.user_id, winnings, "credits", "$inc")

                    # Add to win history
                    win_entry = {
                        "type": "win",
                        "game": "limbo",
                        "bet": self.bet_amount,
                        "amount": winnings,
                        "multiplier": self.target_multiplier,
                        "timestamp": int(time.time())
                    }
                    db.collection.update_one(
                        {"discord_id": self.user_id},
                        {"$push": {"history": {"$each": [win_entry], "$slice": -100}}}
                    )

                    # Update server history
                    server_db = Servers()
                    server_data = server_db.fetch_server(self.ctx.guild.id)

                    if server_data:
                        server_win_entry = {
                            "type": "win",
                            "game": "limbo",
                            "user_id": self.user_id,
                            "user_name": self.ctx.author.name,
                            "bet": self.bet_amount,
                            "amount": winnings,
                            "multiplier": self.target_multiplier,
                            "timestamp": int(time.time())
                        }
                        server_db.collection.update_one(
                            {"server_id": self.ctx.guild.id},
                            {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
                        )

                    # Update user stats
                    db.collection.update_one(
                        {"discord_id": self.user_id},
                        {"$inc": {"total_won": 1, "total_earned": winnings}}
                    )

                    # Update server profit (user won)
                    loss = winnings - self.bet_amount
                    server_db.update_server_profit(self.ctx.guild.id, -loss)
                else:
                    self.total_profit -= self.bet_amount

                    # Add to loss history
                    loss_entry = {
                        "type": "loss",
                        "game": "limbo",
                        "bet": self.bet_amount,
                        "amount": self.bet_amount,
                        "timestamp": int(time.time())
                    }
                    db.collection.update_one(
                        {"discord_id": self.user_id},
                        {"$push": {"history": {"$each": [loss_entry], "$slice": -100}}}
                    )

                    # Update server history
                    server_db = Servers()
                    server_data = server_db.fetch_server(self.ctx.guild.id)

                    if server_data:
                        server_loss_entry = {
                            "type": "loss",
                            "game": "limbo",
                            "user_id": self.user_id,
                            "user_name": self.ctx.author.name,
                            "bet": self.bet_amount,
                            "timestamp": int(time.time())
                        }
                        server_db.collection.update_one(
                            {"server_id": self.ctx.guild.id},
                            {"$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}}}
                        )

                        # Update server profit (user lost)
                        server_db.update_server_profit(self.ctx.guild.id, self.bet_amount)

                    # Update user stats
                    db.collection.update_one(
                        {"discord_id": self.user_id},
                        {"$inc": {"total_lost": 1}}
                    )

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
        """Create an embed displaying the game status"""
        if self.total_bets == 0:
            # Initial embed
            game_mode_text = "Auto-betting mode" if self.roll_mode == "auto" else f"Fixed {self.rolls_remaining} rolls mode"
            embed = discord.Embed(
                title="🎮 Limbo Game",
                description=f"Target Multiplier: **{self.target_multiplier:.2f}x**\nBet Amount: **{self.bet_amount}**\nMode: **{game_mode_text}**",
                color=0x2B2D31
            )
            embed.add_field(name="Status", value="Game starting...", inline=False)
            embed.set_footer(text="BetSync Casino • Limbo", icon_url=self.ctx.bot.user.avatar.url)
            return embed

        # Regular game embed
        if self.total_profit >= 0:
            # Profit (green)
            embed = discord.Embed(
                title="🎮 Limbo Game",
                description=f"Target Multiplier: **{self.target_multiplier:.2f}x**\nBet Amount: **{self.bet_amount}**\nRolled: **{self.current_multiplier:.2f}x**",
                color=0x00FF00
            )
        else:
            # Loss (red)
            embed = discord.Embed(
                title="🎮 Limbo Game",
                description=f"Target Multiplier: **{self.target_multiplier:.2f}x**\nBet Amount: **{self.bet_amount}**\nRolled: **{self.current_multiplier:.2f}x**",
                color=0xFF0000
            )

        embed.add_field(
            name="Stats",
            value=f"Total Bets: **{self.total_bets}**\nTotal Profit/Loss: **{self.total_profit:.2f}**",
            inline=False
        )

        # Add history
        if self.history:
            history_text = ""
            for i, (mult, won) in enumerate(self.history):
                emoji_prefix = "✅" if won else "❌"
                history_text += f"{emoji_prefix} {mult:.2f}x\n"
            embed.add_field(name="History (Last 10)", value=history_text, inline=False)

        embed.set_footer(text="BetSync Casino • Limbo", icon_url=self.ctx.bot.user.avatar.url)
        return embed

    async def generate_multiplier_image(self, multiplier, won):
        """Generate an image showing the multiplier"""
        # Create a new image with dark background
        width, height = 500, 300
        background_color = (17, 24, 39)  # Dark blue-black

        img = Image.new('RGB', (width, height), background_color)
        draw = ImageDraw.Draw(img)

        # Determine text color based on win/loss
        text_color = (0, 255, 0) if won else (255, 0, 0)  # Green for win, red for loss

        # Prepare the text
        multiplier_text = f"{multiplier:.2f}x"

        # Choose font size based on text length
        font_size = 120
        if len(multiplier_text) > 5:
            font_size = int(font_size * 7 / len(multiplier_text))

        # Load font
        try:
            font = ImageFont.truetype("roboto.ttf", font_size)
        except:
            # Fallback to default font
            font = ImageFont.load_default()

        # Center the text
        text_width = draw.textlength(multiplier_text, font=font)
        text_height = font_size
        position = ((width - text_width) / 2, (height - text_height) / 2)

        # Draw the text
        draw.text(position, multiplier_text, font=font, fill=text_color)

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

    @commands.command(aliases=["l"])
    async def limbo(self, ctx, bet_amount: str = None, target_multiplier: str = None, rolls_or_currency: str = None, currency_type: str = None):
        """Play Limbo - choose a target multiplier and win if the roll is higher!"""
        if not bet_amount or not target_multiplier:
            embed = discord.Embed(
                title="🎮 How to Play Limbo",
                description=(
                    "**Limbo** is a game where you set a target multiplier. If the rolled number is higher than or equal to your target, you win!\n\n"
                    "**Usage:** `!limbo <bet_amount> <target_multiplier> [rolls|auto] [currency_type]`\n"
                    "**Example:** `!limbo 100 1.5` or `!limbo 50 2.75 10` or `!limbo 100 2 auto credits`\n\n"
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

        # Process bet amount
        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if user_data == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate bet amount
        try:
            # Handle 'all' or 'max' bet
            if bet_amount.lower() in ['all', 'max']:
                bet_amount_value = user_data['tokens'] + user_data['credits']
            else:
                # Check if bet has 'k' or 'm' suffix
                if bet_amount.lower().endswith('k'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000
                elif bet_amount.lower().endswith('m'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000000
                else:
                    bet_amount_value = float(bet_amount)

            bet_amount_value = float(bet_amount_value)  # Keep as float to support decimals

            if bet_amount_value <= 0:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Please enter a valid number or 'all'.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

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
                return await ctx.reply(embed=embed)

            # Round to 2 decimal places
            target_multiplier_value = round(target_multiplier_value, 2)

        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Multiplier",
                description="Please enter a valid multiplier (e.g., 1.5, 2.0, etc.).",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get user balances
        tokens_balance = user_data['tokens']
        credits_balance = user_data['credits']

        # Determine if rolls_or_currency is specifying rolls or currency
        rolls = None

        # Check if rolls_or_currency parameter exists
        if rolls_or_currency:
            if rolls_or_currency.lower() == "auto":
                rolls = None  # Auto mode
            elif rolls_or_currency.lower() in ['token', 'tokens', 'credit', 'credits']:
                # This is actually currency_type
                currency_type = rolls_or_currency
                rolls_or_currency = None
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
                        return await ctx.reply(embed=embed)
                    elif rolls > 200:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Too Many Rolls",
                            description="Maximum number of rolls is 200.",
                            color=0xFF0000
                        )
                        return await ctx.reply(embed=embed)
                    rolls_or_currency = None
                except ValueError:
                    # Not a valid number, treat as currency type
                    currency_type = rolls_or_currency
                    rolls_or_currency = None

        # Determine which currency to use 
        tokens_used = 0
        credits_used = 0

        # If currency type is specified, respect it
        if currency_type:
            currency_type = currency_type.lower()
            if currency_type in ['token', 'tokens']:
                if bet_amount_value <= tokens_balance:
                    tokens_used = bet_amount_value
                else:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Insufficient Tokens",
                        description=f"You don't have enough tokens. Your tokens balance: **{tokens_balance:.2f}**",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
            elif currency_type in ['credit', 'credits']:
                if bet_amount_value <= credits_balance:
                    credits_used = bet_amount_value
                else:
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Insufficient Credits",
                        description=f"You don't have enough credits. Your credits balance: **{credits_balance:.2f}**",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Currency",
                    description="Please use 'tokens' or 'credits' as currency type.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:
            # Auto determine what to use
            if bet_amount_value <= tokens_balance:
                tokens_used = bet_amount_value
            elif bet_amount_value <= credits_balance:
                credits_used = bet_amount_value
            elif bet_amount_value <= tokens_balance + credits_balance:
                # Use all tokens and some credits
                tokens_used = tokens_balance
                credits_used = bet_amount_value - tokens_balance
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Funds",
                    description=f"You don't have enough funds. Your balance: **{tokens_balance:.2f} tokens** and **{credits_balance:.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Create a new game instance
        game = LimboGame(self, ctx, bet_amount_value, target_multiplier_value, ctx.author.id, rolls)
        game.tokens_used = tokens_used
        game.credits_used = credits_used

        # Store the game in ongoing games
        self.ongoing_games[ctx.author.id] = game

        # Start the game
        await game.start_game()

    @limbo.before_invoke
    async def before_limbo(self, ctx):
        # Ensure the user has an account
        db = Users()
        if db.fetch_user(ctx.author.id) == False:
            dump = {
                "discord_id": ctx.author.id,
                "tokens": 0,
                "credits": 0, 
                "history": [],
                "total_deposit_amount": 0,
                "total_withdraw_amount": 0,
                "total_spent": 0,
                "total_earned": 0,
                'total_played': 0,
                'total_won': 0,
                'total_lost': 0
            }
            db.register_new_user(dump)

            embed = discord.Embed(
                title=":wave: Welcome to BetSync Casino!",
                color=0x00FFAE,
                description="**Type** `!guide` **to get started**"
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await ctx.reply("By using BetSync, agree to our TOS. Type `!tos` to know more.", embed=embed)


def setup(bot):
    bot.add_cog(LimboCog(bot))