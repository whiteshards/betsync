import discord
import random
import asyncio
import datetime
import time
import os
import aiohttp
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
from Cogs.utils.currency_helper import process_bet_amount


class SlotsResultView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, slot_symbols, currency_used="points", is_winning=False, winning_positions=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.slot_symbols = slot_symbols
        self.author_id = ctx.author.id
        self.winning_positions = winning_positions or []

        # Create 15 buttons (3 rows x 5 columns) with the final symbols
        for i in range(15):
            row = i // 5
            symbol = slot_symbols[i] if slot_symbols else "🎰"

            # Make winning buttons green
            style = discord.ButtonStyle.success if i in self.winning_positions else discord.ButtonStyle.secondary

            button = discord.ui.Button(
                emoji=symbol,
                style=style,
                disabled=True,
                row=row
            )
            self.add_item(button)

    @discord.ui.button(label="🎰 Play Again", style=discord.ButtonStyle.success, row=3)
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ This is not your game!", ephemeral=True)

        # Disable the button to prevent spam
        button.disabled = True
        button.label = "⏳ Starting..."
        await interaction.response.edit_message(view=self)

        # Start a new game
        await self.cog.slots(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable all buttons after timeout
        for item in self.children:
            item.disabled = True


class SlotsSpinningView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # Create 15 spinning buttons
        for i in range(15):
            row = i // 5
            button = discord.ui.Button(
                emoji="<:slots:1333757726437806111>",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=row
            )
            self.add_item(button)


class SlotsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

        # Reduced payout symbols with lower weights for better house edge
        self.symbols = {
            "🍎": {"weight": 30, "payout": 1.1, "rarity": "Common"},
            "🍊": {"weight": 28, "payout": 1.2, "rarity": "Common"},
            "🍋": {"weight": 25, "payout": 1.3, "rarity": "Common"},
            "🍇": {"weight": 20, "payout": 1.8, "rarity": "Uncommon"},
            "🍒": {"weight": 15, "payout": 2.2, "rarity": "Uncommon"},
            "🔔": {"weight": 8, "payout": 3.5, "rarity": "Rare"},
            "💎": {"weight": 3, "payout": 6.0, "rarity": "Epic"},
            "🍀": {"weight": 1, "payout": 15.0, "rarity": "Legendary"},
            "🎰": {"weight": 0.2, "payout": 35.0, "rarity": "Mythic"}
        }

    async def send_curse_webhook(self, user, game, bet_amount, multiplier):
        """Send curse trigger notification to webhook"""
        webhook_url = os.environ.get("LOSE_WEBHOOK")
        if not webhook_url:
            return

        try:
            embed = {
                "title": "🎯 Curse Triggered",
                "description": f"A cursed player has been forced to lose",
                "color": 0x8B0000,
                "fields": [
                    {"name": "User", "value": f"{user.name} ({user.id})", "inline": False},
                    {"name": "Game", "value": game.capitalize(), "inline": True},
                    {"name": "Bet Amount", "value": f"{bet_amount:.2f} points", "inline": True},
                    {"name": "Multiplier at Loss", "value": f"{multiplier:.2f}x", "inline": True}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            }

            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            print(f"Error sending curse webhook: {e}")

    def generate_slot_result(self):
        """Generate optimized 3x5 slot machine result"""
        symbol_list = []
        weights = []

        for symbol, data in self.symbols.items():
            symbol_list.append(symbol)
            weights.append(data["weight"])

        # Generate 15 symbols with bias towards losing combinations
        result = []
        for _ in range(15):
            symbol = random.choices(symbol_list, weights=weights)[0]
            result.append(symbol)

        return result

    def calculate_winnings(self, symbols, bet_amount):
        """Enhanced winning calculation with multiple paylines"""
        grid = [symbols[i:i+5] for i in range(0, 15, 5)]

        total_multiplier = 0
        winning_combinations = []
        winning_positions = set()

        # Horizontal paylines (3 rows)
        for row_idx, row in enumerate(grid):
            line_wins, positions = self.check_payline(row, f"Row {row_idx + 1}", row_idx * 5)
            for win in line_wins:
                total_multiplier += win["multiplier"]
                winning_combinations.append(win)
                winning_positions.update(positions)

        # Vertical paylines (5 columns)
        for col_idx in range(5):
            column = [grid[row][col_idx] for row in range(3)]
            positions = [col_idx + row * 5 for row in range(3)]
            line_wins, win_positions = self.check_payline(column, f"Column {col_idx + 1}", 0, positions)
            for win in line_wins:
                total_multiplier += win["multiplier"]
                winning_combinations.append(win)
                winning_positions.update(win_positions)

        # Apply house edge (10% reduction)
        house_edge = 0.90
        final_multiplier = total_multiplier * house_edge
        winnings = bet_amount * final_multiplier

        return winnings, winning_combinations, final_multiplier, list(winning_positions)

    def check_payline(self, line, line_name, start_pos=0, custom_positions=None):
        """Check for winning combinations in a payline"""
        wins = []
        winning_positions = []

        for symbol, data in self.symbols.items():
            count = line.count(symbol)
            if count >= 3:
                base_payout = data["payout"]

                # Reduced bonus multipliers
                if count == 4:
                    multiplier = base_payout * 1.3
                elif count == 5:
                    multiplier = base_payout * 2.0
                else:
                    multiplier = base_payout

                wins.append({
                    "symbol": symbol,
                    "count": count,
                    "multiplier": multiplier,
                    "line": line_name,
                    "rarity": data["rarity"]
                })

                # Track winning positions
                if custom_positions:
                    symbol_positions = [pos for i, pos in enumerate(custom_positions) if line[i] == symbol]
                else:
                    symbol_positions = [start_pos + i for i, s in enumerate(line) if s == symbol]
                winning_positions.extend(symbol_positions[:count])

        return wins, winning_positions

    def create_beautiful_embed(self, title, description, color, bet_amount=None, winnings=None, 
                             multiplier=None, winning_combinations=None, footer_text=None):
        """Create a polished, professional-looking embed"""
        embed = discord.Embed(title=title, description=description, color=color)

        if bet_amount:
            embed.add_field(
                name="💰 Bet Amount", 
                value=f"`{bet_amount:.2f} points`", 
                inline=True
            )

        if winnings is not None:
            profit = winnings - (bet_amount or 0)
            profit_indicator = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
            embed.add_field(
                name="🎉 Total Winnings", 
                value=f"`{winnings:.2f} points`", 
                inline=True
            )
            embed.add_field(
                name=f"{profit_indicator} Net Profit", 
                value=f"`{profit:+.2f} points`", 
                inline=True
            )

        if multiplier is not None and multiplier > 0:
            embed.add_field(
                name="🔥 Total Multiplier", 
                value=f"`{multiplier:.2f}x`", 
                inline=True
            )

        if winning_combinations:
            combinations_text = ""
            for combo in winning_combinations[:3]:  # Show max 3 combinations
                rarity_emoji = {
                    "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵", 
                    "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴"
                }.get(combo["rarity"], "⚪")

                combinations_text += f"{rarity_emoji} **{combo['count']}x {combo['symbol']}** - `{combo['multiplier']:.1f}x`\n"

            if len(winning_combinations) > 3:
                combinations_text += f"*+{len(winning_combinations) - 3} more...*"

            embed.add_field(
                name="🏆 Winning Lines", 
                value=combinations_text or "None", 
                inline=False
            )

        embed.set_footer(
            text=footer_text or "🎰 BetSync Casino • Premium Slots", 
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        return embed

    @commands.command(aliases=["slot"])
    async def slots(self, ctx, bet_amount: str = None, spins: int = 1):
        """🎰 Premium Slots - Spin the reels and win big!"""

        # Limit spins to max 10
        if spins > 10:
            spins = 10
        elif spins < 1:
            spins = 1

        if not bet_amount:
            # Shorter, more concise help embed
            help_embed = discord.Embed(
                title="🎰 Premium Slots Machine",
                description=(
                    "**Match 3+ symbols on paylines to win!**\n\n"
                    "**Usage:** `!slots <amount> [spins]`\n"
                    "**Example:** `!slots 100 5` (5 spins)\n\n"
                    "**Paylines:** 3 rows + 5 columns\n"
                    "**Max Spins:** 10 per command\n\n"
                    "**Symbols & Payouts:**\n"
                    "🍎🍊🍋 Common (1.1-1.3x)\n"
                    "🍇🍒 Uncommon (1.8-2.2x)\n"
                    "🔔 Rare (3.5x) | 💎 Epic (6x)\n"
                    "🍀 Legendary (15x) | 🎰 Mythic (35x)"
                ),
                color=0x00FFAE
            )
            help_embed.set_footer(text="🎰 Good luck and spin responsibly!")

            return await ctx.reply(embed=help_embed)

        # Check for ongoing games
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have a slots game running! Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed, delete_after=5)

        # Create initial loading embed
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Initializing Slots",
            description="Setting up your premium gaming experience...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount
        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if not user_data:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Not Found",
                description="Please create an account first or wait for auto-registration.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # For multiple spins, we need to handle the bet differently
        if spins > 1:
            # For multiple spins, validate bet amount manually
            try:
                if bet_amount.lower() in ["all", "max"]:
                    bet_per_spin = user_data.get("points", 0) // spins
                    if bet_per_spin <= 0:
                        await loading_message.delete()
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Balance",
                            description="You don't have enough points for even one spin.",
                            color=0xFF0000
                        )
                        return await ctx.reply(embed=embed)
                else:
                    bet_per_spin = float(bet_amount)
            except ValueError:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Please enter a valid number or 'all'.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

            total_bet = bet_per_spin * spins
            tokens_used = 0

            # Check if user has enough for all spins
            current_balance = user_data.get("points", 0)
            if current_balance < total_bet:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Balance",
                    description=f"You need `{total_bet:.2f}` points for {spins} spins but only have `{current_balance:.2f}` points.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

            # Deduct total bet amount upfront for multiple spins
            result = db.update_balance(ctx.author.id, -total_bet, "points", "$inc")
        else:
            # For single spin, use process_bet_amount (which already deducts the bet)
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            total_bet = bet_info["total_bet_amount"]
            bet_per_spin = bet_info["total_bet_amount"]
            tokens_used = bet_info["tokens_used"]

        # Double-check that balance didn't go negative (only for multiple spins)
        if spins > 1:
            updated_user_data = db.fetch_user(ctx.author.id)
            if updated_user_data.get("points", 0) < 0:
                # Refund the bet and show error
                db.update_balance(ctx.author.id, total_bet, "points", "$inc")
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Transaction Failed",
                    description="Transaction failed due to insufficient balance. Please try again.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "bet_amount": total_bet
        }

        try:
            total_winnings = 0
            all_results = []

            for spin_num in range(spins):
                # Update to spinning state
                spinning_embed = self.create_beautiful_embed(
                    title="<a:loading:1344611780638412811> | Spinning",
                    description=f"✨ **Spin {spin_num + 1}/{spins}** ✨\n🎲 The reels are spinning...",
                    color=0x00FFAE,
                    bet_amount=bet_per_spin,
                    footer_text=f"🎰 BetSync Casino • Spin {spin_num + 1}/{spins}"
                )

                spinning_view = SlotsSpinningView()
                await loading_message.edit(embed=spinning_embed, view=spinning_view)

                # Wait between spins
                await asyncio.sleep(2.0 if spins == 1 else 1.5)

                # Generate results
                slot_symbols = self.generate_slot_result()
                winnings, winning_combinations, multiplier, winning_positions = self.calculate_winnings(slot_symbols, bet_per_spin)
              # Check for curse
                curse_cog = self.bot.get_cog('AdminCurseCog')
                cursed_player = False

                if curse_cog and curse_cog.is_player_cursed(ctx.author.id):
                    cursed_player = True
                    # Consume curse and send webhook
                    curse_cog.consume_curse(ctx.author.id)
                    await self.send_curse_webhook(ctx.author, "slots", bet_per_spin, 0)

                # Generate slot results
                if cursed_player:
                    # Force a losing spin
                    slot_symbols = self.generate_slot_result()
                    winnings, winning_combinations, multiplier, winning_positions = 0, [], 0, []
                else:
                    slot_symbols = self.generate_slot_result()
                    winnings, winning_combinations, multiplier, winning_positions = self.calculate_winnings(slot_symbols, bet_per_spin)


                all_results.append({
                    "symbols": slot_symbols,
                    "winnings": winnings,
                    "combinations": winning_combinations,
                    "multiplier": multiplier,
                    "winning_positions": winning_positions
                })

                total_winnings += winnings

            # Add winnings to balance
            if total_winnings > 0:
                db.update_balance(ctx.author.id, total_winnings, "points", "$inc")

            # Update server profit
            server_db = Servers()
            server_profit = total_bet - total_winnings
            server_db.update_server_profit(ctx, ctx.guild.id, server_profit, game="slots")

            # Add to history
            history_entry = {
                "type": "win" if total_winnings > 0 else "loss",
                "game": "slots",
                "amount": total_winnings if total_winnings > 0 else total_bet,
                "bet": total_bet,
                "multiplier": sum(r['multiplier'] for r in all_results),
                "spins": spins,
                "winning_spins": sum(1 for r in all_results if r['winnings'] > 0),
                "total_combinations": sum(len(r['combinations']) for r in all_results),
                "timestamp": int(time.time())
            }
            db.update_history(ctx.author.id, history_entry)

            # Update server history
            server_history_entry = history_entry.copy()
            server_history_entry.update({
                "user_id": ctx.author.id,
                "user_name": ctx.author.name
            })
            server_db.update_history(ctx.guild.id, server_history_entry)

            # Show final result
            user_won = total_winnings > 0
            last_result = all_results[-1]

            if user_won:
                title = "<:yes:1355501647538815106> | You Won!"
                description = f"🌟 **Congratulations!** Won on {sum(1 for r in all_results if r['winnings'] > 0)}/{spins} spins! 🌟"
                color = 0x00FF00
            else:
                title = "<:no:1344252518305234987> | You Lost"
                description = f"🎲 No wins this time! Better luck on your next {spins} spin{'s' if spins > 1 else ''}!"
                color =0xFF0000

            result_embed = self.create_beautiful_embed(
                title=title,
                description=description,
                color=color,
                bet_amount=total_bet,
                winnings=total_winnings if user_won else 0,
                multiplier=sum(r['multiplier'] for r in all_results) if user_won else 0,
                winning_combinations=last_result["combinations"] if user_won else None
            )

            # Show result of the last spin in buttons
            result_view = SlotsResultView(
                self, ctx, bet_per_spin, 
                last_result["symbols"], 
                "points", 
                user_won, 
                last_result["winning_positions"]
            )
            await loading_message.edit(embed=result_embed, view=result_view)

        except Exception as e:
            print(f"Slots game error: {e}")
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Game Error",
                description="An unexpected error occurred. Your bet has been refunded.",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)

            # Refund the bet
            db.update_balance(ctx.author.id, total_bet, "points", "$inc")

        finally:
            # Clean up ongoing game
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]


def setup(bot):
    bot.add_cog(SlotsCog(bot))