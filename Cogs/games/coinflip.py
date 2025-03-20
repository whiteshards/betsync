import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, side=None, currency_used="credits"):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.side = side
        self.currency_used = currency_used
        self.message = None
        self.author_id = ctx.author.id  # Added to match CasesPlayAgainView

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self,button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the button to prevent spam clicks
        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        message = await interaction.original_response()
        await message.edit(view=self)

        # Send a loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Processing Coinflip...",
            description="Please wait while we process your request...",
            color=0x00FFAE
        )
        
        #loading_message = await interaction.followup.send(embed=loading_embed)

        # Get the context for the new game
        ctx = await self.cog.bot.get_context(self.message)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        #success, bet_info, error_embed = await process_bet_amount(self.ctx, str(self.bet_amount), self.currency_used, loading_message)

        # If processing failed, return the error
        #if not success:
            #return await interaction.followup.send(embed=error_embed, ephemeral=True)

        # Run the command again with the side preference if it exists
        if self.side:
            await self.cog.coinflip(self.ctx, self.bet_amount, side=self.side)
        else:
            await self.cog.coinflip(self.ctx, self.bet_amount)

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True

        # Try to update the message if it exists
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Error updating message on timeout: {e}")


class CoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["cf", "coin", "flip"])
    async def coinflip(self, ctx, bet_amount: str = None, side=None, currency_type: str = None):
        """Play coinflip - bet on heads or tails to win 1.95x your bet!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Coinflip",
                description=(
                    "**Coinflip** is a game where you bet on the outcome of a coin toss.\n\n"
                    "**Usage:** `!coinflip <amount> [currency_type] [heads/tails]`\n"
                    "**Example:** `!coinflip 100` or `!coinflip 100 tokens heads`\n\n"
                    "- **If you don't specify heads or tails, one will be chosen randomly**\n"
                    "- **If you win, you receive 1.95x your bet!**\n"
                    "- **If you lose, you lose your bet**\n"
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
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Coinflip Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount
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

        #Import currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process bet using currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)


        # Successful bet processing - extract relevant information
        tokens_used = bet_info["tokens_used"]
        credits_used = bet_info["credits_used"]
        bet_amount_value = bet_info["total_bet_amount"]

        # Determine which currency was primarily used for display purposes
        if tokens_used > 0 and credits_used > 0:
            currency_used = "mixed"
        elif tokens_used > 0:
            currency_used = "tokens"
        else:
            currency_used = "credits"

        # Update the loading message to show bet details
        if currency_used == "mixed":
            currency_display = f"{tokens_used} tokens and {credits_used} credits"
        else:
            currency_display = f"{bet_amount_value} {currency_used}"

        loading_embed.description = f"Setting up your {currency_display} coinflip game..."
        await loading_message.edit(embed=loading_embed)

        # Choose a side if none specified
        if not side or side.lower() not in ["heads", "tails"]:
            side = random.choice(["heads", "tails"])
        else:
            side = side.lower()


        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "bet_amount": bet_amount_value,
            "side": side
        }

        # Delete loading message
        await loading_message.delete()

        try:
            # Create initial embed with rolling animation
            coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
            initial_embed = discord.Embed(
                title="🪙 | Coinflip Game",
                description=f"**Bet Amount:** {currency_display}\n**Your Choice:** {side.capitalize()}\n\n{coin_flip_animated} Flipping coin...",
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Send initial message
            message = await ctx.reply(embed=initial_embed)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Reset random seed and determine the result
            random.seed()
            result = random.choice(['heads', 'tails'])

            # Use custom coin emojis
            heads_emoji = "<:heads:1344974756448833576>"
            tails_emoji = "<:tails:1344974822009999451>"

            result_emoji = heads_emoji if result == 'heads' else tails_emoji

            # Determine if user won
            user_won = side == result

            # Calculate winnings (1.95x multiplier)
            multiplier = 1.95
            win_amount = round(bet_amount_value * multiplier, 2)

            # Add winnings if user won (always in credits)
            if user_won:
                db = Users()  # Reinstantiate db to ensure we have a fresh connection
                db.update_balance(ctx.author.id, win_amount, "credits", "$inc")
                # Update server history and profit
                server_db = Servers()
                #server_data = server_db.fetch_server(ctx.guild.id)
                server_db.update_server_profit(ctx.guild.id, (bet_amount_value - win_amount), game="coinflip")
            else:
                server_db = Servers()
                server_db.update_server_profit(ctx.guild.id, bet_amount_value, game="coinflip")
    

            

         

                

                # Add to server history
                history_entry = {
                    "type": "coinflip",
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name,
                    "amount": bet_amount_value,
                    "currency": "mixed" if tokens_used > 0 and credits_used > 0 else ("tokens" if tokens_used > 0 else "credits"),
                    "result": result,
                    "bet": side,
                    "won": user_won,
                    "win_amount": win_amount if user_won else 0,
                    "timestamp": int(time.time())
                }
                server_db.update_history(ctx.guild.id, history_entry)

            # Add game to user history
            history_entry = {
                "game": "coinflip",
                "bet_amount": bet_amount_value,
                "currency": currency_used,
                "result": "win" if user_won else "loss",
                "side_chosen": side,
                "side_result": result,
                "win_amount": win_amount if user_won else 0,
                "timestamp": int(time.time())
            }
            db = Users()  # Reinstantiate db
            db.update_history(ctx.author.id, history_entry)

            # Get user balance after the game
            db = Users()  # Reinstantiate db
            user_data = db.fetch_user(ctx.author.id)

            # Format the currency display for the result
            if currency_used == "mixed":
                currency_display = f"{tokens_used} tokens and {credits_used} credits"
            else:
                currency_display = f"{bet_amount_value} {currency_used}"

            # Prepare result embed
            if user_won:
                result_embed = discord.Embed(
                    title=f"🎉 | You won {win_amount} credits!",
                    description=(
                        f"**You chose:** {heads_emoji if side == 'heads' else tails_emoji} **{side.capitalize()}**\n"
                        f"**Result:** {result_emoji} **{result.capitalize()}**\n\n"
                        f"**Bet:** {currency_display}\n"
                        f"**Multiplier:** {multiplier}x\n"
                        f"**Winnings:** {win_amount} credits\n"
                        f"**New Balance:** {user_data['credits']} credits | {user_data['tokens']} tokens"
                    ),
                    color=0x00FF00
                )
            else:
                result_embed = discord.Embed(
                    title=f"😢 | You lost your bet!",
                    description=(
                        f"**You chose:** {heads_emoji if side == 'heads' else tails_emoji} **{side.capitalize()}**\n"
                        f"**Result:** {result_emoji} **{result.capitalize()}**\n\n"
                        f"**Bet:** {currency_display}\n"
                        f"**New Balance:** {user_data['credits']} credits | {user_data['tokens']} tokens"
                    ),
                    color=0xFF0000
                )

            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Create view with play again button, including the player's choice for next game
            play_again_view = PlayAgainView(self, ctx, bet_amount_value, side, currency_used)

            # Make sure to update the message with the view properly attached
            await message.edit(embed=result_embed, view=play_again_view)

            # Store message reference in view for timeout handling
            play_again_view.message = message

            # Clear ongoing game
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

        except Exception as e:
            # Handle any errors
            print(f"Error in coinflip game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing coinflip. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)

            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]


def setup(bot):
    bot.add_cog(CoinflipCog(bot))