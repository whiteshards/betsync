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
            "deposit": "Get deposit address for supported currencies",
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
            "rockpaperscissors": "Play the classic game against other players",
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

    @commands.command(name="signup")
    async def signup(self, ctx):
        embed = discord.Embed(
            title=":wave: **Welcome to BetSync Casino**",
            description="Press The Button Below To Sign Up If You're A New User!",
            color=0x00FFAE
        )
        await ctx.reply(embed=embed, view=MainView(self.bot, ctx.author))

def setup(bot):
    bot.add_cog(Start(bot))
    