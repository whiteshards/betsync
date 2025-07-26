import discord
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users

class MainView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__()
        self.bot = bot
        self.user = user

    @discord.ui.button(label="Sign Up", style=discord.ButtonStyle.green)
    async def signup(self,button, interaction: discord.Interaction):
        dump = {"discord_id": self.user.id, "tokens": 0, "credits": 0, "history": []}
        money = emoji()["money"]
        response = Users().register_new_user(dump)

        if response is False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | **User Already Has An Account.**",
                color=0xFF0000,
                description="- **You Are Already Registered In Our Database.**"
            )
        else:
            embed = discord.Embed(
                title="**Registered New User**",
                description="**Your discord account has been successfully registered in our database with the following details:**\n```Tokens: 0\nCredits: 0```",
                color=0x00FFAE
            )
            embed.add_field(name=f"{money} Get Started", value="- **Type !help or !guide to start betting!**", inline=False)

        embed.set_footer(text="BetSync Casino • Best Casino", icon_url=self.user.avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GamePaginator(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.current_page = 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.embeds[self.current_page])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.embeds[self.current_page])

class Start(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_descriptions = {
            # Profile & Stats
            "profile": "View your casino profile and statistics",
            #"history": "View your transaction history",
            #"stats": "View your gambling statistics",
            "leaderboard": "View top players and your rank.",

            # Currency & Banking
            "deposit": "Deposit currency for tokens",
            "withdraw": "Withdraw your credits to crypto",
            "tip": "Send tokens to other players",

            # Information
            #"guide": "View the complete casino guide",
            "help": "Quick overview of main commands",
            "commands": "Show all available commands",

            # Account Management
            #"signup": "Create a new casino account",
            "rakeback": "Get cashback on your bets",
            "daily": "Claim your daily reward (requires meeting criteria)",
            "ref": "View referral statistics and leaderboard",

            # Server Features
            #"serverstats": "View server statistics and earnings",
            #"serverbethistory": "View server's betting history",
            #"airdrop": "Create a token/credit airdrop",

            # Lottery System
            #"loterry": "View or participate in the current lottery",
            #"loterryhistory": "View past lottery results",

            # Games List 
            "games": "List all available casino games",
            #"multiplayer": "View available PvP games"
        }

        self.game_descriptions = {
            "blackjack": "🃏 Classic card game - Get 21 without going over",
            "mines": "💣 Avoid the mines and collect multipliers",
            "keno": "🎱 Pick numbers and match them to win",
            "coinflip": "🪙 Simple heads or tails betting",
            "dice": "🎲 Roll dice and predict the outcome",
            "tower": "🗼 Climb the tower and cash out before you fall",
            "wheel": "🎡 Spin the wheel of fortune",
            "limbo": "🚁 Predict if the multiplier will be over your target",
            "hilo": "📈 Guess if the next card is higher or lower",
            "plinko": "🔴 Drop the ball and watch it bounce to prizes",
            "baccarat": "🎴 Classic casino card game",
            "poker": "🃏 Five-card poker with payouts",
            "penalty": "⚽ Penalty shootout betting game",
            "race": "🏎️ Bet on racing cars",
            "match": "🎯 Memory matching game",
            "pump": "📈 Predict market pumps and dumps",
            "build": "🏗️ Build towers with risk-based blocks",
            "crosstheroad": "🚗 Navigate traffic and earn multipliers",
            "cases": "📦 Open mystery cases for rewards",
            "carddraw": "🎴 Draw cards and build winning hands",
            "progressivecf": "🪙 Progressive coinflip with growing jackpot",
            "slots": "🎰 Premium slots machine - Match symbols to win big"
        }


    @commands.command(name="tnc", aliases=["terms", "tos"])
    async def tnc(self, ctx):
        embeds = []
        fields_per_page = 4

        tnc_fields = [
            ("1. Introduction", "Welcome to betsync – a Discord bot designed to simulate betting and gambling-style games on Discord servers. By using betsync, you agree to abide by these Terms & Conditions ('Terms'). If you do not agree with any part of these Terms, please do not use the bot."),
            ("2. Acceptance of Terms", "By accessing or using betsync, you confirm that you have read, understood, and agree to be bound by these Terms and any future amendments."),
            ("3. Eligibility", "• You must be at least 18 years old, or the legal age in your jurisdiction, to use betsync.\n• By using betsync, you confirm that you meet this age requirement and have the legal capacity to enter this agreement."),
            ("4. Use of betsync", "• Purpose: betsync is intended for entertainment purposes only.\n• Betting Simulation: The bot simulates gambling activities with an RTP of 98.5%.\n• Randomness: All game outcomes are determined by a Random Number Generator (RNG)."),
            ("5. Virtual Currency & Wagering", "• Virtual Nature: Any currency or points used by betsync are virtual and hold no real-world monetary value.\n• Wagering: All bets placed are for simulation purposes only."),
            ("6. Responsible Gambling", "• Gambling—even in a simulated environment—carries inherent risks.\n• Please use betsync responsibly.\n• If you suspect you have a gambling problem, please seek professional help."),
            ("7. Limitation of Liability", "• 'As Is' Service: betsync is provided on an 'as is' basis without warranties.\n• No Liability: The creators will not be liable for any damages arising from your use."),
            ("8. Modifications and Termination", "• Changes: We reserve the right to modify these Terms at any time.\n• Termination: We may suspend or terminate your access at our sole discretion."),
            ("9. Intellectual Property", "All content, trademarks, and intellectual property related to betsync are owned by its creators. You are granted a non-exclusive license to use betsync solely for personal purposes."),
            ("10. Governing Law", "These Terms are governed by applicable laws and any disputes shall be resolved through informal negotiations first.")
        ]

        # Create pages
        for i in range(0, len(tnc_fields), fields_per_page):
            page_fields = tnc_fields[i:i + fields_per_page]

            embed = discord.Embed(
                title="BetSync Terms & Conditions",
                description="Last Updated: March 2025",
                color=0x00FFAE
            )

            for name, value in page_fields:
                embed.add_field(name=name, value=value, inline=False)

            embed.set_footer(text=f"Page {i//fields_per_page + 1}/{(len(tnc_fields) + fields_per_page - 1)//fields_per_page}")
            embeds.append(embed)

        view = GamePaginator(embeds)
        await ctx.reply(embed=embeds[0], view=view)

    #@commands.command(name="signup")
    async def signup(self, ctx):
        embed = discord.Embed(
            title=":wave: **Welcome to BetSync Casino**",
            description="Press The Button Below To Sign Up If You're A New User!",
            color=0x00FFAE
        )
        await ctx.reply(embed=embed, view=MainView(self.bot, ctx.author))

def setup(bot):
    bot.add_cog(Start(bot))