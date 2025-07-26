import discord
import random
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class RacePlayAgainView(discord.ui.View):
    """View with a Play Again button that shows after a game ends"""
    def __init__(self, cog, ctx, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None
        self.original_author = ctx.author  # Store the original author explicitly

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, button, interaction):
        # Check if the person clicking is the original player
        if interaction.user.id != self.original_author.id:
            return await interaction.response.send_message("Only the original player can use this button!", ephemeral=True)

        # Disable the button after click
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with same bet amount
        # Pass the interaction.channel instead of self.ctx
        await self.cog.race(self.ctx, str(self.bet_amount))


class RaceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.track_length = 15  # Length of the race track

    @commands.command(aliases=["carrace"])
    async def race(self, ctx, bet_amount: str = None):
        """Play the car racing game - pick a car, win 3x if it finishes first!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🏎️ How to Play Car Race",
                description=(
                    "**Car Race** is a game where you bet on which car will win the race!\n\n"
                    "**Usage:** `!race <amount>`\n"
                    "**Example:** `!race 100`\n\n"
                    "- **Choose one of the four cars to bet on**\n"
                    "- **If your car wins, you receive 3x your bet!**\n"
                    "- **If your car loses, you lose your bet**\n"
                    "- **Payouts are made in credits**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game in Progress",
                description="You already have a race game in progress.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Processing Race Bet...",
            description="Please wait while we process your request...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

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
            tokens_used = bet_info["tokens_used"]
            #credits_used = bet_info["credits_used"]
            bet_amount = bet_info["total_bet_amount"]

            # Det
            currency_used = "points"

        except Exception as e:
            print(f"Error processing bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {str(e)}")


        # Mark this user as having an ongoing game
        self.ongoing_games[ctx.author.id] = {"bet_amount": bet_amount, "currency_used": currency_used, "ctx": ctx}

        # Create car selection embed
        embed = discord.Embed(
            title="🏎️ CAR RACE - CHOOSE YOUR CAR",
            description=f"**Bet Amount:** `{bet_amount} {currency_used}`\n\nSelect a car to bet on:",
            color=0x00FFAE
        )

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

        # Update the loading message with the car selection and buttons
        await loading_message.edit(embed=embed, view=view)
        game_message = loading_message
        self.ongoing_games[ctx.author.id]["message"] = game_message

        # Auto-cancel the game after 30 seconds if no selection is made
        await asyncio.sleep(30)

        # Check if the game still exists and no car was selected
        if ctx.author.id in self.ongoing_games:
            game_data = self.ongoing_games[ctx.author.id]
            if "selected_car" not in game_data:
                # Remove the game from ongoing games
                del self.ongoing_games[ctx.author.id]

                # Refund the bet
                #Implement refund logic here using currency_helper if needed

                cancel_embed = discord.Embed(
                    title="🚫 Race Cancelled",
                    description=(
                        "You didn't pick a car in time.\n"
                        f"Your bet of `{bet_amount:.2f} {currency_used}` has been refunded."
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

        # Check if a car was already selected to prevent double-clicks
        if "selected_car" in self.ongoing_games[author.id]:
            await interaction.response.send_message("You have already selected a car!", ephemeral=True)
            return

        # Save the selected car
        self.ongoing_games[author.id]["selected_car"] = selected_car

        # Acknowledge the selection
        try:
            await interaction.response.send_message(f"You selected Car {selected_car}! Race starting...", ephemeral=True)
        except Exception as e:
            print(f"Error responding to interaction: {e}")

        try:
            # Delete the car selection message
            message = self.ongoing_games[author.id]["message"]
            await message.delete()
        except Exception as e:
            print(f"Error deleting selection message: {e}")

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
            description=f"{author.mention} chose Car {selected_car}. Race is starting!",
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
        message = await ctx.reply(embed=race_embed)

        # Run the race
        winner = None

        while winner is None:
            # Move all cars simultaneously and check for winner immediately
            for i in range(4):
                # More varied speed with better randomization
                move = random.choice([1, 1, 2, 2, 3])  # Weighted toward 1-2, occasional 3
                car_positions[i] = min(car_positions[i] + move, self.track_length)

                # Check if this car won (first to reach finish line)
                if car_positions[i] >= self.track_length and winner is None:
                    winner = i + 1
                    break  # Stop immediately when first car reaches finish

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

            # Slower delay between updates
            await asyncio.sleep(0.8)

            # Stop immediately if we have a winner
            if winner is not None:
                break



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
            server_db.update_server_profit(ctx, ctx.guild.id, server_profit, game="race")

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
                    f"You bet **{bet_amount:.2f} {currency_used}** on Car {selected_car} and won **{win_amount:.2f} points**!\n\n"
                    f"**Winnings:** `{win_amount:.2f} points`"
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

        # Show only the winner car in final results
        winner_position = car_positions[winner - 1]
        winner_track = "⬜" * winner_position + f"{car_colors[winner - 1]}" + "⬜" * (self.track_length - winner_position - 1) + "🏁"

        result_embed.add_field(
            name=f"🏆 Winner: {car_emojis[winner - 1]} Car {winner}",
            value=winner_track,
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

        # Delete the race in progress message
        try:
            await message.delete()
        except Exception as e:
            print(f"Error deleting race progress message: {e}")

        # Add play again button
        play_again_view = RacePlayAgainView(self, ctx, bet_amount, timeout=60)
        play_again_message = await ctx.reply(embed=result_embed, view=play_again_view)
        play_again_view.message = play_again_message

def setup(bot):
    bot.add_cog(RaceCog(bot))