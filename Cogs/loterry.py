import os
import discord
import datetime
import time
import random
import asyncio
from discord.ext import commands, tasks
from Cogs.utils.mongo import Users, MongoClient
from Cogs.utils.emojis import emoji
from colorama import Fore

class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lottery_collection = MongoClient(os.getenv("MONGO"))["BetSync"]["lottery"]
        self.current_lottery = None
        self.lottery_cooldown = {}
        self.initialize_lottery()
        self.lottery_reset.start()

    def cog_unload(self):
        self.lottery_reset.cancel()

    def initialize_lottery(self):
        """Initialize or fetch the current lottery"""
        current = self.lottery_collection.find_one({"status": "active"})
        
        if not current:
            # Create a new lottery if none is active
            next_draw_time = self.get_next_draw_time()
            new_lottery = {
                "status": "active",
                "entries": [],
                "total_pot": 0,
                "created_at": int(time.time()),
                "draw_time": next_draw_time,
                "winner": None
            }
            self.lottery_collection.insert_one(new_lottery)
            self.current_lottery = new_lottery
        else:
            self.current_lottery = current

    def get_next_draw_time(self):
        """Calculate the next draw time (2:00 AM UTC)"""
        now = datetime.datetime.utcnow()
        if now.hour >= 2:
            # If it's past 2 AM, set for next day
            next_draw = now.replace(hour=2, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        else:
            # If it's before 2 AM, set for today
            next_draw = now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        return int(next_draw.timestamp())

    @tasks.loop(minutes=1)
    async def lottery_reset(self):
        """Check if it's time to draw the lottery"""
        try:
            if not self.current_lottery:
                self.initialize_lottery()
                return
                
            now = int(time.time())
            
            # If current time has passed the draw time
            if now >= self.current_lottery["draw_time"]:
                await self.draw_lottery()
                self.initialize_lottery()  # Create new lottery
        except Exception as e:
            print(f"{Fore.RED}[-] Lottery reset error: {e}")

    @lottery_reset.before_loop
    async def before_lottery_reset(self):
        await self.bot.wait_until_ready()

    async def draw_lottery(self):
        """Draw the lottery and announce the winner"""
        if not self.current_lottery:
            return
            
        entries = self.current_lottery["entries"]
        total_pot = self.current_lottery["total_pot"]
        
        if not entries:
            # No entries, no winner
            self.lottery_collection.update_one(
                {"_id": self.current_lottery["_id"]},
                {"$set": {"status": "completed", "winner": None}}
            )
            return
            
        # Calculate winning amount (96% of pot)
        winning_amount = int(total_pot * 0.96)
        
        # Create weighted list of user IDs based on number of entries
        user_entries = {}
        for entry in entries:
            user_id = entry["user_id"]
            if user_id in user_entries:
                user_entries[user_id] += 1
            else:
                user_entries[user_id] = 1
        
        # Create a weighted list for random selection
        weighted_entries = []
        for user_id, count in user_entries.items():
            weighted_entries.extend([user_id] * count)
        
        # Draw a winner
        winner_id = random.choice(weighted_entries)
        winner_entries = user_entries[winner_id]
        winner_user = await self.bot.fetch_user(winner_id)
        
        # Update lottery record
        self.lottery_collection.update_one(
            {"_id": self.current_lottery["_id"]},
            {
                "$set": {
                    "status": "completed", 
                    "winner": {
                        "user_id": winner_id,
                        "username": winner_user.name if winner_user else "Unknown",
                        "entries": winner_entries,
                        "winnings": winning_amount
                    }
                }
            }
        )
        
        # Update winner's balance
        db = Users()
        db.update_balance(winner_id, winning_amount, "tokens", "$inc")
        
        # Add to winner's history
        history_entry = {
            "type": "win",
            "game": "lottery",
            "amount": winning_amount,
            "timestamp": int(time.time())
        }
        db.collection.update_one(
            {"discord_id": winner_id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
        )
        
        # No longer announcing to all servers, only DMing the winner
        
        # Also DM the winner
        try:
            dm_embed = discord.Embed(
                title="🎉 You Won the Lottery! 🎉",
                description=f"Congratulations! You won **{winning_amount}** tokens in the lottery!",
                color=discord.Color.gold()
            )
            dm_embed.add_field(
                name="Your Entries",
                value=f"{winner_entries} entries"
            )
            dm_embed.add_field(
                name="Total Prize Pool",
                value=f"{total_pot} tokens"
            )
            dm_embed.set_footer(text="BetSync Casino • Thanks for playing!")
            
            if winner_user:
                await winner_user.send(embed=dm_embed)
        except Exception as e:
            print(f"Failed to DM lottery winner {winner_id}: {e}")

    def calculate_probabilities(self):
        """Calculate winning probability for each participant"""
        if not self.current_lottery:
            return {}
            
        entries = self.current_lottery["entries"]
        if not entries:
            return {}
            
        # Count entries per user
        user_entries = {}
        for entry in entries:
            user_id = entry["user_id"]
            if user_id in user_entries:
                user_entries[user_id] += 1
            else:
                user_entries[user_id] = 1
        
        # Calculate probabilities
        total_entries = len(entries)
        probabilities = {}
        
        for user_id, entry_count in user_entries.items():
            probabilities[user_id] = (entry_count / total_entries) * 100
            
        return probabilities
        
    async def process_ticket_purchase(self, ctx, quantity=1):
        """Process a ticket purchase for the lottery"""
        if not self.current_lottery:
            self.initialize_lottery()
            
        if ctx.author.id in self.lottery_cooldown and time.time() - self.lottery_cooldown[ctx.author.id] < 5:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Purchase Cooldown",
                description="Please wait a few seconds before buying more tickets.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return False
            
        # Calculate cost (10 tokens per ticket)
        cost = quantity * 10
        
        # Process payment through currency helper
        db = Users()
        balance = db.fetch_user(ctx.author.id)
        
        if not balance:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | No Account",
                description="You don't have an account yet. Use `!start` to create one.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return False
            
        tokens_balance = balance.get("tokens", 0)
        credits_balance = balance.get("credits", 0)
        
        # Check if user has enough tokens or credits
        if tokens_balance >= cost:
            # Use tokens
            currency_used = "tokens"
            success = db.update_balance(ctx.author.id, -cost, currency_used, "$inc")
        elif credits_balance >= cost:
            # Use credits
            currency_used = "credits"
            success = db.update_balance(ctx.author.id, -cost, currency_used, "$inc")
        else:
            # Not enough funds
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You need {cost} tokens or credits to buy {quantity} {'tickets' if quantity > 1 else 'ticket'}.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return False
            
        if not success:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Transaction Failed",
                description="There was an error processing your purchase.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return False
            
        # Add entries to the lottery
        new_entries = []
        for _ in range(quantity):
            entry = {
                "user_id": ctx.author.id,
                "username": ctx.author.name,
                "timestamp": int(time.time()),
                "currency_used": currency_used
            }
            new_entries.append(entry)
            
        # Update the lottery in the database
        self.lottery_collection.update_one(
            {"_id": self.current_lottery["_id"]},
            {
                "$push": {"entries": {"$each": new_entries}},
                "$inc": {"total_pot": cost}
            }
        )
        
        # Update the local cache
        self.current_lottery["entries"].extend(new_entries)
        self.current_lottery["total_pot"] += cost
        
        # Set cooldown
        self.lottery_cooldown[ctx.author.id] = time.time()
        
        return True

    @commands.command(aliases=["lottery"])
    async def loterry(self, ctx, action=None, quantity: int = 1):
        """View or participate in the current lottery"""
        if not self.current_lottery:
            self.initialize_lottery()
            
        if action and action.lower() in ["buy", "purchase"]:
            # Validate quantity
            if quantity <= 0:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Quantity",
                    description="You must buy at least 1 ticket.",
                    color=discord.Color.red()
                )
                return await ctx.reply(embed=embed)
                
            if quantity > 100:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Too Many Tickets",
                    description="You can buy a maximum of 100 tickets at once.",
                    color=discord.Color.red()
                )
                return await ctx.reply(embed=embed)
                
            # Process the purchase
            loading_embed = discord.Embed(
                title="<a:loading:1344611780638412811> | Processing Purchase...",
                description=f"Buying {quantity} {'tickets' if quantity > 1 else 'ticket'} for {quantity * 10} tokens...",
                color=discord.Color.gold()
            )
            message = await ctx.reply(embed=loading_embed)
            
            success = await self.process_ticket_purchase(ctx, quantity)
            
            if success:
                # Get user's current probability
                probabilities = self.calculate_probabilities()
                user_probability = probabilities.get(ctx.author.id, 0)
                
                success_embed = discord.Embed(
                    title="<:checkmark:1344252974188335206> | Tickets Purchased!",
                    description=f"You've successfully purchased {quantity} {'tickets' if quantity > 1 else 'ticket'} for the lottery!",
                    color=discord.Color.green()
                )
                success_embed.add_field(
                    name="Your Odds of Winning",
                    value=f"{user_probability:.2f}%"
                )
                success_embed.add_field(
                    name="Draw Time",
                    value=f"<t:{self.current_lottery['draw_time']}:R>"
                )
                success_embed.add_field(
                    name="Current Prize Pool",
                    value=f"{self.current_lottery['total_pot']} tokens"
                )
                await message.edit(embed=success_embed)
            else:
                await message.delete()
        else:
            # Show current lottery status
            total_entries = len(self.current_lottery["entries"])
            user_entries = sum(1 for entry in self.current_lottery["entries"] if entry["user_id"] == ctx.author.id)
            total_pot = self.current_lottery["total_pot"]
            draw_time = self.current_lottery["draw_time"]
            
            # Calculate user's winning probability
            probabilities = self.calculate_probabilities()
            user_probability = probabilities.get(ctx.author.id, 0)
            
            embed = discord.Embed(
                title="🎰 BetSync Lottery",
                description=(
                    "Try your luck in our daily lottery! Each ticket costs **10 tokens**.\n"
                    "The more tickets you buy, the higher your chances of winning!"
                ),
                color=0xFFD700
            )
            
            embed.add_field(
                name="Current Prize Pool",
                value=f"{total_pot} tokens"
            )
            embed.add_field(
                name="Payout",
                value="96% of the pot"
            )
            embed.add_field(
                name="Draw Time",
                value=f"<t:{draw_time}:R>"
            )
            embed.add_field(
                name="Total Entries",
                value=f"{total_entries} tickets"
            )
            embed.add_field(
                name="Your Entries",
                value=f"{user_entries} tickets"
            )
            embed.add_field(
                name="Your Win Chance",
                value=f"{user_probability:.2f}%"
            )
            
            embed.add_field(
                name="How to Play",
                value=(
                    "Use `!loterry buy <quantity>` to purchase tickets.\n"
                    "Example: `!loterry buy 5` to buy 5 tickets."
                ),
                inline=False
            )
            
            # Get last lottery winner
            last_lottery = self.lottery_collection.find_one(
                {"status": "completed", "winner": {"$ne": None}},
                sort=[("draw_time", -1)]
            )
            
            if last_lottery and last_lottery.get("winner"):
                winner = last_lottery["winner"]
                embed.add_field(
                    name="Last Winner",
                    value=(
                        f"**{winner['username']}** won **{winner['winnings']}** tokens "
                        f"with {winner['entries']} {'entries' if winner['entries'] > 1 else 'entry'}!"
                    ),
                    inline=False
                )
                
            embed.set_footer(text="BetSync Casino • Daily Lottery")
            await ctx.reply(embed=embed)

    @commands.command(aliases=["lh"])
    async def loterryhistory(self, ctx):
        """View lottery history"""
        # Get the last 5 completed lotteries
        history = list(self.lottery_collection.find(
            {"status": "completed"},
            sort=[("draw_time", -1)],
            limit=5
        ))
        
        if not history:
            embed = discord.Embed(
                title="📜 Lottery History",
                description="No lottery has been completed yet.",
                color=discord.Color.blue()
            )
            return await ctx.reply(embed=embed)
            
        embed = discord.Embed(
            title="📜 Lottery History",
            description="The most recent lottery results:",
            color=discord.Color.blue()
        )
        
        for i, lottery in enumerate(history, 1):
            draw_time = lottery.get("draw_time", 0)
            total_pot = lottery.get("total_pot", 0)
            total_entries = len(lottery.get("entries", []))
            winner = lottery.get("winner", {})
            
            if winner:
                winner_info = (
                    f"**{winner.get('username', 'Unknown')}** won **{winner.get('winnings', 0)}** tokens "
                    f"with {winner.get('entries', 0)} entries!"
                )
            else:
                winner_info = "No entries, no winner."
                
            embed.add_field(
                name=f"Lottery #{i} - <t:{draw_time}:D>",
                value=(
                    f"Prize Pool: {total_pot} tokens\n"
                    f"Total Entries: {total_entries}\n"
                    f"Winner: {winner_info}"
                ),
                inline=False
            )
            
        embed.set_footer(text="BetSync Casino • Lottery History")
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Lottery(bot))
