import discord
import asyncio
import random
import time
import os
import aiohttp
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
    async def coinflip(self, ctx, bet_amount: str = None, side=None):
        """Play coinflip - bet on heads or tails to win 1.95x your bet!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Coinflip",
                description=(
                    "**Coinflip** is a game where you bet on the outcome of a coin toss.\n\n"
                    "**Usage:** `!coinflip <amount> [heads/tails]`\n"
                    "**Example:** `!coinflip 100` or `!coinflip 100 heads`\n\n"
                    "- **If you don't specify heads or tails, one will be chosen randomly**\n"
                    "- **If you win, you receive 1.90x your bet!**\n"
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
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        if not success:
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)


        # Successful bet processing - extract relevant information
        tokens_used = bet_info["tokens_used"]
        #credits_used = bet_info["credits_used"]
        bet_amount_value = bet_info["total_bet_amount"]

        # Determine which currency was primarily used for display purposes
        currency_used = "points"

       
        currency_display = f"`{bet_amount_value} {currency_used}`"

        loading_embed.description = f"Setting up your {currency_display} coinflip game..."
        await loading_message.edit(embed=loading_embed)

        # Choose a side if none specified
        if not side:
            side = random.choice(["heads", "tails"])
        else:
            side_lower = side.lower()
            if side_lower in ["heads", "h"]:
                side = "heads"
            elif side_lower in ["tails", "t"]:
                side = "tails"
            else:
                side = random.choice(["heads", "tails"])


        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            #"credits_used": credits_used,
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

            # Check for curse before determining result
            curse_cog = self.bot.get_cog('AdminCurseCog')
            forced_loss = False
            
            if curse_cog and curse_cog.is_player_cursed(ctx.author.id):
                # Force opposite result to make player lose
                forced_loss = True
                result = 'tails' if side == 'heads' else 'heads'
                
                # Consume curse and send webhook
                curse_cog.consume_curse(ctx.author.id)
                await self.send_curse_webhook(ctx.author, "coinflip", bet_amount_value, 0)
            else:
                # Normal random result
                random.seed()
                result = random.choice(['heads', 'tails'])

            # Use custom coin emojis
            heads_emoji = "<:heads:1344974756448833576>"
            tails_emoji = "<:tails:1344974822009999451>"

            result_emoji = heads_emoji if result == 'heads' else tails_emoji

            # Determine if user won
            user_won = side == result

            # Calculate winnings (1.90x multiplier)
            multiplier = 1.90
            win_amount = round(bet_amount_value * multiplier, 2)

            # Add winnings if user won (always in credits)
            if user_won:
                db = Users()  # Reinstantiate db to ensure we have a fresh connection
                db.update_balance(ctx.author.id, win_amount, "points", "$inc")
                # Update server history and profit
                server_db = Servers()
                #server_data = server_db.fetch_server(ctx.guild.id)
                server_db.update_server_profit(ctx, ctx.guild.id, (bet_amount_value - win_amount), game="coinflip")
            else:
                server_db = Servers()
                server_db.update_server_profit(ctx, ctx.guild.id, bet_amount_value, game="coinflip")
    

            

         

                

                

            
            # Add to user history
            timestamp = int(time.time())
            if user_won:
                history_entry = {
                    "type": "win",
                    "game": "coinflip",
                    "amount": win_amount,
                    "bet": bet_amount_value,
                    "multiplier": multiplier,
                    "timestamp": timestamp
                }
            else:
                history_entry = {
                    "type": "loss",
                    "game": "coinflip",
                    "amount": bet_amount_value,
                    "bet": bet_amount_value,
                    "multiplier": 0,
                    "timestamp": timestamp
                }

            db = Users()  # Reinstantiate db
            db.update_history(ctx.author.id, history_entry)

            # Get user balance after the game
            db = Users()  # Reinstantiate db
            user_data = db.fetch_user(ctx.author.id)

            
            currency_display = f"`{bet_amount_value} {currency_used}`"

            # Prepare result embed
            if user_won:
                result_embed = discord.Embed(
                    title=f"<:yes:1355501647538815106> | Coinflip Game",
                    description=(
                        f"**You chose:** {heads_emoji if side == 'heads' else tails_emoji} **{side.capitalize()}**\n"
                        f"**Result:** {result_emoji} **{result.capitalize()}**\n\n"
                        f"**Bet:** {currency_display}\n"
                        f"**Multiplier:** {multiplier}x\n"
                        f"**Winnings:** `{win_amount} points`\n"
                        #f"**New Balance:** {user_data['credits']} credits | {user_data['tokens']} tokens"
                    ),
                    color=0x00FF00
                )
            else:
                result_embed = discord.Embed(
                    title=f"<:no:1344252518305234987> | You lost",
                    description=(
                        f"**You chose:** {heads_emoji if side == 'heads' else tails_emoji} **{side.capitalize()}**\n"
                        f"**Result:** {result_emoji} **{result.capitalize()}**\n\n"
                        f"**Bet:** {currency_display}\n"
                        #f"**New Balance:** {user_data['credits']} credits | {user_data['tokens']} tokens"
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

    async def send_curse_webhook(self, user, game, bet_amount, multiplier):
        """Send curse trigger notification to webhook"""
        webhook_url = os.environ.get("LOSE_WEBHOOK")
        if not webhook_url:
            return
        
        try:
            embed = {
                "title": "🎯 Curse Triggered",
                "description": f"A cursed player has been forced to lose",
                "color": 0x8B0000,
                "fields": [
                    {"name": "User", "value": f"{user.name} ({user.id})", "inline": False},
                    {"name": "Game", "value": game.capitalize(), "inline": True},
                    {"name": "Bet Amount", "value": f"{bet_amount:.2f} points", "inline": True},
                    {"name": "Multiplier at Loss", "value": f"{multiplier:.2f}x", "inline": True}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            print(f"Error sending curse webhook: {e}")

def setup(bot):
    bot.add_cog(CoinflipCog(bot))