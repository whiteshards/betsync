import discord
import random
import asyncio
import datetime
import os
import aiohttp
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from colorama import Fore

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

    @discord.ui.button(label="Build Again", style=discord.ButtonStyle.green, emoji="🏗️")
    async def play_again_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        await self.cog.build(self.ctx, str(self.bet_amount))

class BuildGameView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None
        self.current_level = 0
        self.max_levels = 15
        self.game_over = False
        self.tower_blocks = []
        self.selected_blocks = []

        # Block types with different risk/reward ratios (10% house edge built in)
        self.block_types = {
            "🟢": {"name": "Safe Block", "success_rate": 0.85, "multiplier": 1.12},
            "🟡": {"name": "Balanced Block", "success_rate": 0.70, "multiplier": 1.25},
            "🟠": {"name": "Risky Block", "success_rate": 0.55, "multiplier": 1.45},
            "🔴": {"name": "Extreme Block", "success_rate": 0.40, "multiplier": 1.80}
        }

        self.current_multiplier = 1.0
        self.total_multiplier = 1.0

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        if self.game_over:
            return

        # Add block selection buttons
        for emoji, block_info in self.block_types.items():
            button = discord.ui.Button(
                emoji=emoji,
                label=f"{block_info['name']} ({block_info['success_rate']*100:.0f}%)",
                style=discord.ButtonStyle.secondary,
                custom_id=f"block_{emoji}"
            )
            button.callback = self.block_callback
            self.add_item(button)

        # Add cash out button if not on first level
        if self.current_level > 0:
            cash_out_button = discord.ui.Button(
                label="Cash Out",
                style=discord.ButtonStyle.success,
                emoji="💰",
                custom_id="cash_out"
            )
            cash_out_button.callback = self.cash_out_callback
            self.add_item(cash_out_button)

    def calculate_payout(self):
        return round(self.bet_amount * self.total_multiplier, 2)

    def create_tower_display(self):
        tower = ""

        # Display from top to bottom
        for level in range(self.max_levels - 1, -1, -1):
            if level < len(self.tower_blocks):
                # Show placed blocks
                block = self.tower_blocks[level]
                tower += f"{block['emoji']} "
            elif level == self.current_level:
                # Current building level
                tower += "🔨 "
            else:
                # Empty levels
                tower += "⬜ "

            # Add level indicator every 5 levels
            if (self.max_levels - level) % 5 == 0:
                tower += f"← Level {self.max_levels - level}\n"
            else:
                tower += "\n"

        tower += "🏗️ Foundation\n"
        return tower

    def create_embed(self, status="building"):
        if status == "building":
            embed = discord.Embed(
                title="🏗️ Tower Builder",
                description="**Build your tower by choosing blocks with different risk levels!**",
                color=0x00FFAE
            )

            embed.add_field(
                name="🎮 Building Progress",
                value=f"**Level:** {self.current_level + 1}/{self.max_levels}\n**Current Multiplier:** {self.total_multiplier:.2f}x",
                inline=True
            )

            embed.add_field(
                name="💰 Potential Earnings",
                value=f"**Bet:** `{self.bet_amount} points`\n**Potential Win:** `{self.calculate_payout()} points`",
                inline=True
            )

            # Block info
            block_info = ""
            for emoji, info in self.block_types.items():
                block_info += f"{emoji} {info['name']}: {info['success_rate']*100:.0f}% success, {info['multiplier']:.2f}x\n"

            embed.add_field(
                name="🧱 Block Types",
                value=block_info,
                inline=False
            )

            embed.add_field(
                name="🏗️ Your Tower",
                value=self.create_tower_display(),
                inline=False
            )

            if self.current_level == 0:
                embed.set_footer(text="Choose a block type to start building your tower!")
            else:
                embed.set_footer(text="Continue building or cash out your winnings!")

        elif status == "success":
            embed = discord.Embed(
                title="🏗️ Block Placed Successfully!",
                description=f"**Great choice!** Your {self.selected_blocks[-1]['name']} held strong!",
                color=0x00FF00
            )

            embed.add_field(
                name="🎮 Building Progress",
                value=f"**Level:** {self.current_level + 1}/{self.max_levels}\n**Current Multiplier:** {self.total_multiplier:.2f}x",
                inline=True
            )

            embed.add_field(
                name="💰 Potential Earnings",
                value=f"**Bet:** `{self.bet_amount} points`\n**Potential Win:** `{self.calculate_payout()} points`",
                inline=True
            )

            embed.add_field(
                name="🏗️ Your Tower",
                value=self.create_tower_display(),
                inline=False
            )

            if self.current_level == self.max_levels:
                embed.set_footer(text="🎉 Congratulations! You've built the tallest tower!")
            else:
                embed.set_footer(text="Keep building or secure your winnings!")

        elif status == "collapse":
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Tower Collapsed!",
                description=f"**Oh no!** Your {self.selected_blocks[-1]['name']} couldn't hold the weight!",
                color=0xFF0000
            )

            embed.add_field(
                name="💔 Final Results",
                value=f"**Levels Built:** {self.current_level}\n**Lost:** `{self.bet_amount} points`",
                inline=True
            )

            embed.add_field(
                name="🏗️ Final Tower",
                value=self.create_tower_display(),
                inline=False
            )

            embed.set_footer(text="Better luck next time! Try different block combinations.")

        elif status == "cash_out":
            payout = self.calculate_payout()
            profit = payout - self.bet_amount

            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Tower Complete!",
                description=f"**Excellent work!** You've cashed out your tower construction!",
                color=0x00FF00
            )

            embed.add_field(
                name="💰 Final Results",
                value=f"**Initial Bet:** `{self.bet_amount} points`\n**Final Multiplier:** {self.total_multiplier:.2f}x\n**Payout:** `{payout} points`\n**Profit:** `{profit} points`",
                inline=False
            )

            embed.add_field(
                name="🏗️ Completed Tower",
                value=self.create_tower_display(),
                inline=False
            )

            embed.set_footer(text="You've successfully secured your construction earnings!")

        embed.set_author(name=f"Builder: {self.ctx.author.name}", icon_url=self.ctx.author.avatar.url)
        return embed

    async def block_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        await interaction.response.defer()

        # Get selected block type
        block_emoji = interaction.data["custom_id"].split('_')[1]
        block_info = self.block_types[block_emoji]

        # Store the selected block
        selected_block = {
            "emoji": block_emoji,
            "name": block_info["name"],
            "success_rate": block_info["success_rate"],
            "multiplier": block_info["multiplier"]
        }
        self.selected_blocks.append(selected_block)

        # Determine if block placement succeeds
        success = random.random() < block_info["success_rate"]

        if success:
            # Block placed successfully
            self.tower_blocks.append(selected_block)
            self.current_level += 1
            self.total_multiplier *= block_info["multiplier"]

            # Check if tower is complete
            if self.current_level >= self.max_levels:
                self.game_over = True
                await self.process_cashout(interaction)
                return

            # Update for next level
            self.update_buttons()

            # Show success message briefly
            await interaction.followup.edit_message(
                message_id=self.message.id,
                embed=self.create_embed(status="success"),
                view=self
            )

        else:
            # Tower collapsed
            self.game_over = True
            self.clear_items()

            await interaction.followup.edit_message(
                message_id=self.message.id,
                embed=self.create_embed(status="collapse"),
                view=self
            )

            await self.process_loss()

    async def cash_out_callback(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.game_over = True

        for item in self.children:
            item.disabled = True

        await interaction.response.defer()
        await self.process_cashout(interaction)

    async def process_cashout(self, interaction):
        payout = self.calculate_payout()

        db = Users()
        try:
            # Update user balance
            db.update_balance(self.ctx.author.id, payout, "points", "$inc")

            # Create win history entry
            win_entry = {
                "type": "win",
                "game": "build",
                "bet": self.bet_amount,
                "amount": payout,
                "multiplier": self.total_multiplier,
                "levels": self.current_level,
                "timestamp": int(datetime.datetime.now().timestamp())
            }

            # Update user stats
            db.collection.update_one(
                {"discord_id": self.ctx.author.id},
                {
                    "$push": {"history": {"$each": [win_entry], "$slice": -100}},
                    "$inc": {
                        "total_played": 1,
                        "total_won": 1,
                        "total_earned": payout
                    }
                }
            )

            # Update server stats
            if isinstance(self.ctx.channel, discord.TextChannel):
                server_db = Servers()
                server_profit = self.bet_amount - payout
                server_db.update_server_profit(self.ctx, self.ctx.guild.id, server_profit, game="build")

                server_bet_entry = win_entry.copy()
                server_bet_entry.update({
                    "user_id": self.ctx.author.id,
                    "user_name": self.ctx.author.name
                })

                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
                )

        except Exception as e:
            print(f"Error processing cashout: {e}")
            return False

        # Create play again view
        play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount)

        cashout_embed = self.create_embed(status="cash_out")
        await self.message.edit(embed=cashout_embed, view=play_again_view)
        play_again_view.message = self.message

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

        return True

    async def process_loss(self):
        # Create loss entry
        loss_entry = {
            "type": "loss",
            "game": "build",
            "bet": self.bet_amount,
            "amount": self.bet_amount,
            "levels": self.current_level,
            "timestamp": int(datetime.datetime.now().timestamp())
        }

        # Update user stats
        db = Users()
        db.collection.update_one(
            {"discord_id": self.ctx.author.id},
            {
                "$push": {"history": {"$each": [loss_entry], "$slice": -100}},
                "$inc": {
                    "total_played": 1,
                    "total_lost": 1,
                    "total_spent": self.bet_amount
                }
            }
        )

        # Update server stats
        try:
            if isinstance(self.ctx.channel, discord.TextChannel):
                server_db = Servers()
                server_db.update_server_profit(self.ctx, self.ctx.guild.id, self.bet_amount, game="build")

                server_bet_entry = loss_entry.copy()
                server_bet_entry.update({
                    "user_id": self.ctx.author.id,
                    "user_name": self.ctx.author.name
                })

                server_db.collection.update_one(
                    {"server_id": self.ctx.guild.id},
                    {"$push": {"server_bet_history": {"$each": [server_bet_entry], "$slice": -100}}}
                )
        except Exception as e:
            print(f"Error updating server stats: {e}")

        # Create play again view
        play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount, timeout=15)
        await self.message.edit(view=play_again_view)
        play_again_view.message = self.message

        if self.ctx.author.id in self.cog.ongoing_games:
            del self.cog.ongoing_games[self.ctx.author.id]

    async def on_timeout(self):
        if not self.game_over and self.current_level > 0:
            await self.process_cashout(None)

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass

        if not self.game_over:
            self.game_over = True
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

class BuildCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["builder", "construct"])
    async def build(self, ctx, bet_amount: str = None):
        """Build a tower by choosing blocks with different risk levels!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":information_source: | How to Play Build",
                description=(
                    "**Build** is a tower construction game where you choose blocks with different risk levels!\n\n"
                    "**Usage:** `!build <amount>`\n"
                    "**Example:** `!build 100`\n\n"
                    "**Block Types:**\n"
                    "🟢 **Safe Block:** 85% success rate, 1.12x multiplier\n"
                    "🟡 **Balanced Block:** 70% success rate, 1.25x multiplier\n"
                    "🟠 **Risky Block:** 55% success rate, 1.45x multiplier\n"
                    "🔴 **Extreme Block:** 40% success rate, 1.80x multiplier\n\n"
                    "Build up to 15 levels! Each successful block placement multiplies your potential winnings. Cash out anytime or risk it all for the maximum tower height!"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino • Aliases: !builder, !tower, !construct")
            return await ctx.reply(embed=embed)

        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing construction project. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Send loading message
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Preparing Construction Site...",
            description="Setting up your building materials and workspace.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount
        from Cogs.utils.currency_helper import process_bet_amount
        success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

        if not success:
            return await ctx.reply(embed=error_embed)

        total_bet = bet_info["total_bet_amount"]

        # Record game stats
        db = Users()
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": total_bet}}
        )

        # Create game view
        game_view = BuildGameView(self, ctx, total_bet, timeout=180)

        await loading_message.delete()

        game_message = await ctx.reply(embed=game_view.create_embed(status="building"), view=game_view)
        game_view.message = game_message

        self.ongoing_games[ctx.author.id] = {
            "game_type": "build",
            "game_view": game_view,
            "start_time": time.time()
        }

def setup(bot):
    bot.add_cog(BuildCog(bot))