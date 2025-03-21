
import discord
import random
from discord.ext import commands
from datetime import datetime
from Cogs.utils.mongo import Users, Servers

class RoleSelectionView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_type, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_type = currency_type
        self.message = None

    @discord.ui.button(label="Penalty Taker", style=discord.ButtonStyle.primary, emoji="⚽", custom_id="taker")
    async def taker_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        
        # Start game as penalty taker
        await self.cog.start_as_taker(self.ctx, interaction, self.bet_amount, self.currency_type)

    @discord.ui.button(label="Goalkeeper", style=discord.ButtonStyle.success, emoji="🧤", custom_id="goalkeeper")
    async def goalkeeper_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        
        # Start game as goalkeeper
        await self.cog.start_as_goalkeeper(self.ctx, interaction, self.bet_amount, self.currency_type)

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
                
                # Remove from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
            except:
                pass


class PenaltyButtonView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, role="taker", timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.role = role
        self.message = None
        self.clicked = False  # Prevent multiple clicks

    @discord.ui.button(label="Left", style=discord.ButtonStyle.primary, emoji="⬅️", custom_id="left")
    async def left_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        
        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "left", self.bet_amount)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "left", self.bet_amount)

    @discord.ui.button(label="Middle", style=discord.ButtonStyle.primary, emoji="⬆️", custom_id="middle")
    async def middle_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        #await interaction.response.edit_message(view=self)
        
        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "middle", self.bet_amount)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "middle", self.bet_amount)

    @discord.ui.button(label="Right", style=discord.ButtonStyle.primary, emoji="➡️", custom_id="right")
    async def right_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.defer()
        await interaction.message.edit(view=self)
        #await interaction.response.edit_message(view=self)
        
        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "right", self.bet_amount)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "right", self.bet_amount)

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
                
                # Remove from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
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
        #await interaction.response.edit_message(view=self)

        # Check if user can afford the same bet
        

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
        self.ongoing_games = {}
        self.message = None
        self.message2 = None

    @commands.command(aliases=["pen", "pk"])
    async def penalty(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play penalty shootout - choose to be a penalty taker or goalkeeper!"""
        if not bet_amount:
            embed = discord.Embed(
                title="⚽ How to Play Penalty",
                description=(
                    "**Penalty** is a game where you can be either a penalty taker or a goalkeeper!\n\n"
                    "**Usage:** `!penalty <amount> [currency_type]`\n"
                    "**Example:** `!penalty 100` or `!penalty 100 credits`\n\n"
                    "**Choose your role:**\n"
                    "- **As Penalty Taker:** Choose where to shoot (left/middle/right). If the goalkeeper dives in a different direction, you score and win 1.45x your bet!\n"
                    "- **As Goalkeeper:** Choose where to dive (left/middle/right). If you guess correctly where the striker will shoot, you save and win 2.1x your bet!\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        

        # Create loading embed
        loading_embed = discord.Embed(
            title="⚽ Setting up the penalty game...",
            description="Processing your bet...",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Import the currency helper
        from Cogs.utils.currency_helper import process_bet_amount

        try:
            # Process the bet amount using the currency helper
            success, bet_info, error_embed = await process_bet_amount(ctx, bet_amount, currency_type, loading_message)

            # If processing failed, return the error
            if not success:
                await loading_message.delete()
                return await ctx.reply(embed=error_embed)

            # Successful bet processing - extract relevant information
            tokens_used = bet_info.get("tokens_used", 0)
            credits_used = bet_info.get("credits_used", 0)
            bet_amount = bet_info.get("total_bet_amount", 0)
            currency_used = bet_info.get("currency_type", "credits")  # Default to credits if not specified
        except Exception as e:
            print(f"Error processing bet: {e}")
            await loading_message.delete()
            return await ctx.reply(f"An error occurred while processing your bet: {str(e)}")

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount,
            "currency_type": currency_used,
            "tokens_used": tokens_used,
            "credits_used": credits_used
        }

        # Deduct bet from user's balance
        

        # Create role selection embed
        embed = discord.Embed(
            title="⚽ PENALTY KICK - CHOOSE YOUR ROLE",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_used}\n\n"
                "**Choose your role:**\n"
                "**🧤 Goalkeeper:** You dive to save the shot. Win 2.1x if you save!\n"
                "**⚽ Penalty Taker:** You shoot at goal. Win 1.45x if you score!"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create view with role selection buttons
        view = RoleSelectionView(self, ctx, bet_amount, currency_type, timeout=30)
        
        # Update the loading message instead of deleting and creating a new one
        self.message = await loading_message.edit(embed=embed, view=view)
        view.message = loading_message

    async def start_as_taker(self, ctx, interaction, bet_amount, currency_type):
        """Start the game as a penalty taker"""
        #await self.message.delete()
        embed = discord.Embed(
            title="⚽ PENALTY KICK - YOU ARE THE TAKER",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_type}\n"
                f"**Potential win:** {bet_amount*1.45:,.2f} credits\n\n"
                "**Choose where to shoot by clicking a button below:**"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create view with shooting buttons
        view = PenaltyButtonView(self, ctx, bet_amount, role="taker", timeout=30)
        self.message2 = await self.message.edit(embed=embed, view=view)
        view.message = self.message2

    async def start_as_goalkeeper(self, ctx, interaction, bet_amount, currency_type):
        """Start the game as a goalkeeper"""
        #await self.message.delete()
        embed = discord.Embed(
            title="🧤 PENALTY KICK - YOU ARE THE GOALKEEPER",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_type}\n"
                f"**Potential win:** {bet_amount*2.1:,.2f} credits\n\n"
                "**Choose where to dive by clicking a button below:**"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create view with diving buttons
        view = PenaltyButtonView(self, ctx, bet_amount, role="goalkeeper", timeout=30)
        self.message2 = await self.message.edit(embed=embed, view=view)
        view.message = self.message2

    async def process_penalty_shot(self, ctx, interaction, shot_direction, bet_amount):
        """Process the penalty shot when user is the taker"""
        #await self.message.delete()
        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

        # Goalkeeper picks a random direction
        goalkeeper_directions = ["left", "middle", "right"]
        goalkeeper_direction = random.choice(goalkeeper_directions)

        # Determine the outcome
        goal_scored = shot_direction != goalkeeper_direction

        # Calculate winnings
        multiplier = 1.45
        winnings = bet_amount * multiplier if goal_scored else 0

        # Create result embed
        if goal_scored:
            title = "🎉 GOAL! YOU SCORED! 🎉"
            description = f"You shot **{shot_direction.upper()}**, the goalkeeper dove **{goalkeeper_direction.upper()}**.\n\n**You won {winnings:,.2f} credits!**"
            color = 0x00FF00  # Green for win

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")

            # Update statistics
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_won": 1, "total_earned": winnings}}
            )

            # Result text
            result_text = f"**You shot {shot_direction.upper()} and the goalkeeper went {goalkeeper_direction.upper()}!**"
        else:
            title = "❌ SAVED! THE GOALKEEPER STOPPED YOUR SHOT! ❌"
            description = f"You shot **{shot_direction.upper()}**, the goalkeeper dove **{goalkeeper_direction.upper()}**.\n\n**You lost {bet_amount:,.2f} credits.**"
            color = 0xFF0000  # Red for loss

            # Update statistics
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

            # Result text
            result_text = f"**You shot {shot_direction.upper()} and the goalkeeper went {goalkeeper_direction.upper()}!**"

        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"{result_text}\n\n{description}",
            color=color
        )
        embed.set_footer(text="BetSync Casino | Want to try again?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_taker", bet_amount, shot_direction, goalkeeper_direction, goal_scored, multiplier, winnings)

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await self.message2.edit(embed=embed, view=play_again_view)
        play_again_view.message = message

    async def process_goalkeeper_save(self, ctx, interaction, dive_direction, bet_amount):
        #await self.message.delete()
        """Process the penalty save when user is the goalkeeper"""
        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

        # Striker picks a random direction
        striker_directions = ["left", "middle", "right"]
        striker_direction = random.choice(striker_directions)

        # Determine the outcome
        save_made = dive_direction == striker_direction

        # Calculate winnings
        multiplier = 2.1  # Higher multiplier for goalkeeper
        winnings = bet_amount * multiplier if save_made else 0

        # Create result embed
        if save_made:
            title = "🎉 SAVE! YOU STOPPED THE SHOT! 🎉"
            description = f"You dove **{dive_direction.upper()}**, the striker shot **{striker_direction.upper()}**.\n\n**You won {winnings:,.2f} credits!**"
            color = 0x00FF00  # Green for win

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")

            # Update statistics
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_won": 1, "total_earned": winnings}}
            )
            nnn = Servers()
            nnn.update_server_profit(ctx.guild.id, -winnings, game="penalty")
            # Result text
            result_text = f"**You dove {dive_direction.upper()} and the striker shot {striker_direction.upper()}!**"
        else:
            title = "❌ GOAL! THE STRIKER SCORED PAST YOU! ❌"
            description = f"You dove **{dive_direction.upper()}**, the striker shot **{striker_direction.upper()}**.\n\n**You lost {bet_amount:,.2f} credits.**"
            color = 0xFF0000  # Red for loss

            # Update statistics
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

            # Result text
            result_text = f"**You dove {dive_direction.upper()} and the striker shot {striker_direction.upper()}!**"

        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"{result_text}\n\n{description}",
            color=color
        )
        embed.set_footer(text="BetSync Casino | Want to try again?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_goalkeeper", bet_amount, dive_direction, striker_direction, save_made, multiplier, winnings)
        nnn = Servers()
        nnn.update_server_profit(ctx.guild.id, bet_amount, game="penalty")
        

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await self.message2.edit(embed=embed, view=play_again_view)
        play_again_view.message = message

    def update_bet_history(self, ctx, game_type, bet_amount, user_choice, ai_choice, won, multiplier, winnings):
        """Update bet history in database"""
        # Create timestamp
        timestamp = int(datetime.utcnow().timestamp())
        
        # Create game data
        game_data = {
            "game": game_type,
            "type": "win" if won else "loss",
            "bet": bet_amount,
            "amount": winnings if won else bet_amount,
            "multiplier": multiplier if won else 0,
            "choice": user_choice,
            "outcome": ai_choice,
            "win": won,
            "timestamp": timestamp
        }
        
        # Update user history
        db = Users()
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [game_data], "$slice": -100}}}
        )

        # Update server history with additional user information
        server_db = Servers()
        server_id = ctx.guild.id if ctx.guild else None
        
        if server_id:
            server_game_data = game_data.copy()
            server_game_data["user_id"] = ctx.author.id
            server_game_data["user_name"] = str(ctx.author)
            
            server_db.update_history(server_id, server_game_data)


def setup(bot):
    bot.add_cog(PenaltyCog(bot))
