
import os
import discord
import random
import asyncio
import datetime
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used="credits"):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None
        self.author_id = ctx.author.id

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the button to prevent spam clicks
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        # Get the context for the new game
        ctx = await self.cog.bot.get_context(self.message)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process bet using currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, self.bet_amount, self.currency_used, None)
        if not success:
            return await interaction.followup.send(embed=error_embed)

        # Launch a new game
        await self.cog.hilo(ctx, bet_info["amount"], bet_info["currency"])

class HiLoView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used, deck, current_card, current_multiplier=1.0, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.deck = deck
        self.current_card = current_card
        self.current_multiplier = current_multiplier
        self.current_winnings = bet_amount * current_multiplier
        self.message = None
        self.game_over = False

    @discord.ui.button(label="HIGHER", style=discord.ButtonStyle.primary, emoji="⬆️")
    async def higher_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        await self.process_round(interaction, "high")

    @discord.ui.button(label="LOWER", style=discord.ButtonStyle.primary, emoji="⬇️")
    async def lower_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        await self.process_round(interaction, "low")

    @discord.ui.button(label="SKIP", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        await self.process_round(interaction, "skip")

    @discord.ui.button(label="CASH OUT", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        await self.cash_out(interaction)

    async def cash_out(self, interaction):
        """Cash out current winnings"""
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        self.game_over = True
        winnings = self.current_winnings
        
        # Update the embed
        embed = discord.Embed(
            title="🃏 HiLo - CASHED OUT 💰",
            description=f"**{self.ctx.author.name}** cashed out with **{winnings:.2f}** {self.currency_used}!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Current Card",
            value=self.get_card_emoji(self.current_card),
            inline=True
        )
        
        embed.add_field(
            name="Multiplier",
            value=f"{self.current_multiplier:.2f}x",
            inline=True
        )
        
        embed.add_field(
            name="Final Winnings", 
            value=f"{winnings:.2f} {self.currency_used}",
            inline=True
        )
        
        embed.set_footer(text=f"BetSync Casino • {len(self.deck)} cards left in deck")
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Process winnings using the currency helper
        from Cogs.utils.currency_helper import process_win
        await process_win(self.ctx, winnings, self.currency_used, "hilo", skip_context=True)
        
        # Add to user and server history
        self.cog.add_to_history(self.ctx.author.id, self.ctx.guild.id, winnings, self.bet_amount, "win", "hilo")
        
        # Remove from ongoing games
        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]
        
        # Add play again button
        view = PlayAgainView(self.cog, self.ctx, self.bet_amount, self.currency_used)
        view.message = self.message
        
        await interaction.followup.send(
            f"Would you like to play again with {self.bet_amount} {self.currency_used}?",
            view=view
        )

    async def process_round(self, interaction, choice):
        """Process a round of HiLo"""
        if self.game_over or len(self.deck) == 0:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            return
            
        # Get the next card
        new_card = self.deck.pop(0)
        
        # Skip just changes the card without affecting winnings
        if choice == "skip":
            self.current_card = new_card
            embed = self.create_game_embed()
            return await interaction.response.edit_message(embed=embed, view=self)
            
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
            
            # Update game state
            self.current_multiplier *= new_multiplier
            self.current_winnings = self.bet_amount * self.current_multiplier
            self.current_card = new_card
            
            # Update the embed
            embed = self.create_game_embed(previous_card=self.current_card, win=True)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # Game over - player lost
            self.game_over = True
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
                
            # Create losing embed
            embed = discord.Embed(
                title="🃏 HiLo - GAME OVER 💔",
                description=f"**{self.ctx.author.name}** guessed {choice.upper()} and lost!",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="Previous Card",
                value=self.get_card_emoji(self.current_card),
                inline=True
            )
            
            embed.add_field(
                name="New Card",
                value=self.get_card_emoji(new_card),
                inline=True
            )
            
            embed.add_field(
                name="Potential Winnings Lost", 
                value=f"{self.current_winnings:.2f} {self.currency_used}",
                inline=True
            )
            
            embed.set_footer(text="BetSync Casino • Better luck next time!")
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Add to history
            self.cog.add_to_history(self.ctx.author.id, self.ctx.guild.id, 0, self.bet_amount, "loss", "hilo")
            
            # Remove from ongoing games
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]
                
            # Add play again button
            view = PlayAgainView(self.cog, self.ctx, self.bet_amount, self.currency_used)
            view.message = self.message
            
            await interaction.followup.send(
                f"Would you like to play again with {self.bet_amount} {self.currency_used}?",
                view=view
            )

    def create_game_embed(self, previous_card=None, win=False):
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
            name="Current Card",
            value=self.get_card_emoji(self.current_card),
            inline=True
        )
        
        embed.add_field(
            name="Current Multiplier",
            value=f"{self.current_multiplier:.2f}x",
            inline=True
        )
        
        embed.add_field(
            name="Current Winnings", 
            value=f"{self.current_winnings:.2f} {self.currency_used}",
            inline=True
        )
        
        if previous_card and win:
            embed.add_field(
                name="Previous Card",
                value=self.get_card_emoji(previous_card),
                inline=True
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
        house_edge = 0.04  # 4% house edge
        if probability <= 0:
            return 1.0  # Safety check
        return (1.0 - house_edge) / probability

class HiLo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    def add_to_history(self, user_id, server_id, amount, bet_amount, result_type, game):
        """Add game result to user and server history"""
        try:
            # Update user history
            db = Users()
            history_entry = {
                "type": result_type,
                "game": game,
                "amount": amount if result_type == "win" else 0,
                "bet": bet_amount,
                "timestamp": int(time.time())
            }
            db.update_history(user_id, history_entry)
            
            # Update server history
            server_db = Servers()
            server_history_entry = {
                "user_id": user_id,
                "type": result_type,
                "game": game,
                "amount": amount if result_type == "win" else 0,
                "bet": bet_amount,
                "timestamp": int(time.time())
            }
            server_db.update_history(server_id, server_history_entry)
            
            # Update server profit
            if result_type == "win":
                server_db.update_server_profit(server_id, -amount)
            else:
                server_db.update_server_profit(server_id, bet_amount)
                
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
    async def hilo(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play the HiLo card game - guess if the next card will be higher or lower!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🃏 How to Play HiLo",
                description=(
                    "**HiLo** is a card game where you bet on whether the next card will be higher or lower than the current one!\n\n"
                    "**Usage:** `!hilo <amount> [currency_type]`\n"
                    "**Example:** `!hilo 100` or `!hilo 100 tokens`\n\n"
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

        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing HiLo Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        # Process the bet amount using the currency helper
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)
        if not success:
            return await ctx.reply(embed=error_embed)
            
        # Set up the game
        bet_amount = bet_info["amount"]
        currency_used = bet_info["currency"]
        
        # Create a shuffled deck of cards
        deck = self.create_deck()
        
        # Draw the first card
        current_card = deck.pop(0)
        
        # Create game view
        view = HiLoView(self, ctx, bet_amount, currency_used, deck, current_card)
        
        # Create initial game embed
        embed = view.create_game_embed()
        
        # Mark user as having an ongoing game
        self.ongoing_games[ctx.author.id] = "hilo"
        
        # Send the game message
        message = await ctx.reply(embed=embed, view=view)
        view.message = message
        
        # Delete loading message
        try:
            await loading_message.delete()
        except:
            pass

def setup(bot):
    bot.add_cog(HiLo(bot))
