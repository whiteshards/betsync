import os
import discord
import random
import asyncio
import time
import io
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import process_bet_amount
import aiohttp

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount):
        super().__init__(timeout=240)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        #self.currency_used = currency_used
        self.message = None
        self.author_id = ctx.author.id

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self,button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            try:
                return await interaction.response.send_message("This is not your game!", ephemeral=True)
            except discord.errors.NotFound:
                return

        # Disable the button to prevent spam clicks
        for item in self.children:
            item.disabled = True
        
        try:
            await interaction.message.edit(view=self)
        except discord.errors.NotFound:
            pass

        # Show processing message
        try:
            await interaction.response.send_message("Starting a new game...", ephemeral=True)
        except discord.errors.NotFound:
            # Interaction expired, send a regular message instead
            await interaction.followup.send("Starting a new game...", ephemeral=True)

        try:
            # Get the context for the new game
            #ctx = await self.cog.bot.get_context(self.message)

            # Import the currency helper
            #from Cogs.utils.currency_helper import process_bet_amount

            # Process bet using currency helper
            #success, bet_info, error_embed = await process_bet_amount(self.ctx, self.bet_amount, self.currency_used, None)
            #if not success:
                #return await interaction.followup.send(embed=error_embed)

            # Launch a new game
            await self.cog.hilo(self.ctx, self.bet_amount)

        except Exception as e:
            # Handle any errors
            print(f"Error in Play Again: {e}")
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> Error Starting New Game",
                description=f"There was a problem starting a new HiLo game. Please try again later.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class HiLoView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, deck, current_card, current_multiplier=1.0, timeout=240):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        #self.currency_used = currency_used
        self.deck = deck
        self.current_card = current_card
        self.current_multiplier = current_multiplier
        self.current_winnings = bet_amount * current_multiplier
        self.message = None
        self.game_over = False
        self.previous_cards = []  # Track previous cards for display
        self.high_profit = 0      # Track potential high profit
        self.low_profit = 0       # Track potential low profit
        self.skips_used = 0       # Track how many skips have been used

    async def on_timeout(self):
        """Handle timeout - refund the bet and notify the user"""
        if self.game_over:
            return  # Game already ended, no need for timeout handling

        # Get database
        from Cogs.utils.mongo import Users
        db = Users()

        # Refund the bet amount in the appropriate currency
        try:
            # Process refund
            db.update_balance(self.ctx.author.id, self.bet_amount)

            # Create timeout message
            embed = discord.Embed(
                title="⏱️ HiLo Game Timeout",
                description=f"Your HiLo game has timed out and your bet of **{self.bet_amount} {self.currency_used}** has been refunded.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="BetSync Casino • Game expired due to inactivity")

            # Disable all buttons
            for child in self.children:
                child.disabled = True

            # Send timeout notification and update the game message
            await self.message.edit(embed=embed, view=self)
            await self.ctx.channel.send(f"{self.ctx.author.mention} Your HiLo game has timed out and your bet has been refunded.")

            # Remove from ongoing games
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

        except Exception as e:
            print(f"Error handling HiLo timeout: {e}")
            # Try to send error notification
            try:
                await self.ctx.channel.send(f"{self.ctx.author.mention} Your HiLo game has timed out. Error processing refund.")
            except:
                pass

    @discord.ui.button(label="HIGHER", style=discord.ButtonStyle.primary, emoji="⬆️")
    async def higher_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        await interaction.response.defer()
        await self.process_round(interaction, "high")

    @discord.ui.button(label="LOWER", style=discord.ButtonStyle.primary, emoji="⬇️")
    async def lower_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        await interaction.response.defer()
        await self.process_round(interaction, "low")

    @discord.ui.button(label="SKIP", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        await interaction.response.defer()
        await self.process_round(interaction, "skip")

    @discord.ui.button(label="CASH OUT", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        await interaction.response.defer()
        await self.cash_out(interaction)

    async def cash_out(self, interaction):
        """Cash out current winnings"""
        self.game_over = True
        winnings = self.current_winnings

        # Create final game image showing cash out
        game_image = await self.cog.create_game_image(self.current_card, self.previous_cards, 
                                                     0, 0, winnings,
                                                     cashed_out=True, current_winnings=self.current_winnings)

        # Get database connections
        from Cogs.utils.mongo import Users, Servers
        db = Users()

        # Process winnings directly with mongo
        try:
            # Update user's balance
            update_success = db.update_balance(self.ctx.author.id, winnings)

            if not update_success:
                # Handle the error
                error_embed = discord.Embed(
                    title="⚠️ Error Processing Winnings",
                    description=f"There was an error processing your winnings. Please contact support.",
                    color=discord.Color.red()
                )
                return await interaction.response.edit_message(embed=error_embed)

            # Update user stats
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {"$inc": {"total_won": 1, "total_earned": winnings}}
            )

            # Update the embed
            embed = discord.Embed(
                title="<:yes:1355501647538815106> CASHED OUT",
                description=f"**{self.ctx.author.name}** cashed out with `{winnings:.2f} points`",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Multiplier",
                value=f"{self.current_multiplier:.2f}x",
                inline=True
            )

            embed.add_field(
                name="Final Winnings", 
                value=f"`{winnings:.2f} points`",
                inline=True
            )

            # Add card history field if we have previous cards
            if self.previous_cards:
                # Format card history with newest cards first
                card_history = []
                for i, card in enumerate(self.previous_cards):
                    card_emoji = self.get_card_emoji(card)
                    if i == 0 and len(self.previous_cards) == len(card_history) + 1:
                        card_history.append(f"**Start: {card_emoji}**")
                    else:
                        card_history.append(card_emoji)

                # Join the cards with arrows in between
                card_history_text = " → ".join(card_history)
                if len(card_history) > 0:
                    embed.add_field(
                        name="Card History",
                        value=card_history_text,
                        inline=False
                    )

            embed.set_footer(text=f"BetSync Casino • Play again with the button below")

            # Set the game image
            file = discord.File(fp=game_image, filename="hilo_game.png")
            embed.set_image(url="attachment://hilo_game.png")

            # Add to user and server history
            timestamp = int(time.time())
            history_entry = {
                "type": "win",
                "game": "hilo",
                "amount": winnings,
                "bet": self.bet_amount,
                "multiplier": self.current_multiplier,
                "cards_revealed": len(self.previous_cards) + 1,
                "final_card": self.get_card_emoji(self.current_card),
                "timestamp": timestamp
            }

            db = Users()
            db.update_history(self.ctx.author.id, history_entry)

            # Update server history
            server_db = Servers()
            server_history_entry = history_entry.copy()
            server_history_entry.update({
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name
            })
            server_db.update_history(self.ctx.guild.id, server_history_entry)

            # Remove from ongoing games
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

            # Create a new view with just the Play Again button
            view = PlayAgainView(self.cog, self.ctx, self.bet_amount)
            view.message = self.message

            await interaction.message.edit(embed=embed, file=file, view=view)

        except Exception as e:
            # Handle any unexpected errors
            print(f"Error processing HiLo cash out: {e}")
            error_embed = discord.Embed(
                title="⚠️ Error Processing Winnings",
                description=f"There was an error processing your winnings. Please try again or contact support.",
                color=discord.Color.red()
            )
            error_embed.set_footer(text="BetSync Casino • Error logged")
            await interaction.message.edit(embed=error_embed)

    async def process_round(self, interaction, choice):
        """Process a round of HiLo"""
        if self.game_over or len(self.deck) == 0:
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            return

        # Get the next card
        new_card = self.deck.pop(0)

        # Skip just changes the card without affecting winnings
        if choice == "skip":
            # Check if the player has already used their skip
            if self.skips_used >= 1:
                error_embed = discord.Embed(
                    title="❌ Skip Limit Reached",
                    description="You can only skip one round per game!",
                    color=discord.Color.red()
                )
                await interaction.message.edit(embed=error_embed, ephemeral=True)
                return

            # Increment skip counter
            self.skips_used += 1

            # Save current card to previous cards before updating
            self.previous_cards.append(self.current_card)
            # Keep only the last 5 previous cards to avoid crowding
            if len(self.previous_cards) > 5:
                self.previous_cards.pop(0)

            self.current_card = new_card

            # Update potential profits
            self.calculate_potential_profits()

            # Create game image
            game_image = await self.cog.create_game_image(self.current_card, self.previous_cards, 
                                                          self.high_profit, self.low_profit, 
                                                          self.current_winnings,
                                                          current_winnings=self.current_winnings)

            # Update the embed with the image
            embed = self.create_game_embed()
            file = discord.File(fp=game_image, filename="hilo_game.png")
            embed.set_image(url="attachment://hilo_game.png")

            try:
                await interaction.message.edit(embed=embed, file=file, view=self)
            except discord.errors.HTTPException as e:
                print(f"HTTP Error when editing message: {e}")
                # Try sending a new message if editing fails
                await interaction.followup.send("There was an issue updating the game. Here's the current state:", embed=embed, file=file, view=self)

            return

        # Check if the guess is correct
        current_value = self.get_card_value(self.current_card)
        new_value = self.get_card_value(new_card)

        # Determine if player won
        won = False
        if choice == "high":
            # Win if new card is higher or same card from different suit
            if new_value > current_value or (new_value == current_value and new_card[1] != self.current_card[1]):
                won = True
        elif choice == "low":
            # Win if new card is lower
            if new_value < current_value:
                won = True

        # Update the UI based on result
        if won:
            # Calculate new multiplier based on probability
            probability = self.calculate_probability(choice)
            new_multiplier = self.calculate_multiplier(probability)

            # Save current card to previous cards
            self.previous_cards.append(self.current_card)
            # Keep only the last 5 previous cards
            if len(self.previous_cards) > 5:
                self.previous_cards.pop(0)

            # Update game state
            self.current_multiplier *= new_multiplier
            self.current_winnings = self.bet_amount * self.current_multiplier
            self.current_card = new_card

            # Update potential profits
            self.calculate_potential_profits()

            # Create game image
            game_image = await self.cog.create_game_image(self.current_card, self.previous_cards, 
                                                          self.high_profit, self.low_profit, 
                                                          self.current_winnings,
                                                          current_winnings=self.current_winnings)

            # Update the embed with the image
            embed = self.create_game_embed(win=True)
            file = discord.File(fp=game_image, filename="hilo_game.png")
            embed.set_image(url="attachment://hilo_game.png")

            try:
                await interaction.message.edit(embed=embed, file=file, view=self)
            except discord.errors.HTTPException as e:
                print(f"HTTP Error when editing message: {e}")
                # Try sending a new message if editing fails
                await interaction.followup.send("There was an issue updating the game. Here's the current state:", embed=embed, file=file, view=self)
        else:
            # Game over - player lost
            self.game_over = True

            # Add the last card to previous cards for the final image
            self.previous_cards.append(self.current_card)
            if len(self.previous_cards) > 5:
                self.previous_cards.pop(0)

            # Create final game image showing the losing card
            game_image = await self.cog.create_game_image(new_card, self.previous_cards, 
                                                          0, 0, 0,
                                                          game_over=True, lost_choice=choice, current_winnings=self.current_winnings)

            # Create losing embed
            embed = discord.Embed(
                title="🃏 HiLo - GAME OVER 💔",
                description=f"**{self.ctx.author.name}** guessed {choice.upper()} and lost!",
                color=discord.Color.red()
            )

            embed.add_field(
                name="Potential Winnings Lost", 
                value=f"`{self.current_winnings:.2f} points`",
                inline=True
            )

            # Add card history field 
            if self.previous_cards:
                # Format card history
                card_history = []
                for i, card in enumerate(self.previous_cards):
                    card_emoji = self.get_card_emoji(card)
                    if i == 0 and len(self.previous_cards) == len(card_history) + 1:
                        card_history.append(f"**Start: {card_emoji}**")
                    else:
                        card_history.append(card_emoji)

                # Add the final losing card
                card_history.append(f"❌ {self.get_card_emoji(new_card)}")

                # Join the cards with arrows in between
                card_history_text = " → ".join(card_history)
                if len(card_history) > 0:
                    embed.add_field(
                        name="Card History",
                        value=card_history_text,
                        inline=False
                    )

            embed.set_footer(text="BetSync Casino • Play again with the button below")

            # Set the game image
            file = discord.File(fp=game_image, filename="hilo_game.png")
            embed.set_image(url="attachment://hilo_game.png")

            # Add to history
            timestamp = int(time.time())
            history_entry = {
                "type": "loss",
                "game": "hilo",
                "amount": self.bet_amount,
                "bet": self.bet_amount,
                "multiplier": 0,
                "cards_revealed": len(self.previous_cards) + 1,
                "final_card": self.get_card_emoji(new_card),
                "choice": choice,
                "timestamp": timestamp
            }

            db = Users()
            db.update_history(self.ctx.author.id, history_entry)

            # Update server history
            server_db = Servers()
            server_history_entry = history_entry.copy()
            server_history_entry.update({
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name
            })
            server_db.update_history(self.ctx.guild.id, server_history_entry)

            # Remove from ongoing games
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

            # Create play again view
            view = PlayAgainView(self.cog, self.ctx, self.bet_amount)
            view.message = self.message

            # Update the message with the embed and play again button
            await interaction.message.edit(embed=embed, file=file, view=view)

    def create_game_embed(self, win=False):
        """Create the game embed"""
        color = discord.Color.gold()
        if win:
            title = "🃏 HiLo - CORRECT! 🎉"
            color = discord.Color.green()
        else:
            title = "🃏 HiLo - Choose Wisely"

        embed = discord.Embed(
            title=title,
            description=f"Will the next card be higher or lower than the current one?",
            color=color
        )

        embed.add_field(
            name="Current Multiplier",
            value=f"{self.current_multiplier:.2f}x",
            inline=True
        )

        embed.add_field(
            name="Current Winnings", 
            value=f"`{self.current_winnings:.2f} points`",
            inline=True
        )

        if self.skips_used > 0:
            embed.add_field(
                name="Skip Used",
                value=f"{self.skips_used}/1",
                inline=True
            )

        # Add card history field if we have previous cards
        if self.previous_cards:
            # Format card history with newest cards first
            card_history = []
            for i, card in enumerate(self.previous_cards):
                card_emoji = self.get_card_emoji(card)
                if i == 0 and len(self.previous_cards) == len(card_history) + 1:
                    card_history.append(f"**Start: {card_emoji}**")
                else:
                    card_history.append(card_emoji)

            # Join the cards with arrows in between
            card_history_text = " → ".join(card_history)
            if len(card_history) > 0:
                embed.add_field(
                    name="Card History",
                    value=card_history_text,
                    inline=False
                )

        embed.set_footer(text=f"BetSync Casino • {len(self.deck)} cards left in deck")
        return embed

    def get_card_emoji(self, card):
        """Get emoji representation of a card"""
        value, suit = card

        # Map suit to emoji
        suit_emoji = {
            "hearts": "♥️",
            "diamonds": "♦️",
            "clubs": "♣️",
            "spades": "♠️"
        }

        # Map value to display value
        value_map = {
            1: "A",
            11: "J",
            12: "Q", 
            13: "K"
        }

        display_value = value_map.get(value, str(value))
        return f"{display_value} {suit_emoji[suit]}"

    def get_card_value(self, card):
        """Get numerical value of a card"""
        value, _ = card
        return value

    def calculate_probability(self, choice):
        """Calculate probability of winning based on current card and choice"""
        current_value = self.get_card_value(self.current_card)

        # Count higher, lower, and equal cards in the deck
        higher_count = 0
        lower_count = 0
        equal_count = 0

        for card in self.deck:
            card_value = self.get_card_value(card)
            if card_value > current_value:
                higher_count += 1
            elif card_value < current_value:
                lower_count += 1
            else:
                # Same value, different suit
                if card[1] != self.current_card[1]:
                    equal_count += 1

        # Calculate probability based on choice
        if choice == "high":
            return (higher_count + equal_count) / len(self.deck) if len(self.deck) > 0 else 0
        elif choice == "low":
            return lower_count / len(self.deck) if len(self.deck) > 0 else 0
        return 0

    def calculate_multiplier(self, probability):
        """Calculate round multiplier based on probability"""
        house_edge = 0.10  # 10% house edge
        if probability <= 0:
            return 1.0  # Safety check
        return (1.0 - house_edge) / probability

    def calculate_potential_profits(self):
        """Calculate potential profits for high and low bets"""
        # Calculate high probability and multiplier
        high_probability = self.calculate_probability("high")
        high_multiplier = self.calculate_multiplier(high_probability)
        self.high_profit = self.current_winnings * high_multiplier

        # Calculate low probability and multiplier
        low_probability = self.calculate_probability("low")
        low_multiplier = self.calculate_multiplier(low_probability)
        self.low_profit = self.current_winnings * low_multiplier
    
    async def send_curse_webhook(self, user, game, bet_amount, multiplier):
        """Sends a message to the curse webhook."""
        webhook_url = os.getenv("LOSE_WEBHOOK")
        if not webhook_url:
            print("LOSE_WEBHOOK not set in environment variables.")
            return

        embed = discord.Embed(
            title="Curse Triggered",
            description=f"User {user.name} ({user.id}) lost in {game} due to curse.",
            color=discord.Color.red()
        )
        embed.add_field(name="Bet Amount", value=f"{bet_amount}", inline=True)
        embed.add_field(name="Multiplier", value=f"{multiplier:.2f}x", inline=True)

        payload = {
            "embeds": [embed.to_dict()]
        }

        async with aiohttp.ClientSession() as session:
            try:
                await session.post(webhook_url, json=payload)
            except Exception as e:
                print(f"Error sending webhook: {e}")

class HiLo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.card_cache = {}  # Cache for loaded card images

    async def create_game_image(self, current_card, previous_cards, high_profit, low_profit, total_profit, 
                               game_over=False, lost_choice=None, cashed_out=False, current_winnings=0):
        """Generate the game image similar to the provided example"""
        # Create base canvas (dark blue background)
        width, height = 1000, 500  # Reduced height since we're not showing previous cards
        bg_color = (12, 26, 38)  # Darker blue background matching reference
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        # Try to load font, fall back to default if not found
        try:
            font_path = "roboto.ttf"
            small_font = ImageFont.truetype(font_path, 16)
            medium_font = ImageFont.truetype(font_path, 20)
            large_font = ImageFont.truetype(font_path, 28)  # Increased font size for card guides
        except Exception:
            small_font = ImageFont.load_default()
            medium_font = ImageFont.load_default()
            large_font = ImageFont.load_default()

        # Draw card value guides at the left and right (K and A) - larger with better styling
        self.draw_card_guides(draw, width, large_font, small_font)

        # Draw the current card in the center - larger size
        current_card_img = await self.get_card_image(current_card)
        # Make current card 20% larger
        new_width, new_height = int(current_card_img.width * 1.2), int(current_card_img.height * 1.2)
        current_card_img = current_card_img.resize((new_width, new_height))
        current_card_pos = (width//2 - new_width//2, height//2 - 180)
        image.paste(current_card_img, current_card_pos, current_card_img.convert("RGBA"))

        # Draw profit information bar
        self.draw_profit_bar(draw, width, height, high_profit, low_profit, total_profit, small_font, current_winnings)

        # Convert to bytes for Discord
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer

    def draw_card_guides(self, draw, width, large_font, small_font):
        """Draw the card value guides (K and A) with explanations"""
        # Card guide styling
        guide_border_color = (30, 40, 50)
        guide_text_color = (120, 140, 150)

        # Left side - K guide (larger and more visible)
        guide_width, guide_height = 120, 150
        left_x = 120
        guide_y = 150

        # Draw rounded rectangle for K guide
        draw.rectangle(
            [left_x - guide_width//2, guide_y, left_x + guide_width//2, guide_y + guide_height], 
            fill=(20, 30, 40),
            outline=guide_border_color, 
            width=2
        )

        # Draw K and arrow
        draw.text((left_x, guide_y + 40), "K", fill=guide_text_color, font=large_font, anchor="mm")
        #draw.text((left_x, guide_y + 80), "↑", fill=guide_text_color, font=large_font, anchor="mm")

        # Draw explanation text below guide box
        draw.text(
            (left_x, guide_y + guide_height + 30), 
            "KING BEING", 
            fill=guide_text_color, 
            font=small_font, 
            anchor="mm"
        )
        draw.text(
            (left_x, guide_y + guide_height + 50), 
            "THE HIGHEST", 
            fill=guide_text_color, 
            font=small_font, 
            anchor="mm"
        )

        # Right side - A guide (larger and more visible)
        right_x = width - 120

        # Draw rounded rectangle for A guide
        draw.rectangle(
            [right_x - guide_width//2, guide_y, right_x + guide_width//2, guide_y + guide_height], 
            fill=(20, 30, 40),
            outline=guide_border_color, 
            width=2
        )

        # Draw A and arrow
        draw.text((right_x, guide_y + 40), "A", fill=guide_text_color, font=large_font, anchor="mm")
        #draw.text((right_x, guide_y + 80), "↓", fill=guide_text_color, font=large_font, anchor="mm")

        # Draw explanation text below guide box
        draw.text(
            (right_x, guide_y + guide_height + 30), 
            "ACE BEING", 
            fill=guide_text_color, 
            font=small_font, 
            anchor="mm"
        )
        draw.text(
            (right_x, guide_y + guide_height + 50), 
            "THE LOWEST", 
            fill=guide_text_color, 
            font=small_font, 
            anchor="mm"
        )

    def draw_profit_bar(self, draw, width, height, high_profit, low_profit, total_profit, font, current_winnings):
        """Draw the profit information bar with improved styling matching reference"""
        # Draw profit bar background
        bar_y = 420
        bar_height = 70
        draw.rectangle([20, bar_y, width - 20, bar_y + bar_height], fill=(25, 35, 45))

        # Divide into three sections
        section_width = (width - 40) // 3

        # Helper function to format profit values
        def format_profit(value):
            return f"{value:.2f}"  # Always 2 decimal places

        # Try to load arial font for profit bar text
        try:
            profit_font_small = ImageFont.truetype("arial.ttf", 16)
            profit_font_large = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            # Fallback to default/provided font if arial.ttf can't be loaded
            profit_font_small = font
            profit_font_large = font

        # Higher profit section
        high_multiplier = high_profit/total_profit if total_profit else 0
        draw.text(
            (30 + section_width//2, bar_y + 20), 
            f"Profit Higher ({self.format_multiplier(high_multiplier)}×)", 
            fill=(180, 200, 220), 
            font=profit_font_small, 
            anchor="mm"
        )
        draw.text(
            (30 + section_width//2, bar_y + 50), 
            f"{format_profit(high_profit)} points", 
            fill=(255, 255, 255), 
            font=profit_font_large, 
            anchor="mm"
        )

        # Lower profit section
        low_multiplier = low_profit/total_profit if total_profit else 0
        draw.text(
            (30 + section_width + section_width//2, bar_y + 20), 
            f"Profit Lower ({self.format_multiplier(low_multiplier)}×)", 
            fill=(180, 200, 220), 
            font=profit_font_small, 
            anchor="mm"
        )
        draw.text(
            (30 + section_width + section_width//2, bar_y + 50), 
            f"{format_profit(low_profit)} points", 
            fill=(255, 255, 255), 
            font=profit_font_large, 
            anchor="mm"
        )

        # Total profit section with current multiplier
        #current_mult = total_profit/current_winnings if current_winnings and total_profit != current_winnings else 1.0
        draw.text(
            (30 + 2*section_width + section_width//2, bar_y + 20), 
            "Current Winnings", 
            fill=(180, 200, 220), 
            font=profit_font_small, 
            anchor="mm"
        )
        draw.text(
            (30 + 2*section_width + section_width//2, bar_y + 50), 
            f"{format_profit(total_profit)} points", 
            fill=(255, 255, 255), 
            font=profit_font_large, 
            anchor="mm"
        )

    def format_multiplier(self, value):
        """Format multiplier to show 2 decimal places"""
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return "0.00"

    # Previous cards drawing method removed as requested - now displaying in embed

    async def get_card_image(self, card):
        """Get the card image from assets folder or cache"""
        value, suit = card

        # Convert card value to filename format
        value_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
        card_value = value_map.get(value, str(value))

        # Generate file path
        card_key = f"{suit}_{card_value}"

        # Check if card is in cache
        if card_key in self.card_cache:
            return self.card_cache[card_key]

        # Load the card image
        try:
            card_path = f"assests/{suit}_{card_value}.png"
            card_img = Image.open(card_path).convert("RGBA")

            # Resize to standard size
            card_img = card_img.resize((120, 180))

            # Store in cache
            self.card_cache[card_key] = card_img
            return card_img
        except Exception as e:
            print(f"Error loading card image: {e}")
            # Create a blank white card as fallback
            card_img = Image.new("RGBA", (120, 180), (255, 255, 255, 255))
            draw = ImageDraw.Draw(card_img)

            # Add card value and suit text
            suit_symbol = {"hearts": "♥", "diamonds": "♦", "clubs": "♣", "spades": "♠"}
            text_color = (255, 0, 0) if suit in ["hearts", "diamonds"] else (0, 0, 0)

            draw.text((60, 90), f"{card_value}\n{suit_symbol.get(suit, '')}", 
                     fill=text_color, anchor="mm")

            self.card_cache[card_key] = card_img
            return card_img

    def get_card_image_sync(self, card):
        """Synchronous version of get_card_image to use when drawing multiple cards"""
        value, suit = card

        # Convert card value to filenameformat
        value_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
        card_value = value_map.get(value, str(value))

        # Generate file path
        card_key = f"{suit}_{card_value}"

        # Check if card is in cache
        if card_key in self.card_cache:
            return self.card_cache[card_key]

        # Load the card image
        try:
            card_path = f"assests/{suit}_{card_value}.png"
            card_img = Image.open(card_path).convert("RGBA")

            # Resize to standard size
            card_img = card_img.resize((120, 180))

            # Store in cache
            self.card_cache[card_key] = card_img
            return card_img
        except Exception as e:
            print(f"Error loading card image: {e}")
            # Create a blank white card as fallback
            card_img = Image.new("RGBA", (120, 180), (255, 255, 255, 255))
            draw = ImageDraw.Draw(card_img)

            # Add card value and suit text
            suit_symbol = {"hearts": "♥", "diamonds": "♦", "clubs": "♣", "spades": "♠"}
            text_color = (255, 0, 0) if suit in ["hearts", "diamonds"] else (0, 0, 0)

            draw.text((60, 90), f"{card_value}\n{suit_symbol.get(suit, '')}", 
                     fill=text_color, anchor="mm")

            self.card_cache[card_key] = card_img
            return card_img

    def add_to_history(self, ctx, user_id, server_id, amount, bet_amount, result_type, game):
        """Add game result to user and server history"""
        try:
            server_db = Servers()

            # Update server profit
            if result_type == "win":
                server_db.update_server_profit(ctx, server_id, (bet_amount - amount), game="hilo")
            else:
                server_db.update_server_profit(ctx, server_id, bet_amount, game="hilo")

        except Exception as e:
            print(f"Error updating history: {e}")

    def create_deck(self):
        """Create a standard deck of cards"""
        values = list(range(1, 14))  # 1 to 13 (Ace to King)
        suits = ["hearts", "diamonds", "clubs", "spades"]

        deck = [(value, suit) for value in values for suit in suits]
        random.shuffle(deck)
        return deck

    @commands.command(aliases=["hl"])
    async def hilo(self, ctx, bet_amount: str = None):
        """Play the HiLo card game - guess if the next card will be higher or lower!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🃏 How to Play HiLo",
                description=(
                    "**HiLo** is a card game where you bet on whether the next card will be higher or lower than the current one!\n\n"
                    "**Usage:** `!hilo <amount>`\n"
                    "**Example:** `!hilo 100`\n\n"
                    "- **You'll be shown a card and need to decide if the next one will be higher or lower**\n"
                    "- **The multiplier changes based on your odds of winning each round**\n"
                    "- **Continue playing to increase your multiplier or cash out anytime**\n"
                    "- **Guess wrong and you lose everything!**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !hl")
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        try:
            # Send loading message
            #loading_emoji = emoji()["loading"]
            loading_embed = discord.Embed(
                title=f"Preparing HiLo Game...",
                description="Please wait while we set up your game.",
                color=0x00FFAE
            )
            loading_message = await ctx.reply(embed=loading_embed)

            # Import the currency helper
            from Cogs.utils.currency_helper import process_bet_amount

            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)
            if not success:
                try:
                    await loading_message.delete()
                except:
                    pass
                return await ctx.reply(embed=error_embed)

            # Set up the game
            tu = bet_info["tokens_used"]

            currency_used = "points"
            # Update loading message to indicate progress
            await loading_message.edit(embed=discord.Embed(
                title=f"Setting Up Game...",
                description=f"Placing bet of {bet_amount} {currency_used}...",
                color=0x00FFAE
            ))

            # Create a shuffled deck of cards
            deck = self.create_deck()

            # Draw the first card
            current_card = deck.pop(0)

            # Create game view
            view = HiLoView(self, ctx, int(bet_amount), deck, current_card)

            # Calculate initial potential profits
            view.calculate_potential_profits()

            # Update loading message again
            await loading_message.edit(embed=discord.Embed(
                title=f"Generating Game...",
                description=f"Creating game display...",
                color=0x00FFAE
            ))

            # Generate the initial game image
            game_image = await self.create_game_image(current_card, [], 
                                                    view.high_profit, view.low_profit, 
                                                    view.current_winnings, current_winnings=view.current_winnings)

            # Create initial game embed
            embed = view.create_game_embed()

            # Add the image to the embed
            file = discord.File(fp=game_image, filename="hilo_game.png")
            embed.set_image(url="attachment://hilo_game.png")

            # Mark user as having an ongoing game
            self.ongoing_games[ctx.author.id] = "hilo"

            # Send the game message
            message = await ctx.reply(embed=embed, file=file, view=view)
            view.message = message

            # Delete loading message
            try:
                await loading_message.delete()
            except:
                pass

        except Exception as e:
            # Handle any unexpected errors
            print(f"Error in HiLo game: {e}")
            error_embed = discord.Embed(
                title="❌ Error Starting Game",
                description=f"There was a problem starting your HiLo game. Please try again later.",
                color=0xFF0000
            )
            error_embed.set_footer(text="If this issue persists, please contact a server admin.")

            # Clean up ongoing game entry if it was created
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

            # Try to delete loading message if it exists
            try:
                if 'loading_message' in locals():
                    await loading_message.delete()
            except:
                pass

            await ctx.reply(embed=error_embed)

def setup(bot):
    bot.add_cog(HiLo(bot))