
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji
import os
import datetime
import json
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

class ReferralRewardsView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
    
    @discord.ui.button(label="Referral Rewards", style=discord.ButtonStyle.green, emoji="💰")
    async def referral_rewards(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only view your own referral rewards!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Get user data for rank calculation
            users_db = Users()
            user_data = users_db.fetch_user(self.user_id)
            if not user_data:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | User Not Found",
                    description="Could not find your user data.",
                    color=0xFF0000
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Calculate user rank and reward percentage
            user_level = user_data.get("level", 1)
            rank_info = self.get_rank_info(user_level)
            
            # Get referral data
            referral_data = self.cog.referral_collection.find_one({"user_id": self.user_id})
            if not referral_data:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | No Referral Data",
                    description="You don't have any referral data yet.",
                    color=0xFF0000
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Get list of currently invited users
            invited_users = referral_data.get("invited_users", [])
            current_invited_ids = [user_data["user_id"] for user_data in invited_users]
            
            # Remove users who have left
            left_user_ids = referral_data.get("left_user_ids", [])
            current_invited_ids = [uid for uid in current_invited_ids if uid not in left_user_ids]
            
            if not current_invited_ids:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | No Current Invites",
                    description="You don't have any current invites to calculate community rewards from.",
                    color=0xFF0000
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Calculate community activity bonus from invited users
            total_activity = 0
            
            for invited_user_id in current_invited_ids:
                invited_user_data = users_db.fetch_user(invited_user_id)
                if invited_user_data:
                    total_played = invited_user_data.get("total_played", 0)
                    total_activity += total_played
            
            # Calculate community bonus based on activity
            community_bonus = total_activity * rank_info["percentage"]
            
            # Round to nearest whole number
            community_bonus = round(community_bonus)
            
            # Check if user has stored claimable rewards
            stored_rewards = self.cog.referral_collection.find_one({"user_id": self.user_id, "type": "rewards"})
            if not stored_rewards:
                stored_rewards = {
                    "user_id": self.user_id,
                    "type": "rewards",
                    "ltc_points": 0,
                    "btc_points": 0,
                    "last_updated": datetime.datetime.utcnow().isoformat()
                }
                self.cog.referral_collection.insert_one(stored_rewards)
            
            # Add new community bonus to stored rewards
            ltc_bonus = community_bonus // 2
            btc_bonus = community_bonus - ltc_bonus
            
            # Update stored rewards
            self.cog.referral_collection.update_one(
                {"user_id": self.user_id, "type": "rewards"},
                {
                    "$inc": {
                        "ltc_points": ltc_bonus,
                        "btc_points": btc_bonus
                    },
                    "$set": {"last_updated": datetime.datetime.utcnow().isoformat()}
                }
            )
            
            # Get updated stored rewards
            updated_rewards = self.cog.referral_collection.find_one({"user_id": self.user_id, "type": "rewards"})
            total_ltc_points = updated_rewards.get("ltc_points", 0)
            total_btc_points = updated_rewards.get("btc_points", 0)
            
            # Create rewards embed
            embed = discord.Embed(
                title="💰 Community Rewards",
                description=f"Your community activity bonus from {len(current_invited_ids)} active members",
                color=0x00FFAE
            )
            
            # Add rank information
            embed.add_field(
                name=f"{rank_info['emoji']} Your Rank",
                value=f"```{rank_info['name']} (Level {user_level})```",
                inline=False
            )
            
            # Add progress bar for next level
            if user_level < 50:  # Max level
                current_xp = user_data.get("xp", 0)
                next_level_xp = self.get_xp_for_level(user_level + 1)
                current_level_xp = self.get_xp_for_level(user_level)
                xp_progress = current_xp - current_level_xp
                xp_needed = next_level_xp - current_level_xp
                
                progress_percentage = min(xp_progress / xp_needed, 1.0)
                bar_length = 20
                filled_bars = int(progress_percentage * bar_length)
                empty_bars = bar_length - filled_bars
                
                embed.add_field(
                    name="📊 Level Progress",
                    value=f"```[{'█' * filled_bars}{'░' * empty_bars}] {int(progress_percentage * 100)}%```\n`{xp_progress}/{xp_needed} XP to next level`",
                    inline=False
                )
            
            embed.add_field(
                name="🏆 Community Bonus Rate",
                value=f"```{rank_info['percentage']:.1%} per member activity```",
                inline=False
            )
            
            embed.add_field(
                name="🎁 Available Rewards",
                value=f"```Total: {total_ltc_points + total_btc_points} points```",
                inline=False
            )
            
            embed.add_field(
                name="🪙 LTC Rewards",
                value=f"```{total_ltc_points} points```",
                inline=True
            )
            
            embed.add_field(
                name="₿ BTC Rewards", 
                value=f"```{total_btc_points} points```",
                inline=True
            )
            
            # Check if minimum claim amount is met
            can_claim_ltc = total_ltc_points >= 50
            can_claim_btc = total_btc_points >= 50
            
            if can_claim_ltc or can_claim_btc:
                embed.add_field(
                    name="✅ Claim Status",
                    value="Your rewards are ready to claim!\n*Minimum 50 points required per currency*",
                    inline=False
                )
                # Create claim view
                claim_view = ReferralClaimView(self.cog, self.user_id, total_ltc_points, total_btc_points)
                await interaction.followup.send(embed=embed, view=claim_view, ephemeral=True)
            else:
                embed.add_field(
                    name="🔒 Claim Status",
                    value=f"Minimum 50 points required per currency to claim\nLTC: {total_ltc_points}/50 | BTC: {total_btc_points}/50",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while calculating rewards: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    def get_rank_info(self, level):
        """Get rank information based on level"""
        if level >= 40:
            return {"name": "Diamond Elite", "emoji": "💎", "percentage": 0.08}
        elif level >= 25:
            return {"name": "Platinum Master", "emoji": "🏆", "percentage": 0.06}
        elif level >= 15:
            return {"name": "Gold Expert", "emoji": "🥇", "percentage": 0.04}
        elif level >= 5:
            return {"name": "Silver Pro", "emoji": "🥈", "percentage": 0.02}
        else:
            return {"name": "Bronze Member", "emoji": "🥉", "percentage": 0.01}
    
    def get_xp_for_level(self, level):
        """Calculate XP required for a specific level"""
        if level <= 1:
            return 0
        # Exponential XP curve: level^2 * 100
        return (level - 1) ** 2 * 100

class ReferralClaimView(discord.ui.View):
    def __init__(self, cog, user_id, ltc_points, btc_points):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.ltc_points = ltc_points
        self.btc_points = btc_points
        self.ltc_claimed = False
        self.btc_claimed = False
    
    @discord.ui.button(label="Claim LTC Reward", style=discord.ButtonStyle.secondary, emoji="🪙")
    async def claim_ltc(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only claim your own rewards!", ephemeral=True)
            return
        
        if self.ltc_claimed:
            await interaction.response.send_message("You have already claimed your LTC reward!", ephemeral=True)
            return
        
        if self.ltc_points < 50:
            await interaction.response.send_message("You need at least 50 LTC points to claim!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Add points to user balance
            users_db = Users()
            users_db.update_balance(self.user_id, self.ltc_points, operation="$inc")
            
            # Reset LTC points in database
            self.cog.referral_collection.update_one(
                {"user_id": self.user_id, "type": "rewards"},
                {"$set": {"ltc_points": 0}}
            )
            
            self.ltc_claimed = True
            button.disabled = True
            button.label = "LTC Claimed ✓"
            
            await interaction.edit_original_response(view=self)
            
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | LTC Reward Claimed",
                description=f"Successfully claimed **{self.ltc_points} points** as LTC community bonus!",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to claim LTC reward: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Claim BTC Reward", style=discord.ButtonStyle.secondary, emoji="₿")
    async def claim_btc(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only claim your own rewards!", ephemeral=True)
            return
        
        if self.btc_claimed:
            await interaction.response.send_message("You have already claimed your BTC reward!", ephemeral=True)
            return
        
        if self.btc_points < 50:
            await interaction.response.send_message("You need at least 50 BTC points to claim!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Add points to user balance
            users_db = Users()
            users_db.update_balance(self.user_id, self.btc_points, operation="$inc")
            
            # Reset BTC points in database
            self.cog.referral_collection.update_one(
                {"user_id": self.user_id, "type": "rewards"},
                {"$set": {"btc_points": 0}}
            )
            
            self.btc_claimed = True
            button.disabled = True
            button.label = "BTC Claimed ✓"
            
            await interaction.edit_original_response(view=self)
            
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | BTC Reward Claimed",
                description=f"Successfully claimed **{self.btc_points} points** as BTC community bonus!",
                color=0x00FFAE
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"Failed to claim BTC reward: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class ReferralsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_server_id = int(os.environ.get('MAINSERVER_ID', 0))
        
        # Initialize referral tracking database
        self.mongodb = MongoClient(os.environ["MONGO"])
        self.db = self.mongodb["BetSync"]
        self.referral_collection = self.db["referrals"]
        
    @commands.command(aliases=["ref", "referrals"])
    async def referral(self, ctx, user: discord.Member = None):
        """View referral statistics (Main server only)
        
        Usage: !referral [user]
        """
        # Check if command is being used in the main server
        if ctx.guild.id != self.main_server_id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Wrong Server",
                description="This command can only be used in the main server.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Default to command author if no user specified
        target_user = user or ctx.author
        
        # Send loading embed
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Loading Referral Data...",
            description="Please wait while we fetch the referral statistics.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        try:
            # Get referral data from database
            referral_data = self.referral_collection.find_one({"user_id": target_user.id})
            
            if not referral_data:
                # Initialize referral data if not exists
                referral_data = {
                    "user_id": target_user.id,
                    "total_joins": 0,
                    "current_invites": 0,
                    "rejoins": 0,
                    "left_users": 0,
                    "invited_users": [],
                    "left_user_ids": [],
                    "rejoined_user_ids": []
                }
                self.referral_collection.insert_one(referral_data)
            
            # Extract statistics
            total_joins = referral_data.get("total_joins", 0)
            current_invites = referral_data.get("current_invites", 0)
            rejoins = referral_data.get("rejoins", 0)
            left_users = referral_data.get("left_users", 0)
            
            # Create main embed
            embed = discord.Embed(
                title="<:yes:1355501647538815106> | Referral Statistics",
                description=f"Showing referral data for {target_user.mention}",
                color=0x00FFAE
            )
            
            # Add user avatar
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Main statistics
            embed.add_field(
                name="📊 Current Invites",
                value=f"```{current_invites:,}```",
                inline=True
            )
            
            embed.add_field(
                name="👥 Total Joins",
                value=f"```{total_joins:,}```",
                inline=True
            )
            
            embed.add_field(
                name="🔄 Rejoins",
                value=f"```{rejoins:,}```",
                inline=True
            )
            
            embed.add_field(
                name="👋 Left Users",
                value=f"```{left_users:,}```",
                inline=True
            )
            
            # Show recent activity if available
            invited_users = referral_data.get("invited_users", [])
            if invited_users:
                recent_invites = invited_users[-5:]  # Show last 5 invites
                invite_list = []
                for user_data in recent_invites:
                    join_date = user_data.get("join_date", "Unknown")
                    if isinstance(join_date, str):
                        try:
                            join_date = datetime.datetime.fromisoformat(join_date).strftime("%m/%d/%Y")
                        except:
                            join_date = "Unknown"
                    invite_list.append(f"<@{user_data['user_id']}> - {join_date}")
                
                embed.add_field(
                    name="🎯 Recent Invites",
                    value="\n".join(invite_list) if invite_list else "No recent invites",
                    inline=False
                )
            
            # Leaderboard position
            try:
                # Get all users sorted by current invites
                leaderboard = list(self.referral_collection.find().sort("current_invites", -1))
                user_rank = next((i + 1 for i, data in enumerate(leaderboard) if data["user_id"] == target_user.id), "N/A")
                
                embed.add_field(
                    name="🏆 Server Rank",
                    value=f"```#{user_rank}```" if user_rank != "N/A" else "```Unranked```",
                    inline=True
                )
            except:
                pass
            
            # Footer
            embed.set_footer(
                text=f"BetSync Casino • Requested by {ctx.author.name}",
                icon_url=self.bot.user.avatar.url
            )
            
            # Add timestamp
            embed.timestamp = discord.utils.utcnow()
            
            # Create view with referral rewards button
            view = ReferralRewardsView(self, target_user.id)
            
            await loading_message.edit(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Error",
                description=f"An error occurred while fetching referral data: {str(e)}",
                color=0xFF0000
            )
            await loading_message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track when a member joins via invite"""
        if member.guild.id != self.main_server_id:
            return
            
        try:
            # Get current invites
            current_invites = await member.guild.invites()
            
            # Compare with stored invites to find which one was used
            stored_invites = await self.get_stored_invites(member.guild.id)
            
            inviter_id = None
            for current_invite in current_invites:
                if current_invite.inviter:
                    stored_invite = stored_invites.get(current_invite.code)
                    if stored_invite and current_invite.uses > stored_invite["uses"]:
                        inviter_id = current_invite.inviter.id
                        break
            
            # Update stored invites
            await self.update_stored_invites(member.guild.id, current_invites)
            
            if inviter_id:
                # Check if this person was previously invited by anyone (including this inviter)
                previous_inviter_data = self.referral_collection.find_one(
                    {"left_user_ids": member.id}
                )
                
                is_rejoin = False
                is_invite_switch = False
                
                if previous_inviter_data:
                    previous_inviter_id = previous_inviter_data["user_id"]
                    
                    if previous_inviter_id == inviter_id:
                        # Same inviter - this is a rejoin
                        is_rejoin = True
                        # Ensure inviter data exists first
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$setOnInsert": {
                                    "user_id": inviter_id,
                                    "total_joins": 0,
                                    "current_invites": 0,
                                    "rejoins": 0,
                                    "left_users": 0,
                                    "invited_users": [],
                                    "left_user_ids": [],
                                    "rejoined_user_ids": []
                                }
                            },
                            upsert=True
                        )
                        # Remove from left users and add to rejoined (but don't increment current_invites for rejoins)
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$pull": {"left_user_ids": member.id},
                                "$addToSet": {"rejoined_user_ids": member.id},
                                "$inc": {"rejoins": 1}
                            }
                        )
                    else:
                        # Different inviter - this is an invite switch
                        is_invite_switch = True
                        # Remove from previous inviter's left_user_ids (no changes to their stats)
                        self.referral_collection.update_one(
                            {"user_id": previous_inviter_id},
                            {"$pull": {"left_user_ids": member.id}}
                        )
                        
                        # For invite switches, this should count as a rejoin for the new inviter, NOT a new invite
                        # Ensure new inviter data exists first
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$setOnInsert": {
                                    "user_id": inviter_id,
                                    "total_joins": 0,
                                    "current_invites": 0,
                                    "rejoins": 0,
                                    "left_users": 0,
                                    "invited_users": [],
                                    "left_user_ids": [],
                                    "rejoined_user_ids": []
                                }
                            },
                            upsert=True
                        )
                        
                        # Add as rejoin for new inviter (not a new invite)
                        self.referral_collection.update_one(
                            {"user_id": inviter_id},
                            {
                                "$inc": {"rejoins": 1},
                                "$addToSet": {"rejoined_user_ids": member.id}
                            }
                        )
                
                if not is_rejoin and not is_invite_switch:
                    # Completely new invite
                    invite_data = {
                        "user_id": member.id,
                        "username": member.name,
                        "join_date": datetime.datetime.utcnow().isoformat()
                    }
                    
                    # Ensure inviter data exists and update (use upsert to create if doesn't exist)
                    self.referral_collection.update_one(
                        {"user_id": inviter_id},
                        {
                            "$inc": {"total_joins": 1, "current_invites": 1},
                            "$addToSet": {"invited_users": invite_data},
                            "$setOnInsert": {
                                "user_id": inviter_id,
                                "rejoins": 0,
                                "left_users": 0,
                                "left_user_ids": [],
                                "rejoined_user_ids": []
                            }
                        },
                        upsert=True
                    )
                
                if is_rejoin:
                    print(f"[REFERRAL] {member.name} (rejoined) via invite from {inviter_id}")
                elif is_invite_switch:
                    print(f"[REFERRAL] {member.name} (switched invites) from {previous_inviter_data['user_id']} to {inviter_id}")
                else:
                    print(f"[REFERRAL] {member.name} (joined) via invite from {inviter_id}")
                
        except Exception as e:
            print(f"Error tracking member join: {e}")
    
    @commands.Cog.listener() 
    async def on_member_remove(self, member):
        """Track when a member leaves"""
        if member.guild.id != self.main_server_id:
            return
            
        try:
            # Find who invited this user
            referral_data = self.referral_collection.find_one(
                {"invited_users.user_id": member.id}
            )
            
            if referral_data:
                inviter_id = referral_data["user_id"]
                
                # Update referral statistics
                self.referral_collection.update_one(
                    {"user_id": inviter_id},
                    {
                        "$inc": {"left_users": 1, "current_invites": -1},
                        "$addToSet": {"left_user_ids": member.id}
                    }
                )
                
                print(f"[REFERRAL] {member.name} left, deducted from {inviter_id}'s current invites")
                
        except Exception as e:
            print(f"Error tracking member leave: {e}")
    
    async def get_stored_invites(self, guild_id):
        """Get stored invite data for comparison"""
        try:
            stored_data = self.db["invite_cache"].find_one({"guild_id": guild_id})
            return stored_data.get("invites", {}) if stored_data else {}
        except:
            return {}
    
    async def update_stored_invites(self, guild_id, current_invites):
        """Update stored invite data"""
        try:
            invite_data = {}
            for invite in current_invites:
                if invite.inviter:
                    invite_data[invite.code] = {
                        "uses": invite.uses,
                        "inviter_id": invite.inviter.id
                    }
            
            self.db["invite_cache"].update_one(
                {"guild_id": guild_id},
                {"$set": {"invites": invite_data}},
                upsert=True
            )
        except Exception as e:
            print(f"Error updating stored invites: {e}")

def setup(bot):
    bot.add_cog(ReferralsCog(bot))
