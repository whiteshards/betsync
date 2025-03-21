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
            "history": "View your transaction history",
            "stats": "View your gambling statistics",
            "leaderboard": "View top players by winnings",

            # Currency & Banking
            "deposit": "Deposit currency for tokens",
            "withdraw": "Withdraw your credits to crypto",
            "tip": "Send tokens to other players",

            # Information
            "guide": "View the complete casino guide",
            "help": "Quick overview of main commands",
            "commands": "Show all available commands",

            # Account Management
            #"signup": "Create a new casino account",
            "rakeback": "Get cashback on your bets",

            # Server Features
            "serverstats": "View server statistics and earnings",
            "serverbethistory": "View server's betting history",
            "airdrop": "Create a token/credit airdrop",

            # Lottery System
            "loterry": "View or participate in the current lottery",
            "loterryhistory": "View past lottery results",

            # Games List 
            "games": "List all available casino games",
            #"multiplayer": "View available PvP games"
        }

        self.game_descriptions = {
            "blackjack": "A classic casino card game where you compete against the dealer to get closest to 21",
            "baccarat": "An elegant card game where you bet on either the Player or Banker hand",
            "coinflip": "A simple heads or tails game with 2x payout",
            "crash": "Watch the multiplier rise and cash out before it crashes",
            "carddraw": "Higher card wielder wins (PvP Only)",
            "cases": "Draw multipliers from cases",
            "crosstheroad": "Guide your character across increasing multipliers without crashing",
            "dice": "Roll the dice and win based on the number prediction",
            "hilo": "Predict if the next card will be higher or lower",
            "keno": "Pick numbers and win based on how many match the draw",
            "limbo": "Choose a target multiplier and win if the result goes over it",
            "match": "Match pairs of cards to win prizes",
            "mines": "Navigate through a minefield collecting gems without hitting mines",
            "penalty": "Score penalty kicks to win tokens",
            "plinko": "Drop balls through pegs for random multipliers",
            "poker": "Classic Texas Hold'em poker against other players",
            "progressivecf": "Coinflip with increasing multipliers on win streaks",
            "pump": "Pump up the balloon but don't let it pop",
            "race": "Bet on racers and win based on their position",
            #"rockpaperscissors": "Play the classic game against other players (PvP + PvE)",
            'tictactoe': "Play classic tictactoe with friends (PvP Only)",
            "tower": "Climb the tower avoiding wrong choices",
            "wheel": "Spin the wheel for various multipliers"
        }

    @commands.command(name="games")
    async def games(self, ctx):
        embeds = []
        games_per_page = 10

        # Sort games alphabetically
        sorted_games = sorted(self.game_descriptions.items())
        total_games = len(sorted_games)

        # Create pages
        for i in range(0, len(sorted_games), games_per_page):
            page_games = sorted_games[i:i + games_per_page]

            embed = discord.Embed(
                title="BetSync Casino Games",
                description=f"**{total_games} Games Available** • Type any command to see usage\n─────────────────────────",
                color=0x00FFAE
            )

            games_list = "\n".join([f"`!{name}` • **{desc}**" for name, desc in page_games])
            embed.description += f"\n\n{games_list}"

            embed.set_footer(text=f"Page {i//games_per_page + 1}/{(len(sorted_games) + games_per_page - 1)//games_per_page}")
            embeds.append(embed)

        view = GamePaginator(embeds)
        await ctx.reply(embed=embeds[0], view=view)

    @commands.command(name="commands")
    async def show_commands(self, ctx):
        embeds = []
        commands_per_page = 10

        # Sort commands alphabetically
        sorted_commands = sorted(self.command_descriptions.items())
        total_commands = len(sorted_commands)

        # Create pages
        for i in range(0, len(sorted_commands), commands_per_page):
            page_commands = sorted_commands[i:i + commands_per_page]

            embed = discord.Embed(
                title="BetSync Casino Commands",
                description=f"**{total_commands} Commands Available** • Type any command to see usage\n─────────────────────────",
                color=0x00FFAE
            )

            commands_list = "\n".join([f"`!{name}` • **{desc}**" for name, desc in page_commands])
            embed.description += f"\n\n{commands_list}"

            embed.set_footer(text=f"Page {i//commands_per_page + 1}/{(len(sorted_commands) + commands_per_page - 1)//commands_per_page}")
            embeds.append(embed)

        view = GamePaginator(embeds)
        await ctx.reply(embed=embeds[0], view=view)

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