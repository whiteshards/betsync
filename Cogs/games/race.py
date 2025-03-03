import discord
import random
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class RacePlayAgainView(discord.ui.View):
    """View with a Play Again button that shows after a game ends"""
    def __init__(self, cog, ctx, bet_amount, currency_used, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, button, interaction):
        # Check if the person clicking is the original player
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Only the original player can use this button!", ephemeral=True)

        # Disable the button after click
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with same bet amount
        await self.cog.race(interaction.channel, str(self.bet_amount), self.currency_used)


class RaceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.track_length = 15  # Length of the race track

    @commands.command(aliases=["carrace"])
    async def race(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play the car racing game - pick a car, win 3x if it finishes first!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🏎️ How to Play Car Race",
                description=(
                    "**Car Race** is a game where you bet on which car will win the race!\n\n"
                    "**Usage:** `!race <amount> [currency_type]`\n"
                    "**Example:** `!race 100` or `!race 100 tokens`\n\n"
                    "- **Choose one of the four cars to bet on**\n"
                    "- **If your car wins, you receive 3x your bet!**\n"
                    "- **If your car loses, you lose your bet**\n"
                    "- **Payouts are made in credits**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Get user's balance
        author = ctx.author
        db = Users()
        user_data = db.fetch_user(author.id)
        tokens_balance = user_data.get('tokens', 0)
        credits_balance = user_data.get('credits', 0)

        author = ctx.author

        # Check if user already has an ongoing game
        if author.id in self.ongoing_games:
            return await ctx.reply("You already have a game in progress!")

        # Process bet amount and currency
        try:
            if bet_amount.lower() in ["all", "max"]:
                if currency_type:
                    if currency_type.lower() in ["tokens", "t"]:
                        bet_amount = tokens_balance
                        currency_used = "tokens"
                    elif currency_type.lower() in ["credits", "c"]:
                        bet_amount = credits_balance
                        currency_used = "credits"
                    else:
                        return await ctx.reply("Invalid currency type. Use 'tokens' or 'credits'.")
                else:
                    # If no currency specified with all/max, use the currency with higher balance
                    if tokens_balance >= credits_balance:
                        bet_amount = tokens_balance
                        currency_used = "tokens"
                    else:
                        bet_amount = credits_balance
                        currency_used = "credits"
            else:
                try:
                    bet_amount = float(bet_amount)
                    if bet_amount <= 0:
                        return await ctx.reply("Bet amount must be positive!")
                except ValueError:
                    return await ctx.reply("Invalid bet amount! Please enter a valid number.")

                # Handle currency selection
                if currency_type:
                    if currency_type.lower() in ["tokens", "t"]:
                        currency_used = "tokens"
                        if tokens_balance < bet_amount:
                            return await ctx.reply(f"You don't have enough tokens! Your balance: {tokens_balance:.2f} tokens")
                    elif currency_type.lower() in ["credits", "c"]:
                        currency_used = "credits"
                        if credits_balance < bet_amount:
                            return await ctx.reply(f"You don't have enough credits! Your balance: {credits_balance:.2f} credits")
                    else:
                        return await ctx.reply("Invalid currency type. Use 'tokens' or 'credits'.")
                else:
                    # If no currency specified, use what the user has
                    if tokens_balance >= bet_amount:
                        currency_used = "tokens"
                    elif credits_balance >= bet_amount:
                        currency_used = "credits"
                    else:
                        # Try to use a combination of both currencies if the total is enough
                        if tokens_balance + credits_balance >= bet_amount:
                            # Use tokens first, then credits
                            tokens_to_use = min(tokens_balance, bet_amount)
                            credits_to_use = bet_amount - tokens_to_use

                            # Update balances
                            db.update_balance(author.id, -tokens_to_use, "tokens", "$inc")
                            db.update_balance(author.id, -credits_to_use, "credits", "$inc")

                            await ctx.send(f"Using {tokens_to_use:.2f} tokens and {credits_to_use:.2f} credits for your bet.")
                            currency_used = "mixed"  # Special case for mixed currency
                        else:
                            return await ctx.reply(f"You don't have enough funds! Tokens: {tokens_balance:.2f}, Credits: {credits_balance:.2f}")
        except Exception as e:
            return await ctx.reply(f"An error occurred: {str(e)}")

        # Deduct the bet amount if not using mixed currency (mixed was already deducted)
        if currency_used != "mixed":
            db.update_balance(author.id, -bet_amount, currency_used, "$inc")

        # Check if user already has an ongoing game
        if author.id in self.ongoing_games:
            return await ctx.reply("You already have a game ongoing")
        try:
            if "all" in bet_amount.lower() or "max" in bet_amount.lower():
                db = Users()
                user_data = db.fetch_user(author.id)
                if currency_type and currency_type.lower() in ["credits", "tokens"]:
                    currency_used = currency_type.lower()
                    bet_amount = user_data[currency_used]
                else:
                    # Default to credits
                    currency_used = "credits"
                    bet_amount = user_data["credits"]
            else:
                bet_amount = float(bet_amount)

                # Default to credits if no currency specified
                if not currency_type or currency_type.lower() not in ["credits", "tokens"]:
                    currency_used = "credits"
                else:
                    currency_used = currency_type.lower()
        except ValueError:
            return await ctx.reply("Please enter a valid bet amount!")

        # Validate bet amount
        if bet_amount <= 0:
            return await ctx.reply("Bet amount must be greater than 0!")

        # Check if user has enough balance
        db = Users()
        user_data = db.fetch_user(author.id)

        if bet_amount > user_data[currency_used]:
            return await ctx.reply(f"You don't have enough {currency_used} for this bet!")

        # Deduct bet amount from user's balance
        db.update_balance(author.id, -bet_amount, currency_used, "$inc")

        # Create a game instance
        game_data = {
            "ctx": ctx,
            "bet_amount": bet_amount,
            "currency_used": currency_used
        }
        self.ongoing_games[author.id] = game_data

        # Create initial embed to select a car
        select_embed = discord.Embed(
            title="🏎️ Car Race",
            description=(
                f"**Bet:** {bet_amount:.2f} {currency_used}\n\n"
                "**Choose a car to bet on:**\n"
                "1️⃣ - Red Car\n"
                "2️⃣ - Blue Car\n"
                "3️⃣ - Green Car\n"
                "4️⃣ - Yellow Car\n\n"
                "Click a button below to pick your car."
            ),
            color=0x00FFAE
        )
        select_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create buttons to select cars
        view = discord.ui.View(timeout=30)

        # Add buttons for each car with fixed callbacks
        async def make_callback(car_num):
            async def callback(interaction):
                await self.car_selected(interaction, car_num, bet_amount, currency_used)
            return callback

        for i in range(1, 5):
            car_button = discord.ui.Button(label=f"Car {i}", style=discord.ButtonStyle.secondary, row=0)
            car_button.callback = await make_callback(i)
            view.add_item(car_button)

        game_message = await ctx.reply(embed=select_embed, view=view)
        self.ongoing_games[author.id]["message"] = game_message

        # Auto-cancel the game after 30 seconds if no selection is made
        await asyncio.sleep(30)
        if author.id in self.ongoing_games and "selected_car" not in self.ongoing_games[author.id]:
            if author.id in self.ongoing_games:
                del self.ongoing_games[author.id]

            # Refund the bet
            db.update_balance(author.id, bet_amount, currency_used, "$inc")

            cancel_embed = discord.Embed(
                title="🚫 Race Cancelled",
                description=(
                    "You didn't pick a car in time.\n"
                    f"Your bet of {bet_amount:.2f} {currency_used} has been refunded."
                ),
                color=0xFF0000
            )

            # Update the message if it still exists
            try:
                await game_message.edit(embed=cancel_embed, view=None)
            except:
                pass

    async def car_selected(self, interaction, selected_car, bet_amount, currency_used):
        """Process a car selection."""
        author = interaction.user

        # Make sure this is the game owner
        if author.id not in self.ongoing_games:
            await interaction.response.send_message("You don't have an active game!", ephemeral=True)
            return

        # Save the selected car
        self.ongoing_games[author.id]["selected_car"] = selected_car

        # Acknowledge the selection
        try:
            await interaction.response.defer()
        except Exception as e:
            print(f"Error deferring interaction: {e}")

        try:
            # Disable all buttons
            message = self.ongoing_games[author.id]["message"]
            view = discord.ui.View()
            for i in range(1, 5):
                btn = discord.ui.Button(label=f"Car {i}", style=discord.ButtonStyle.secondary, disabled=True)
                view.add_item(btn)

            # Update selection message
            selection_embed = discord.Embed(
                title="🏎️ Race Starting",
                description=(
                    f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                    f"**You selected:** Car {selected_car}\n\n"
                    "The race is about to begin! Good luck!"
                ),
                color=0x00FFAE
            )

            await message.edit(embed=selection_embed, view=view)
        except Exception as e:
            print(f"Error updating selection message: {e}")

        # Run the race
        await self.run_race(interaction, selected_car, bet_amount, currency_used)

    async def run_race(self, interaction, selected_car, bet_amount, currency_used):
        ctx = self.ongoing_games[interaction.user.id].get("ctx")
        author = interaction.user

        # Initialize car positions
        car_positions = [0, 0, 0, 0]  # Starting positions for all 4 cars
        car_emojis = ["🏎️", "🏎️", "🏎️", "🏎️"]
        car_colors = ["🟥", "🟦", "🟩", "🟨"]  # Different colors for each car

        # Initial race display
        race_embed = discord.Embed(
            title="🏁 Race in Progress...",
            description=f"You chose Car {selected_car}. Race is starting!",
            color=0x00FFAE
        )

        # Setup initial track visualization
        for i in range(4):
            car_num = i + 1
            track = f"{car_colors[i]}" + "⬜" * (self.track_length - 1) + "🏁"  # Colored starting position, rest white (empty track), finish line
            race_embed.add_field(
                name=f"{car_emojis[i]} Car {car_num}" + (" (Your Pick)" if car_num == selected_car else ""),
                value=track,
                inline=False
            )

        race_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        message = await ctx.send(embed=race_embed)

        # Run the race
        winner = None

        while winner is None:
            # Add random progress to each car
            for i in range(4):
                # Faster racing with more varied speeds
                move = random.randint(1, 3)
                car_positions[i] = min(car_positions[i] + move, self.track_length)

                # Check if this car reached the finish line
                if car_positions[i] >= self.track_length:
                    winner = i + 1

            # Update the race display
            updated_embed = discord.Embed(
                title="🏁 Race in Progress...",
                description=f"You chose Car {selected_car}. The race is heating up!",
                color=0x00FFAE
            )

            # Update track visualization
            for i in range(4):
                car_num = i + 1
                position = car_positions[i]

                # Create track with car position
                track = "⬜" * position + f"{car_colors[i]}" + "⬜" * (self.track_length - position - 1) + "🏁"

                # Highlight player's car
                car_label = f"{car_emojis[i]} Car {car_num}" + (" (Your Pick)" if car_num == selected_car else "")

                updated_embed.add_field(
                    name=car_label,
                    value=track,
                    inline=False
                )

            updated_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await message.edit(embed=updated_embed)

            # Stop immediately if we have a winner
            if winner is not None:
                break

            # Shorter delay between updates (reduced to make race faster)
            await asyncio.sleep(0.3)

        # Determine race result
        user_won = selected_car == winner
        win_amount = 0

        if user_won:
            win_amount = bet_amount * 3

        # Update MongoDB
        db = Users()

        # Update gameplay statistics
        db.collection.update_one(
            {"discord_id": author.id},
            {"$inc": {
                "total_played": 1,
                "total_won": 1 if user_won else 0,
                "total_lost": 0 if user_won else 1,
                "total_spent": bet_amount,
                "total_earned": win_amount
            }}
        )

        # Add to user's credits if they won
        if user_won:
            db.update_balance(author.id, win_amount, "credits", "$inc")

        # Update server profit statistics if in a server
        if hasattr(ctx, 'guild') and ctx.guild:
            server_db = Servers()
            server_profit = bet_amount - win_amount
            server_db.update_server_profit(ctx.guild.id, server_profit)

            # Add game to server history
            history_entry = {
                "game": "race",
                "user_id": author.id,
                "username": author.name,
                "bet_amount": bet_amount,
                "currency": currency_used,
                "result": "win" if user_won else "loss",
                "profit": server_profit,
                "timestamp": int(discord.utils.utcnow().timestamp())
            }
            server_db.update_history(ctx.guild.id, history_entry)

        # Add game to user history
        history_entry = {
            "game": "race",
            "bet_amount": bet_amount,
            "currency": currency_used,
            "result": "win" if user_won else "loss",
            "win_amount": win_amount,
            "timestamp": int(discord.utils.utcnow().timestamp())
        }
        db.update_history(author.id, history_entry)

        # Final results embed with improved visuals
        if user_won:
            result_embed = discord.Embed(
                title="🏆 You Won!",
                description=(
                    f"**Car {winner}** crossed the finish line first!\n\n"
                    f"You bet **{bet_amount:.2f} {currency_used}** on Car {selected_car} and won **{win_amount:.2f} credits**!\n\n"
                    f"**Winnings:** {win_amount:.2f} credits"
                ),
                color=0x00FF00
            )
        else:
            result_embed = discord.Embed(
                title="❌ You Lost!",
                description=(
                    f"**Car {winner}** crossed the finish line first!\n\n"
                    f"Your Car {selected_car} didn't win. You lost **{bet_amount:.2f} {currency_used}**.\n\n"
                    f"Better luck next time!"
                ),
                color=0xFF0000
            )

        # Final race visualization
        for i in range(4):
            car_num = i + 1
            position = car_positions[i]

            # Create final track display
            track = "⬜" * position + f"{car_colors[i]}" + "⬜" * (self.track_length - position - 1) + "🏁"

            # Highlight winner and player's car
            car_label = f"{car_emojis[i]} Car {car_num}"
            if car_num == winner:
                car_label += " 🏆"
            if car_num == selected_car:
                car_label += " (Your Pick)"

            result_embed.add_field(
                name=car_label,
                value=track,
                inline=False
            )

        # Show selected car and result
        result_embed.add_field(
            name="Your choice:",
            value=f"Car {selected_car}",
            inline=True
        )
        result_embed.add_field(
            name="Winner:",
            value=f"Car {winner}",
            inline=True
        )

        result_embed.set_footer(text=f"BetSync Casino • {currency_used.capitalize()} bet: {bet_amount:.2f}", icon_url=self.bot.user.avatar.url)

        # Clean up ongoing game
        if author.id in self.ongoing_games:
            del self.ongoing_games[author.id]

        # Add play again button
        play_again_view = RacePlayAgainView(self, ctx, bet_amount, currency_used)
        play_again_message = await message.edit(embed=result_embed, view=play_again_view)
        play_again_view.message = play_again_message

def setup(bot):
    bot.add_cog(RaceCog(bot))