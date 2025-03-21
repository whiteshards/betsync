from pymongo import MongoClient
import os
import datetime
from colorama import Back, Fore, Style
from dotenv import load_dotenv
load_dotenv()

mongodb = MongoClient(os.environ["MONGO"])


class Users:

    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["users"]

    def get_all_users(self):
        return self.collection.find()

    def register_new_user(self, user_data):
        discordid = user_data["discord_id"]
        if self.collection.count_documents({"discord_id": discordid}):
            return False
        else:
            new_user = self.collection.insert_one(user_data)
            return new_user.inserted_id

    def fetch_user(self, user_id):
        if self.collection.count_documents({"discord_id": user_id}):
            return self.collection.find_one({"discord_id": user_id})

        else:
            return False

    def update_balance(self, user_id, amount, currency: str = "tokens", operation = "$set"):
        try:
            # Get user data before update to track the change
            user_before = self.fetch_user(user_id)
            if not user_before:
                return False

            previous_amount = user_before.get(currency, 0)

            # Update the balance
            self.collection.update_one({"discord_id": user_id}, {operation: {currency: amount}})

            # Get updated user data
            user_after = self.fetch_user(user_id)
            if not user_after:
                return False

            new_amount = user_after.get(currency, 0)

            # Determine if this was an increase or decrease
            change = 0
            if operation == "$set":
                change = new_amount - previous_amount
            elif operation == "$inc":
                change = amount

            # Send webhook notification
            import aiohttp
            import json
            import os
            import asyncio
            import discord
            from datetime import datetime

            webhook_url = os.environ.get("WEBHOOK")
            if webhook_url:
                # Get user object to fetch avatar if possible
                user = None
                try:
                    # Try to get the user from the bot's cache
                    if hasattr(self, 'bot'):
                        user = self.bot.get_user(user_id)
                except:
                    pass

                # Create a pretty embed
                embed = discord.Embed(
                    title=f"{'Balance Added' if change > 0 else 'Balance Deducted'}",
                    color=0x00FF00 if change > 0 else 0xFF0000,
                    timestamp=datetime.now(),
                    description=(
                        f"<:Veried_memeber_icon:1347561332043677706> <@{user_id}>\n"
                        f"<:member_hexagon:1347561410837876786> `{user_id}`\n\n"
                        f"{'<:star_token:1347561369901203499>' if currency == 'tokens' else '<:NA_CashIcon:1347561395083804702>'} **{currency.capitalize()}**\n"
                        f"Previous: **{previous_amount:.2f}**\n"
                        f"New: **{new_amount:.2f}**\n"
                        f"Change: **{'+' if change > 0 else ''}{change:.2f}**"
                    )
                )

                # Set thumbnail to user avatar if available
                if user and user.avatar:
                    embed.set_thumbnail(url=user.avatar.url)

                # Add footer
                embed.set_footer(text="BetSync Casino | Balance Update")

                # Send the webhook
                webhook_data = {
                    "embeds": [embed.to_dict()]
                }

                # Use asyncio to send the webhook in a non-blocking way
                async def send_webhook():
                    async with aiohttp.ClientSession() as session:
                        async with session.post(webhook_url, json=webhook_data) as response:
                            if response.status != 204:
                                print(f"Failed to send webhook: {response.status}")

                # Run the async function without blocking
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(send_webhook())
                    else:
                        loop.run_until_complete(send_webhook())
                except Exception as e:
                    print(f"Error sending webhook: {e}")

            return True
        except Exception as e:
            print(f"Error updating balance: {e}")
            return False

    def update_history(self, user_id, history_entry):
        """Add an entry to user's bet history with 100 entry limit"""
        try:
            self.collection.update_one(
                {"discord_id": user_id},
                {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
            )
            return True
        except Exception as e:
            print(f"Error updating user history: {e}")
            return False


class Servers:

    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["servers"]

    def get_total_all_servers(self):
        return self.collection.count_documents({})

    def new_server(self, dump):
        server_id = dump["server_id"]
        if self.collection.count_documents({"server_id": server_id}):
            return False
        else:
            new_server_ = self.collection.insert_one(dump) 
            return self.collection.find_one({"server_id": server_id})

    def update_server_profit(self, server_id, amount, game=None):
        """Update server profit statistics"""
        npc = self.db["net_profit"]
        profit_tracker = ProfitData()
        server_profit_tracker = ServerProfit()
        
        try:
            # Get server name
            server_info = self.collection.find_one({"server_id": server_id})
            server_name = server_info.get("server_name", f"Unknown Server ({server_id})")
            
            # Update server profit
            self.collection.update_one(
                {"server_id": server_id},
                {"$inc": {"total_profit": amount}}
            )

            # Update daily profit tracking
            profit_tracker.update_daily_profit(amount)
            
            # Update server-specific profit tracking
            server_profit_tracker.update_server_profit(server_id, server_name, amount)
            
            # Update net profit
            
            # Update game-specific profit
            if game:
                if npc.count_documents({"game": game}):
                    npc.update_one({"game": game}, {"$inc": {"total_profit": amount}})
                else: 
                    npc.insert_one({"game": game, "total_profit": amount})
                rn = datetime.datetime.now().strftime("%X")
                print(f"{Back.CYAN}  {Style.DIM}{server_id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}{amount} ({round((amount)*0.0212, 3)}$){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}{game}, sv_profit{Fore.WHITE}")
            return True
        except Exception as e:
            print(f"Error updating server profit: {e}")
            return False

    def get_np(self, game=None):
        if game:
            npc = self.db["net_profit"]
            return npc.find_one({"game": game})
        else:
            npc = self.db["net_profit"]
            return npc.find_one({})

    def update_history(self, server_id, history_entry):
        """Add an entry to server's bet history with 100 entry limit"""
        try:
            self.collection.update_one(
                {"server_id": server_id},
                {"$push": {"server_bet_history": {"$each": [history_entry], "$slice": -100}}}
            )
            return True
        except Exception as e:
            print(f"Error updating server history: {e}")
            return False

    def add_bet_to_history(self, server_id, history_entry):
        """Alias for update_history for backward compatibility"""
        return self.update_history(server_id, history_entry)

    def fetch_server(self, server_id):
        if self.collection.count_documents({"server_id": server_id}):
            return self.collection.find_one({"server_id": server_id})
        else:
            return False


class ServerProfit:
    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["server_profit"]
        
    def get_server_profit(self, server_id=None, date=None):
        """
        Get server profit data for a specific server, date, or all servers
        
        Args:
            server_id: Optional server ID to filter by
            date: Optional date to filter by (defaults to today)
            
        Returns:
            A single document or list of documents matching the criteria
        """
        # Default to today if no date specified
        if date is None:
            date = datetime.date.today().strftime("%Y-%m-%d")
        
        # If server_id is provided, return just that server's data
        if server_id:
            return self.collection.find_one({"server_id": server_id, "date": date})
        
        # Otherwise return all servers for the date
        return list(self.collection.find({"date": date}))
    
    def update_server_profit(self, server_id, server_name, amount):
        """
        Update server profit for today
        
        Args:
            server_id: The Discord server ID
            server_name: The name of the server
            amount: The profit amount to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get today's date
            today = datetime.date.today().strftime("%Y-%m-%d")
            
            # Use upsert to handle both new records and updates
            result = self.collection.update_one(
                {"server_id": server_id, "date": today},
                {
                    "$inc": {"profit": amount},
                    "$setOnInsert": {
                        "date": today,
                        "server_id": server_id,
                        "server_name": server_name
                    }
                },
                upsert=True
            )
            
            rn = datetime.datetime.now().strftime("%X")
            print(f"{Back.CYAN}  {Style.DIM}{server_id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}{amount} ({round((amount)*0.0212, 3)}$){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}sv_profit_record{Fore.WHITE}")
            
            return True
        except Exception as e:
            print(f"Error updating server profit: {e}")
            return False
    
    def get_all_server_profits(self, date=None):
        """Get profit data for all servers on a specific date"""
        if date is None:
            date = datetime.date.today().strftime("%Y-%m-%d")
            
        return list(self.collection.find({"date": date}))


class ProfitData:
    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["profit_data"]

    def update_daily_profit(self, amount, game=None):
        # Convert datetime.date to string format (YYYY-MM-DD)
        today = datetime.date.today().strftime("%Y-%m-%d")
        try:
            # Use upsert to handle both document creation and updating
            # This creates the document if it doesn't exist, or updates it if it does
            # The setOnInsert ensures we set initial values only if creating a new document
            result = self.collection.update_one(
                {"date": today},
                {
                    "$inc": {"total_profit": amount},
                    "$setOnInsert": {
                        "date": today,
                        "games": {}  # Initialize games object if needed
                    }
                },
                upsert=True  # Create document if it doesn't exist
            )
            
            # If game is specified, update game-specific profit
            if game:
                # Use dot notation to safely update nested fields
                game_field = f"games.{game}"
                self.collection.update_one(
                    {"date": today},
                    {
                        "$inc": {game_field: amount}
                    },
                    upsert=True
                )
            
            return True
        except Exception as e:
            print(f"Error updating daily profit: {e}")
            print(f"Details: {str(e)}")  # More detailed error logging
            return False

    def get_profit_data(self, date=None):
        if date:
            # Convert date to string if it's a datetime object
            if isinstance(date, (datetime.date, datetime.datetime)):
                date = date.strftime("%Y-%m-%d")
            return self.collection.find_one({"date": date})
        else:
            return list(self.collection.find())