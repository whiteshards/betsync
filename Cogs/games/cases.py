import discord
import random
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class CasesPlayAgainView(discord.ui.View):
    """View with a Play Again button that shows after a game ends"""
    def __init__(self, cog, ctx, bet_amount, currency_used, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.message = None
        self.original_author = ctx.author  # Store the original author explicitly

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success)
    async def play_again(self, button, interaction):
        # Check if the person clicking is the original player
        if interaction.user.id != self.original_author.id:
            return await interaction.response.send_message("Only the original player can use this button!", ephemeral=True)

        # Disable the button after click
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        # Start a new game with same bet amount
        await self.cog.cases(self.ctx, str(self.bet_amount), self.currency_used)


class CasesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Define case multipliers and their chances based on provided image
        self.multipliers = [
            {"value": 23.0, "chance": 0.01, "emoji": "💎", "name": "LEGENDARY"},
            {"value": 10.0, "chance": 0.02, "emoji": "🌟", "name": "EPIC"},
            {"value": 3.0, "chance": 0.04, "emoji": "✨", "name": "RARE"},
            {"value": 2.0, "chance": 0.07, "emoji": "🔷", "name": "UNCOMMON"},
            {"value": 1.09, "chance": 0.10, "emoji": "🔹", "name": "COMMON"},
            {"value": 0.4, "chance": 0.35, "emoji": "💢", "name": "BAD LUCK"},
            {"value": 0.1, "chance": 0.41, "emoji": "💀", "name": "TERRIBLE"}
        ]

        # Validate that probabilities sum to 1
        total_prob = sum(item["chance"] for item in self.multipliers)
        if abs(total_prob - 1.0) > 0.001:  # Allow small floating-point error
            print(f"Warning: Case probabilities sum to {total_prob}, not 1.0")

    @commands.command(aliases=["case", "crate"])
    async def cases(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Open a case and test your luck with different multipliers!"""
        if not bet_amount:
            embed = discord.Embed(
                title="📦 How to Play Cases",
                description=(
                    "**Cases** is a game where you open a case to win credits based on multipliers!\n\n"
                    "**Usage:** `!cases <amount> [currency_type]`\n"
                    "**Example:** `!cases 100` or `!cases 100 tokens`\n\n"
                    "**Possible Rewards:**\n"
                    f"💎 **LEGENDARY** (23x) - 1% chance\n"
                    f"🌟 **EPIC** (10x) - 2% chance\n"
                    f"✨ **RARE** (3x) - 4% chance\n"
                    f"🔷 **UNCOMMON** (2x) - 7% chance\n"
                    f"🔹 **COMMON** (1.09x) - 10% chance\n"
                    f"💢 **BAD LUCK** (0.4x) - 35% chance\n"
                    f"💀 **TERRIBLE** (0.1x) - 41% chance\n\n"
                    "**Payouts are made in credits!**"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Get user's balance
        author = ctx.author
        db = Users()
        user_data = db.fetch_user(author.id)
        tokens_balance = user_data.get('tokens', 0)
        credits_balance = user_data.get('credits', 0)

        # Process bet amount and currency
        try:
            # Handle all/max bet amount
            if isinstance(bet_amount, str) and bet_amount.lower() in ["all", "max"]:
                if currency_type:
                    if currency_type.lower() in ["tokens", "t"]:
                        bet_amount = tokens_balance
                        currency_used = "tokens"
                    elif currency_type.lower() in ["credits", "c"]:
                        bet_amount = credits_balance
                        currency_used = "credits"
                    else:
                        return await ctx.reply("Invalid currency type. Use 'tokens' or 'credits'.")
                else:
                    # If no currency specified with all/max, use the currency with higher balance
                    if tokens_balance >= credits_balance:
                        bet_amount = tokens_balance
                        currency_used = "tokens"
                    else:
                        bet_amount = credits_balance
                        currency_used = "credits"
            else:
                # Handle numeric bet amount
                try:
                    bet_amount = float(bet_amount)
                    if bet_amount <= 0:
                        return await ctx.reply("Bet amount must be positive!")
                except ValueError:
                    return await ctx.reply("Invalid bet amount! Please enter a valid number.")

                # Handle currency selection
                if currency_type:
                    if currency_type.lower() in ["tokens", "t"]:
                        currency_used = "tokens"
                    elif currency_type.lower() in ["credits", "c"]:
                        currency_used = "credits"
                    else:
                        return await ctx.reply("Invalid currency type. Use 'tokens' or 'credits'.")
                else:
                    # Default to tokens if no currency specified
                    currency_used = "tokens"

            # Validate user has enough balance
            if currency_used == "tokens" and tokens_balance < bet_amount:
                return await ctx.reply(f"You don't have enough tokens! Your balance: {tokens_balance:.2f} tokens")
            elif currency_used == "credits" and credits_balance < bet_amount:
                return await ctx.reply(f"You don't have enough credits! Your balance: {credits_balance:.2f} credits")

            # Deduct the bet amount
            db.update_balance(author.id, -bet_amount, currency_used, "$inc")

        except Exception as e:
            return await ctx.reply(f"An error occurred: {str(e)}")

        # Send initial message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} Opening Case...",
            description=f"Bet: **{bet_amount:.2f} {currency_used}**",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Create a clean spinning animation
        animation_embed = discord.Embed(
            title="📦 Case Opening",
            description=f"Bet: **{bet_amount:.2f} {currency_used}**",
            color=0x00FFAE
        )

        # Determine result first to avoid sticking issues
        random_value = random.random()
        cumulative_prob = 0
        selected_multiplier = None

        for multiplier in self.multipliers:
            cumulative_prob += multiplier["chance"]
            if random_value <= cumulative_prob:
                selected_multiplier = multiplier
                break

        if not selected_multiplier:  # Fallback in case of floating-point issues
            selected_multiplier = self.multipliers[-1]
            
        # Spinning reel animation - properly aligned and fixed
        for i in range(8):  # 8 spins for animation
            # Create a clean display of spinning items
            shuffled_items = self.multipliers.copy()
            random.shuffle(shuffled_items)
            
            # Make sure the animation shows the actual result at the end
            if i == 7:  # On last spin, make sure middle item is the result
                center_idx = -1
                for idx, item in enumerate(shuffled_items):
                    if item["value"] == selected_multiplier["value"] and item["name"] == selected_multiplier["name"]:
                        center_idx = idx
                        break
                
                # If found, swap to make it the middle item
                if center_idx != -1 and center_idx != 1:
                    shuffled_items[center_idx], shuffled_items[1] = shuffled_items[1], shuffled_items[center_idx]
                # If not found (unlikely), replace middle item directly
                elif center_idx == -1:
                    shuffled_items[1] = selected_multiplier

            reel = ""
            for j in range(3):
                item = shuffled_items[j]
                if j == 1:
                    # Center item highlighted with consistent alignment
                    reel += f"▶️ {item['emoji']} **{item['name']}** ({item['value']}x) ◀️\n"
                else:
                    # Consistent padding for non-selected items for better alignment
                    reel += f"   {item['emoji']} {item['name']} ({item['value']}x)\n"

            animation_embed.description = f"Bet: **{bet_amount:.2f} {currency_used}**\n\n{reel}"
            
            try:
                await loading_message.edit(embed=animation_embed)
                await asyncio.sleep(0.08 if i < 6 else 0.12)  # Even faster animation with slight slowdown at end
            except Exception as e:
                print(f"Error in animation: {e}")
                # If edit fails, continue to next frame
                continue

        # Calculate winnings
        win_amount = bet_amount * selected_multiplier["value"]
        user_won = selected_multiplier["value"] > 1.0

        # Update MongoDB
        # Update gameplay statistics
        db.collection.update_one(
            {"discord_id": author.id},
            {"$inc": {
                "total_played": 1,
                "total_won": 1 if user_won else 0,
                "total_lost": 0 if user_won else 1,
                "total_spent": bet_amount,
                "total_earned": win_amount if user_won else 0
            }}
        )

        # Add to user's credits - always payout in credits
        db.update_balance(author.id, win_amount, "credits", "$inc")

        # Update server profit statistics if in a server
        if hasattr(ctx, 'guild') and ctx.guild:
            server_db = Servers()
            server_profit = bet_amount - win_amount
            server_db.update_server_profit(ctx.guild.id, server_profit)

            # Add game to server history
            history_entry = {
                "game": "cases",
                "user_id": author.id,
                "username": author.name,
                "bet_amount": bet_amount,
                "currency": currency_used,
                "result": "win" if user_won else "loss",
                "multiplier": selected_multiplier["value"],
                "profit": server_profit,
                "timestamp": int(discord.utils.utcnow().timestamp())
            }
            server_db.update_history(ctx.guild.id, history_entry)

        # Add game to user history
        history_entry = {
            "game": "cases",
            "bet_amount": bet_amount,
            "currency": currency_used,
            "result": "win" if user_won else "loss",
            "multiplier": selected_multiplier["value"],
            "win_amount": win_amount,
            "timestamp": int(discord.utils.utcnow().timestamp())
        }
        db.update_history(author.id, history_entry)

        # Set color based on result tier
        if selected_multiplier["value"] >= 10:  # Legendary/Epic
            color = 0xFFD700  # Gold
        elif selected_multiplier["value"] >= 2:  # Rare/Uncommon
            color = 0x00FF00  # Green
        elif selected_multiplier["value"] >= 1:  # Common
            color = 0x00AAFF  # Blue
        else:  # Bad luck / Terrible
            color = 0xFF0000  # Red

        # Create a simplified and clean result embed
        result_embed = discord.Embed(
            title=f"📦 {selected_multiplier['emoji']} {selected_multiplier['name']} {selected_multiplier['emoji']}",
            description=(
                f"**Multiplier: {selected_multiplier['value']}x**\n"
                f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                f"**Payout:** {win_amount:.2f} credits\n"
                f"**Profit:** {win_amount - bet_amount:.2f} credits"
            ),
            color=color
        )

        # Add multiplier info in a clean format
        case_info = ""
        for m in sorted(self.multipliers, key=lambda x: x["value"], reverse=True):
            # Highlight the result
            if m["value"] == selected_multiplier["value"]:
                case_info += f"➡️ {m['emoji']} **{m['name']}** ({m['value']}x) - {m['chance']*100:.1f}% ⬅️\n"
            else:
                case_info += f"{m['emoji']} {m['name']} ({m['value']}x) - {m['chance']*100:.1f}%\n"

        result_embed.add_field(
            name="📋 Case Contents",
            value=case_info,
            inline=False
        )

        result_embed.set_footer(text=f"BetSync Casino • {currency_used.capitalize()} bet: {bet_amount:.2f}", icon_url=self.bot.user.avatar.url)

        # Add play again button
        play_again_view = CasesPlayAgainView(self, ctx, bet_amount, currency_used)
        play_again_message = await loading_message.edit(embed=result_embed, view=play_again_view)
        play_again_view.message = play_again_message

def setup(bot):
    bot.add_cog(CasesCog(bot))