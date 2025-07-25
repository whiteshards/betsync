
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class WheelSelectionView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, spins, game_id, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.spins = spins
        self.game_id = game_id
        self.message = None

    @discord.ui.button(label="🎰 SPIN THE WHEEL", style=discord.ButtonStyle.primary, emoji="🎰", custom_id="spin_wheel")
    async def spin_wheel(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        
        # Start the wheel spin instantly
        await self.cog.start_wheel_spin(self.ctx, interaction, self.bet_amount, self.spins, self.game_id)

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
                
                # Remove from ongoing games
                if self.game_id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.game_id]
            except:
                pass


class InstantSpinView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, spins, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.spins = spins
        self.message = None

    @discord.ui.button(label="🎰 SPIN AGAIN", style=discord.ButtonStyle.primary, emoji="🎰", custom_id="spin_again")
    async def spin_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Start a new game with the same parameters
        await self.cog.wheel(self.ctx, str(self.bet_amount), self.spins)

    @discord.ui.button(label="💰 DOUBLE BET", style=discord.ButtonStyle.danger, emoji="💰", custom_id="double_bet")
    async def double_bet(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Double the bet and start new game
        await self.cog.wheel(self.ctx, str(self.bet_amount * 2), self.spins)

    @discord.ui.button(label="📈 MAX SPINS", style=discord.ButtonStyle.success, emoji="📈", custom_id="max_spins")
    async def max_spins(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Start with maximum spins
        await self.cog.wheel(self.ctx, str(self.bet_amount), 15)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


class WheelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        # Define color multipliers with proper house edge (casino-favorable)
        self.colors = {
            "gray": {"emoji": "⚫", "multiplier": 0, "chance": 65, "name": "BUST"},
            "yellow": {"emoji": "🟡", "multiplier": 1.5, "chance": 20, "name": "BRONZE"},
            "red": {"emoji": "🔴", "multiplier": 2.5, "chance": 8, "name": "SILVER"},
            "blue": {"emoji": "🔵", "multiplier": 4.0, "chance": 4, "name": "GOLD"},
            "green": {"emoji": "🟢", "multiplier": 8.0, "chance": 2, "name": "DIAMOND"},
            "purple": {"emoji": "🟣", "multiplier": 15.0, "chance": 0.8, "name": "RUBY"},
            "orange": {"emoji": "🟠", "multiplier": 25.0, "chance": 0.2, "name": "LEGENDARY"}
        }
        # Calculate total chance (now uses weighted system for better precision)
        self.total_chance = 1000  # Using 1000 for precise decimal chances
        
        # Convert percentages to weighted ranges for precise probability
        self.weighted_colors = []
        for color, data in self.colors.items():
            weight = int(data["chance"] * 10)  # Convert to integer weights
            self.weighted_colors.extend([color] * weight)

    @commands.command(aliases=["wh"])
    async def wheel(self, ctx, bet_amount: str = None, spins: int = 1):
        """🎰 Spin the Fortune Wheel - instant results, instant wins!"""
        # Limit the number of spins to 15
        if spins > 15:
            spins = 15
        elif spins < 1:
            spins = 1

        if not bet_amount:
            embed = discord.Embed(
                title="🎰 **FORTUNE WHEEL** 🎰",
                description=(
                    "```ansi\n"
                    "\u001b[1;33m💎 INSTANT FORTUNE AWAITS 💎\u001b[0m\n"
                    "```\n"
                    "**🚀 Quick Start:**\n"
                    "> `!wheel <amount> [spins]`\n"
                    "> `!wheel 100 5` - Bet 100 on each of 5 spins (500 total)!\n\n"
                    
                    "**🎨 Wheel Zones & Multipliers:**\n"
                    "> ⚫ **BUST** - 0x (65% chance) - Game over!\n"
                    "> 🟡 **BRONZE** - 1.5x (20% chance) - Small win!\n"
                    "> 🔴 **SILVER** - 2.5x (8% chance) - Nice win!\n"
                    "> 🔵 **GOLD** - 4x (4% chance) - Great win!\n"
                    "> 🟢 **DIAMOND** - 8x (2% chance) - Amazing win!\n"
                    "> 🟣 **RUBY** - 15x (0.8% chance) - Epic win!\n"
                    "> 🟠 **LEGENDARY** - 25x (0.2% chance) - ULTIMATE!\n\n"
                    
                    "**⚡ Features:**\n"
                    "> • Instant results - no waiting!\n"
                    "> • Multi-spin capability (max 15)\n"
                    "> • Quick action buttons\n"
                    "> • Progressive excitement\n\n"
                    
                    "```diff\n"
                    "+ Ready for instant fortune? Let's spin! 🎰\n"
                    "```"
                ),
                color=0xFF6B00
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
            embed.set_footer(text="🎰 BetSync Casino • Fortune favors the bold!", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send exciting loading message
        loading_embed = discord.Embed(
            title="🎰 **PREPARING THE WHEEL...**",
            description=(
                "```ansi\n"
                "\u001b[1;36m⚡ PROCESSING INSTANT FORTUNE ⚡\u001b[0m\n"
                "```\n"
                "```yaml\n"
                "Status: Validating bet...\n"
                "Action: Charging wheel...\n"
                "Ready: Almost there...\n"
                "```"
            ),
            color=0x00FFFF
        )
        loading_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount using currency_helper
        from Cogs.utils.currency_helper import process_bet_amount
        
        # Initialize database connection
        db = Users()
        
        # For multiple spins, we need to calculate the total bet first
        if spins > 1:
            # First validate the base bet amount
            try:
                if bet_amount.lower() in ["all", "max"]:
                    # For "all", divide by spins to get per-spin amount, then multiply back
                    user_data = db.fetch_user(ctx.author.id)
                    if user_data == False:
                        await loading_message.delete()
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | User Not Found",
                            description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                            color=0xFF0000
                        )
                        return await ctx.reply(embed=embed)
                    
                    available_balance = user_data.get("points", 0)
                    bet_amount_value = available_balance // spins  # Per spin amount
                    total_bet_needed = bet_amount_value * spins
                    
                    if bet_amount_value <= 0:
                        await loading_message.delete()
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Balance",
                            description=f"You don't have enough points for {spins} spins.",
                            color=0xFF0000
                        )
                        return await ctx.reply(embed=embed)
                else:
                    bet_amount_value = float(bet_amount)
                    total_bet_needed = bet_amount_value * spins
                    
                # Check if user has enough for total bet
                user_data = db.fetch_user(ctx.author.id)
                current_balance = user_data.get("points", 0)
                if current_balance < total_bet_needed:
                    await loading_message.delete()
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Insufficient Balance",
                        description=f"You need `{total_bet_needed:.0f}` points for {spins} spins of `{bet_amount_value:.0f}` each, but only have `{current_balance:.0f}` points.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
                
                # Deduct the total amount
                db.update_balance(ctx.author.id, -total_bet_needed, "points", "$inc")
                tokens_used = 0
                
            except ValueError:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Please enter a valid number or 'all'.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:
            # Single spin - use normal process_bet_amount
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)
            
            # If processing failed, return the error
            if not success:
                await loading_message.delete() 
                return await ctx.reply(embed=error_embed)
                
            # Extract needed values from bet_info
            tokens_used = bet_info["tokens_used"]
            total_bet = bet_info["total_bet_amount"]
            bet_amount_value = total_bet

        # Generate unique game ID
        import uuid
        game_id = str(uuid.uuid4())
            
        # Mark game as ongoing
        self.ongoing_games[game_id] = {
            "user_id": ctx.author.id,
            "bet_amount": bet_amount_value,
            "tokens_used": tokens_used,
            "spins": spins
        }

        # Skip to results immediately
        await self.start_wheel_spin(ctx, loading_message, bet_amount_value, spins, game_id)

    async def start_wheel_spin(self, ctx, message, bet_amount, spins, game_id):
        """Start the wheel spinning with instant results"""
        # Remove from ongoing games
        if game_id in self.ongoing_games:
            del self.ongoing_games[game_id]

        # Calculate results for all spins with improved house edge (15%)
        house_edge = 0.15  # 15% house edge for better player experience

        # Store results for all spins
        spin_results = []
        total_winnings = 0
        bet_total = bet_amount  # Each spin uses the full bet amount
        total_bet_amount = bet_total * spins  # Total deducted is bet × spins

        # Calculate results for each spin instantly
        for spin_num in range(spins):
            # Use new weighted random selection for precise probabilities
            result_color = random.choice(self.weighted_colors)

            # Get base multiplier for the result
            base_multiplier = self.colors[result_color]["multiplier"]
            result_emoji = self.colors[result_color]["emoji"]
            result_name = self.colors[result_color]["name"]

            # Apply house edge to multiplier (15% reduction on all wins)
            if base_multiplier > 0:
                result_multiplier = base_multiplier * (1 - house_edge)
            else:
                result_multiplier = 0  # BUST stays 0

            # Calculate winnings for this spin
            winnings = bet_total * result_multiplier
            
            # Keep original display values for consistency
            display_multiplier = result_multiplier
            display_name = result_name
            total_winnings += winnings

            # Add this result to our results list
            spin_results.append({
                "color": result_color,
                "emoji": result_emoji,
                "multiplier": display_multiplier,
                "actual_multiplier": result_multiplier,  # Keep actual for calculations
                "winnings": winnings,
                "spin_number": spin_num + 1,
                "name": display_name
            })

        # Show instant results with excitement
        await self.show_wheel_results(ctx, message, spin_results, bet_total, total_bet_amount, total_winnings, spins)

    async def show_wheel_results(self, ctx, message, spin_results, bet_total, total_bet_amount, total_winnings, spins):
        """Show the final wheel results with exciting presentation"""
        # Create result embed - use consistent titles for any win
        if total_winnings > 0:
            title = "🎰 **WHEEL RESULT** 🎰"
            color = 0x00FF00
            result_icon = "<:yes:1355501647538815106>"
        else:
            title = "🎰 **WHEEL RESULT** 🎰"
            color = 0xFF4444
            result_icon = "<:no:1344252518305234987>"

        embed = discord.Embed(
            title=f"{result_icon} | {title}",
            color=color
        )

        # Format bet description with excitement
        embed.description = f"```ansi\n\u001b[1;36m💰 TOTAL BET: {total_bet_amount:.2f} points\u001b[0m\n"
        if spins > 1:
            embed.description += f"\u001b[1;37m🎰 PER SPIN: {bet_total:.2f} points\u001b[0m\n"
        embed.description += "```"

        # Create a summary of all results with visual excitement
        if spins > 1:
            results_summary = ""
            wins_count = 0
            diamond_hits = 0
            gold_hits = 0
            
            # Group results by color for cleaner display
            color_counts = {}
            for result in spin_results:
                color = result['color']
                if color not in color_counts:
                    color_counts[color] = {
                        'count': 0, 
                        'total_winnings': 0, 
                        'emoji': result['emoji'], 
                        'multiplier': result['multiplier'],
                        'name': result['name']
                    }
                color_counts[color]['count'] += 1
                color_counts[color]['total_winnings'] += result['winnings']
                if result['multiplier'] > 0:
                    wins_count += 1
                if result['name'] == "DIAMOND":
                    diamond_hits += 1
                elif result['name'] == "GOLD":
                    gold_hits += 1

            # Display grouped results
            for color, data in color_counts.items():
                if data['count'] > 0:
                    results_summary += f"{data['emoji']} **{data['name']}** x{data['count']} - {data['multiplier']:.2f}x - {data['total_winnings']:.2f} pts\n"

            embed.add_field(
                name=f"🎰 Spin Results ({wins_count}/{spins} wins)",
                value=results_summary,
                inline=False
            )
        else:
            # Single spin - show main result
            main_result = spin_results[0]
            
            embed.add_field(
                name="🎯 Result",
                value=f"{main_result['emoji']} **{main_result['name']}** - {main_result['multiplier']:.2f}x",
                inline=False
            )

        # Add overall result field with winnings
        if total_winnings > 0:
            embed.add_field(
                name=f"🏆 Final Results",
                value=(
                    f"**💰 Total Winnings:** {total_winnings:.2f} points\n"
                    f"**⚡ Multiplier:** {total_winnings/total_bet_amount:.2f}x"
                ),
                inline=False
            )

            # Update user's balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, total_winnings, "credits", "$inc")

            # Process stats and history
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id) if ctx.guild else None

            # Track wins and losses for stats
            wins_count = 0
            losses_count = 0
            house_profit = 0

            # History entries for batch update
            history_entries = []
            server_history_entries = []

            for i, result in enumerate(spin_results):
                # Process individual spin history
                if result["multiplier"] > 0:
                    # This spin was a win
                    wins_count += 1
                    history_entry = {
                        "type": "win",
                        "game": "wheel",
                        "bet": bet_total,
                        "amount": result["winnings"],
                        "multiplier": result.get("actual_multiplier", result["multiplier"]),
                        "timestamp": int(time.time()) + i
                    }

                    if server_data:
                        server_bet_history_entry = {
                            "type": "win",
                            "game": "wheel",
                            "user_id": ctx.author.id,
                            "user_name": ctx.author.name,
                            "bet": bet_total,
                            "amount": result["winnings"],
                            "multiplier": result.get("actual_multiplier", result["multiplier"]),
                            "timestamp": int(time.time()) + i
                        }
                        server_history_entries.append(server_bet_history_entry)
                        house_profit += bet_total - result["winnings"]
                else:
                    # This spin was a loss
                    losses_count += 1
                    history_entry = {
                        "type": "loss",
                        "game": "wheel",
                        "bet": bet_total,
                        "amount": bet_total,
                        "multiplier": result.get("actual_multiplier", result["multiplier"]),
                        "timestamp": int(time.time()) + i
                    }

                    if server_data:
                        server_bet_history_entry = {
                            "type": "loss",
                            "game": "wheel",
                            "user_id": ctx.author.id,
                            "user_name": ctx.author.name,
                            "bet": bet_total,
                            "amount": bet_total,
                            "multiplier": result.get("actual_multiplier", result["multiplier"]),
                            "timestamp": int(time.time()) + i
                        }
                        server_history_entries.append(server_bet_history_entry)
                        house_profit += bet_total

                history_entries.append(history_entry)

            # Update user's stats with all spins
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$push": {"history": {"$each": history_entries, "$slice": -100}},
                    "$inc": {
                        "total_played": spins,
                        "total_won": wins_count,
                        "total_lost": losses_count,
                        "total_earned": total_winnings,
                        "total_spent": total_bet_amount - total_winnings if total_winnings < total_bet_amount else 0
                    }
                }
            )

            # Update server data with all spins
            if server_data and server_history_entries:
                server_db.update_server_profit(ctx, ctx.guild.id, house_profit, game="wheel")

        else:
            # Complete loss (all bust)
            embed.add_field(
                name="💸 Results",
                value=(
                    f"**💸 Total Loss:** {total_bet_amount:.2f} points\n"
                    f"**🎰 All spins hit BUST zone**"
                ),
                inline=False
            )

        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1345317103158431805.png")
        embed.set_footer(text="🎰 BetSync Casino • Instant action awaits!", icon_url=self.bot.user.avatar.url)

        # Create instant action view with multiple options
        view = InstantSpinView(self, ctx, bet_total, spins=spins)
        await message.edit(embed=embed, view=view)
        view.message = message

        # Remove user from ongoing games
        self.ongoing_games.pop(ctx.author.id, None)


def setup(bot):
    bot.add_cog(WheelCog(bot))
