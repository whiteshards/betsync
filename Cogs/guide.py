import discord
import json
import asyncio
from discord.ext import commands
from Cogs.utils.emojis import emoji

class Guide(commands.Cog):
    def __init__(self, bot):

        self.emojis = emoji()
        self.required = [self.emojis["money"]]	
        self.bot = bot

    @commands.command()
    async def help(self, ctx):
        embed = discord.Embed(
            title="BetSync Casino Commands",
            description="Welcome to BetSync Casino. Use `!guide` for detailed information.",
            color=0x00FFAE
        )

        embed.add_field(
            name="What is BetSync?",
            value="**BetSync** is a **modern crypto casino bot** offering:\n"
                  "• **Provably Fair Games**: All outcomes are verifiable\n"
                  "• **High RTP**: 98.5% return to player rate\n"
                  "• **Secure**: Cryptographically secure random number generation\n"
                  "• **Fast**: Instant deposits and quick withdrawals\n"
                  "• **24/7 Support**: Always here to help\n"
                  "• **Multiple Games**: From classics to modern favorites",
            inline=False
        )

        embed.add_field(
            name="Currency Information",
            value="**Tokens & Credits**\nTokens: Used for betting\nCredits: Used for withdrawals",
            inline=False
        )

        embed.add_field(
            name="Banking",
            value="**Deposits**\n`!dep <currency>`\n**Withdrawals**\n`!withdraw <amount> <address>` (Min: 20 Credits)",
            inline=False
        )

        embed.add_field(
            name="Popular Games",
            value="`!blackjack` Classic card game\n`!mines` Find gems\n`!crash` Multiplier game\n`!coinflip` Heads or tails\n`!cases` Open cases",
            inline=False
        )

        embed.add_field(
            name="Account",
            value="`!profile` View stats\n`!history` Transaction history\n`!rakeback` Get cashback\n`!modmail` Contact administrators",
            inline=False
        )

        embed.set_footer(text="BetSync Casino • Type any command for detailed usage", icon_url=self.bot.user.avatar.url)
        
        # Send the embed to the user
        return await ctx.reply(embed=embed)

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 24-hour cooldown
    async def modmail(self, ctx):
        """Send a message to the bot administrators"""
        # First, send instructions to the user
        embed = discord.Embed(
            title="📧 ModMail System",
            description="Please check your DMs to continue with the ModMail process.",
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)
        
        try:
            # Send DM to user asking for their message
            dm_embed = discord.Embed(
                title="📧 ModMail System",
                description="Please type your message below. This will be sent to the bot administrators.\n\nYou have 200 seconds to reply.",
                color=0x00FFAE
            )
            dm_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            dm = await ctx.author.send(embed=dm_embed)
            
            # Wait for user's response
            def check(m):
                return m.author == ctx.author and m.channel == dm.channel and not m.content.startswith('!')
            
            try:
                # Wait for response with timeout
                response = await self.bot.wait_for('message', check=check, timeout=200)
                message_content = response.content
                
                # Load admin IDs from file
                admin_ids = []
                try:
                    with open("admins.txt", "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and line.isdigit():
                                admin_ids.append(int(line))
                except Exception as e:
                    await ctx.author.send(f"Error processing ModMail: {e}")
                    return
                
                # Create embed for admins
                admin_embed = discord.Embed(
                    title="📨 New ModMail",
                    description=f"**From:** {ctx.author.mention} (`{ctx.author.id}`)\n**Server:** {ctx.guild.name} (`{ctx.guild.id}`)\n\n**Message:**\n{message_content}",
                    color=0xFF9900,
                    timestamp=ctx.message.created_at
                )
                admin_embed.set_footer(text=f"User ID: {ctx.author.id}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                
                # Send message to all admins
                sent_count = 0
                for admin_id in admin_ids:
                    try:
                        admin = await self.bot.fetch_user(admin_id)
                        if admin:
                            await admin.send(embed=admin_embed)
                            sent_count += 1
                    except Exception as e:
                        print(f"Failed to send ModMail to admin {admin_id}: {e}")
                
                # Confirm to user
                if sent_count > 0:
                    confirm_embed = discord.Embed(
                        title="✅ ModMail Sent",
                        description="Your message has been sent to the administrators. Please wait patiently for a response.",
                        color=0x00FF00
                    )
                    confirm_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                    await ctx.author.send(embed=confirm_embed)
                else:
                    error_embed = discord.Embed(
                        title="❌ ModMail Failed",
                        description="Failed to send your message to any administrators. Please try again later or contact support.",
                        color=0xFF0000
                    )
                    error_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                    await ctx.author.send(embed=error_embed)
                
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ ModMail Timed Out",
                    description="You did not provide a message within the time limit. Please use `!modmail` again if you still need to contact administrators.",
                    color=0xFF0000
                )
                timeout_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                await ctx.author.send(embed=timeout_embed)
        
        except discord.Forbidden:
            # User has DMs closed
            error_embed = discord.Embed(
                title="❌ ModMail Failed",
                description="I couldn't send you a DM. Please enable DMs from server members and try again.",
                color=0xFF0000
            )
            error_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await ctx.reply(embed=error_embed)
            self.modmail.reset_cooldown(ctx)

        await ctx.reply(embed=embed)

    @commands.command()
    async def guide(self, ctx):
        embed = discord.Embed(title=":slot_machine: **Welcome to BetSync Casino!**", color=0x00FFAE, description="**BetSync** is a **Crypto Powered Casino** where you can bet, win, and enjoy a variety of games. We offer **fast deposits**, **fair games**, and **multiple earning methods**! Here\'s everything you need to know to get started:\n")
        embed.add_field(name=f"{self.required[0]} **Tokens & Credits**", value="- **Tokens**: Used for **betting and playing games**.Use `!deposit` to get tokens\n- **Credits**: Rewarded after **winning a bet**, Used for **withdrawals**`!withdraw <credits` and **Betting**.\n- **Conversion Rates**:\n```\n1 Token/Credit = $0.0212\n```\nUse `!rate <amount> <currency>` to convert between **Tokens**, **Credits**, and **crypto**.\n", inline=False)
        embed.add_field(name=":inbox_tray: **Deposits & Withdrawals**", value="- **Deposit**: Use `!deposit` to select a currency and get a address\n- **Minimum Deposit**: Check in `!help`\n- **Withdraw**: Use `!withdraw`.\n- **Minimum Withdrawal**: 20 Credits.\n- **Processing**: Deposits are instant after 1 confirmation. Withdrawals take a few minutes.\n", inline=False)
        embed.add_field(name=":gift: **Earn Free Tokens**", value="- **Daily Reward**: Use `!daily` to claim **free tokens**.\n- **Giveaways**: Look out for **airdrops** hosted \n- **Tips**: Other players can **tip you tokens**.\n- **Rakeback:** Get **cashback** on bets via `!rakeback` **(based on deposits).**\n", inline=False)
        embed.add_field(name=":video_game: **Playing Games**", value="- **See All Games:** Use `!help` to view available games.\n- **Multiplayer Games:** Use `!multiplayer` to see PvP games.\n - **Popular Games:** Play **Blackjack**,** Keno:**, **Towers:**, **Mines:**, **Coinflip**, and more!\n Each game has a **detailed command:**, e.g., `!blackjack` for rules, bets, and payouts.\n", inline=False)
        embed.add_field(name=":shield: **Fairness & Security**", value="- All games use **cryptographically secure random number generation**\n- **Provably Fair**: Every bet is `verifiable and unbiased`.\n- **98.5% RTP**: Fair odds compared to other casinos\n", inline=False)
        embed.add_field(name=":scroll: **Example Commands**", value="- `!deposit:` **Deposit** \n - `!withdraw:` **Withdraw** \n - `!rate 100 BTC:` **Convert** \n - `!blackjack 10:` **Bet** \n - `!mines 5 3:` **Play Mines** \n - `!help:` **All Commands**", inline=False)
        embed.add_field(name=":question_mark: **Need Help?**", value="- For support, type `!support` and **submit a request.**\n- Got **feedback?** Let us know!", inline=False)
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_author(name="BetSync Official Guide", icon_url=self.bot.user.avatar.url)

        await ctx.message.reply(embed=embed)

def setup(bot):
    bot.add_cog(Guide(bot))