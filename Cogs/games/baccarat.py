
import discord
import asyncio
import random
import datetime
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class BaccaratView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_type, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_type = currency_type

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game.", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.defer()
        message = await interaction.original_message()
        await message.edit(view=self)
        
        # Call the baccarat command again with the same bet
        await self.cog.baccarat(self.ctx, self.bet_amount, self.currency_type)

class BaccaratGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        self.card_ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.card_suits = ['hearts', 'diamonds', 'clubs', 'spades']

    def calculate_baccarat_value(self, cards):
        """Calculate the value of a baccarat hand"""
        value = 0
        for card in cards:
            rank = card[0]
            if rank == 'A':
                value += 1
            elif rank in ['10', 'J', 'Q', 'K']:
                value += 0  # 10 and face cards are worth 0 in baccarat
            else:
                value += int(rank)
        
        # In baccarat, only the ones digit matters
        return value % 10

    def get_card_emoji(self, card):
        """Get a textual representation of a card"""
        rank, suit = card
        suit_emoji = {
            'hearts': '♥️',
            'diamonds': '♦️',
            'clubs': '♣️',
            'spades': '♠️'
        }
        return f"`{rank}{suit_emoji[suit]}`"

    def deal_card(self, deck):
        """Deal a card from the deck"""
        if not deck:
            # Regenerate deck if it's empty (unlikely but just in case)
            deck = [(rank, suit) for rank in self.card_ranks for suit in self.card_suits]
            random.shuffle(deck)
        return deck.pop()

    @commands.command(aliases=["bacc", "bc"])
    async def baccarat(self, ctx, bet_amount: str = None, currency_type: str = None, bet_on: str = None):
        """Play Baccarat - bet on Player, Banker, or Tie"""
        
        # Show help if no bet amount specified
        if not bet_amount:
            embed = discord.Embed(
                title="🎴 How to Play Baccarat",
                description=(
                    "**Baccarat** is a simple card game where you bet on which hand will win.\n\n"
                    "**Usage:** `!baccarat <amount> [currency_type] [player/banker/tie]`\n"
                    "**Example:** `!baccarat 100 tokens player`\n\n"
                    "- **Player & Banker each get 2 cards**\n"
                    "- **Card values: A=1, 2-9=face value, 10/J/Q/K=0**\n"
                    "- **Only the ones digit of the total matters (12 = 2)**\n"
                    "- **Win 1.95x your bet on correct player/banker pick**\n"
                    "- **Win 8x your bet on a correct tie prediction**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !bacc, !bc")
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
                title=f"{loading_emoji} | Preparing Baccarat Game...",
                description="Please wait while we set up your game.",
                color=0x00FFAE
            )
            loading_message = await ctx.reply(embed=loading_embed)
            
            # Import the currency helper
            from Cogs.utils.currency_helper import process_bet_amount
            
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)
            if not success:
                try:
                    await loading_message.delete()
                except:
                    pass
                return await ctx.reply(embed=error_embed)
            
            # Extract bet information
            tokens_used = bet_info["tokens_used"]
            credits_used = bet_info["credits_used"]
            total_bet = bet_info["total_bet_amount"]
            
            # Determine currency used for results
            currency_used = "tokens" if tokens_used > 0 else "credits"
            
            # Format bet description
            if tokens_used > 0 and credits_used > 0:
                bet_description = f"Bet: **{tokens_used:.2f} tokens** and **{credits_used:.2f} credits**"
            elif tokens_used > 0:
                bet_description = f"Bet: **{tokens_used:.2f} tokens**"
            else:
                bet_description = f"Bet: **{credits_used:.2f} credits**"
            
            # Validate bet_on parameter or handle interactive selection
            valid_options = ["player", "p", "banker", "b", "tie", "t"]
            
            # If bet_on is not provided or is invalid, prompt user to choose
            if bet_on is None or bet_on.lower() not in valid_options:
                # Create buttons for choosing bet
                class BetSelectionView(discord.ui.View):
                    def __init__(self, timeout=30):
                        super().__init__(timeout=timeout)
                        self.bet_on = None
                    
                    @discord.ui.button(label="Player (1.95x)", style=discord.ButtonStyle.primary)
                    async def player_button(self, button, interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message("This is not your game.", ephemeral=True)
                        self.bet_on = "player"
                        self.stop()
                        
                    @discord.ui.button(label="Banker (1.95x)", style=discord.ButtonStyle.danger)
                    async def banker_button(self, button, interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message("This is not your game.", ephemeral=True)
                        self.bet_on = "banker"
                        self.stop()
                    
                    @discord.ui.button(label="Tie (4x)", style=discord.ButtonStyle.secondary)
                    async def tie_button(self, button, interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message("This is not your game.", ephemeral=True)
                        self.bet_on = "tie"
                        self.stop()
                
                # Delete the loading message
                await loading_message.delete()
                
                # Prompt user to choose
                selection_embed = discord.Embed(
                    title="🎴 Baccarat - Select Your Bet",
                    description=(
                        f"{bet_description}\n\n"
                        "**Choose who to bet on:**\n"
                        "**Player** - Win 1.95x if player hand wins\n"
                        "**Banker** - Win 1.95x if banker hand wins\n"
                        "**Tie** - Win 4x if the hands tie"
                    ),
                    color=0x00FFAE
                )
                view = BetSelectionView()
                selection_message = await ctx.reply(embed=selection_embed, view=view)
                
                # Wait for selection
                await view.wait()
                
                # If timeout or no selection
                if not view.bet_on:
                    # Refund the bet
                    user_db = Users()
                    if tokens_used > 0:
                        user_db.update_balance(ctx.author.id, tokens_used, "tokens", "$inc")
                    if credits_used > 0:
                        user_db.update_balance(ctx.author.id, credits_used, "credits", "$inc")
                    
                    # Update message
                    timeout_embed = discord.Embed(
                        title="<:no:1344252518305234987> | Bet Cancelled",
                        description="You didn't select an option in time. Your bet has been refunded.",
                        color=0xFF0000
                    )
                    await selection_message.edit(embed=timeout_embed, view=None)
                    return
                
                bet_on = view.bet_on
                await selection_message.delete()
                
                # Create a new loading message
                loading_message = await ctx.reply(embed=loading_embed)
            else:
                # Normalize bet_on
                if bet_on.lower() in ["p", "player"]:
                    bet_on = "player"
                elif bet_on.lower() in ["b", "banker"]:
                    bet_on = "banker"
                else:
                    bet_on = "tie"
            
            # Mark the game as ongoing
            self.ongoing_games[ctx.author.id] = {
                "tokens_used": tokens_used,
                "credits_used": credits_used,
                "bet_amount": total_bet,
                "bet_on": bet_on
            }
            
            # Create a deck of cards
            deck = [(rank, suit) for rank in self.card_ranks for suit in self.card_suits]
            random.shuffle(deck)
            
            # Deal initial cards
            player_cards = [self.deal_card(deck), self.deal_card(deck)]
            banker_cards = [self.deal_card(deck), self.deal_card(deck)]
            
            # Calculate scores
            player_score = self.calculate_baccarat_value(player_cards)
            banker_score = self.calculate_baccarat_value(banker_cards)
            
            # Determine winner
            if player_score > banker_score:
                winner = "player"
                win_multiplier = 1.95 if bet_on == "player" else 0
            elif banker_score > player_score:
                winner = "banker"
                win_multiplier = 1.95 if bet_on == "banker" else 0
            else:
                winner = "tie"
                win_multiplier = 4 if bet_on == "tie" else 0
            
            # Calculate winnings
            win_amount = total_bet * win_multiplier
            
            # Delete loading message
            await loading_message.delete()
            
            # Create result embed
            result_embed = discord.Embed(
                title="🎴 Baccarat Results",
                color=0x00FFAE if win_amount > 0 else 0xFF0000
            )
            
            # Show bet information
            result_embed.add_field(
                name="Your Bet",
                value=f"{bet_description}\nYou bet on: **{bet_on.title()}**",
                inline=False
            )
            
            # Display both hands
            player_cards_str = " ".join(self.get_card_emoji(card) for card in player_cards)
            banker_cards_str = " ".join(self.get_card_emoji(card) for card in banker_cards)
            
            result_embed.add_field(
                name=f"Player Hand - {player_score}",
                value=player_cards_str,
                inline=True
            )
            
            result_embed.add_field(
                name=f"Banker Hand - {banker_score}",
                value=banker_cards_str,
                inline=True
            )
            
            # Show result
            if win_amount > 0:
                result_text = f"**YOU WON!** {bet_on.title()} wins!\nWon: **{win_amount:.2f}** {currency_used}"
            else:
                result_text = f"**YOU LOST!** {winner.title()} wins!\nLost: **{total_bet:.2f}** {currency_used}"
            
            result_embed.add_field(
                name="Result",
                value=result_text,
                inline=False
            )
            
            result_embed.set_footer(text="BetSync Casino • Use the Play Again button to play another round")
            
            # Process game result in the database
            user_db = Users()
            server_db = Servers()
            
            # Timestamp for history entries
            timestamp = int(datetime.datetime.now().timestamp())
            
            if win_amount > 0:
                # Player wins - add winnings to balance
                user_db.update_balance(ctx.author.id, win_amount, "credits", "$inc")
                
                # Add win to history
                history_entry = {
                    "type": "win",
                    "game": "baccarat",
                    "amount": win_amount,
                    "bet": total_bet,
                    "multiplier": win_multiplier,
                    "timestamp": timestamp
                }
                
                user_db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {
                        "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                        "$inc": {"total_earned": win_amount, "total_won": 1, "total_played": 1}
                    }
                )
                
                # Update server stats - casino loses
                server_db.update_server_profit(ctx.guild.id, -(win_amount - total_bet), game="baccarat")
                
                # Add to server history
                server_history_entry = {
                    "type": "win",
                    "game": "baccarat",
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name,
                    "bet_amount": total_bet,
                    "win_amount": win_amount,
                    "timestamp": timestamp
                }
                
                server_db.update_history(ctx.guild.id, server_history_entry)
            else:
                # Player loses - record loss
                history_entry = {
                    "type": "loss",
                    "game": "baccarat",
                    "amount": total_bet,
                    "timestamp": timestamp
                }
                
                user_db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {
                        "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                        "$inc": {"total_spent": total_bet, "total_lost": 1, "total_played": 1}
                    }
                )
                
                # Update server stats - casino wins
                server_db.update_server_profit(ctx.guild.id, total_bet, game="baccarat")
                
                # Add to server history
                server_history_entry = {
                    "type": "loss",
                    "game": "baccarat",
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name,
                    "bet_amount": total_bet,
                    "timestamp": timestamp
                }
                
                server_db.update_history(ctx.guild.id, server_history_entry)
            
            # Remove game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]
            
            # Create Play Again button
            view = BaccaratView(self, ctx, bet_amount, currency_type)
            
            # Send result
            await ctx.reply(embed=result_embed, view=view)
            
        except Exception as e:
            # Handle any errors
            print(f"Error in baccarat game: {e}")
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while playing baccarat: {e}",
                color=0xFF0000
            )
            
            # Try to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]
            
            try:
                await loading_message.delete()
            except:
                pass
                
            await ctx.reply(embed=error_embed)

def setup(bot):
    bot.add_cog(BaccaratGame(bot))
