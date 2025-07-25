import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import os
import aiohttp

class PCFView(discord.ui.View):
    def __init__(self, cog, ctx, message, bet_amount, initial_multiplier=1, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message = message
        self.bet_amount = bet_amount
        self.currency_used = "points"
        self.current_flips = 0
        self.current_multiplier = initial_multiplier
        self.max_flips = 15
        self.choice = None
        self.last_result = None

    @discord.ui.button(label="HEADS", style=discord.ButtonStyle.primary, emoji="🪙")
    async def heads_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "heads"
        await self.flip_coin(interaction)

    @discord.ui.button(label="TAILS", style=discord.ButtonStyle.primary, emoji="🪙")
    async def tails_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "tails"
        await self.flip_coin(interaction)

    @discord.ui.button(label="CASH OUT", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.current_flips == 0:
            return await interaction.response.send_message("You need to flip at least once before cashing out!", ephemeral=True)

        # Disable all buttons to prevent further interactions
        for item in self.children:
            item.disabled = True

        # Update the view first
        await interaction.response.edit_message(view=self)

        # Process cashout
        await self.cog.process_cashout(self.ctx, interaction, self.message, 
                                      self.bet_amount,
                                      self.current_flips, self.current_multiplier)

    async def flip_coin(self, interaction):
        # Check if we've already done 15 flips
        if self.current_flips >= self.max_flips:
            # Automatically cash out at max flips
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(view=self)

            await self.cog.process_cashout(self.ctx, interaction, self.message, 
                                          self.bet_amount,
                                          self.current_flips, self.current_multiplier,
                                          auto_cashout=True)
            return

        # Flip the coin (50/50 chance)
        result = random.choice(["heads", "tails"])
        self.last_result = result

        # Check if the player won this round
        if result == self.choice:
            # Player guessed correctly
            self.current_flips += 1
            self.current_multiplier *= 1.96  # Multiply by 1.96 for each correct guess

            # Create updated embed
            # Use custom coin emojis
            heads_emoji = "<:heads:1344974756448833576>"
            tails_emoji = "<:tails:1344974822009999451>"
            result_emoji = heads_emoji if result == "heads" else tails_emoji

            # Create flip visualization - show previous flips and empty spaces for remaining flips
            flip_visualization = ""
            for i in range(self.max_flips):
                if i < self.current_flips:
                    # Show the result emoji for completed flips
                    if i == self.current_flips - 1:
                        # Highlight the current flip
                        flip_visualization += result_emoji + " "
                    else:
                        # Show previous flips (we don't track them individually, so use the current result as placeholder)
                        flip_visualization += result_emoji + " "
                else:
                    # Show empty space for remaining flips
                    flip_visualization += "⬜ "

            embed = discord.Embed(
                title="🪙 | Progressive Coinflip",
                description=f"You flipped **{result.upper()}** {result_emoji} and chose **{self.choice.upper()}**\n\n**YOU WIN!**\n\nCurrent Multiplier: **{self.current_multiplier:.2f}x**\nCurrent Flips: **{self.current_flips}/{self.max_flips}**\n\n{flip_visualization}\n\nChoose your next flip or cash out!",
                color=0x00FF00
            )
            # Update embed footer
            embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)

            # Enable buttons for next round
            for item in self.children:
                item.disabled = False

            # Send the updated embed
            await interaction.response.edit_message(embed=embed, view=self)

            # Reset choice for next round
            self.choice = None

        else:
            # Player lost
            # Create losing embed
            # Use custom coin emojis
            heads_emoji = "<:heads:1344974756448833576>"
            tails_emoji = "<:tails:1344974822009999451>"
            result_emoji = heads_emoji if result == "heads" else tails_emoji

            # Create flip visualization - show previous flips with X for failure
            flip_visualization = ""
            for i in range(self.max_flips):
                if i < self.current_flips:
                    # Show the result emoji for completed flips
                    flip_visualization += result_emoji + " "
                elif i == self.current_flips:
                    # Show the failed flip with a cross emoji
                    flip_visualization += "❌ "
                else:
                    # Show empty space for remaining flips
                    flip_visualization += "⬜ "

            embed = discord.Embed(
                title="🪙 | Progressive Coinflip - GAME OVER!",
                description=f"You flipped **{result.upper()}** {result_emoji} and chose **{self.choice.upper()}**\n\n**YOU LOSE!**\n\nCurrent Flips: **{self.current_flips}/{self.max_flips}**\nMultiplier: **{self.current_multiplier:.2f}x**\n\n{flip_visualization}",
                color=0xFF0000
            )
            # Update embed footer
            embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)

            # Disable all buttons
            for item in self.children:
                item.disabled = True

            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)

            # Add play again button
            play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount)
            await interaction.message.edit(view=play_again_view)
            play_again_view.message = interaction.message

            # Process loss (if they've already flipped some coins)
            if self.current_flips > 0:
                # Register the loss in history
                db = Users()

                loss_entry = {
                    "type": "loss",
                    "game": "progressive_coinflip",
                    "bet": self.bet_amount,
                    "flips": self.current_flips,
                    "multiplier": self.current_multiplier,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": self.ctx.author.id},
                    {"$push": {"history": {"$each": [loss_entry], "$slice": -100}}}
                )

                # Update server history if available
                server_db = Servers()
                server_data = server_db.fetch_server(self.ctx.guild.id)

                if server_data:
                    server_loss_entry = {
                        "type": "loss",
                        "game": "progressive_coinflip",
                        "user_id": self.ctx.author.id,
                        "user_name": self.ctx.author.name,
                        "bet": self.bet_amount,
                        "flips": self.current_flips,
                        "timestamp": int(time.time())
                    }
                    server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="progressivecoinflip")

                # Update user stats
                db.collection.update_one(
                    {"discord_id": self.ctx.author.id},
                    {"$inc": {"total_lost": 1}}
                )

            # Remove from ongoing games
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

    async def on_timeout(self):
        # If player doesn't choose, auto cash out
        if not self.choice and self.current_flips > 0:
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)

                # Process automatic cashout
                await self.cog.process_cashout(self.ctx, None, self.message, 
                                              self.bet_amount,
                                              self.current_flips, self.current_multiplier,
                                              auto_cashout=True)
            except:
                pass
        else:
            # Just disable the buttons
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)
            except:
                pass

            # Clean up ongoing game
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

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


class PlayAgainView(discord.ui.View):
    """View with a Play Again button that shows after a game ends"""
    def __init__(self, cog, ctx, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        #self.currency_used = currency_used
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent double-clicks
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)
        await self.cog.progressivecf(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


class ContinueOrCashoutView(discord.ui.View):
    """View with buttons to continue flipping or cash out"""
    def __init__(self, cog, ctx, message, bet_amount, flips, multiplier, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message = message
        self.bet_amount = bet_amount
        #self.currency_used = currency_used
        self.flips = flips
        self.multiplier = multiplier

    @discord.ui.button(label="HEADS", style=discord.ButtonStyle.primary, emoji="🪙")
    async def heads_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Continue game with heads
        await self.cog.continue_progressive_flips(
            self.ctx, 
            interaction, 
            self.message, 
            self.bet_amount, 
            #self.currency_used, 
            "heads", 
            self.flips, 
            self.multiplier
        )

    @discord.ui.button(label="TAILS", style=discord.ButtonStyle.primary, emoji="🪙")
    async def tails_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Continue game with tails
        await self.cog.continue_progressive_flips(
            self.ctx, 
            interaction, 
            self.message, 
            self.bet_amount, 
            #self.currency_used, 
            "tails", 
            self.flips, 
            self.multiplier
        )

    @discord.ui.button(label="CASH OUT", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable all buttons
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Process cashout
        await self.cog.process_cashout(
            self.ctx, 
            interaction, 
            self.message, 
            self.bet_amount, 
            #self.currency_used, 
            self.flips, 
            self.multiplier
        )

    async def on_timeout(self):
        # Auto cash out on timeout
        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
            await self.cog.process_cashout(
                self.ctx, 
                None, 
                self.message, 
                self.bet_amount, 
                #self.currency_used, 
                self.flips, 
                self.multiplier,
                auto_cashout=True
            )
        except:
            pass


class ProgressiveCoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pcf"])
    async def progressivecf(self, ctx, bet_amount: str = None):
        """Play progressive coinflip - win multiple times to increase your multiplier!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Progressive Coinflip",
                description=(
                    "**Progressive Coinflip** is a game where you can win multiple times in a row for increasing rewards.\n\n"
                    "**Usage:** `!progressivecf <amount>`\n"
                    "**Example:** `!progressivecf 100`\n\n"
                    "**How to Play:**\n"
                    "1. Choose heads or tails for each flip\n"
                    "2. Each correct guess multiplies your winnings by 1.96x\n"
                    "3. You can cash out anytime or continue flipping\n"
                    "4. Maximum 15 flips allowed\n"
                    "5. If you lose a flip, you get nothing\n\n"
                    "**Currency Options:**\n"
                    "- You can bet using tokens (T) or credits (C)\n"
                    "- Winnings are always paid in credits"
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
        #loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"Preparing Progressive Coinflip...",
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

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        try:
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount,loading_message)

            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            # Successful bet processing - extract relevant information
            tokens_used = bet_info.get("tokens_used", 0)
            #credits_used = bet_info.get("credits_used", 0)
            bet_amount_value = bet_info.get("total_bet_amount", 0)
            currency_used = "points" # Default to credits if not specified


            currency_display = f"{bet_amount_value} {currency_used}"

            loading_embed.description = f"Setting up your {currency_display} progressive coinflip game..."
            await loading_message.edit(embed=loading_embed)

        except Exception as e:
            print(f"Error processing bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {str(e)}")

        # Get total amount bet
        total_bet = bet_amount_value

        # Delete loading message
        await loading_message.delete()

        # Create initial game embed
        initial_embed = discord.Embed(
            title="🪙 | Progressive Coinflip",
            description=(
                f"**Bet:** `{total_bet:,.2f} {currency_used}`\n"
                f"**Initial Multiplier:** 1.96x\n\n"
                "Choose heads or tails to start flipping!"
            ),
            color=0x00FFAE
        )
        initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Send initial game message
        game_message = await ctx.reply(embed=initial_embed)

        # Create game view
        game_view = PCFView(self, ctx, game_message, total_bet)
        await game_message.edit(view=game_view)

        # Mark game as ongoing (after successful bet processing)
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount_value,
            "currency_type": currency_used
        }

    async def process_cashout(self, ctx, interaction, message, bet_amount, flips, multiplier, auto_cashout=False):
        """Process cashout for the player"""
        # Calculate winnings (only credits)
        winnings = bet_amount * multiplier

        # Create cashout embed
        cashout_embed = discord.Embed(
            title="🪙 | Progressive Coinflip - CASHED OUT!",
            description=(
                f"**Initial Bet:** `{bet_amount:.2f} points`\n"
                f"**Successful Flips:** {flips}\n"
                f"**Final Multiplier:** {multiplier:.2f}x\n\n"
                f"**Winnings:** `{winnings:.2f} points`"
            ),
            color=0x00FF00
        )

        if auto_cashout:
            cashout_embed.description += "\n\n*Automatically cashed out due to maximum flips reached or timeout.*"

        cashout_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Update message
        try:
            await message.edit(embed=cashout_embed, view=None)
        except:
            pass

        # Add play again button
        play_again_view = PlayAgainView(self, ctx, bet_amount)
        await message.edit(view=play_again_view)
        play_again_view.message = message

        # Process win
        # Add credits to user
        db = Users()
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "progressive_coinflip",
            "bet": bet_amount,
            "amount": winnings,
            "flips": flips,
            "multiplier": multiplier,
            "timestamp": int(time.time())
        }
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [win_entry], "$slice": -100}}}
        )

        # Update server history
        server_db = Servers()
        server_data = server_db.fetch_server(ctx.guild.id)

        if server_data:
            server_win_entry = {
                "type": "win",
                "game": "progressive_coinflip",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": winnings,
                "flips": flips,
                "multiplier": multiplier,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

            # Update server profit (negative because player won)
            server_db.update_server_profit(ctx, ctx.guild.id, (bet_amount - winnings), game="progressivecoinflip")

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings, "total_played": 1}}
        )

        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

    async def start_progressive_game(self, ctx, message, bet_amount, side):
        """Start the progressive coinflip game after the user selects a side"""

        # Initial multiplier
        initial_multiplier = 1

        # Create animated coinflip
        try:
            # Update embed with rolling animation
            coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
            initial_embed = discord.Embed(
                title="🪙 | Progressive Coinflip",
                description=(
                    f"**Bet:** `{bet_amount:.2f} points`\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Initial Multiplier:** {initial_multiplier}x\n\n"
                    f"{coin_flip_animated} Flipping coin..."
                ),
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update message
            await message.edit(embed=initial_embed, view=None)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Start the progressive coinflip game
            await self.continue_progressive_flips(
                ctx, 
                None, 
                message,
                bet_amount,
                side, 
                0, 
                initial_multiplier
            )

        except Exception as e:
            # Handle any errors
            print(f"Error in progressive coinflip game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing progressive coinflip. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)

            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    async def continue_progressive_flips(self, ctx, interaction, message, bet_amount, side, current_flips, current_multiplier):
        """Continue flipping in progressive coinflip"""

        # Determine the result
        result = random.choice(['heads', 'tails'])

        # Use custom coin emojis
        heads_emoji = "<:heads:1344974756448833576>"
        tails_emoji = "<:tails:1344974822009999451>"

        result_emoji = heads_emoji if result == 'heads' else tails_emoji

        # Determine if user won
        user_won = side == result

        # Update flips count
        current_flips += 1

        # Create result embed
        if user_won:
            # Calculate new multiplier (multiply by 1.96)
            new_multiplier = round(current_multiplier * 1.96, 2)

            # Calculate current potential winnings
            potential_winnings = round(bet_amount * new_multiplier, 2)

            # Create flip visualization - show previous flips and empty spaces for remaining flips
            flip_visualization = ""
            for i in range(15):  # max flips is 15
                if i < current_flips:
                    # Show the result emoji for completed flips
                    if i == current_flips - 1:
                        # Highlight the current flip with its specific result
                        emoji_to_use = heads_emoji if result == "heads" else tails_emoji
                        flip_visualization += emoji_to_use + " "
                    else:
                        # Show previous flips (we don't track them individually, so this is simplified)
                        # In reality this should track past flips, but we'll just use a generic coin
                        flip_visualization += heads_emoji + " "  # Placeholder for previous flips
                else:
                    # Show empty space for remaining flips
                    flip_visualization += "⬜ "

            # Check if max flips reached
            max_flips_reached = current_flips >= 15

            if max_flips_reached:
                # Auto cash out at max flips
                result_embed = discord.Embed(
                    title="🪙 | Progressive Coinflip - MAX FLIPS REACHED!",
                    description=(
                        f"**Bet:** `{bet_amount:.2f} points`\n"
                        f"**Your Choice:** {side.capitalize()}\n"
                        f"**Result:** {result.capitalize()} {result_emoji}\n"
                        f"**Flips:** {current_flips}/15\n"
                        f"**Final Multiplier:** {new_multiplier}x\n\n"
                        f"{flip_visualization}\n\n"
                        f"🎉 **YOU WON {potential_winnings:.2f} POINTS!** 🎉\n"
                        f"*Maximum flips reached - auto cashed out!*"
                    ),
                    color=0x00FF00
                )
                result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

                # Update message
                await message.edit(embed=result_embed, view=None)

                # Process win
                await self.process_win(ctx, bet_amount, new_multiplier, current_flips)

                # Add play again button
                play_again_view = PlayAgainView(self, ctx, bet_amount)
                await message.edit(view=play_again_view)
                play_again_view.message = message

                # Remove from ongoing games
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]
            else:
                # Continue game
                result_embed = discord.Embed(
                    title="🪙 | Progressive Coinflip - YOU WON!",
                    description=(
                        f"**Bet:** `{bet_amount:.2f} points`\n"
                        f"**Your Choice:** {side.capitalize()}\n"
                        f"**Result:** {result.capitalize()} {result_emoji}\n"
                        f"**Flips:** {current_flips}/15\n"
                        f"**Current Multiplier:** {new_multiplier}x\n"
                        f"**Potential Win:** `{potential_winnings:.2f} points`\n\n"
                        f"{flip_visualization}\n\n"
                        f"Would you like to continue flipping or cash out?"
                    ),
                    color=0x00FFAE
                )
                result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

                # Create continue/cashout view
                continue_view = ContinueOrCashoutView(
                    self, ctx, message, bet_amount, current_flips, new_multiplier
                )

                # Update message with continue options
                if interaction:
                    await interaction.response.edit_message(embed=result_embed, view=continue_view)
                else:
                    await message.edit(embed=result_embed, view=continue_view)
        else:
            # User lost
            # Create flip visualization with X for failure
            flip_visualization = ""
            for i in range(15):  # max flips is 15
                if i < current_flips:
                    # Show emoji for previous successful flips
                    flip_visualization += heads_emoji + " "  # Placeholder for previous flips
                elif i == current_flips:
                    # Show the failed flip with a cross emoji
                    flip_visualization += "❌ "
                else:
                    # Show empty space for remaining flips
                    flip_visualization += "⬜ "

            result_embed = discord.Embed(
                title="🪙 | Progressive Coinflip - YOU LOST!",
                description=(
                    f"**Bet:** `{bet_amount:.2f} points`\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Result:** {result.capitalize()} {result_emoji}\n"
                    f"**Flips:** {current_flips}/15\n\n"
                    f"{flip_visualization}\n\n"
                    f"❌ **YOU LOST EVERYTHING!** ❌"
                ),
                color=0xFF0000
            )
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update message
            if interaction:
                await interaction.response.edit_message(embed=result_embed, view=None)
            else:
                await message.edit(embed=result_embed, view=None)

            # Process loss
            await self.process_loss(ctx, bet_amount, current_flips)

            # Add play again button
            play_again_view = PlayAgainView(self, ctx, bet_amount)
            await message.edit(view=playagain_view)
            play_again_view.message = message

            # Remove from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    async def process_win(self, ctx, bet_amount, multiplier, flips):
        """Process win for progressive coinflip"""
        # Calculate winnings
        winnings = bet_amount * multiplier

        # Get database connection
        db = Users()

        # Add credits to user (always give credits for winnings)
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "pcf",
            "bet": bet_amount,
            "amount": winnings,
            "multiplier": multiplier,
            "flips": flips,
            "timestamp": int(time.time())
        }
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [win_entry], "$slice": -100}}}
        )

        # Update server history
        server_db = Servers()
        server_data = server_db.fetch_server(ctx.guild.id)

        if server_data:
            server_win_entry = {
                "type": "win",
                "game": "pcf",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": winnings,
                "multiplier": multiplier,
                "flips": flips,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

            # Update server profit (negative value because server loses when player wins)
            profit = winnings - bet_amount
            server_db.update_server_profit(ctx, ctx.guild.id, -profit)

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings}}
        )

    async def process_loss(self, ctx, bet_amount, flips):
        """Process loss for progressive coinflip"""
        # Get database connection
        db = Users()

        # Add to loss history
        loss_entry = {
            "type": "loss",
            "game": "pcf",
            "bet": bet_amount,
            "amount": bet_amount,
            "flips": flips,
            "timestamp": int(time.time())
        }
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [loss_entry], "$slice": -100}}}
        )

        # Update server history
        server_db = Servers()
        server_data = server_db.fetch_server(ctx.guild.id)

        if server_data:
            server_loss_entry = {
                "type": "loss",
                "game": "pcf",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "flips": flips,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}}}
            )

            # Update server profit
            server_db.update_server_profit(ctx, ctx.guild.id, bet_amount)

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_lost": 1}}
        )



def setup(bot):
    bot.add_cog(ProgressiveCoinflipCog(bot))