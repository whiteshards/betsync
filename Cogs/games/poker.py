import discord
import random
import os
import time
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io

from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

# Define the paytable with multipliers for each hand type
paytable = {
    "Royal Flush": 1000,
    "Straight Flush": 200,
    "Four of a Kind": 60,
    "Full House": 25,
    "Flush": 20,
    "Straight": 15,
    "Three of a Kind": 9,
    "Two Pair": 4,
    "One Pair": 1,
    "High Card": 0
}

class CardDeck:
    def __init__(self):
        self.ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.suits = ['hearts', 'diamonds', 'clubs', 'spades']
        self.deck = [(rank, suit) for suit in self.suits for rank in self.ranks]
        random.shuffle(self.deck)

    def draw_cards(self, count):
        if len(self.deck) < count:
            return None
        return [self.deck.pop() for _ in range(count)]

class HoldButton(discord.ui.Button):
    def __init__(self, card_index, card_info):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=f"Card {card_index+1}",
            custom_id=f"hold_{card_index}"
        )
        self.card_index = card_index
        self.card_info = card_info
        self.is_held = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.is_held = not self.is_held
        if self.is_held:
            self.style = discord.ButtonStyle.success
            self.label = f"Card {self.card_index+1} (Held)"
        else:
            self.style = discord.ButtonStyle.secondary
            self.label = f"Card {self.card_index+1}"

        self.view.held_cards[self.card_index] = self.is_held

        # Generate new game image with updated held status
        image_bytes = await self.view.cog.generate_game_image(
            self.view.cards, 
            self.view.held_cards,
            is_final=False
        )

        file = discord.File(image_bytes, filename="poker_game.png")
        embed = discord.Embed(
            title="🃏 Video Poker",
            description=f"Select cards to hold, then click 'Deal' to replace the rest.",
            color=0x00FFAE
        )
        embed.set_image(url="attachment://poker_game.png")
        embed.set_footer(text="BetSync Casino • Hold cards you want to keep")

        await interaction.response.edit_message(attachments=[file], embed=embed, view=self.view)

class PokerView(discord.ui.View):
    def __init__(self, cog, ctx, cards, user_id, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.cards = cards
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.held_cards = [False, False, False, False, False]
        self.message = None

        # Add hold buttons for each card
        for i, card in enumerate(cards):
            self.add_item(HoldButton(i, card))

        # Add deal button
        deal_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Deal",
            custom_id="deal"
        )
        deal_button.callback = self.deal_callback
        self.add_item(deal_button)

    async def deal_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        # Update message
        await interaction.response.edit_message(view=self)

        # Replace unheld cards
        await self.cog.replace_cards(self.ctx, self.cards, self.held_cards, self.bet_amount, self.message)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

        # Return the bet if the game timed out
        db = Users()
        db.update_balance(self.user_id, self.bet_amount, "credits", "$inc")

        try:
            timeout_embed = discord.Embed(
                title="⏰ Game Timed Out",
                description="Your bet has been returned.",
                color=discord.Color.red()
            )
            await self.ctx.author.send(embed=timeout_embed)
        except:
            pass

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="play_again")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Use the same bet amount without specifying currency
        await self.cog.poker(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

class Poker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    async def generate_game_image(self, cards, held_cards, is_final=False, win_type=None):
        # Create background with modern gray
        width, height = 1000, 500
        bg_color = (40, 40, 40)  # Modern dark gray
        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        # Try to load font
        try:
            small_font = ImageFont.truetype("roboto.ttf", 24)
            medium_font = ImageFont.truetype("roboto.ttf", 32)
            large_font = ImageFont.truetype("roboto.ttf", 48)
        except Exception:
            small_font = ImageFont.load_default()
            medium_font = ImageFont.load_default()
            large_font = ImageFont.load_default()

        # Title at the top
        draw.text((width//2, 50), "BetRush Poker", font=large_font, fill=(200, 200, 200), anchor="mm")

        # Load and place cards
        card_width = 150
        card_height = 220
        card_spacing = 20
        total_width = (card_width * 5) + (card_spacing * 4)
        start_x = (width - total_width) // 2
        y_position = 150

        for i, (rank, suit) in enumerate(cards):
            # Convert J, Q, K, A to their full names for file paths
            if rank == 'J':
                card_rank = 'J'
            elif rank == 'Q':
                card_rank = 'Q'
            elif rank == 'K':
                card_rank = 'K'
            elif rank == 'A':
                card_rank = 'A'
            else:
                card_rank = rank

            card_path = f"assests/{suit}_{card_rank}.png"

            try:
                card_img = Image.open(card_path)
                card_img = card_img.resize((card_width, card_height), Image.Resampling.LANCZOS)

                # Create an outline
                if is_final and win_type is not None:
                    # Green outline for winning cards
                    outline_color = (0, 255, 0, 255)  # Green
                elif held_cards[i]:
                    # Yellow outline for held cards
                    outline_color = (255, 255, 0, 255)  # Yellow
                else:
                    # No outline
                    outline_color = None

                if outline_color:
                    # Create an outline by expanding the card and filling with outline color
                    outline_size = 5  # Thinner outline
                    outline = ImageOps.expand(card_img, border=outline_size, fill=outline_color)
                    image.paste(outline, (start_x + (i * (card_width + card_spacing)), y_position))
                else:
                    image.paste(card_img, (start_x + (i * (card_width + card_spacing)), y_position))
            except Exception as e:
                print(f"Error loading card image: {e}")
                # Draw placeholder if image not found
                placeholder_pos = (start_x + (i * (card_width + card_spacing)), y_position)
                draw.rectangle(
                    [placeholder_pos, (placeholder_pos[0] + card_width, placeholder_pos[1] + card_height)],
                    outline=(255, 255, 255),
                    width=2
                )
                draw.text(
                    (placeholder_pos[0] + card_width//2, placeholder_pos[1] + card_height//2),
                    f"{rank} of {suit}",
                    font=small_font,
                    fill=(255, 255, 255),
                    anchor="mm"
                )

            # Add HOLD text overlay for held cards
            if held_cards[i]:
                hold_pos = (start_x + (i * (card_width + card_spacing)) + card_width//2,
                           y_position + card_height - 40)
                # Semi-transparent background for HOLD text
                draw.rectangle(
                    [(hold_pos[0] - 50, hold_pos[1] - 15), (hold_pos[0] + 50, hold_pos[1] + 15)],
                    fill=(50, 50, 50, 150)
                )
                draw.text(hold_pos, "HOLD", font=medium_font, fill=(255, 255, 255), anchor="mm")

        # Add win type at the bottom if final
        if is_final and win_type is not None:
            if win_type != "High Card":
                multiplier = paytable.get(win_type, 0)
                draw.text(
                    (width//2, height - 70),
                    f"{win_type} - {multiplier}x",
                    font=large_font,
                    fill=(255, 255, 255),
                    anchor="mm"
                )
            else:
                draw.text(
                    (width//2, height - 70),
                    "No Win",
                    font=large_font,
                    fill=(255, 100, 100),
                    anchor="mm"
                )

        # Save image to bytes
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes

    def evaluate_hand(self, cards):
        # Extract ranks and suits
        ranks = [card[0] for card in cards]
        suits = [card[1] for card in cards]

        # Convert face cards to numbers for easier evaluation
        rank_values = []
        for rank in ranks:
            if rank == 'A':
                rank_values.append(14)
            elif rank == 'K':
                rank_values.append(13)
            elif rank == 'Q':
                rank_values.append(12)
            elif rank == 'J':
                rank_values.append(11)
            else:
                rank_values.append(int(rank))

        # Count occurrences of each rank
        rank_counts = {}
        for r in rank_values:
            if r in rank_counts:
                rank_counts[r] += 1
            else:
                rank_counts[r] = 1

        # Check for flush (all same suit)
        is_flush = len(set(suits)) == 1

        # Check for straight (sequential ranks)
        sorted_values = sorted(rank_values)
        is_straight = False

        # Regular straight
        if sorted_values == list(range(sorted_values[0], sorted_values[0] + 5)):
            is_straight = True
        # A-5 straight
        elif sorted_values == [2, 3, 4, 5, 14]:
            is_straight = True

        # Royal flush
        if is_flush and sorted_values == [10, 11, 12, 13, 14]:
            return "Royal Flush"

        # Straight flush
        if is_straight and is_flush:
            return "Straight Flush"

        # Four of a kind
        if 4 in rank_counts.values():
            return "Four of a Kind"

        # Full house (three of a kind and a pair)
        if 3 in rank_counts.values() and 2 in rank_counts.values():
            return "Full House"

        # Flush
        if is_flush:
            return "Flush"

        # Straight
        if is_straight:
            return "Straight"

        # Three of a kind
        if 3 in rank_counts.values():
            return "Three of a Kind"

        # Two pair
        if list(rank_counts.values()).count(2) == 2:
            return "Two Pair"

        # One pair
        if 2 in rank_counts.values():
            return "One Pair"

        # High card
        return "High Card"

    def get_winning_cards(self, cards, hand_type):
        # Return indices of the cards that make up the winning hand
        ranks = [(i, card[0]) for i, card in enumerate(cards)]

        # Convert face cards to numbers
        rank_values = []
        for i, rank in ranks:
            if rank == 'A':
                rank_values.append((i, 14))
            elif rank == 'K':
                rank_values.append((i, 13))
            elif rank == 'Q':
                rank_values.append((i, 12))
            elif rank == 'J':
                rank_values.append((i, 11))
            else:
                rank_values.append((i, int(rank)))

        # Count occurrences of each rank
        rank_counts = {}
        for i, r in rank_values:
            if r in rank_counts:
                rank_counts[r].append(i)
            else:
                rank_counts[r] = [i]

        if hand_type == "Royal Flush" or hand_type == "Straight Flush" or hand_type == "Flush":
            # All cards are part of the winning hand
            return [True, True, True, True, True]

        if hand_type == "Straight":
            # All cards are part of the winning hand
            return [True, True, True, True, True]

        if hand_type == "Four of a Kind":
            winning_indices = []
            for r, indices in rank_counts.items():
                if len(indices) == 4:
                    winning_indices = indices
                    break
            result = [False] * 5
            for idx in winning_indices:
                result[idx] = True
            return result

        if hand_type == "Full House":
            three_kind = []
            pair = []
            for r, indices in rank_counts.items():
                if len(indices) == 3:
                    three_kind = indices
                elif len(indices) == 2:
                    pair = indices
            result = [False] * 5
            for idx in three_kind + pair:
                result[idx] = True
            return result

        if hand_type == "Three of a Kind":
            winning_indices = []
            for r, indices in rank_counts.items():
                if len(indices) == 3:
                    winning_indices = indices
                    break
            result = [False] * 5
            for idx in winning_indices:
                result[idx] = True
            return result

        if hand_type == "Two Pair":
            pairs = []
            for r, indices in rank_counts.items():
                if len(indices) == 2:
                    pairs.extend(indices)
            result = [False] * 5
            for idx in pairs:
                result[idx] = True
            return result

        if hand_type == "One Pair":
            winning_indices = []
            for r, indices in rank_counts.items():
                if len(indices) == 2:
                    winning_indices = indices
                    break
            result = [False] * 5
            for idx in winning_indices:
                result[idx] = True
            return result

        # High Card - no winning combination
        return [False, False, False, False, False]

    @commands.command(aliases=["p"])
    async def poker(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play video poker - hold cards and try to make the best hand!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🃏 How to Play Video Poker",
                description=(
                    "**Video Poker** is a card game where you aim to get the best hand possible.\n\n"
                    "**Usage:** `!poker <amount> [currency_type]`\n"
                    "**Example:** `!poker 100` or `!poker 100 tokens`\n\n"
                    "**How to Play:**\n"
                    "1. You are dealt 5 cards\n"
                    "2. Select which cards to hold (keep)\n"
                    "3. Non-held cards are replaced with new ones\n"
                    "4. Your final hand determines your winnings\n\n"
                    "**Payouts:**\n"
                    "- Royal Flush: 1000x\n"
                    "- Straight Flush: 200x\n" 
                    "- Four of a Kind: 60x\n"
                    "- Full House: 25x\n"
                    "- Flush: 20x\n"
                    "- Straight: 15x\n"
                    "- Three of a Kind: 9x\n"
                    "- Two Pair: 4x\n"
                    "- One Pair: 1x\n"
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

        # Validate bet using the currency_helper
        try:
            from Cogs.utils.currency_helper import process_bet_amount
            loading_message = await ctx.reply("Processing bet...") #added loading message

            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            tokens_used = bet_info["tokens_used"] if isinstance(bet_info, dict) else 0
            credits_used = bet_info["credits_used"] if isinstance(bet_info, dict) else 0
            bet_amount_value = bet_info["total_bet_amount"] if isinstance(bet_info, dict) else bet_amount
            #currency_used = bet_info["currency_type"] if isinstance(bet_info, dict) else "credits"

            await loading_message.delete() # deleted loading message after processing


        except Exception as e:
            print(f"Error processing bet: {e}")
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="There was an error processing your bet. Please try again.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Create a new card deck and deal initial 5 cards
        deck = CardDeck()
        initial_cards = deck.draw_cards(5)

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "deck": deck,
            "cards": initial_cards,
            "bet_amount": bet_amount_value, #Use processed bet amount
            #"currency": currency_used #Use processed currency type
        }

        # Generate initial game image
        image_bytes = await self.generate_game_image(
            initial_cards,
            [False, False, False, False, False],
            is_final=False
        )

        file = discord.File(image_bytes, filename="poker_game.png")
        embed = discord.Embed(
            title="🃏 Video Poker",
            description=f"Select cards to hold, then click 'Deal' to replace the rest.",
            color=0x00FFAE
        )
        embed.set_image(url="attachment://poker_game.png")
        embed.set_footer(text="BetSync Casino • Hold cards you want to keep")

        # Create the view with hold buttons
        view = PokerView(self, ctx, initial_cards, ctx.author.id, bet_amount_value) #Use processed bet amount
        message = await ctx.reply(file=file, embed=embed, view=view)
        view.message = message

    async def replace_cards(self, ctx, cards, held_cards, bet_amount, message):
        # Get the ongoing game data
        game_data = self.ongoing_games.get(ctx.author.id)
        if not game_data:
            return

        deck = game_data["deck"]

        # Replace the cards that are not held
        final_cards = cards.copy()
        for i, held in enumerate(held_cards):
            if not held:
                new_card = deck.draw_cards(1)[0]
                final_cards[i] = new_card

        # Evaluate the final hand
        hand_type = self.evaluate_hand(final_cards)

        # Determine which cards make the winning hand
        winning_cards = self.get_winning_cards(final_cards, hand_type)

        # Get the multiplier based on hand type
        multiplier = paytable.get(hand_type, 0)

        # Calculate winnings
        winnings = bet_amount * multiplier

        # Generate final game image
        image_bytes = await self.generate_game_image(
            final_cards, 
            winning_cards,  # Use winning cards for highlighting
            is_final=True,
            win_type=hand_type
        )

        file = discord.File(image_bytes, filename="poker_result.png")

        # Update database
        db = Users()
        server_db = Servers()

        # Record the game result in history
        timestamp = int(time.time())

        if multiplier > 0:
            # Win
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")
            db.update_stats(ctx.author.id, bet_amount, winnings, "win")

            # Add to history
            history_entry = {
                "type": "win",
                "game": "poker",
                "bet": bet_amount,
                "amount": winnings,
                "multiplier": multiplier,
                "timestamp": timestamp
            }
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )

            # Update server stats
            server_entry = {
                "type": "win",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "game": "poker",
                "bet": bet_amount,
                "amount": winnings,
                "multiplier": multiplier,
                "timestamp": timestamp
            }

            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_entry], "$slice": -100}}}
            )

            embed = discord.Embed(
                title="🏆 You Won!",
                description=(
                    f"**Hand:** {hand_type}\n"
                    f"**Multiplier:** {multiplier}x\n"
                    f"**Bet:** {bet_amount}\n"
                    f"**Won:** {winnings} credits"
                ),
                color=0x00FF00
            )
        else:
            # Loss
            db.update_stats(ctx.author.id, bet_amount, 0, "loss")

            # Add to history
            history_entry = {
                "type": "loss",
                "game": "poker",
                "amount": bet_amount,
                "timestamp": timestamp
            }
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )

            # Update server stats
            server_entry = {
                "type": "loss",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "game": "poker",
                "bet": bet_amount,
                "timestamp": timestamp
            }

            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_entry], "$slice": -100}}}
            )

            embed = discord.Embed(
                title="❌ No Win",
                description=(
                    f"**Hand:** {hand_type}\n"
                    f"**Bet:** {bet_amount}"
                ),
                color=0xFF0000
            )

        embed.set_image(url="attachment://poker_result.png")
        embed.set_footer(text="BetSync Casino • Video Poker")

        # Create play again view
        play_again_view = PlayAgainView(self, ctx, bet_amount)
        result_message = await ctx.reply(file=file, embed=embed, view=play_again_view)
        play_again_view.message = result_message

        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

def setup(bot):
    bot.add_cog(Poker(bot))