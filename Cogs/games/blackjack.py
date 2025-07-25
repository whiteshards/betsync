import discord
import random
import os
import io
import datetime
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

# Card values
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11
}

class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None
        self.player_cards = []
        self.dealer_cards = []
        self.deck = self.create_deck()
        self.used_cards = set()  # Track used cards to prevent duplicates
        self.game_over = False

        # Deal initial cards and remove them from the deck
        self.player_cards = []
        self.dealer_cards = []

        # Deal two cards to player and dealer
        for _ in range(2):
            self.player_cards.append(self.draw_card())
            self.dealer_cards.append(self.draw_card())

    def create_deck(self):
        """Create a shuffled deck of cards"""
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck

    def draw_card(self):
        """Draw a card from the deck, ensuring no duplicates"""
        if len(self.used_cards) >= 52:  # All cards used
            # Create a new deck excluding already used cards
            self.deck = self.create_deck()
            self.used_cards = set()

        # Get a card that hasn't been used
        while True:
            if not self.deck:
                self.deck = self.create_deck()

            card = self.deck.pop()
            card_id = f"{card[0]}_{card[1]}"

            if card_id not in self.used_cards:
                self.used_cards.add(card_id)
                return card

    def calculate_hand_value(self, cards):
        """Calculate the value of a hand, handling Aces intelligently"""
        value = 0
        aces = 0

        for card in cards:
            rank = card[0]
            if rank == 'A':
                aces += 1
                value += 11
            else:
                value += CARD_VALUES[rank]

        # Adjust for Aces if needed
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1

        return value

    def format_cards_text(self, cards):
        """Format cards into text with suit emojis."""
        suit_emojis = {
            'hearts': '♥',
            'diamonds': '♦',
            'clubs': '♣',
            'spades': '♠'
        }
        formatted_cards = []
        for rank, suit in cards:
            formatted_cards.append(f"{rank}{suit_emojis[suit]}")
        return ' '.join(formatted_cards)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="hit")
    async def hit_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.game_over:
            return await interaction.response.send_message("This game is already over!", ephemeral=True)

        await interaction.response.defer()

        # Draw a new card for the player
        self.player_cards.append(self.draw_card())

        # Check if player busts
        player_value = self.calculate_hand_value(self.player_cards)

        if player_value > 21:
            for child in self.children:
                child.disabled = True

            self.game_over = True
            # Generate game image showing bust
            image_bytes = await self.cog.generate_game_image(self.player_cards, self.dealer_cards, True)
            file = discord.File(image_bytes, filename="blackjack_game.png")

            # Create results embed
            embed = discord.Embed(
                title="♠️ Blackjack - Bust!",
                description=f"You busted with {player_value}! Dealer wins.",
                color=discord.Color.red()
            )
            # Format player cards with emojis
            player_cards_text = self.format_cards_text(self.player_cards)
            dealer_cards_text = self.format_cards_text(self.dealer_cards)

            embed.add_field(name="Your Hand", value=f"{player_cards_text}\nTotal: {player_value}", inline=True)
            embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_text}\nTotal: {self.calculate_hand_value(self.dealer_cards)}", inline=True)
            embed.set_image(url="attachment://blackjack_game.png")

            # Handle loss in the database
            await self.cog.handle_game_end(
                self.ctx, 
                self.bet_amount,
                self.currency_used,
                "loss", 
                self.player_cards, 
                self.dealer_cards
            )

            # Create play again view
            play_again_view = self.cog.create_play_again_view(self.ctx.author.id, self.bet_amount, self.currency_used)

            # Update message with result and play again button
            await interaction.message.edit(embed=embed, view=play_again_view)
            await interaction.message.edit(file=file)

        else:
            # Update game view with new card
            image_bytes = await self.cog.generate_game_image(self.player_cards, self.dealer_cards, False)
            file = discord.File(image_bytes, filename="blackjack_game.png")

            embed = discord.Embed(
                title="♠️ Blackjack",
                description=f"Your turn! Choose your next move.",
                color=0x00FFAE
            )
            # Format player cards with emojis
            player_cards_text = self.format_cards_text(self.player_cards)

            # Show only dealer's first card with its value
            dealer_first_card = self.dealer_cards[0]
            dealer_first_card_text = f"{dealer_first_card[0]}{['♥', '♦', '♣', '♠'][['hearts', 'diamonds', 'clubs', 'spades'].index(dealer_first_card[1])]}"
            dealer_first_value = CARD_VALUES[dealer_first_card[0]]
            
            embed.add_field(name="Your Hand", value=f"{player_cards_text}\nTotal: {player_value}", inline=True)
            embed.add_field(name="Dealer's Hand", value=f"{dealer_first_card_text} ?\nShowing: {dealer_first_value}", inline=True)
            embed.set_image(url="attachment://blackjack_game.png")

            await interaction.message.edit(embed=embed, view=self)
            await interaction.message.edit(file=file)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="stand")
    async def stand_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.game_over:
            return await interaction.response.send_message("This game is already over!", ephemeral=True)

        # Disable buttons
        await interaction.response.defer() #Added defer for stand button
        for child in self.children:
            child.disabled = True

        self.game_over = True

        # Dealer draws cards until they reach 17 or higher
        dealer_value = self.calculate_hand_value(self.dealer_cards)
        while dealer_value < 17:
            self.dealer_cards.append(self.draw_card())
            dealer_value = self.calculate_hand_value(self.dealer_cards)

        # Calculate final hand values
        player_value = self.calculate_hand_value(self.player_cards)

        # Determine outcome
        win_type = None
        result_description = ""

        if dealer_value > 21:
            # Dealer busts
            win_type = "win"
            result_description = f"Dealer busts with {dealer_value}! You win!"
            embed_color = discord.Color.green()
        elif player_value > dealer_value:
            # Player wins
            win_type = "win"
            result_description = f"You win with {player_value} against dealer's {dealer_value}!"
            embed_color = discord.Color.green()
        elif player_value < dealer_value:
            # Dealer wins
            win_type = "loss"
            result_description = f"Dealer wins with {dealer_value} against your {player_value}."
            embed_color = discord.Color.red()
        else:
            # Push (tie)
            win_type = "push"
            result_description = f"Push! Both you and the dealer have {player_value}."
            embed_color = discord.Color.yellow()

        # Generate final game image
        image_bytes = await self.cog.generate_game_image(self.player_cards, self.dealer_cards, True)
        file = discord.File(image_bytes, filename="blackjack_game.png")

        # Create results embed
        embed = discord.Embed(
            title=f"♠️ Blackjack - {win_type.capitalize()}" if win_type != "push" else "♠️ Blackjack - Push",
            description=result_description,
            color=embed_color
        )
        # Format cards with emojis
        player_cards_text = self.format_cards_text(self.player_cards)
        dealer_cards_text = self.format_cards_text(self.dealer_cards)

        embed.add_field(name="Your Hand", value=f"{player_cards_text}\nTotal: {player_value}", inline=True)
        embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_text}\nTotal: {dealer_value}", inline=True)
        embed.set_image(url="attachment://blackjack_game.png")

        # Handle game outcome in the database
        await self.cog.handle_game_end(
            self.ctx, 
            self.bet_amount,
            self.currency_used,
            win_type, 
            self.player_cards, 
            self.dealer_cards
        )

        # Create play again view
        play_again_view = self.cog.create_play_again_view(self.ctx.author.id, self.bet_amount, self.currency_used)

        # Update message with result and play again button
        await interaction.message.edit(embed=embed, view=play_again_view)
        await interaction.message.edit(file=file)

    #@discord.ui.button(label="Double Down", style=discord.ButtonStyle.danger, custom_id="double")
    async def double_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.game_over:
            return await interaction.response.send_message("This game is already over!", ephemeral=True)

        #Check if player has enough balance to double down
        #await interaction.response.defer()
        db = Users()
        user_data = db.fetch_user(self.ctx.author.id)

        if not user_data:
            return await interaction.response.send_message("User not found in database.", ephemeral=True)

        if self.currency_used == "tokens" and user_data.get("tokens", 0) < self.bet_amount:
            return await interaction.response.send_message(f"You don't have enough tokens to double down.", ephemeral=True)
        elif self.currency_used == "credits" and user_data.get("credits", 0) < self.bet_amount:
            return await interaction.response.send_message(f"You don't have enough credits to double down.", ephemeral=True)

        # First defer the response to avoid interaction timeout
        await interaction.response.defer()

        # Deduct additional bet amount
        db.update_balance(self.ctx.author.id, -self.bet_amount, self.currency_used, "$inc")

        # Double the bet
        original_bet = self.bet_amount
        self.bet_amount *= 2

        # Disable buttons
        for child in self.children:
            child.disabled = True

        self.game_over = True

        # Draw only one card for the player
        self.player_cards.append(self.draw_card())
        player_value = self.calculate_hand_value(self.player_cards)

        # Dealer draws cards if player hasn't busted
        dealer_value = self.calculate_hand_value(self.dealer_cards)
        if player_value <= 21:
            while dealer_value < 17:
                self.dealer_cards.append(self.draw_card())
                dealer_value = self.calculate_hand_value(self.dealer_cards)

        # Determine outcome
        win_type = None
        result_description = f"Double Down! Your bet is now {self.bet_amount}.\n"

        if player_value > 21:
            # Player busts
            win_type = "loss"
            result_description += f"You busted with {player_value}! Dealer wins."
            embed_color = discord.Color.red()
        elif dealer_value > 21:
            # Dealer busts
            win_type = "win"
            result_description += f"Dealer busts with {dealer_value}! You win!"
            embed_color = discord.Color.green()
        elif player_value > dealer_value:
            # Player wins
            win_type = "win"
            result_description += f"You win with {player_value} against dealer's {dealer_value}!"
            embed_color = discord.Color.green()
        elif player_value < dealer_value:
            # Dealer wins
            win_type = "loss"
            result_description += f"Dealer wins with {dealer_value} against your {player_value}."
            embed_color = discord.Color.red()
        else:
            # Push (tie)
            win_type = "push"
            result_description += f"Push! Both you and the dealer have {player_value}."
            embed_color = discord.Color.yellow()

        # Generate final game image
        image_bytes = await self.cog.generate_game_image(self.player_cards, self.dealer_cards, True)
        file = discord.File(image_bytes, filename="blackjack_game.png")

        # Create results embed
        embed = discord.Embed(
            title=f"♠️ Blackjack - Double Down - {win_type.capitalize()}" if win_type != "push" else "♠️ Blackjack - Double Down - Push",
            description=result_description,
            color=embed_color
        )
        # Format cards with emojis
        player_cards_text = self.format_cards_text(self.player_cards)
        dealer_cards_text = self.format_cards_text(self.dealer_cards)

        embed.add_field(name="Your Hand", value=f"{player_cards_text}\nTotal: {player_value}", inline=True)
        embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_text}\nTotal: {dealer_value}", inline=True)
        embed.set_image(url="attachment://blackjack_game.png")

        # Handle game outcome in the database, with doubled bet
        await self.cog.handle_game_end(
            self.ctx, 
            self.bet_amount,
            self.currency_used,
            win_type, 
            self.player_cards, 
            self.dealer_cards
        )

        # Create play again view
        play_again_view = self.cog.create_play_again_view(self.ctx.author.id, original_bet, self.currency_used)

        try:
            # Update message with result and play again button
            await interaction.edit_original_response(embed=embed, view=play_again_view)
            await interaction.message.edit(file=file)
        except Exception as e:
            print(f"Error updating message: {e}")
            # Fallback method if edit fails
            try:
                await interaction.followup.send(embed=embed, file=file, view=play_again_view)
            except Exception as e2:
                print(f"Followup also failed: {e2}")

    async def on_timeout(self):
        if not self.game_over:
            self.game_over = True

            # Disable all buttons
            for child in self.children:
                child.disabled = True

            try:
                # Create timeout embed
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Game Timeout",
                    description="Game timed out due to inactivity. Your bet has been lost.",
                    color=discord.Color.red()
                )

                await self.message.edit(embed=embed, view=self)

                # Handle loss in database
                await self.cog.handle_game_end(
                    self.ctx,
                    self.bet_amount,
                    self.currency_used,
                    "loss",
                    self.player_cards,
                    self.dealer_cards
                )

            except Exception as e:
                print(f"Error in Blackjack timeout handler: {e}")

        # Always remove from ongoing games on timeout
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["bj", "21"])
    async def blackjack(self, ctx, bet_amount: str = None):
        """
        Play a game of Blackjack against the dealer

        Usage: !blackjack <bet amount> [currency_type]
        Example: !blackjack 100 tokens
        """
        # Show help if no bet amount
        if not bet_amount:
            embed = discord.Embed(
                title="♠️ How to Play Blackjack",
                description=(
                    "**Blackjack** is a classic card game where you play against the dealer!\n\n"
                    "**Usage:** `!blackjack <amount>`\n"
                    "**Example:** `!blackjack 100`\n\n"
                    "**Rules:**\n"
                    "- Get closer to 21 than the dealer without going over\n"
                    "- Face cards are worth 10, Aces are 1 or 11\n"
                    "- Dealer must hit until 17 or higher\n"
                    "- Blackjack pays 1.3x your bet & Win Pays 1.80x\n\n"
                    "**Commands:**\n"
                    "- **Hit**: Take another card\n"
                    "- **Stand**: End your turn\n"
                    #"- **Double Down**: Double your bet and take exactly one more card"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !bj, !21")
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
            loading_emoji = emoji()["loading"]
            loading_embed = discord.Embed(
                title=f"{loading_emoji} | Preparing Blackjack Game...",
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
            bet_amount_value = float(bet_amount)

            # Determine currency used
            tu = bet_info["tokens_used"]
            #cu = bet_info["credits_used"]

            currency_used = "points"

            # Create the game view
            view = BlackjackView(self, ctx, bet_amount_value, currency_used)

            # Generate initial game image
            image_bytes = await self.generate_game_image(view.player_cards, view.dealer_cards, False)
            file = discord.File(image_bytes, filename="blackjack_game.png")

            # Calculate initial hand values
            player_value = view.calculate_hand_value(view.player_cards)

            # Check for player blackjack (21 with 2 cards)
            if player_value == 21 and len(view.player_cards) == 2:
                # Player has blackjack - check if dealer also has blackjack
                dealer_value = view.calculate_hand_value(view.dealer_cards)

                # Set game as over and disable buttons
                view.game_over = True
                for child in view.children:
                    child.disabled = True

                if dealer_value == 21 and len(view.dealer_cards) == 2:
                    # Both have blackjack - push (return bet)
                    embed = discord.Embed(
                        title="♠️ Blackjack - Push!",
                        description="Both you and the dealer have Blackjack! Your bet is returned.",
                        color=discord.Color.yellow()
                    )

                    # Handle push in database
                    await self.handle_game_end(
                        ctx,
                        bet_amount_value,
                        currency_used,
                        "push",
                        view.player_cards,
                        view.dealer_cards
                    )
                else:
                    # Player wins with blackjack - 1.3x payout
                    win_amount = bet_amount_value * 1.3

                    embed = discord.Embed(
                        title="<:yes:1355501647538815106> | Blackjack!",
                        description=f"**You win** `{win_amount:.2f} {currency_used}` with a natural blackjack!",
                        color=discord.Color.green()
                    )

                    # Handle blackjack win in database
                    await self.handle_game_end(
                        ctx,
                        bet_amount_value,
                        currency_used,
                        "blackjack",
                        view.player_cards,
                        view.dealer_cards
                    )

                # Show both hands
                # Format player cards with emojis
                player_cards_text = view.format_cards_text(view.player_cards)
                dealer_cards_text = view.format_cards_text(view.dealer_cards)

                embed.add_field(name="Your Hand", value=f"{player_cards_text}\nTotal: {player_value} (Blackjack!)", inline=True)
                embed.add_field(name="Dealer's Hand", value=f"{dealer_cards_text}\nTotal: {dealer_value}", inline=True)
                embed.set_image(url="attachment://blackjack_game.png")

                # Generate final image showing both hands
                image_bytes = await self.generate_game_image(view.player_cards, view.dealer_cards, True)
                file = discord.File(image_bytes, filename="blackjack_game.png")

                # Delete loading message
                await loading_message.delete()

                # Create play again view
                play_again_view = self.create_play_again_view(ctx.author.id, bet_amount_value, currency_used)

                # Send game message with play again buttons
                game_message = await ctx.reply(embed=embed, file=file, view=play_again_view)
                view.message = game_message

            else:
                # Normal game start
                embed = discord.Embed(
                    title="♠️ Blackjack",
                    description="Your turn! Choose your next move.",
                    color=0x00FFAE
                )
                # Format player cards with emojis
                player_cards_text = view.format_cards_text(view.player_cards)

                # Show only dealer's first card with its value
                dealer_first_card = view.dealer_cards[0]
                dealer_first_card_text = f"{dealer_first_card[0]}{['♥', '♦', '♣', '♠'][['hearts', 'diamonds', 'clubs', 'spades'].index(dealer_first_card[1])]}"
                dealer_first_value = CARD_VALUES[dealer_first_card[0]]
                
                embed.add_field(name="Your Hand", value=f"{player_cards_text}\nTotal: {player_value}", inline=True)
                embed.add_field(name="Dealer's Hand", value=f"{dealer_first_card_text} ?\nShowing: {dealer_first_value}", inline=True)
                embed.set_image(url="attachment://blackjack_game.png")

                # Delete loading message
                await loading_message.delete()

                # Send game message
                game_message = await ctx.reply(embed=embed, file=file, view=view)
                view.message = game_message

            # Mark game as ongoing only if it hasn't already ended (e.g., blackjack)
            if not view.game_over:
                self.ongoing_games[ctx.author.id] = {
                    "bet_amount": bet_amount_value,
                    "currency_used": currency_used,
                    "view": view
                }
            else:
                # Game ended immediately (blackjack), ensure it's not marked as ongoing
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]

        except Exception as e:
            print(f"Blackjack error: {e}")
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description="An error occurred while setting up the game.",
                color=0xFF0000
            )
            try:
                await loading_message.delete()
            except:
                pass
            await ctx.reply(embed=error_embed)

    async def generate_game_image(self, player_cards, dealer_cards, show_dealer=False):
        """Generate game image showing card hands, styled like the provided image"""
        # Image dimensions and settings
        width, height = 1000, 600
        bg_color = (8, 28, 40)  # Darker navy blue background to match reference image
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        try:
            # Load fonts
            title_font = ImageFont.truetype("roboto.ttf", 26) 
            subtitle_font = ImageFont.truetype("roboto.ttf", 22)
            value_font = ImageFont.truetype("roboto.ttf", 26)
        except:
            # Fallback fonts
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            value_font = ImageFont.load_default()

        # Card sizes and positioning
        card_width = 120
        card_height = 170
        card_offset = 60  # Increased card spread for better visibility

        # Draw ribbon-style banner
        banner_width = 350
        banner_height = 40
        banner_x = (width - banner_width) // 2
        banner_y = 280

        # Draw ribbon with slight gradient
        banner_color = (48, 58, 68)
        draw.rectangle(
            (banner_x, banner_y, banner_x + banner_width, banner_y + banner_height),
            fill=banner_color,
            outline=(58, 68, 78)
        )

        # Add ribbon ends
        ribbon_end_width = 15
        ribbon_end_height = 20

        # Left ribbon end
        draw.polygon(
            [(banner_x, banner_y), 
             (banner_x - ribbon_end_width, banner_y + (banner_height//2)), 
             (banner_x, banner_y + banner_height)],
            fill=banner_color
        )

        # Right ribbon end
        draw.polygon(
            [(banner_x + banner_width, banner_y), 
             (banner_x + banner_width + ribbon_end_width, banner_y + (banner_height//2)), 
             (banner_x + banner_width, banner_y + banner_height)],
            fill=banner_color
        )

        # Draw the title text
        draw.text(
            (width // 2, banner_y + (banner_height // 2)),
            "BLACKJACK PAYS 3 TO 2",
            font=title_font,
            fill=(220, 220, 220),
            anchor="mm"  # Center alignment
        )

        # Function to draw a card hand with value bubble
        def draw_hand(cards, y_position, is_dealer=False):
            # Calculate total displayed width for centering
            num_cards = len(cards if show_dealer or not is_dealer else [cards[0]])
            total_width = card_width + ((num_cards - 1) * card_offset)
            start_x = (width - total_width) // 2

            # Calculate hand value
            if is_dealer and not show_dealer:
                # Only show value of first card if dealer's hand is hidden
                value = CARD_VALUES[cards[0][0]]
                displayed_cards = [cards[0]]
            else:
                displayed_cards = cards
                # Calculate hand value
                value = 0
                aces = 0

                for card in cards:
                    rank = card[0]
                    if rank == 'A':
                        aces += 1
                        value += 11
                    else:
                        value += CARD_VALUES[rank]

                # Adjust for Aces if needed
                while value > 21 and aces > 0:
                    value -= 10
                    aces -= 1

            # Draw the hand value in a pill-shaped bubble like in the reference
            bubble_width = 50
            bubble_height = 34
            bubble_x = start_x + total_width + 30
            bubble_y = y_position + (card_height // 2) - (bubble_height // 2)

            # Draw rounded rect for value bubble
            draw.rounded_rectangle(
                (bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height),
                radius=17,
                fill=(52, 68, 82)
            )

            # Draw value text
            value_text = str(value)
            draw.text(
                (bubble_x + (bubble_width // 2), bubble_y + (bubble_height // 2)),
                value_text,
                font=value_font,
                fill=(220, 220, 220),
                anchor="mm"  # Center alignment
            )

            # Draw the cards with increased spacing, more like the reference image
            for i, card in enumerate(reversed(displayed_cards)):
                # Calculate position with more space between cards
                idx = len(displayed_cards) - 1 - i
                x = start_x + (idx * card_offset)

                # Determine which card image to use
                if is_dealer and idx > 0 and not show_dealer:
                    # Use back card for dealer's hidden card
                    card_path = "assests/back_card.png"
                else:
                    card_path = f"assests/{card[1]}_{card[0]}.png"

                try:
                    # Load and resize card image
                    card_img = Image.open(card_path).convert('RGBA')
                    card_img = card_img.resize((card_width, card_height))

                    # Create white background for card with subtle shadow effect
                    card_bg = Image.new('RGB', (card_width, card_height), (255, 255, 255))
                    card_bg.paste(card_img, (0, 0), card_img)

                    # Add card to main image
                    image.paste(card_bg, (x, y_position))

                except Exception as e:
                    # Fallback to drawing basic card if image loading fails
                    # Draw card with rounded corners
                    draw.rounded_rectangle(
                        (x, y_position, x + card_width, y_position + card_height),
                        radius=10,
                        fill=(255, 255, 255),
                        outline=(220, 220, 220)
                    )

                    # Draw rank and suit
                    rank = card[0]
                    suit = card[1]

                    # Determine color based on suit
                    text_color = (0, 0, 0)
                    if suit in ['hearts', 'diamonds']:
                        text_color = (220, 30, 30)

                    # Get suit symbol
                    suit_symbol = "♠"
                    if suit == 'hearts':
                        suit_symbol = "♥"
                    elif suit == 'diamonds':
                        suit_symbol = "♦"
                    elif suit == 'clubs':
                        suit_symbol = "♣"

                    # Draw large symbol in center
                    draw.text(
                        (x + (card_width // 2), y_position + (card_height // 2)),
                        suit_symbol,
                        font=title_font,
                        fill=text_color,
                        anchor="mm"
                    )

                    # Draw rank at top-left
                    draw.text(
                        (x + 10, y_position + 10),
                        rank,
                        font=title_font,
                        fill=text_color
                    )

                    # Draw small suit under rank
                    draw.text(
                        (x + 10, y_position + 40),
                        suit_symbol,
                        font=subtitle_font,
                        fill=text_color
                    )

                    # Draw inverted rank and suit at bottom-right
                    draw.text(
                        (x + card_width - 25, y_position + card_height - 40),
                        rank,
                        font=title_font,
                        fill=text_color
                    )
                    draw.text(
                        (x + card_width - 25, y_position + card_height - 70),
                        suit_symbol,
                        font=subtitle_font,
                        fill=text_color
                    )

        # Draw dealer's hand at top (moved up to avoid overlapping with banner)
        draw_hand(dealer_cards, 70, True)

        # Draw player's hand at bottom
        draw_hand(player_cards, 400)

        # Load the background image
        try:
            background_image = Image.open("assests/bjbackground.jpg").convert('RGB')
            background_image = background_image.resize((width, height))
            image = background_image.copy()
            image.paste(image, (0, 0), image)
            draw = ImageDraw.Draw(image)
        except:
            pass

        # Save to bytes
        img_byte_array = io.BytesIO()
        image.save(img_byte_array, format="PNG")
        img_byte_array.seek(0)

        return img_byte_array

    def create_play_again_view(self, user_id, bet_amount, currency_used):
        """Create a view with a play again button"""
        view = discord.ui.View(timeout=60)

        play_again_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Play Again",
            emoji="♠️",
            custom_id=f"blackjack_again_{user_id}"
        )

        async def play_again_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("This is not your game!", ephemeral=True)

            # Start a new game with same bet amount and currency
            await interaction.response.defer()

            # Get the command from the bot
            bet_command = self.bot.get_command('blackjack')
            if bet_command:
                # Create a new context
                new_ctx = await self.bot.get_context(interaction.message)
                new_ctx.author = interaction.user

                # Run the command with the same bet amount and currency
                await bet_command(new_ctx, str(bet_amount))

        play_again_button.callback = play_again_callback
        view.add_item(play_again_button)

        return view

    async def handle_game_end(self, ctx, bet_amount, currency_used, result, player_cards, dealer_cards):
        """Handle game end in the database and update statistics"""
        user_id = ctx.author.id

        # Remove game from ongoing games
        if user_id in self.ongoing_games:
            del self.ongoing_games[user_id]

        # Get database instances
        user_db = Users()
        server_db = Servers()

        # Calculate win amount
        win_amount = 0
        if result == "win":
            win_amount = bet_amount * 1.80
        elif result == "blackjack":
            win_amount = bet_amount * 1.3

        # Timestamp for history entries
        timestamp = int(datetime.datetime.now().timestamp())

        if result == "push":
            # Push - return bet amount only
            user_db.update_balance(user_id, bet_amount, "points", "$inc")
            
            history_entry = {
                "type": "push",
                "game": "blackjack",
                "amount": bet_amount,
                "bet": bet_amount,
                "multiplier": 1.0,
                "timestamp": timestamp
            }

            user_db.collection.update_one(
                {"discord_id": user_id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {"total_played": 1}
                }
            )

            # No server profit change for push
            server_history_entry = {
                "type": "push",
                "game": "blackjack",
                "user_id": user_id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": bet_amount,
                "multiplier": 1.0,
                "timestamp": timestamp
            }
            server_db.update_history(ctx.guild.id, server_history_entry)

        elif result == "win" or result == "blackjack":
            # Player wins - add winnings to balance
            user_db.update_balance(user_id, win_amount, "points", "$inc")

            # Add win to history
            multiplier = 1.3 if result == "blackjack" else 1.80
            history_entry = {
                "type": "win",
                "game": "blackjack",
                "amount": win_amount,
                "bet": bet_amount,
                "multiplier": multiplier,
                "timestamp": timestamp
            }

            user_db.collection.update_one(
                {"discord_id": user_id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {"total_earned": win_amount, "total_won": 1, "total_played": 1}
                }
            )

            # Update server stats - casino loses
            server_db.update_server_profit(ctx, ctx.guild.id, -(win_amount - bet_amount), game="blackjack")

            # Add to server history
            server_history_entry = {
                "type": "win",
                "game": "blackjack",
                "user_id": user_id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": win_amount,
                "multiplier": multiplier,
                "timestamp": timestamp
            }
            server_db.update_history(ctx.guild.id, server_history_entry)

        elif result == "loss":
            # Player loses - already deducted bet when starting game
            history_entry = {
                "type": "loss",
                "game": "blackjack",
                "amount": bet_amount,
                "multiplier": 0,
                "timestamp": timestamp
            }

            user_db.collection.update_one(
                {"discord_id": user_id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {"total_spent": bet_amount, "total_lost": 1, "total_played": 1}
                }
            )

            # Update server stats - casino wins
            server_db.update_server_profit(ctx, ctx.guild.id, bet_amount, game="blackjack")

            # Add to server history
            server_history_entry = {
                "type": "loss",
                "game": "blackjack",
                "user_id": user_id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": bet_amount,
                "multiplier": 0,
                "timestamp": timestamp
            }
            server_db.update_history(ctx.guild.id, server_history_entry)



def setup(bot):
    bot.add_cog(Blackjack(bot))