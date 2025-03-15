import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class RockPaperScissorsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.choices = ["rock", "paper", "scissors"]
        self.choice_emojis = {
            "rock": "🪨",
            "paper": "📄",
            "scissors": "✂️"
        }

    @commands.command(aliases=["rps"])
    async def rockpaperscissors(self, ctx, bet_amount=None, opponent: discord.Member = None, currency_type: str = None):
        """Play Rock Paper Scissors against the bot or another player!"""
        # Show help if no arguments
        if not bet_amount:
            embed = discord.Embed(
                title="🪨 📄 ✂️ Rock Paper Scissors",
                description=(
                    "**Rock Paper Scissors** is a game of chance where you choose one of three options!\n\n"
                    "**Usage:** `!rps [opponent] <amount> [currency_type]`\n"
                    "**Example:** `!rps 100` or `!rps @Friend 100 credits`\n\n"
                    "- **Play against the bot or challenge another player**\n"
                    "- **Win and receive 1.96x your bet!**\n"
                    "- **If it's a draw, you get your bet back**\n"
                    "- **Games timeout after 120 seconds of inactivity**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # If we need to rearrange parameters (no opponent specified)
        if opponent and not bet_amount.isdigit() and not opponent.bot and not opponent.id == ctx.author.id:
            if bet_amount:
                currency_type = currency_type
                bet_amount = bet_amount
            else:
                currency_type = None
                bet_amount = opponent
                opponent = None

        # If opponent is the same as author or a bot, play against the bot instead
        if opponent and (opponent.id == ctx.author.id or opponent.bot):
            opponent = None

        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Rock Paper Scissors...",
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

        # Process bet using currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

        # If processing failed, return the error
        if not success:
            return await ctx.reply(embed=error_embed)

        # Extract needed values from bet_info
        tokens_used = bet_info["tokens_used"]
        credits_used = bet_info["credits_used"]
        total_bet = bet_info["total_bet_amount"]

        # Format bet description
        if tokens_used > 0 and credits_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used} tokens + {credits_used} credits"
        elif tokens_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used} tokens"
        else:
            bet_description = f"**Bet Amount:** {credits_used} credits"

        # Delete loading message
        await loading_message.delete()

        # Record game stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": total_bet}}
        )

        # Logic for playing against bot or another player
        if opponent:
            # PvP mode - Check if opponent exists in the database
            opponent_data = db.fetch_user(opponent.id)
            if opponent_data == False:
                # Refund the player
                if tokens_used > 0:
                    db.update_balance(ctx.author.id, tokens_used, "tokens", "$inc")
                if credits_used > 0:
                    db.update_balance(ctx.author.id, credits_used, "credits", "$inc")

                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Opponent Not Found",
                    description=f"{opponent.mention} doesn't have an account. Please wait for auto-registration or have them use `!signup`.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

            # Set up the game for PvP
            await self.start_pvp_game(ctx, opponent, tokens_used, credits_used, total_bet, bet_description)
        else:
            # PvE mode - Play against the bot
            await self.start_pve_game(ctx, tokens_used, credits_used, total_bet, bet_description)

    async def start_pve_game(self, ctx, tokens_used, credits_used, total_bet, bet_description):
        """Start a Rock Paper Scissors game against the bot"""
        # Create the enhanced initial embed
        embed = discord.Embed(
            title="🎮 Rock Paper Scissors Challenge 🎮",
            color=0x9b59b6
        )
        
        # Add player info field
        embed.add_field(
            name="Player",
            value=f"{ctx.author.mention}",
            inline=True
        )
        
        # Add opponent info field
        embed.add_field(
            name="Opponent",
            value="🤖 BetSync Bot",
            inline=True
        )
        
        # Add bet info field
        embed.add_field(
            name="💰 Bet Amount",
            value=bet_description,
            inline=False
        )
        
        # Add instructions
        embed.add_field(
            name="How to Play",
            value="Choose your move by clicking one of the buttons below.\nWin to receive **1.96x** your bet!",
            inline=False
        )
        
        embed.set_thumbnail(url=ctx.bot.user.avatar.url)
        embed.set_footer(text="BetSync Casino • Game will expire in 2 minutes", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

        # Create button view
        view = RockPaperScissorsView(self, ctx.author.id, tokens_used, credits_used, total_bet)

        # Send the game message
        game_message = await ctx.reply(embed=embed, view=view)

        # Store game info
        self.ongoing_games[ctx.author.id] = {
            "channel_id": ctx.channel.id,
            "message_id": game_message.id,
            "type": "pve",
            "view": view,
            "start_time": time.time()
        }

        # Start timeout task
        self.bot.loop.create_task(
            self.handle_game_timeout(ctx.author.id, ctx.channel.id, game_message.id, 120)
        )

    async def start_pvp_game(self, ctx, opponent, tokens_used, credits_used, total_bet, bet_description):
        """Start a Rock Paper Scissors game against another player"""
        # First, check if opponent already has an ongoing game
        if opponent.id in self.ongoing_games:
            # Refund the initiator
            db = Users()
            if tokens_used > 0:
                db.update_balance(ctx.author.id, tokens_used, "tokens", "$inc")
            if credits_used > 0:
                db.update_balance(ctx.author.id, credits_used, "credits", "$inc")

            embed = discord.Embed(
                title="<:no:1344252518305234987> | Opponent Busy",
                description=f"{opponent.mention} is already in a game. Please try again later.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Create the challenge embed
        challenge_embed = discord.Embed(
            title="🪨 📄 ✂️ Rock Paper Scissors Challenge",
            description=(
                f"{ctx.author.mention} has challenged {opponent.mention} to Rock Paper Scissors!\n\n"
                f"{bet_description}\n\n"
                f"{opponent.mention}, do you accept this challenge?"
            ),
            color=0x00FFAE
        )
        challenge_embed.set_footer(text="BetSync Casino • Challenge expires in 60 seconds")

        # Create accept/decline view
        view = ChallengeView(self, ctx.author, opponent, tokens_used, credits_used, total_bet)

        # Send the challenge message
        challenge_message = await ctx.reply(embed=challenge_embed, view=view)

        # Store game info for initiator
        self.ongoing_games[ctx.author.id] = {
            "channel_id": ctx.channel.id,
            "message_id": challenge_message.id,
            "type": "pvp_pending",
            "opponent_id": opponent.id,
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "total_bet": total_bet,
            "view": view,
            "start_time": time.time()
        }

        # Start timeout task for the challenge
        self.bot.loop.create_task(
            self.handle_challenge_timeout(ctx.author.id, opponent.id, ctx.channel.id, challenge_message.id, 60)
        )

    async def handle_pvp_game(self, initiator, opponent, channel_id, message_id, tokens_used, credits_used, total_bet):
        """Handle the PvP game after the challenge is accepted"""
        # Get the channel and message
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return self.clean_up_game(initiator.id, opponent.id)

        message = await channel.fetch_message(message_id)
        if not message:
            return self.clean_up_game(initiator.id, opponent.id)

        # Update the game status for both players
        self.ongoing_games[initiator.id] = {
            "channel_id": channel_id,
            "message_id": message_id,
            "type": "pvp_active",
            "opponent_id": opponent.id,
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "total_bet": total_bet,
            "choice": None,
            "start_time": time.time()
        }

        self.ongoing_games[opponent.id] = {
            "channel_id": channel_id,
            "message_id": message_id,
            "type": "pvp_active",
            "opponent_id": initiator.id,
            "choice": None,
            "start_time": time.time()
        }

        # Update the embed
        game_embed = discord.Embed(
            title="🪨 📄 ✂️ Rock Paper Scissors Battle",
            description=(
                f"{initiator.mention} vs {opponent.mention}\n\n"
                f"**Bet:** {total_bet} {'tokens' if tokens_used > 0 else 'credits'}\n\n"
                "Both players will receive a DM to make their choice.\n"
                "The results will be announced in this channel."
            ),
            color=0x00FFAE
        )
        game_embed.set_footer(text="BetSync Casino • Game will expire in 2 minutes")

        # Update the message
        await message.edit(embed=game_embed, view=None)

        # Send DMs to both players
        try:
            initiator_view = PlayerChoiceView(self, initiator.id, opponent.id)
            initiator_embed = discord.Embed(
                title="🪨 📄 ✂️ Make Your Choice",
                description=(
                    f"You're playing Rock Paper Scissors against {opponent.name}.\n\n"
                    "Select your move by clicking one of the buttons below."
                ),
                color=0x00FFAE
            )
            await initiator.send(embed=initiator_embed, view=initiator_view)
        except discord.Forbidden:
            # Can't DM initiator
            await self.handle_dm_error(channel, initiator, opponent, tokens_used, credits_used)
            return

        try:
            opponent_view = PlayerChoiceView(self, opponent.id, initiator.id)
            opponent_embed = discord.Embed(
                title="🪨 📄 ✂️ Make Your Choice",
                description=(
                    f"You're playing Rock Paper Scissors against {initiator.name}.\n\n"
                    "Select your move by clicking one of the buttons below."
                ),
                color=0x00FFAE
            )
            await opponent.send(embed=opponent_embed, view=opponent_view)
        except discord.Forbidden:
            # Can't DM opponent
            await self.handle_dm_error(channel, initiator, opponent, tokens_used, credits_used)
            return

        # Start timeout task
        self.bot.loop.create_task(
            self.handle_pvp_timeout(initiator.id, opponent.id, channel_id, message_id, 120)
        )

    async def handle_dm_error(self, channel, initiator, opponent, tokens_used, credits_used):
        """Handle the case where one player has DMs closed"""
        # Refund the initiator
        db = Users()
        if tokens_used > 0:
            db.update_balance(initiator.id, tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(initiator.id, credits_used, "credits", "$inc")

        # Clean up the games
        self.clean_up_game(initiator.id, opponent.id)

        # Send error message
        error_embed = discord.Embed(
            title="<:no:1344252518305234987> | DM Error",
            description="One or both players have their DMs closed. Please enable DMs to play PvP games.",
            color=0xFF0000
        )
        await channel.send(embed=error_embed, content=f"{initiator.mention} {opponent.mention}")

    async def process_pvp_choice(self, player_id, choice):
        """Process a player's choice in a PvP game"""
        if player_id not in self.ongoing_games or self.ongoing_games[player_id]["type"] != "pvp_active":
            return False

        # Store the player's choice
        self.ongoing_games[player_id]["choice"] = choice

        # Get opponent info
        opponent_id = self.ongoing_games[player_id]["opponent_id"]

        # Check if both players have made their choices
        if opponent_id in self.ongoing_games and self.ongoing_games[opponent_id]["choice"] is not None:
            # Both players have chosen, resolve the game
            channel_id = self.ongoing_games[player_id]["channel_id"]
            message_id = self.ongoing_games[player_id]["message_id"]

            player_choice = self.ongoing_games[player_id]["choice"]
            opponent_choice = self.ongoing_games[opponent_id]["choice"]

            # Get player and opponent objects
            player = self.bot.get_user(player_id)
            opponent = self.bot.get_user(opponent_id)

            # Determine who initiated the game (who placed the bet)
            if "tokens_used" in self.ongoing_games[player_id]:
                initiator_id = player_id
                initiator = player
                tokens_used = self.ongoing_games[player_id]["tokens_used"]
                credits_used = self.ongoing_games[player_id]["credits_used"]
                total_bet = self.ongoing_games[player_id]["total_bet"]
            else:
                initiator_id = opponent_id
                initiator = opponent
                tokens_used = self.ongoing_games[opponent_id]["tokens_used"]
                credits_used = self.ongoing_games[opponent_id]["credits_used"]
                total_bet = self.ongoing_games[opponent_id]["total_bet"]

            # Get the channel and message
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return self.clean_up_game(player_id, opponent_id)

            try:
                message = await channel.fetch_message(message_id)
            except:
                message = None

            # Determine the winner
            result, winner_id = self.determine_winner(player_id, player_choice, opponent_id, opponent_choice)

            # Handle the result
            db = Users()

            if result == "draw":
                # Draw - refund the bet
                if tokens_used > 0:
                    db.update_balance(initiator_id, tokens_used, "tokens", "$inc")
                if credits_used > 0:
                    db.update_balance(initiator_id, credits_used, "credits", "$inc")

                result_text = "It's a draw! The bet has been refunded."

                # Update player statistics
                db.collection.update_one(
                    {"discord_id": initiator_id},
                    {"$inc": {"total_played": 0}}  # No change since we already incremented
                )

                # Log the game in history
                history_entry = {
                    "type": "draw",
                    "game": "Rock Paper Scissors",
                    "bet": total_bet,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": initiator_id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )

            elif winner_id == initiator_id:
                # Initiator wins - double the bet
                winnings = total_bet * 2
                db.update_balance(initiator_id, winnings, "credits", "$inc")

                result_text = f"{initiator.mention} wins and receives **{winnings}** credits!"

                # Update player statistics
                db.collection.update_one(
                    {"discord_id": initiator_id},
                    {"$inc": {"total_won": 1, "total_earned": winnings}}
                )

                # Log the game in history
                history_entry = {
                    "type": "win",
                    "game": "Rock Paper Scissors",
                    "bet": total_bet,
                    "amount": winnings,
                    "multiplier": 2,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": initiator_id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )

                # Update server profit only in PVE games
                if game_info["type"] == "pve":
                    server_db = Servers()
                    server_profit = -(winnings - total_bet)  # Server loses the winnings minus the original bet
                    server_db.update_server_profit(channel.guild.id, server_profit, game="rockpaperscissors")

                    # Update server bet history
                    server_history = {
                        "type": "win",
                        "game": "Rock Paper Scissors",
                        "user_id": initiator_id,
                        "user_name": initiator.name,
                        "bet": total_bet,
                        "amount": winnings,
                        "multiplier": 2,
                        "timestamp": int(time.time())
                    }
                    server_db.update_history(channel.guild.id, server_history)

            else:
                # Opponent wins - initiator loses the bet
                result_text = f"{opponent.mention} wins! {initiator.mention} loses the bet."

                # Update player statistics
                db.collection.update_one(
                    {"discord_id": initiator_id},
                    {"$inc": {"total_lost": 1}}
                )

                # Log the game in history
                history_entry = {
                    "type": "loss",
                    "game": "Rock Paper Scissors",
                    "bet": total_bet,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": initiator_id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )

                # Update server profit only in PVE games
                if game_info["type"] == "pve":
                    server_db = Servers()
                    server_profit = total_bet  # Server gets the full bet
                    server_db.update_server_profit(channel.guild.id, server_profit, game="rockpaperscissors")

                    # Update server bet history
                    server_history = {
                        "type": "loss",
                        "game": "Rock Paper Scissors",
                        "user_id": initiator_id,
                        "user_name": initiator.name,
                        "bet": total_bet,
                        "timestamp": int(time.time())
                    }
                    server_db.update_history(channel.guild.id, server_history)

            # Set color based on result
            result_color = 0x2ecc71 if result == "win" else 0xe74c3c if result == "loss" else 0xf1c40f  # Green for win, Red for loss, Yellow for draw
            
            # Create the enhanced result embed
            result_embed = discord.Embed(
                title="🎲 Rock Paper Scissors Results 🎲",
                color=result_color
            )
            
            # Add player choice field with emoji
            result_embed.add_field(
                name=f"{player.name}'s Choice",
                value=f"**{player_choice.capitalize()}** {self.choice_emojis[player_choice]}",
                inline=True
            )
            
            # Add opponent choice field with emoji
            result_embed.add_field(
                name=f"{opponent.name}'s Choice",
                value=f"**{opponent_choice.capitalize()}** {self.choice_emojis[opponent_choice]}",
                inline=True
            )
            
            # Add a field separator
            result_embed.add_field(name="\u200b", value="\u200b", inline=False)
            
            # Add result text as its own field
            result_embed.add_field(
                name="Result",
                value=result_text,
                inline=False
            )
            
            result_embed.set_footer(text="BetSync Casino • Thanks for playing!", icon_url=player.guild.me.avatar.url if hasattr(player, "guild") else None)

            # Send or update the message
            if message:
                await message.edit(embed=result_embed, view=None)
            else:
                await channel.send(embed=result_embed, content=f"{player.mention} {opponent.mention}")

            # Clean up the game
            self.clean_up_game(player_id, opponent_id)

            return True

        return True

    async def process_bot_choice(self, player_id, player_choice):
        """Process the result of a game against the bot"""
        if player_id not in self.ongoing_games or self.ongoing_games[player_id]["type"] != "pve":
            return False

        # Get game info
        channel_id = self.ongoing_games[player_id]["channel_id"]
        message_id = self.ongoing_games[player_id]["message_id"]
        view = self.ongoing_games[player_id]["view"]

        # Get the channel and message
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return self.clean_up_game(player_id)

        try:
            message = await channel.fetch_message(message_id)
        except:
            return self.clean_up_game(player_id)

        # Bot makes a random choice
        bot_choice = random.choice(self.choices)

        # Determine the winner
        player = self.bot.get_user(player_id)
        result = self.determine_bot_winner(player_choice, bot_choice)

        # Get bet info from the view
        tokens_used = view.tokens_used
        credits_used = view.credits_used
        total_bet = view.total_bet

        # Handle the result
        db = Users()

        if result == "win":
            # Player wins - 1.96x the bet
            winnings = total_bet * 1.96
            db.update_balance(player_id, winnings, "credits", "$inc")

            result_text = f"{player.mention} wins and receives **{winnings}** credits!"

            # Update player statistics
            db.collection.update_one(
                {"discord_id": player_id},
                {"$inc": {"total_won": 1, "total_earned": winnings}}
            )

            # Log the game in history
            history_entry = {
                "type": "win",
                "game": "Rock Paper Scissors",
                "bet": total_bet,
                "amount": winnings,
                "multiplier": 1.96,
                "timestamp": int(time.time())
            }
            db.collection.update_one(
                {"discord_id": player_id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )

            # Update server profit
            server_db = Servers()
            server_profit = -(winnings - total_bet)  # Server loses the winnings minus the original bet
            server_db.update_server_profit(channel.guild.id, server_profit, game="rockpaperscissors")

            # Update server bet history
            server_history = {
                "type": "win",
                "game": "Rock Paper Scissors",
                "user_id": player_id,
                "user_name": player.name,
                "bet": total_bet,
                "amount": winnings,
                "multiplier": 1.96,
                "timestamp": int(time.time())
            }
            server_db.update_history(channel.guild.id, server_history)

        elif result == "loss":
            # Player loses the bet
            result_text = f"{player.mention} loses the bet."

            # Update player statistics
            db.collection.update_one(
                {"discord_id": player_id},
                {"$inc": {"total_lost": 1}}
            )

            # Log the game in history
            history_entry = {
                "type": "loss",
                "game": "Rock Paper Scissors",
                "bet": total_bet,
                "timestamp": int(time.time())
            }
            db.collection.update_one(
                {"discord_id": player_id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )

            # Update server profit (only in PVE games, which this is)
            server_db = Servers()
            server_profit = total_bet  # Server gets the full bet
            server_db.update_server_profit(channel.guild.id, server_profit, game="rockpaperscissors")

            # Update server bet history
            server_history = {
                "type": "loss",
                "game": "Rock Paper Scissors",
                "user_id": player_id,
                "user_name": player.name,
                "bet": total_bet,
                "timestamp": int(time.time())
            }
            server_db.update_history(channel.guild.id, server_history)

        else:  # Draw
            # Refund the bet
            if tokens_used > 0:
                db.update_balance(player_id, tokens_used, "tokens", "$inc")
            if credits_used > 0:
                db.update_balance(player_id, credits_used, "credits", "$inc")

            result_text = "It's a draw! The bet has been refunded."

            # Update player statistics
            db.collection.update_one(
                {"discord_id": player_id},
                {"$inc": {"total_played": 0}}  # No change since we already incremented
            )

            # Log the game in history
            history_entry = {
                "type": "draw",
                "game": "Rock Paper Scissors",
                "bet": total_bet,
                "timestamp": int(time.time())
            }
            db.collection.update_one(
                {"discord_id": player_id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )

        # Create the result embed
        result_embed = discord.Embed(
            title="🪨 📄 ✂️ Rock Paper Scissors Results",
            description=(
                f"{player.mention} chose **{player_choice}** {self.choice_emojis[player_choice]}\n"
                f"Bot chose **{bot_choice}** {self.choice_emojis[bot_choice]}\n\n"
                f"{result_text}"
            ),
            color=0x00FFAE
        )
        result_embed.set_footer(text="BetSync Casino")

        # Update the message
        await message.edit(embed=result_embed, view=None)

        # Clean up the game
        self.clean_up_game(player_id)

        return True

    def determine_bot_winner(self, player_choice, bot_choice):
        """Determine the winner between player and bot"""
        if player_choice == bot_choice:
            return "draw"

        if (player_choice == "rock" and bot_choice == "scissors") or \
           (player_choice == "paper" and bot_choice == "rock") or \
           (player_choice == "scissors" and bot_choice == "paper"):
            return "win"

        return "loss"

    def determine_winner(self, player1_id, player1_choice, player2_id, player2_choice):
        """Determine the winner between two players, returns (result, winner_id)"""
        if player1_choice == player2_choice:
            return "draw", None

        if (player1_choice == "rock" and player2_choice == "scissors") or \
           (player1_choice == "paper" and player2_choice == "rock") or \
           (player1_choice == "scissors" and player2_choice == "paper"):
            return "win", player1_id

        return "win", player2_id

    def clean_up_game(self, player1_id, player2_id=None):
        """Clean up game data for one or two players"""
        if player1_id in self.ongoing_games:
            del self.ongoing_games[player1_id]

        if player2_id and player2_id in self.ongoing_games:
            del self.ongoing_games[player2_id]

    async def handle_game_timeout(self, player_id, channel_id, message_id, timeout):
        """Handle timeout for single player games"""
        await asyncio.sleep(timeout)

        # Check if the game is still active
        if player_id not in self.ongoing_games:
            return

        game_info = self.ongoing_games[player_id]

        # Check if it's the same game instance
        if game_info["channel_id"] != channel_id or game_info["message_id"] != message_id:
            return

        # Game has timed out
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return self.clean_up_game(player_id)

        try:
            message = await channel.fetch_message(message_id)
        except:
            return self.clean_up_game(player_id)

        # Get player
        player = self.bot.get_user(player_id)

        # Refund the bet if it's a PvE game
        if game_info["type"] == "pve":
            view = game_info["view"]
            tokens_used = view.tokens_used
            credits_used = view.credits_used

            db = Users()
            if tokens_used > 0:
                db.update_balance(player_id, tokens_used, "tokens", "$inc")
            if credits_used > 0:
                db.update_balance(player_id, credits_used, "credits", "$inc")

        # Create timeout embed
        timeout_embed = discord.Embed(
            title="⏱️ Game Timed Out",
            description=f"The Rock Paper Scissors game has timed out. Any bets have been refunded.",
            color=0xFF0000
        )
        timeout_embed.set_footer(text="BetSync Casino")

        # Update the message
        await message.edit(embed=timeout_embed, view=None)

        # Try to notify the player via DM
        try:
            await player.send(
                embed=discord.Embed(
                    title="⏱️ Game Timed Out",
                    description="Your Rock Paper Scissors game has timed out. Any bets have been refunded.",
                    color=0xFF0000
                )
            )
        except:
            pass

        # Clean up the game
        self.clean_up_game(player_id)

    async def handle_pvp_timeout(self, player1_id, player2_id, channel_id, message_id, timeout):
        """Handle timeout for PvP games"""
        await asyncio.sleep(timeout)

        # Check if the game is still active
        if player1_id not in self.ongoing_games or player2_id not in self.ongoing_games:
            return

        game1_info = self.ongoing_games[player1_id]
        game2_info = self.ongoing_games[player2_id]

        # Check if it's the same game instance
        if game1_info["channel_id"] != channel_id or game1_info["message_id"] != message_id:
            return

        # Check if both players have made their choices
        if "choice" in game1_info and game1_info["choice"] is not None and \
           "choice" in game2_info and game2_info["choice"] is not None:
            return  # Game is already being processed

        # Game has timed out
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return self.clean_up_game(player1_id, player2_id)

        try:
            message = await channel.fetch_message(message_id)
        except:
            return self.clean_up_game(player1_id, player2_id)

        # Get players
        player1 = self.bot.get_user(player1_id)
        player2 = self.bot.get_user(player2_id)

        # Determine who initiated the game (who placed the bet)
        if "tokens_used" in game1_info:
            initiator_id = player1_id
            initiator = player1
            tokens_used = game1_info["tokens_used"]
            credits_used = game1_info["credits_used"]
        else:
            initiator_id = player2_id
            initiator = player2
            tokens_used = game2_info["tokens_used"]
            credits_used = game2_info["credits_used"]

        # Refund the bet
        db = Users()
        if tokens_used > 0:
            db.update_balance(initiator_id, tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(initiator_id, credits_used, "credits", "$inc")

        # Create timeout embed
        timeout_embed = discord.Embed(
            title="⏱️ Game Timed Out",
            description=f"The Rock Paper Scissors game between {player1.mention} and {player2.mention} has timed out. The bet has been refunded.",
            color=0xFF0000
        )
        timeout_embed.set_footer(text="BetSync Casino")

        # Update the message
        await message.edit(embed=timeout_embed, view=None)

        # Try to notify both players via DM
        timeout_dm_embed = discord.Embed(
            title="⏱️ Game Timed Out",
            description="Your Rock Paper Scissors game has timed out. Any bets have been refunded.",
            color=0xFF0000
        )

        try:
            await player1.send(embed=timeout_dm_embed)
        except:
            pass

        try:
            await player2.send(embed=timeout_dm_embed)
        except:
            pass

        # Clean up the game
        self.clean_up_game(player1_id, player2_id)

    async def handle_challenge_timeout(self, initiator_id, opponent_id, channel_id, message_id, timeout):
        """Handle timeout for challenge requests"""
        await asyncio.sleep(timeout)

        # Check if the challenge is still active
        if initiator_id not in self.ongoing_games:
            return

        game_info = self.ongoing_games[initiator_id]

        # Check if it's the same challenge
        if game_info["type"] != "pvp_pending" or game_info["channel_id"] != channel_id or game_info["message_id"] != message_id:
            return

        # Challenge has timed out
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return self.clean_up_game(initiator_id)

        try:
            message = await channel.fetch_message(message_id)
        except:
            return self.clean_up_game(initiator_id)

        # Get players
        initiator = self.bot.get_user(initiator_id)
        opponent = self.bot.get_user(opponent_id)

        # Refund the bet
        tokens_used = game_info["tokens_used"]
        credits_used = game_info["credits_used"]

        db = Users()
        if tokens_used > 0:
            db.update_balance(initiator_id, tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(initiator_id, credits_used, "credits", "$inc")

        # Create timeout embed
        timeout_embed = discord.Embed(
            title="⏱️ Challenge Expired",
            description=f"The Rock Paper Scissors challenge to {opponent.mention} has expired. The bet has been refunded.",
            color=0xFF0000
        )
        timeout_embed.set_footer(text="BetSync Casino")

        # Update the message
        for child in game_info["view"].children:
            child.disabled = True
        await message.edit(embed=timeout_embed, view=game_info["view"])

        # Clean up the game
        self.clean_up_game(initiator_id)


class RockPaperScissorsView(discord.ui.View):
    def __init__(self, cog, player_id, tokens_used, credits_used, total_bet):
        super().__init__(timeout=120)
        self.cog = cog
        self.player_id = player_id
        self.tokens_used = tokens_used
        self.credits_used = credits_used
        self.total_bet = total_bet

    @discord.ui.button(label="Rock", style=discord.ButtonStyle.primary, emoji="🪨")
    async def rock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)

        # Properly acknowledge the interaction
        await interaction.response.defer(ephemeral=True)

        # Send styled feedback message to user
        choice_embed = discord.Embed(
            title="🎮 Your Choice",
            description="You selected **Rock** 🪨",
            color=0x3498db
        )
        choice_embed.set_footer(text="BetSync Casino", icon_url=interaction.client.user.avatar.url)
        await interaction.followup.send(embed=choice_embed, ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Process the choice
        await self.cog.process_bot_choice(self.player_id, "rock")

    @discord.ui.button(label="Paper", style=discord.ButtonStyle.primary, emoji="📄")
    async def paper_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)

        # Properly acknowledge the interaction
        await interaction.response.defer(ephemeral=True)

        # Send styled feedback message to user
        choice_embed = discord.Embed(
            title="🎮 Your Choice",
            description="You selected **Paper** 📄",
            color=0x3498db
        )
        choice_embed.set_footer(text="BetSync Casino", icon_url=interaction.client.user.avatar.url)
        await interaction.followup.send(embed=choice_embed, ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Process the choice
        await self.cog.process_bot_choice(self.player_id, "paper")

    @discord.ui.button(label="Scissors", style=discord.ButtonStyle.primary, emoji="✂️")
    async def scissors_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)

        # Properly acknowledge the interaction
        await interaction.response.defer(ephemeral=True)

        # Send styled feedback message to user
        choice_embed = discord.Embed(
            title="🎮 Your Choice",
            description="You selected **Scissors** ✂️",
            color=0x3498db
        )
        choice_embed.set_footer(text="BetSync Casino", icon_url=interaction.client.user.avatar.url)
        await interaction.followup.send(embed=choice_embed, ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Process the choice
        await self.cog.process_bot_choice(self.player_id, "scissors")


class PlayerChoiceView(discord.ui.View):
    def __init__(self, cog, player_id, opponent_id):
        super().__init__(timeout=120)
        self.cog = cog
        self.player_id = player_id
        self.opponent_id = opponent_id

    @discord.ui.button(label="Rock", style=discord.ButtonStyle.primary, emoji="🪨")
    async def rock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)

        # Properly acknowledge the interaction
        await interaction.response.defer(ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Process the choice
        await interaction.followup.send("You chose **Rock** 🪨. Waiting for your opponent...", ephemeral=True)
        await self.cog.process_pvp_choice(self.player_id, "rock")

    @discord.ui.button(label="Paper", style=discord.ButtonStyle.primary, emoji="📄")
    async def paper_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)

        # Properly acknowledge the interaction
        await interaction.response.defer(ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Process the choice
        await interaction.followup.send("You chose **Paper** 📄. Waiting for your opponent...", ephemeral=True)
        await self.cog.process_pvp_choice(self.player_id, "paper")

    @discord.ui.button(label="Scissors", style=discord.ButtonStyle.primary, emoji="✂️")
    async def scissors_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)

        # Properly acknowledge the interaction
        await interaction.response.defer(ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Process the choice
        await interaction.followup.send("You chose **Scissors** ✂️. Waiting for your opponent...", ephemeral=True)
        await self.cog.process_pvp_choice(self.player_id, "scissors")


class ChallengeView(discord.ui.View):
    def __init__(self, cog, initiator, opponent, tokens_used, credits_used, total_bet):
        super().__init__(timeout=60)
        self.cog = cog
        self.initiator = initiator
        self.opponent = opponent
        self.tokens_used = tokens_used
        self.credits_used = credits_used
        self.total_bet = total_bet

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This challenge is not for you.", ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Start the game
        await interaction.response.defer()
        await self.cog.handle_pvp_game(
            self.initiator, 
            self.opponent, 
            interaction.channel.id, 
            interaction.message.id, 
            self.tokens_used, 
            self.credits_used, 
            self.total_bet
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This challenge is not for you.", ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Refund the initiator
        db = Users()
        if self.tokens_used > 0:
            db.update_balance(self.initiator.id, self.tokens_used, "tokens", "$inc")
        if self.credits_used > 0:
            db.update_balance(self.initiator.id, self.credits_used, "credits", "$inc")

        # Update the message
        declined_embed = discord.Embed(
            title="❌ Challenge Declined",
            description=f"{self.opponent.mention} has declined the Rock Paper Scissors challenge. The bet has been refunded.",
            color=0xFF0000
        )
        declined_embed.set_footer(text="BetSync Casino")

        await interaction.message.edit(embed=declined_embed, view=self)

        # Clean up the game
        if self.initiator.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.initiator.id]


def setup(bot):
    bot.add_cog(RockPaperScissorsCog(bot))