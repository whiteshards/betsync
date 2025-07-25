import discord
import random
from discord.ext import commands
from datetime import datetime
from Cogs.utils.mongo import Users, Servers
import uuid

class RoleSelectionView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, game_id, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.game_id = game_id
        self.message = None

    @discord.ui.button(label="⚽ Striker", style=discord.ButtonStyle.primary, custom_id="taker")
    async def taker_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Start game as penalty taker
        await self.cog.start_as_taker(self.ctx, interaction, self.bet_amount, self.game_id)

    @discord.ui.button(label="🥅 Goalkeeper", style=discord.ButtonStyle.success, custom_id="goalkeeper")
    async def goalkeeper_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Start game as goalkeeper
        await self.cog.start_as_goalkeeper(self.ctx, interaction, self.bet_amount, self.game_id)

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


class PenaltyButtonView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, role, game_id, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.role = role
        self.game_id = game_id
        self.message = None
        self.clicked = False

    @discord.ui.button(label="Left", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="left")
    async def left_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)

        self.clicked = True

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True

        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "left", self.bet_amount, self.game_id)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "left", self.bet_amount, self.game_id)

    @discord.ui.button(label="Middle", style=discord.ButtonStyle.secondary, emoji="⬆️", custom_id="middle")
    async def middle_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)

        self.clicked = True

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True

        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "middle", self.bet_amount, self.game_id)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "middle", self.bet_amount, self.game_id)

    @discord.ui.button(label="Right", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="right")
    async def right_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)

        self.clicked = True

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True

        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "right", self.bet_amount, self.game_id)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "right", self.bet_amount, self.game_id)

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
        await interaction.response.defer()
        await interaction.message.edit(view=self)

        # Show processing message
        await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)

        # Create a new penalty game with the same bet amount
        await self.cog.penalty(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class PenaltyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}  # Now uses game_id instead of user_id

    @commands.command(aliases=["pen", "pk"])
    async def penalty(self, ctx, bet_amount: str = None, role: str = None, direction: str = None):
        """⚽ Play penalty shootout - choose to be a penalty taker or goalkeeper!"""
        if not bet_amount:
            embed = discord.Embed(
                title="⚽ **PENALTY SHOOTOUT** ⚽",
                description=(
                    "```\n"
                    "🎯 Choose Your Role & Test Your Skills!\n"
                    "```\n"
                    "**📋 How to Play:**\n"
                    "> Basic: `!penalty <amount>`\n"
                    "> Direct: `!penalty <amount> <role> <direction>`\n"
                    "> Example: `!penalty 100 s l`\n\n"

                    "**🎯 Roles:**\n"
                    "> • **s/striker/taker** - Penalty taker (1.45x)\n"
                    "> • **g/goalkeeper/keeper** - Goalkeeper (2.1x)\n\n"

                    "**📍 Directions:**\n"
                    "> • **l/left** - Left corner\n"
                    "> • **m/middle/center** - Middle goal\n"
                    "> • **r/right** - Right corner\n\n"

                    "**⚽ Striker Role:**\n"
                    "> • Choose where to shoot (Left/Middle/Right)\n"
                    "> • Beat the goalkeeper to **win 1.45x** your bet!\n"
                    "> • Score = Victory! 🎉\n\n"

                    "**🥅 Goalkeeper Role:**\n"
                    "> • Choose where to dive (Left/Middle/Right)\n"
                    "> • Save the shot to **win 2.1x** your bet!\n"
                    "> • Perfect saves = Big rewards! 💰\n\n"

                    "```diff\n"
                    "+ Higher risk = Higher reward as goalkeeper!\n"
                    "```"
                ),
                color=0x00FF94
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")
            embed.set_footer(text="⚽ BetSync Casino • Ready for the penalty shootout?", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if role and direction are provided for direct execution
        if role and direction:
            return await self.execute_direct_penalty(ctx, bet_amount, role, direction)

        # Create loading embed with animated appearance
        loading_embed = discord.Embed(
            title="⚽ **Setting Up The Penalty Box...**",
            description=(
                "```\n"
                "🔄 Processing your bet...\n"
                "📊 Checking balance...\n"
                "⚽ Preparing the field...\n"
                "```"
            ),
            color=0xFFD700
        )
        loading_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        try:
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            # Successful bet processing - extract relevant information
            tokens_used = bet_info.get("tokens_used", 0)
            bet_amount = bet_info.get("total_bet_amount", 0)
        except Exception as e:
            print(f"Error processing bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {str(e)}")

        # Generate unique game ID to prevent conflicts between users
        game_id = str(uuid.uuid4())

        # Mark game as ongoing with unique game ID
        self.ongoing_games[game_id] = {
            "user_id": ctx.author.id,
            "bet_amount": bet_amount,
            "tokens_used": tokens_used,
            "credits_used": "points"
        }

        # Create enhanced role selection embed
        embed = discord.Embed(
            title="⚽ **CHOOSE YOUR DESTINY** ⚽",
            description=(
                f"```\n"
                f"💰 Your Bet: {bet_amount:,.2f} points\n"
                f"```\n"
                f"**🎯 Pick Your Role:**\n\n"

                f"**🥅 Goalkeeper Challenge:**\n"
                f"> • Dive and save the penalty shot\n"
                f"> • **Win: {bet_amount*2.1:,.2f} points** (2.1x)\n"
                f"> • High risk, high reward! 💎\n\n"

                f"**⚽ Striker Challenge:**\n"
                f"> • Score past the goalkeeper\n"
                f"> • **Win: {bet_amount*1.45:,.2f} points** (1.45x)\n"
                f"> • Aim true and score! 🎯\n\n"

                f"```diff\n"
                f"⏰ Choose wisely - 30 seconds remaining!\n"
                f"```"
            ),
            color=0x00FFAE
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")
        embed.set_footer(text="⚽ BetSync Casino • The crowd is waiting...", icon_url=self.bot.user.avatar.url)

        # Create view with role selection buttons
        view = RoleSelectionView(self, ctx, bet_amount, game_id, timeout=30)

        # Update the loading message instead of deleting and creating a new one
        message = await loading_message.edit(embed=embed, view=view)
        view.message = message

    async def execute_direct_penalty(self, ctx, bet_amount, role, direction):
        """Execute penalty directly with provided role and direction"""
        # Normalize role input
        role_mapping = {
            's': 'striker', 'striker': 'striker', 'taker': 'striker',
            'g': 'goalkeeper', 'goalkeeper': 'goalkeeper', 'keeper': 'goalkeeper'
        }

        # Normalize direction input
        direction_mapping = {
            'l': 'left', 'left': 'left',
            'm': 'middle', 'middle': 'middle', 'center': 'middle',
            'r': 'right', 'right': 'right'
        }

        # Validate inputs
        normalized_role = role_mapping.get(role.lower())
        normalized_direction = direction_mapping.get(direction.lower())

        if not normalized_role:
            return await ctx.reply("❌ Invalid role! Use: `s/striker/taker` or `g/goalkeeper/keeper`")

        if not normalized_direction:
            return await ctx.reply("❌ Invalid direction! Use: `l/left`, `m/middle/center`, or `r/right`")

        # Create loading embed
        loading_embed = discord.Embed(
            title="⚽ **Setting Up Direct Penalty...**",
            description=(
                "```\n"
                "🔄 Processing your bet...\n"
                "📊 Checking balance...\n"
                "⚽ Preparing for action...\n"
                "```"
            ),
            color=0xFFD700
        )
        loading_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        try:
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, loading_message)

            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            # Successful bet processing - extract relevant information
            tokens_used = bet_info.get("tokens_used", 0)
            bet_amount = bet_info.get("total_bet_amount", 0)
        except Exception as e:
            print(f"Error processing bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {str(e)}")

        # Generate unique game ID
        game_id = str(uuid.uuid4())

        # Mark game as ongoing
        self.ongoing_games[game_id] = {
            "user_id": ctx.author.id,
            "bet_amount": bet_amount,
            "tokens_used": tokens_used,
            "credits_used": "points"
        }

        # Execute the penalty based on role
        if normalized_role == 'striker':
            await self.process_penalty_shot_direct(ctx, loading_message, normalized_direction, bet_amount, game_id)
        else:
            await self.process_goalkeeper_save_direct(ctx, loading_message, normalized_direction, bet_amount, game_id)

    async def process_penalty_shot_direct(self, ctx, loading_message, shot_direction, bet_amount, game_id):
        """Process direct penalty shot"""
        # Remove from ongoing games
        if game_id in self.ongoing_games:
            del self.ongoing_games[game_id]

        # Goalkeeper picks a random direction
        goalkeeper_directions = ["left", "middle", "right"]
        goalkeeper_direction = random.choice(goalkeeper_directions)

        # Determine the outcome
        goal_scored = shot_direction != goalkeeper_direction

        # Direction emojis for visual representation
        direction_emojis = {"left": "⬅️", "middle": "⬆️", "right": "➡️"}
        direction_names = {"left": "Left Corner", "middle": "Center Goal", "right": "Right Corner"}

        # Calculate winnings
        multiplier = 1.45
        winnings = bet_amount * multiplier if goal_scored else 0

        # Create result embed
        if goal_scored:
            embed = discord.Embed(
                title=f"<:yes:1355501647538815106> | **GOOOOOAL!** ⚽",
                description=(
                    f"```diff\n"
                    f"+ SPECTACULAR SHOT! THE CROWD GOES WILD!\n"
                    f"```\n"
                    f"**🎯 Your Shot:** {direction_emojis[shot_direction]} {direction_names[shot_direction]}\n"
                    f"**🥅 Keeper Dove:** {direction_emojis[goalkeeper_direction]} {direction_names[goalkeeper_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: GOAL SCORED!\n"
                    f"Winnings: +{winnings:.2f} points\n"
                    f"Multiplier: {multiplier}x\n"
                    f"```\n"

                    f"**🏆 Perfect execution! You've beaten the goalkeeper and won big!**\n"
                    f"> The net bulges as your shot finds its mark! 🎉"
                ),
                color=0x00FF00
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings)

        else:
            embed = discord.Embed(
                title=f"<:no:1344252518305234987> | **SAVED!** 🥅",
                description=(
                    f"```diff\n"
                    f"- The goalkeeper makes a brilliant save!\n"
                    f"```\n"
                    f"**🎯 Your Shot:** {direction_emojis[shot_direction]} {direction_names[shot_direction]}\n"
                    f"**🥅 Keeper Dove:** {direction_emojis[goalkeeper_direction]} {direction_names[goalkeeper_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: SHOT SAVED!\n"
                    f"Loss: -{bet_amount:.2f} points\n"
                    f"```\n"

                    f"**😤 The goalkeeper read your mind! Better luck next time!**\n"
                    f"> What a save! The keeper anticipated your move perfectly! 🧤"
                ),
                color=0xFF4444
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1344252518305234987.png")

            # Update statistics
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

        embed.set_footer(text="⚽ BetSync Casino • Want another shot?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_taker", bet_amount, shot_direction, goalkeeper_direction, goal_scored, multiplier, winnings)

        # Update server profit
        nnn = Servers()
        nnn.update_server_profit(ctx, ctx.guild.id, bet_amount, game="penalty")

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await loading_message.edit(embed=embed, view=play_again_view)
        play_again_view.message = message

    async def process_goalkeeper_save_direct(self, ctx, loading_message, dive_direction, bet_amount, game_id):
        """Process direct goalkeeper save"""
        # Remove from ongoing games
        if game_id in self.ongoing_games:
            del self.ongoing_games[game_id]

        # Striker picks a random direction
        striker_directions = ["left", "middle", "right"]
        striker_direction = random.choice(striker_directions)

        # Determine the outcome
        save_made = dive_direction == striker_direction

        # Direction emojis for visual representation
        direction_emojis = {"left": "⬅️", "middle": "⬆️", "right": "➡️"}
        direction_names = {"left": "Left Corner", "middle": "Center Goal", "right": "Right Corner"}

        # Calculate winnings
        multiplier = 2.1
        winnings = bet_amount * multiplier if save_made else 0

        # Create result embed
        if save_made:
            embed = discord.Embed(
                title=f"<:yes:1355501647538815106> | **INCREDIBLE SAVE!** 🥅",
                description=(
                    f"```diff\n"
                    f"+ WHAT A SAVE! ABSOLUTELY PHENOMENAL!\n"
                    f"```\n"
                    f"**🎯 Striker Shot:** {direction_emojis[striker_direction]} {direction_names[striker_direction]}\n"
                    f"**🥅 Your Dive:** {direction_emojis[dive_direction]} {direction_names[dive_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: SHOT SAVED!\n"
                    f"Winnings: +{winnings:.2f} points\n"
                    f"Multiplier: {multiplier}x\n"
                    f"```\n"

                    f"**🏆 Outstanding reflexes! You've denied the striker and earned big!**\n"
                    f"> The crowd erupts as you make the impossible save! 🙌"
                ),
                color=0x00FF00
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings)

            nnn = Servers()
            nnn.update_server_profit(ctx, ctx.guild.id, -winnings, game="penalty")

        else:
            embed = discord.Embed(
                title=f"<:no:1344252518305234987> | **GOAL CONCEDED!** ⚽",
                description=(
                    f"```diff\n"
                    f"- The striker finds the back of the net!\n"
                    f"```\n"
                    f"**🎯 Striker Shot:** {direction_emojis[striker_direction]} {direction_names[striker_direction]}\n"
                    f"**🥅 Your Dive:** {direction_emojis[dive_direction]} {direction_names[dive_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: GOAL SCORED!\n"
                    f"Loss: -{bet_amount:.2f} points\n"
                    f"```\n"

                    f"**😔 The striker outfoxed you this time! Keep training!**\n"
                    f"> They placed it perfectly in the opposite corner! ⚽"
                ),
                color=0xFF4444
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1344252518305234987.png")

            # Update statistics
            db = Users()

        embed.set_footer(text="🥅 BetSync Casino • Ready for another challenge?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_goalkeeper", bet_amount, dive_direction, striker_direction, save_made, multiplier, winnings)

        # Update server profit
        nnn = Servers()
        nnn.update_server_profit(ctx, ctx.guild.id, bet_amount, game="penalty")

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await loading_message.edit(embed=embed, view=play_again_view)
        play_again_view.message = message

    async def start_as_taker(self, ctx, interaction, bet_amount, game_id):
        """Start the game as a penalty taker"""
        embed = discord.Embed(
            title="⚽ **STRIKER MODE ACTIVATED** ⚽",
            description=(
                f"```\n"
                f"💰 Your Bet: {bet_amount:,.2f} points\n"
                f"🎯 Potential Win: {bet_amount*1.45:,.2f} points\n"
                f"```\n"
                f"**🔥 TIME TO SCORE! 🔥**\n\n"

                f"> The goalkeeper is ready...\n"
                f"> The crowd holds its breath...\n"
                f"> **Choose your target and SHOOT!**\n\n"

                f"```yaml\n"
                f"Left Corner    Middle Goal    Right Corner\n"
                f"   ⬅️             ⬆️             ➡️\n"
                f"```\n"

                f"```diff\n"
                f"+ Pick your spot and beat the keeper!\n"
                f"```"
            ),
            color=0xFF6B35
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")
        embed.set_footer(text="⚽ BetSync Casino • Show them your skills!", icon_url=self.bot.user.avatar.url)

        # Create view with shooting buttons
        view = PenaltyButtonView(self, ctx, bet_amount, "taker", game_id, timeout=30)
        message = await interaction.message.edit(embed=embed, view=view)
        view.message = message

    async def start_as_goalkeeper(self, ctx, interaction, bet_amount, game_id):
        """Start the game as a goalkeeper"""
        embed = discord.Embed(
            title="🥅 **GOALKEEPER MODE ACTIVATED** 🥅",
            description=(
                f"```\n"
                f"💰 Your Bet: {bet_amount:,.2f} points\n"
                f"🏆 Potential Win: {bet_amount*2.1:,.2f} points\n"
                f"```\n"
                f"**🛡️ MAKE THE SAVE! 🛡️**\n\n"

                f"> The striker is approaching...\n"
                f"> This is your moment to shine...\n"
                f"> **Predict their shot and DIVE!**\n\n"

                f"```yaml\n"
                f"Dive Left     Stay Center     Dive Right\n"
                f"   ⬅️             ⬆️             ➡️\n"
                f"```\n"

                f"```diff\n"
                f"+ Trust your instincts and make the save!\n"
                f"```"
            ),
            color=0x4CAF50
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")
        embed.set_footer(text="🥅 BetSync Casino • Be the hero!", icon_url=self.bot.user.avatar.url)

        # Create view with diving buttons
        view = PenaltyButtonView(self, ctx, bet_amount, "goalkeeper", game_id, timeout=30)
        message = await interaction.message.edit(embed=embed, view=view)
        view.message = message

    async def process_penalty_shot(self, ctx, interaction, shot_direction, bet_amount, game_id):
        """Process the penalty shot when user is the taker"""
        # Remove from ongoing games
        if game_id in self.ongoing_games:
            del self.ongoing_games[game_id]

        # Goalkeeper picks a random direction
        goalkeeper_directions = ["left", "middle", "right"]
        goalkeeper_direction = random.choice(goalkeeper_directions)

        # Determine the outcome
        goal_scored = shot_direction != goalkeeper_direction

        # Direction emojis for visual representation
        direction_emojis = {"left": "⬅️", "middle": "⬆️", "right": "➡️"}
        direction_names = {"left": "Left Corner", "middle": "Center Goal", "right": "Right Corner"}

        # Calculate winnings
        multiplier = 1.45
        winnings = bet_amount * multiplier if goal_scored else 0

        # Create result embed
        if goal_scored:
            embed = discord.Embed(
                title=f"<:yes:1355501647538815106> | **GOOOOOAL!** ⚽",
                description=(
                    f"```diff\n"
                    f"+ SPECTACULAR SHOT! THE CROWD GOES WILD!\n"
                    f"```\n"
                    f"**🎯 Your Shot:** {direction_emojis[shot_direction]} {direction_names[shot_direction]}\n"
                    f"**🥅 Keeper Dove:** {direction_emojis[goalkeeper_direction]} {direction_names[goalkeeper_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: GOAL SCORED!\n"
                    f"Winnings: +{winnings:.2f} points\n"
                    f"Multiplier: {multiplier}x\n"
                    f"```\n"

                    f"**🏆 Perfect execution! You've beaten the goalkeeper and won big!**\n"
                    f"> The net bulges as your shot finds its mark! 🎉"
                ),
                color=0x00FF00
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings)

        else:
            embed = discord.Embed(
                title=f"<:no:1344252518305234987> | **SAVED!** 🥅",
                description=(
                    f"```diff\n"
                    f"- The goalkeeper makes a brilliant save!\n"
                    f"```\n"
                    f"**🎯 Your Shot:** {direction_emojis[shot_direction]} {direction_names[shot_direction]}\n"
                    f"**🥅 Keeper Dove:** {direction_emojis[goalkeeper_direction]} {direction_names[goalkeeper_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: SHOT SAVED!\n"
                    f"Loss: -{bet_amount:.2f} points\n"
                    f"f"```\n"

                    f"**😤 The goalkeeper read your mind! Better luck next time!**\n"
                    f"> What a save! The keeper anticipated your move perfectly! 🧤"
                ),
                color=0xFF4444
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1344252518305234987.png")

            # Update statistics
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

        embed.set_footer(text="⚽ BetSync Casino • Want another shot?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_taker", bet_amount, shot_direction, goalkeeper_direction, goal_scored, multiplier, winnings)

        # Update server profit
        nnn = Servers()
        nnn.update_server_profit(ctx, ctx.guild.id, bet_amount, game="penalty")

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await interaction.message.edit(embed=embed, view=play_again_view)
        play_again_view.message = message

    async def process_goalkeeper_save(self, ctx, interaction, dive_direction, bet_amount, game_id):
        """Process the penalty save when user is the goalkeeper"""
        # Remove from ongoing games
        if game_id in self.ongoing_games:
            del self.ongoing_games[game_id]

        # Striker picks a random direction
        striker_directions = ["left", "middle", "right"]
        striker_direction = random.choice(striker_directions)

        # Determine the outcome
        save_made = dive_direction == striker_direction

        # Direction emojis for visual representation
        direction_emojis = {"left": "⬅️", "middle": "⬆️", "right": "➡️"}
        direction_names = {"left": "Left Corner", "middle": "Center Goal", "right": "Right Corner"}

        # Calculate winnings
        multiplier = 2.1
        winnings = bet_amount * multiplier if save_made else 0

        # Create result embed
        if save_made:
            embed = discord.Embed(
                title=f"<:yes:1355501647538815106> | **INCREDIBLE SAVE!** 🥅",
                description=(
                    f"```diff\n"
                    f"+ WHAT A SAVE! ABSOLUTELY PHENOMENAL!\n"
                    f"```\n"
                    f"**🎯 Striker Shot:** {direction_emojis[striker_direction]} {direction_names[striker_direction]}\n"
                    f"**🥅 Your Dive:** {direction_emojis[dive_direction]} {direction_names[dive_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: SHOT SAVED!\n"
                    f"Winnings: +{winnings:.2f} points\n"
                    f"Multiplier: {multiplier}x\n"
                    f"```\n"

                    f"**🏆 Outstanding reflexes! You've denied the striker and earned big!**\n"
                    f"> The crowd erupts as you make the impossible save! 🙌"
                ),
                color=0x00FF00
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1355501647538815106.png")

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings)

            nnn = Servers()
            nnn.update_server_profit(ctx, ctx.guild.id, -winnings, game="penalty")

        else:
            embed = discord.Embed(
                title=f"<:no:1344252518305234987> | **GOAL CONCEDED!** ⚽",
                description=(
                    f"```diff\n"
                    f"- The striker finds the back of the net!\n"
                    f"```\n"
                    f"**🎯 Striker Shot:** {direction_emojis[striker_direction]} {direction_names[striker_direction]}\n"
                    f"**🥅 Your Dive:** {direction_emojis[dive_direction]} {direction_names[dive_direction]}\n\n"

                    f"```yaml\n"
                    f"Result: GOAL SCORED!\n"
                    f"Loss: -{bet_amount:.2f} points\n"
                    f"