import discord
import random
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import process_bet_amount
from PIL import Image, ImageDraw, ImageFont
import io

class CardDrawGameView(discord.ui.View):
    def __init__(self, cog, ctx, opponent, bet_amount, currency_type, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.opponent = opponent
        self.bet_amount = bet_amount
        self.currency_type = currency_type
        self.accepted = False

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, button, interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("You can't accept this challenge, it's not for you!", ephemeral=True)

        self.accepted = True
        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        await self.cog.start_game(self.ctx, self.opponent, self.bet_amount, self.currency_type)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, button, interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("You can't decline this challenge, it's not for you!", ephemeral=True)

        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Refund the bet to the challenger
        from Cogs.utils.mongo import Users
        db = Users()

        # Process refund based on bet information
        if self.bet_amount["tokens_used"] > 0:
            db.update_balance(self.ctx.author.id, self.bet_amount["tokens_used"], "tokens", "$inc")
        if self.bet_amount["credits_used"] > 0:
            db.update_balance(self.ctx.author.id, self.bet_amount["credits_used"], "credits", "$inc")

        decline_embed = discord.Embed(
            title="❌ Challenge Declined",
            description=f"{self.opponent.mention} declined the Card Draw challenge.\nYour bet has been refunded.",
            color=0xFF0000
        )
        await self.ctx.reply(embed=decline_embed)

        # Reset cooldown
        self.cog.carddraw.reset_cooldown(self.ctx)

    async def on_timeout(self):
        if not self.accepted:
            # Refund the bet to the challenger
            from Cogs.utils.mongo import Users
            db = Users()

            # Process refund based on bet information
            if self.bet_amount["tokens_used"] > 0:
                db.update_balance(self.ctx.author.id, self.bet_amount["tokens_used"], "tokens", "$inc")
            if self.bet_amount["credits_used"] > 0:
                db.update_balance(self.ctx.author.id, self.bet_amount["credits_used"], "credits", "$inc")

            timeout_embed = discord.Embed(
                title="⏰ Challenge Expired",
                description=f"{self.opponent.mention} didn't respond to the Card Draw challenge in time.\nYour bet has been refunded.",
                color=0xFFA500
            )
            await self.ctx.reply(embed=timeout_embed)

            # Try to notify the challenger
            try:
                await self.ctx.author.send(f"Your Card Draw challenge to {self.opponent.name} has expired. Your bet has been refunded.")
            except discord.Forbidden:
                pass

            # Reset cooldown
            self.cog.carddraw.reset_cooldown(self.ctx)

        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

class CardDraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.card_values = {
            'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, 
            '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13
        }
        self.card_suits = ['hearts', 'diamonds', 'clubs', 'spades']

    @commands.command(aliases=["cd"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def carddraw(self, ctx, opponent: discord.Member = None, bet_amount = None, currency_type = None):
        """Challenge another user to a Card Draw duel"""
        # Get emojis
        emojis = emoji()
        loading_emoji = emojis["loading"]

        # Check if opponent is specified
        if opponent is None or bet_amount is None:
            # Show usage information
            usage_embed = discord.Embed(
                title="🃏 Card Draw Game",
                description="Challenge another user to a card draw duel! Higher card wins.",
                color=0x00FFAE
            )
            usage_embed.add_field(
                name="Usage", 
                value="`!carddraw @user <bet_amount> [currency]`", 
                inline=False
            )
            usage_embed.add_field(
                name="Card Values", 
                value="A = 1, 2-10 = face value, J = 11, Q = 12, K = 13", 
                inline=False
            )
            usage_embed.add_field(
                name="Payout", 
                value="Winner gets 1.96x their bet", 
                inline=False
            )
            usage_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=usage_embed)

        # Check if opponent is self
        if opponent.id == ctx.author.id:
            self.carddraw.reset_cooldown(ctx)
            return await ctx.reply("You can't challenge yourself!")

        # Check if opponent is a bot
        if opponent.bot:
            self.carddraw.reset_cooldown(ctx)
            return await ctx.reply("You can't challenge a bot!")

        # Process bet amount
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Processing Card Draw Challenge",
            description="Please wait while we process your bet...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        success, bet_info, error_embed = await process_bet_amount(
            ctx, bet_amount, currency_type, loading_message
        )

        if not success:
            self.carddraw.reset_cooldown(ctx)
            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Create challenge embed
        challenge_embed = discord.Embed(
            title="🃏 Card Draw Challenge",
            description=f"{ctx.author.mention} has challenged {opponent.mention} to a Card Draw duel!",
            color=0x00FFAE
        )

        bet_display = ""
        if bet_info["tokens_used"] > 0 and bet_info["credits_used"] > 0:
            bet_display = f"**{bet_info['tokens_used']:.2f} tokens** and **{bet_info['credits_used']:.2f} credits**"
        elif bet_info["tokens_used"] > 0:
            bet_display = f"**{bet_info['tokens_used']:.2f} tokens**"
        else:
            bet_display = f"**{bet_info['credits_used']:.2f} credits**"

        challenge_embed.add_field(
            name="Bet Amount", 
            value=bet_display, 
            inline=True
        )
        challenge_embed.add_field(
            name="Potential Win", 
            value=f"**{bet_info['total_bet_amount'] * 1.96:.2f}**", 
            inline=True
        )
        challenge_embed.set_footer(text="This challenge expires in 30 seconds")

        await loading_message.delete()

        # Create and send the view
        view = CardDrawGameView(
            self, ctx, opponent, bet_info, 
            "tokens" if bet_info["tokens_used"] > 0 else "credits"
        )
        message = await ctx.reply(embed=challenge_embed, view=view)
        view.message = message

    async def start_game(self, ctx, opponent, bet_info, currency_type):
        """Start the card draw game after opponent accepts the challenge"""
        # Get emojis
        emojis = emoji()
        loading_emoji = emojis["loading"]

        # Process opponent's bet
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Processing Opponent's Bet",
            description="Please wait while we process the opponent's bet...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Get the same amount from opponent
        opponent_success, opponent_bet_info, error_embed = await process_bet_amount(
            ctx, bet_info["total_bet_amount"], currency_type, loading_message, opponent
        )

        if not opponent_success:
            # Refund challenger
            db = Users()
            if bet_info["tokens_used"] > 0:
                db.update_balance(ctx.author.id, bet_info["tokens_used"], "tokens", "$inc")
            if bet_info["credits_used"] > 0:
                db.update_balance(ctx.author.id, bet_info["credits_used"], "credits", "$inc")

            await loading_message.delete()
            return await ctx.reply(embed=error_embed)

        # Draw cards
        await loading_message.edit(
            embed=discord.Embed(
                title=f"{loading_emoji} | Drawing Cards",
                description="Drawing cards for both players...",
                color=0x00FFAE
            )
        )

        # Generate a card for each player
        challenger_card = self.draw_card()
        opponent_card = self.draw_card()

        # Generate the game image
        game_image = await self.generate_game_image(ctx.author, opponent, challenger_card, opponent_card)

        # Determine winner
        challenger_value = self.card_values[challenger_card[0]]
        opponent_value = self.card_values[opponent_card[0]]

        if challenger_value > opponent_value:
            # Challenger wins
            winner = ctx.author
            winner_bet_info = bet_info
            winner_card = challenger_card
            loser = opponent
            loser_bet_info = opponent_bet_info
            loser_card = opponent_card
            result = "win"
        elif opponent_value > challenger_value:
            # Opponent wins
            winner = opponent
            winner_bet_info = opponent_bet_info
            winner_card = opponent_card
            loser = ctx.author
            loser_bet_info = bet_info
            loser_card = challenger_card
            result = "win"
        else:
            # Draw
            result = "draw"

        # Process result
        db = Users()

        if result == "win":
            # Calculate winnings (1.96x bet)
            winnings = winner_bet_info["total_bet_amount"] * 1.96

            # Update winner's balance
            db.update_balance(winner.id, winnings, "credits", "$inc")

            # Update stats
            db.collection.update_one(
                {"discord_id": winner.id},
                {"$inc": {"total_earned": winnings, "total_won": 1, "total_played": 1}}
            )
            db.collection.update_one(
                {"discord_id": loser.id},
                {"$inc": {"total_lost": 1, "total_played": 1}}
            )

            # Add to history
            winner_history = {
                "type": "win",
                "game": "carddraw",
                "amount": winnings,
                "bet": winner_bet_info["total_bet_amount"],
                "timestamp": int(ctx.message.created_at.timestamp())
            }
            loser_history = {
                "type": "loss",
                "game": "carddraw",
                "amount": loser_bet_info["total_bet_amount"],
                "timestamp": int(ctx.message.created_at.timestamp())
            }

            db.collection.update_one(
                {"discord_id": winner.id},
                {"$push": {"history": {"$each": [winner_history], "$slice": -100}}}
            )
            db.collection.update_one(
                {"discord_id": loser.id},
                {"$push": {"history": {"$each": [loser_history], "$slice": -100}}}
            )

            # Create result embed
            result_embed = discord.Embed(
                title="🃏 Card Draw Results",
                description=f"{winner.mention} wins with a **{winner_card[0]} of {winner_card[1]}**!",
                color=0x00FF00
            )

            # Calculate profit
            profit = winnings - winner_bet_info["total_bet_amount"]

            result_embed.add_field(
                name="Winner", 
                value=f"{winner.mention} - **{winner_card[0]} of {winner_card[1]}**", 
                inline=False
            )
            result_embed.add_field(
                name="Loser", 
                value=f"{loser.mention} - **{loser_card[0]} of {loser_card[1]}**", 
                inline=False
            )
            result_embed.add_field(
                name="Profit", 
                value=f"**+{profit:.2f}**", 
                inline=True
            )
            result_embed.add_field(
                name="Total Won", 
                value=f"**{winnings:.2f}**", 
                inline=True
            )

        else:  # Draw
            # Refund both players
            if bet_info["tokens_used"] > 0:
                db.update_balance(ctx.author.id, bet_info["tokens_used"], "tokens", "$inc")
            if bet_info["credits_used"] > 0:
                db.update_balance(ctx.author.id, bet_info["credits_used"], "credits", "$inc")

            if opponent_bet_info["tokens_used"] > 0:
                db.update_balance(opponent.id, opponent_bet_info["tokens_used"], "tokens", "$inc")
            if opponent_bet_info["credits_used"] > 0:
                db.update_balance(opponent.id, opponent_bet_info["credits_used"], "credits", "$inc")

            # Update stats
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1}}
            )
            db.collection.update_one(
                {"discord_id": opponent.id},
                {"$inc": {"total_played": 1}}
            )

            # Add to history
            draw_history = {
                "type": "draw",
                "game": "carddraw",
                "amount": 0,
                "bet": bet_info["total_bet_amount"],
                "timestamp": int(ctx.message.created_at.timestamp())
            }

            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$push": {"history": {"$each": [draw_history], "$slice": -100}}}
            )
            db.collection.update_one(
                {"discord_id": opponent.id},
                {"$push": {"history": {"$each": [draw_history], "$slice": -100}}}
            )

            # Create result embed
            result_embed = discord.Embed(
                title="🃏 Card Draw Results",
                description="It's a draw! Both bets have been refunded.",
                color=0xFFAA00
            )

            result_embed.add_field(
                name=ctx.author.name, 
                value=f"**{challenger_card[0]} of {challenger_card[1]}**", 
                inline=True
            )
            result_embed.add_field(
                name=opponent.name, 
                value=f"**{opponent_card[0]} of {opponent_card[1]}**", 
                inline=True
            )

        # Set image and footer
        file = discord.File(fp=game_image, filename="carddraw.png")
        result_embed.set_image(url="attachment://carddraw.png")
        result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Delete loading message and send result
        await loading_message.delete()
        await ctx.reply(embed=result_embed)

    def draw_card(self):
        """Draw a random card and return tuple (value, suit)"""
        value = random.choice(list(self.card_values.keys()))
        suit = random.choice(self.card_suits)
        return (value, suit)

    async def generate_game_image(self, player1, player2, player1_card, player2_card):
        """Generate an image showing the card draw game result"""
        # Create image with dark background
        width, height = 1000, 500
        image = Image.new("RGB", (width, height), (30, 30, 50))
        draw = ImageDraw.Draw(image)

        # Load fonts
        try:
            title_font = ImageFont.truetype("roboto.ttf", 36)
            name_font = ImageFont.truetype("roboto.ttf", 28)
            card_font = ImageFont.truetype("roboto.ttf", 48)
            vs_font = ImageFont.truetype("roboto.ttf", 42)
        except:
            # Fall back to default if font not found
            title_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            card_font = ImageFont.load_default()
            vs_font = ImageFont.load_default()

        # Draw title
        draw.text((width // 2, 50), "Card Draw Duel", fill=(255, 255, 255), font=title_font, anchor="mm")

        # Draw player names and VS text
        draw.text((width // 4, 120), player1.name, fill=(200, 200, 255), font=name_font, anchor="mm")
        draw.text((width // 2, height // 2), "VS", fill=(255, 50, 50), font=vs_font, anchor="mm")
        draw.text((width * 3 // 4, 120), player2.name, fill=(200, 200, 255), font=name_font, anchor="mm")

        # Draw player cards
        p1_card_text = f"{player1_card[0]} of {player1_card[1]}"
        p2_card_text = f"{player2_card[0]} of {player2_card[1]}"

        # Create card backgrounds
        card_width = 250
        card_height = 200
        card_radius = 20

        # Draw Player 1's card
        p1_card_x = width // 4 - card_width // 2
        p1_card_y = height // 2 - card_height // 2
        self.draw_rounded_rectangle(draw, (p1_card_x, p1_card_y, p1_card_x + card_width, p1_card_y + card_height), 
                                    card_radius, fill=(255, 255, 255), outline=(50, 50, 50), width=5)

        # Draw Player 2's card
        p2_card_x = width * 3 // 4 - card_width // 2
        p2_card_y = height // 2 - card_height // 2
        self.draw_rounded_rectangle(draw, (p2_card_x, p2_card_y, p2_card_x + card_width, p2_card_y + card_height), 
                                    card_radius, fill=(255, 255, 255), outline=(50, 50, 50), width=5)

        # Draw card values
        # Color based on suit
        p1_color = (0, 0, 0)  # Default black
        if player1_card[1] in ['hearts', 'diamonds']:
            p1_color = (200, 0, 0)  # Red for hearts/diamonds

        p2_color = (0, 0, 0)  # Default black
        if player2_card[1] in ['hearts', 'diamonds']:
            p2_color = (200, 0, 0)  # Red for hearts/diamonds

        # Draw suit symbols and values
        p1_text = player1_card[0]
        p2_text = player2_card[0]

        # Add emoji based on suit
        p1_suit = "♠️" if player1_card[1] == "spades" else "♣️" if player1_card[1] == "clubs" else "♥️" if player1_card[1] == "hearts" else "♦️"
        p2_suit = "♠️" if player2_card[1] == "spades" else "♣️" if player2_card[1] == "clubs" else "♥️" if player2_card[1] == "hearts" else "♦️"

        # Draw card values in center of cards
        draw.text((p1_card_x + card_width // 2, p1_card_y + card_height // 2 - 30), 
                  p1_text, fill=p1_color, font=card_font, anchor="mm")
        draw.text((p1_card_x + card_width // 2, p1_card_y + card_height // 2 + 30), 
                  p1_suit, fill=p1_color, font=card_font, anchor="mm")

        draw.text((p2_card_x + card_width // 2, p2_card_y + card_height // 2 - 30), 
                  p2_text, fill=p2_color, font=card_font, anchor="mm")
        draw.text((p2_card_x + card_width // 2, p2_card_y + card_height // 2 + 30), 
                  p2_suit, fill=p2_color, font=card_font, anchor="mm")

        # Draw BetSync Casino at bottom
        draw.text((width // 2, height - 30), "BetSync Casino", fill=(150, 150, 150), font=name_font, anchor="mm")

        # Save image to buffer
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    def draw_rounded_rectangle(self, draw, xy, radius, fill=None, outline=None, width=1):
        """Draw a rounded rectangle"""
        x1, y1, x2, y2 = xy

        # Draw four corners
        draw.ellipse((x1, y1, x1 + radius * 2, y1 + radius * 2), fill=fill, outline=outline, width=width)
        draw.ellipse((x2 - radius * 2, y1, x2, y1 + radius * 2), fill=fill, outline=outline, width=width)
        draw.ellipse((x1, y2 - radius * 2, x1 + radius * 2, y2), fill=fill, outline=outline, width=width)
        draw.ellipse((x2 - radius * 2, y2 - radius * 2, x2, y2), fill=fill, outline=outline, width=width)

        # Draw four sides
        draw.rectangle((x1 + radius, y1, x2 - radius, y2), fill=fill, outline=None)
        draw.rectangle((x1, y1 + radius, x2, y2 - radius), fill=fill, outline=None)

        # Draw outline if specified
        if outline:
            draw.line((x1 + radius, y1, x2 - radius, y1), fill=outline, width=width)  # Top
            draw.line((x1 + radius, y2, x2 - radius, y2), fill=outline, width=width)  # Bottom
            draw.line((x1, y1 + radius, x1, y2 - radius), fill=outline, width=width)  # Left
            draw.line((x2, y1 + radius, x2, y2 - radius), fill=outline, width=width)  # Right

def setup(bot):
    bot.add_cog(CardDraw(bot))