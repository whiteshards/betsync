
import discord
import random
import datetime
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

# Card values
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11
}

# Card suit emojis
CARD_SUITS = {
    'hearts': '♥️',
    'diamonds': '♦️',
    'clubs': '♣️',
    'spades': '♠️'
}

class CardDrawView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None
        self.game_over = False
        
        # Create a deck of cards
        self.deck = self.create_deck()
        
        # Draw cards for player and dealer
        self.player_card = self.draw_card()
        self.dealer_card = self.draw_card()
        
    def create_deck(self):
        """Create a shuffled deck of cards"""
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck
        
    def draw_card(self):
        """Draw a card from the deck"""
        if not self.deck:
            self.deck = self.create_deck()
        return self.deck.pop()
    
    def format_card(self, card):
        """Format a card with emoji and backticks"""
        rank, suit = card
        emoji = CARD_SUITS[suit]
        return f"`{rank} {emoji}`"
    
    def get_card_value(self, card):
        """Get the value of a card"""
        rank = card[0]
        return CARD_VALUES[rank]
    
    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success, emoji="🎮", custom_id="play_again")
    async def play_again_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        await interaction.response.defer()
        
        # Get the command from the bot
        carddraw_command = self.cog.bot.get_command('carddraw')
        if carddraw_command:
            # Create a new context
            new_ctx = await self.cog.bot.get_context(interaction.message)
            new_ctx.author = interaction.user
            
            # Run the command with the same bet amount
            await carddraw_command(new_ctx, str(self.bet_amount))
            
    async def on_timeout(self):
        if not self.game_over:
            self.game_over = True
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
                
            try:
                # Create timeout embed
                embed = discord.Embed(
                    title="🃏 Card Draw - Timeout",
                    description="Game timed out due to inactivity.",
                    color=discord.Color.red()
                )
                
                await self.message.edit(embed=embed, view=self)
                
            except Exception as e:
                print(f"Error in Card Draw timeout handler: {e}")

class CardDraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        
    @commands.command(aliases=["cd", "card"])
    async def carddraw(self, ctx, bet_amount: str = None):
        """
        Play Card Draw against the dealer - higher card wins!
        
        Usage: !carddraw <bet amount>
        Example: !carddraw 100
        """
        # Show help if no bet amount
        if not bet_amount:
            embed = discord.Embed(
                title="🃏 How to Play Card Draw",
                description=(
                    "**Card Draw** is a simple game where you draw one card against the dealer!\n\n"
                    "**Usage:** `!carddraw <amount>`\n"
                    "**Example:** `!carddraw 100`\n\n"
                    "**Rules:**\n"
                    "- You and the dealer each draw one card\n"
                    "- Higher card wins (values same as Blackjack)\n"
                    "- Card values: 2-10 = face value, J/Q/K = 10, A = 11\n"
                    "- Win and get 1.9x your bet!\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !cd, !card")
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
                title=f"{loading_emoji} | Preparing Card Draw Game...",
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
            tokens_used = bet_info["tokens_used"]
            currency_used = "points"
            
            # Create the game view
            view = CardDrawView(self, ctx, bet_amount_value, currency_used)
            
            # Delete loading message
            await loading_message.delete()
            
            # Get card values
            player_value = view.get_card_value(view.player_card)
            dealer_value = view.get_card_value(view.dealer_card)
            
            # Determine the winner
            if player_value > dealer_value:
                result = "win"
                win_amount = bet_amount_value * 1.9
                result_text = f"**You Win!** `{win_amount:.2f} {currency_used}`"
                embed_color = discord.Color.green()
                title = "<:yes:1355501647538815106> Card Draw - You Win!"
            elif player_value < dealer_value:
                result = "loss"
                result_text = "**Dealer Wins!** Better luck next time."
                embed_color = discord.Color.red()
                title = "🃏 Card Draw - Dealer Wins"
            else:
                result = "push"
                result_text = "**It's a Tie!** Your bet has been returned."
                embed_color = discord.Color.yellow()
                title = "🃏 Card Draw - Push!"
                
            # Create game result embed
            embed = discord.Embed(
                title=title,
                description=result_text,
                color=embed_color
            )
            
            # Format cards with emojis and backticks
            player_card_formatted = view.format_card(view.player_card)
            dealer_card_formatted = view.format_card(view.dealer_card)
            
            embed.add_field(name="Your Card", value=f"{player_card_formatted} (Value: {player_value})", inline=True)
            embed.add_field(name="Dealer's Card", value=f"{dealer_card_formatted} (Value: {dealer_value})", inline=True)
            
            # Handle game outcome in the database
            await self.handle_game_end(
                ctx,
                bet_amount_value,
                currency_used,
                result,
                view.player_card,
                view.dealer_card
            )
            
            # Mark game as over
            view.game_over = True
            
            # Send result message with play again button
            game_message = await ctx.reply(embed=embed, view=view)
            view.message = game_message
            
        except Exception as e:
            print(f"Card Draw error: {e}")
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
            
    async def handle_game_end(self, ctx, bet_amount, currency_used, result, player_card, dealer_card):
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
            win_amount = bet_amount * 1.9
        elif result == "push":
            win_amount = bet_amount  # Return original bet
            
        # Timestamp for history entries
        timestamp = int(datetime.datetime.now().timestamp())
        
        if result == "win" or result == "push":
            # Player wins or push - add winnings to balance
            user_db.update_balance(user_id, win_amount, "points", "$inc")
            
            # Add win to history
            multiplier = 1.9 if result == "win" else 1.0
            history_entry = {
                "type": "win" if result == "win" else "push",
                "game": "carddraw",
                "amount": win_amount,
                "bet": bet_amount,
                "multiplier": multiplier,
                "timestamp": timestamp
            }
            
            user_db.collection.update_one(
                {"discord_id": user_id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {"total_earned": win_amount, "total_won": 1 if result == "win" else 0, "total_played": 1}
                }
            )
            
            # Update server stats - casino loses on win, neutral on push
            if result == "win":
                server_db.update_server_profit(ctx, ctx.guild.id, -(win_amount - bet_amount), game="carddraw")
            
            # Add to server history
            server_history_entry = {
                "type": result,
                "game": "carddraw",
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
                "game": "carddraw",
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
            server_db.update_server_profit(ctx, ctx.guild.id, bet_amount, game="carddraw")
            
            # Add to server history
            server_history_entry = {
                "type": "loss",
                "game": "carddraw",
                "user_id": user_id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": bet_amount,
                "multiplier": 0,
                "timestamp": timestamp
            }
            server_db.update_history(ctx.guild.id, server_history_entry)

def setup(bot):
    bot.add_cog(CardDraw(bot))
