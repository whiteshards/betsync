import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class WheelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        # Define color multipliers
        self.colors = {
            "gray": {"emoji": "⚪", "multiplier": 0, "chance": 50},
            "yellow": {"emoji": "🟡", "multiplier": 1.5, "chance": 25},
            "red": {"emoji": "🔴", "multiplier": 2, "chance": 15},
            "blue": {"emoji": "🔵", "multiplier": 3, "chance": 7},
            "green": {"emoji": "🟢", "multiplier": 5, "chance": 3}
        }
        # Calculate total chance to verify it sums to 100
        self.total_chance = sum(color["chance"] for color in self.colors.values())

    @commands.command(aliases=["wh"])
    async def wheel(self, ctx, bet_amount: str = None, spins: int = 1):
        """Play the wheel game - bet on colors with different multipliers!"""
        # Limit the number of spins to 15
        if spins > 15:
            spins = 15
        elif spins < 1:
            spins = 1
        if not bet_amount:
            embed = discord.Embed(
                title="<a:hersheyparkSpin:1345317103158431805> How to Play Wheel",
                description=(
                    "**Wheel** is a game where you bet and win based on where the wheel lands.\n\n"
                    "**Usage:** `!wheel <amount> [currency_type]`\n"
                    "**Example:** `!wheel 100` or `!wheel 100 tokens`\n\n"
                    "**Colors and Multipliers:**\n"
                    "⚪ **Gray** - 0x (Loss)\n"
                    "🟡 **Yellow** - 1.5x\n"
                    "🔴 **Red** - 2x\n"
                    "🔵 **Blue** - 3x\n"
                    "🟢 **Green** - 5x\n\n"
                    "You bet using points.\n"
                    "- Winnings are always paid in points."
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        #oading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Wheel Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount using currency_helper
        from Cogs.utils.currency_helper import process_bet_amount
        
        # First process the bet amount for a single spin
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount*spins, loading_message)
        
        # If processing failed, return the error
        if not success:
            await loading_message.delete() 
            return await ctx.reply(embed=error_embed)
            
        # Extract needed values from bet_info
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]
        bet_amount_value = total_bet
        
        # Calculate total amounts for multiple spins
        total_tokens_used = tokens_used * spins
        #total_credits_used = credits_used * spins
        
        # Verify user has enough for all spins
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        
        if user_data == False:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
            
        #tokens_balance = user_data['tokens']
        #credits_balance = user_data['credits']
        
        # Check if user has enough 
            
        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount_value,
            "tokens_used": total_tokens_used,
            #"credits_used": total_credits_used,
            "spins": spins
        }
        

        # Delete loading message
        await loading_message.delete()

        # Create initial wheel embed
        wheel_embed = discord.Embed(
            title="<a:hersheyparkSpin:1345317103158431805> Wheel of Fortune",
            description=(
                f"The wheel is spinning for {spins} spin{'s' if spins > 1 else ''}...\n\n"
                "**Your Bet:** "
            ),
            color=0x00FFAE
        )

        # Format bet description
        per_spin_text = ""
        wheel_embed.description += f"{total_tokens_used:.2f} points"

        if spins > 1:
            wheel_embed.description += f" ({per_spin_text} per spin)"

        wheel_embed.add_field(
            name="Possible Outcomes",
            value=(
                "⚪ **Gray** - 0x (Loss)\n"
                "🟡 **Yellow** - 1.5x\n"
                "🔴 **Red** - 2x\n"
                "🔵 **Blue** - 3x\n"
                "🟢 **Green** - 5x"
            ),
            inline=False
        )

        wheel_embed.add_field(
            name="Wheel Spinning",
            value="⚙️ " + "⬛" * 10 + " ⚙️",
            inline=False
        )

        wheel_embed.set_footer(text="BetSync Casino • Good luck!", icon_url=self.bot.user.avatar.url)

        # Send the initial wheel embed
        wheel_message = await ctx.reply(embed=wheel_embed)

        # Create spinning animation - reduced to exactly 2 seconds total
        spinning_frames = [
            "⚙️ " + "⬛" * 4 + "🟡" + "⬛" * 5 + " ⚙️",
            "⚙️ " + "⬛" * 5 + "🔴" + "⬛" * 4 + " ⚙️",
            "⚙️ " + "⬛" * 6 + "🔵" + "⬛" * 3 + " ⚙️",
            "⚙️ " + "⬛" * 7 + "🟢" + "⬛" * 2 + " ⚙️",
            "⚙️ " + "⬛" * 8 + "⚪" + "⬛" * 1 + " ⚙️",
            "⚙️ " + "⬛" * 9 + "🟡" + " ⚙️",
            "⚙️ " + "🔴" + "⬛" * 9 + " ⚙️",
            "⚙️ " + "⬛" * 1 + "🔵" + "⬛" * 8 + " ⚙️",
            "⚙️ " + "⬛" * 2 + "🟢" + "⬛" * 7 + " ⚙️",
            "⚙️ " + "⬛" * 3 + "⚪" + "⬛" * 6 + " ⚙️"
        ]

        # Animate the wheel spinning - 20 frames × 0.1s = 2 seconds total
        for _ in range(1):  # Reduced to 2 cycles
            for frame in spinning_frames:
                wheel_embed.set_field_at(
                    1,  # Index 1 is the "Wheel Spinning" field
                    name="Wheel Spinning",
                    value=frame,
                    inline=False
                )
                await wheel_message.edit(embed=wheel_embed)
                await asyncio.sleep(0.1)  # Reduced speed for animation

        # Calculate results for all spins with house edge (3-5%)
        house_edge = 0.04  # 4% house edge

        # Store results for all spins
        spin_results = []
        total_winnings = 0
        bet_total = tokens_used 
        total_bet_amount = bet_total * spins

        # Calculate results for each spin
        for _ in range(spins):
            # Apply house edge to outcome calculation
            if random.random() < house_edge:
                # Force a loss (gray) more often for house edge
                result_color = "gray"
            else:
                # Normal weighted random selection
                random_value = random.randint(1, self.total_chance)
                cumulative = 0
                result_color = None

                for color, data in self.colors.items():
                    cumulative += data["chance"]
                    if random_value <= cumulative:
                        result_color = color
                        break

            # Get multiplier for the result
            result_multiplier = self.colors[result_color]["multiplier"]
            result_emoji = self.colors[result_color]["emoji"]

            # Calculate winnings for this spin (always paid out in credits)
            winnings = bet_total * result_multiplier
            total_winnings += winnings

            # Add this result to our results list
            spin_results.append({
                "color": result_color,
                "emoji": result_emoji,
                "multiplier": result_multiplier,
                "winnings": winnings
            })

        # Update the wheel embed with a single animated result
        random_result = random.choice(spin_results)
        result_frame = "⚙️ " + "⬛" * 5 + random_result["emoji"] + "⬛" * 4 + " ⚙️"
        wheel_embed.set_field_at(
            1,
            name="Wheel Animation",
            value=result_frame,
            inline=False
        )

        # Create a summary of all results
        results_summary = ""
        wins_count = 0
        for i, result in enumerate(spin_results):
            if result["multiplier"] > 0:
                wins_count += 1
            results_summary += f"Spin {i+1}: {result['emoji']} ({result['color'].capitalize()}) - {result['multiplier']}x - {result['winnings']:.2f} points\n"

        # Add overall results summary
        wheel_embed.add_field(
            name=f"Spin Results ({wins_count}/{spins} wins)",
            value=results_summary,
            inline=False
        )

        # Add overall result field
        if total_winnings > 0:
            net_profit = total_winnings - total_bet_amount
            wheel_embed.add_field(
                name=f"🎉 Overall Results",
                value=f"**Total Bet:** {total_bet_amount:.2f}\n**Total Winnings:** {total_winnings:.2f} points\n**Net Profit:** {net_profit:.2f} points",
                inline=False
            )

            if net_profit > 0:
                wheel_embed.color = 0x00FF00  # Green for overall profit
            else:
                wheel_embed.color = 0xFFA500  # Orange for win but overall loss/breakeven

            # Update user's balance with winnings
            db.update_balance(ctx.author.id, total_winnings, "credits", "$inc")

            # Process stats and history for each spin
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id) if ctx.guild else None

            # Track wins and losses for stats
            wins_count = 0
            losses_count = 0
            house_profit = 0

            # History entries for batch update
            history_entries = []
            server_history_entries = []

            for i, result in enumerate(spin_results):
                # Process individual spin history
                if result["multiplier"] > 0:
                    # This spin was a win
                    wins_count += 1
                    history_entry = {
                        "type": "win",
                        "game": "wheel",
                        "bet": bet_total,
                        "amount": result["winnings"],
                        "multiplier": result["multiplier"],
                        "timestamp": int(time.time()) + i  # Ensure unique timestamps
                    }

                    if server_data:
                        server_bet_history_entry = {
                            "type": "win",
                            "game": "wheel",
                            "user_id": ctx.author.id,
                            "user_name": ctx.author.name,
                            "bet": bet_total,
                            "amount": result["winnings"],
                            "multiplier": result["multiplier"],
                            "timestamp": int(time.time()) + i
                        }
                        server_history_entries.append(server_bet_history_entry)
                        house_profit += bet_total - result["winnings"]
                else:
                    # This spin was a loss
                    losses_count += 1
                    history_entry = {
                        "type": "loss",
                        "game": "wheel",
                        "bet": bet_total,
                        "amount": bet_total,
                        "multiplier": result["multiplier"],
                        "timestamp": int(time.time()) + i
                    }

                    if server_data:
                        server_bet_history_entry = {
                            "type": "loss",
                            "game": "wheel",
                            "user_id": ctx.author.id,
                            "user_name": ctx.author.name,
                            "bet": bet_total,
                            "amount": bet_total,
                            "multiplier": result["multiplier"],
                            "timestamp": int(time.time()) + i
                        }
                        server_history_entries.append(server_bet_history_entry)
                        house_profit += bet_total

                history_entries.append(history_entry)

            # Update user's stats with all spins
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$push": {"history": {"$each": history_entries, "$slice": -100}},
                    "$inc": {
                        "total_played": spins,
                        "total_won": wins_count,
                        "total_lost": losses_count,
                        "total_earned": total_winnings,
                        "total_spent": total_bet_amount - total_winnings if total_winnings < total_bet_amount else 0
                    }
                }
            )

            # Update server data with all spins
            if server_data and server_history_entries:
                server_db.update_server_profit(ctx, ctx.guild.id, house_profit, game="wheel")

            # Set final embed color based on overall result
            if total_winnings > total_bet_amount:
                wheel_embed.color = 0x00FF00  # Green for overall profit
            elif total_winnings > 0:
                wheel_embed.color = 0xFFA500  # Orange for some wins but overall loss
            else:
                wheel_embed.color = 0xFF0000  # Red for complete loss

        else:
            # Complete loss (all gray)
            wheel_embed.color = 0xFF0000
            wheel_embed.add_field(
                name="😢 Game Over",
                value=f"**Total Loss:** {total_bet_amount:.2f}",
                inline=False
            )

        # Update the embed with play again button
        await wheel_message.edit(embed=wheel_embed)

        # Create play again view
        view = PlayAgainView(self, ctx, bet_total, spins=spins)
        await wheel_message.edit(view=view)
        view.message = wheel_message

        # Remove user from ongoing games
        self.ongoing_games.pop(ctx.author.id, None)


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15, spins=1):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.spins = spins
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="play_again")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Use the same bet amount and spins without specifying currency
        # The currency helper in the wheel command will handle balance checks and currency selection
        await self.cog.wheel(self.ctx, str(self.bet_amount), self.spins)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


def setup(bot):
    bot.add_cog(WheelCog(bot))