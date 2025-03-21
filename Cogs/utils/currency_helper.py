import discord
from Cogs.utils.mongo import Users
import datetime
from colorama import Fore, Back, Style
import json
from dotenv import load_dotenv
load_dotenv()

async def process_bet_amount(ctx, bet_amount, currency_type, loading_message=None, user=None):
    """
    Processes bet amounts intelligently based on user's balance and specified currency.

    Args:
        ctx: The command context
        bet_amount: The amount to bet (can be a number, string, "all", or "max")
        currency_type: Optional currency type ("tokens", "t", "credits", "c")
        loading_message: Optional message to update with bet information
        user: Optional user object to process bet for (defaults to ctx.author)

    Returns:
        tuple: (success, bet_info, error_embed)
            - success: Boolean indicating if bet processing was successful
            - bet_info: Dict with processed bet information (if successful)
            - error_embed: Error embed to return to user (if not successful)
    """
    author = ctx.author
    user = ctx.author if user is None else user
    db = Users()
    user_data = db.fetch_user(user.id)

    if not user_data:
        error_embed = discord.Embed(
            title="<:no:1344252518305234987> | Account Required",
            description=f"{user.mention} needs an account to place bets. Use a command to create one.",
            color=0xFF0000
        )
        return False, None, error_embed

    tokens_balance = user_data.get('tokens', 0)
    credits_balance = user_data.get('credits', 0)

    # Process bet amount and determine value
    try:
        # Handle all/max bet amount
        if isinstance(bet_amount, str) and bet_amount.lower() in ["all", "max"]:
            if currency_type:
                if currency_type.lower() in ["tokens", "t"]:
                    if tokens_balance <= 0:
                        error_embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Tokens",
                            description=f"{user.mention} doesn't have any tokens to bet.",
                            color=0xFF0000
                        )
                        return False, None, error_embed
                    bet_amount_value = tokens_balance
                    currency_specified = "tokens"
                elif currency_type.lower() in ["credits", "c"]:
                    if credits_balance <= 0:
                        error_embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Credits",
                            description=f"{user.mention} doesn't have any credits to bet.",
                            color=0xFF0000
                        )
                        return False, None, error_embed
                    bet_amount_value = credits_balance
                    currency_specified = "credits"
                else:
                    error_embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Currency",
                        description="Invalid currency type. Use 'tokens' or 'credits'.",
                        color=0xFF0000
                    )
                    return False, None, error_embed
            else:
                # If no currency specified with all/max, check if user has any balance
                if tokens_balance <= 0 and credits_balance <= 0:
                    error_embed = discord.Embed(
                        title="<:no:1344252518305234987> | Insufficient Balance",
                        description=f"{user.mention} doesn't have any tokens or credits to bet.",
                        color=0xFF0000
                    )
                    return False, None, error_embed

                # If no currency specified with all/max, use the currency with higher balance
                if tokens_balance >= credits_balance:
                    bet_amount_value = tokens_balance
                    currency_specified = "tokens"
                else:
                    bet_amount_value = credits_balance
                    currency_specified = "credits"
        else:
            # Handle numeric bet amount and k/m multipliers
            if isinstance(bet_amount, str):
                if bet_amount.lower().endswith('k'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000
                elif bet_amount.lower().endswith('m'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000000
                else:
                    bet_amount_value = float(bet_amount)
            else:
                bet_amount_value = float(bet_amount)

            bet_amount_value = round(bet_amount_value, 2)

            if bet_amount_value <= 0:
                error_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return False, None, error_embed

            # Determine currency if specified
            if currency_type:
                if currency_type.lower() in ["tokens", "t"]:
                    currency_specified = "tokens"
                elif currency_type.lower() in ["credits", "c"]:
                    currency_specified = "credits"
                else:
                    error_embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Currency",
                        description="Invalid currency type. Use 'tokens' or 'credits'.",
                        color=0xFF0000
                    )
                    return False, None, error_embed
            else:
                # Auto-determine which currency to use based on balances
                currency_specified = None
    except ValueError:
        error_embed = discord.Embed(
            title="<:no:1344252518305234987> | Invalid Amount",
            description="Please enter a valid number or 'all'.",
            color=0xFF0000
        )
        return False, None, error_embed

    # Now determine how to handle the bet based on currency and amount
    tokens_used = 0
    credits_used = 0

    # If user specified a currency, try to use that currency first
    if currency_specified == "tokens":
        if bet_amount_value <= tokens_balance:
            tokens_used = bet_amount_value
        else:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Tokens",
                description=f"{user.mention} doesn't have enough tokens. Your balance: **{tokens_balance:.2f} tokens**",
                color=0xFF0000
            )
            return False, None, error_embed
    elif currency_specified == "credits":
        if bet_amount_value <= credits_balance:
            credits_used = bet_amount_value
        else:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Credits",
                description=f"{user.mention} doesn't have enough credits. Your balance: **{credits_balance:.2f} credits**",
                color=0xFF0000
            )
            return False, None, error_embed
    else:
        # No currency specified - determine intelligently

        # Case 1: User has enough tokens
        if bet_amount_value <= tokens_balance:
            tokens_used = bet_amount_value

        # Case 2: User has enough credits
        elif bet_amount_value <= credits_balance:
            credits_used = bet_amount_value

        # Case 3: User doesn't have enough of either individually, but has enough combined
        elif bet_amount_value <= (tokens_balance + credits_balance):
            tokens_used = tokens_balance
            credits_used = bet_amount_value - tokens_balance

        # Case 4: User doesn't have enough combined
        else:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"{user.mention} doesn't have enough balance. They have **{tokens_balance:.2f} tokens** and **{credits_balance:.2f} credits**",
                color=0xFF0000
            )
            return False, None, error_embed

    # Apply the deductions to the user's balance
    if tokens_used > 0:
        db.update_balance(user.id, -tokens_used, "tokens", "$inc")

    if credits_used > 0:
        db.update_balance(user.id, -credits_used, "credits", "$inc")

    # Calculate and add XP (1 XP per token/credit wagered)
    xp_to_add = tokens_used + credits_used
    current_xp = user_data.get('xp', 0)
    current_level = user_data.get('level', 1)

    # Calculate XP limit for current level (10 for level 1, then 10% increase per level)
    xp_limit = 10 * (1 + (current_level - 1) * 0.1)
    xp_limit = round(xp_limit)

    # Calculate new XP and check if level up is needed
    new_xp = current_xp + xp_to_add
    new_level = current_level

    # Handle level progression
    while new_xp >= xp_limit:
        new_xp -= xp_limit
        new_level += 1
        # Recalculate XP limit for the new level
        xp_limit = 10 * (1 + (new_level - 1) * 0.1)
        xp_limit = round(xp_limit)

    # Update XP and level in database
    db.collection.update_one(
        {"discord_id": user.id},
        {"$set": {"xp": new_xp, "level": new_level}}
    )

    # Load rank data from JSON file
    with open('static_data/ranks.json', 'r') as f:
        rank_data = json.load(f)

    # Get current rank and check if user is eligible for a rank up
    current_rank = user_data.get('rank', 0)
    new_rank = current_rank
    rank_changed = False
    rank_name = "Bronze"  # Default rank name

    # Sort ranks by level requirement to find the highest applicable rank
    sorted_ranks = sorted(rank_data.items(), key=lambda x: x[1]['level_requirement'])
    for rank_name, rank_info in sorted_ranks:
        if new_level >= rank_info['level_requirement']:
            if current_rank != rank_info['level_requirement']:
                new_rank = rank_info['level_requirement']
                rank_changed = True

    # Find current rank name
    for name, info in rank_data.items():
        if info['level_requirement'] == current_rank:
            rank_name = name
            break

    # Calculate rakeback based on rank
    rakeback_percentage = 0.0
    for name, info in rank_data.items():
        if info['level_requirement'] == (new_rank if rank_changed else current_rank):
            rakeback_percentage = info['rakeback_percentage']
            rank_name = name
            break

    # Calculate rakeback tokens to be added
    total_bet = tokens_used + credits_used
    rakeback_amount = total_bet * (rakeback_percentage / 100)

    # Update user's rakeback_tokens in the database
    if rakeback_amount > 0:
        current_rakeback = user_data.get('rakeback_tokens', 0)
        db.collection.update_one(
            {"discord_id": user.id},
            {"$set": {"rakeback_tokens": current_rakeback + rakeback_amount}}
        )

    # Update user's rank if changed
    if rank_changed:
        db.collection.update_one(
            {"discord_id": user.id},
            {"$set": {"rank": new_rank}}
        )

    # Create a result dictionary with all relevant information
    bet_info = {
        "tokens_used": tokens_used,
        "credits_used": credits_used,
        "total_bet_amount": tokens_used + credits_used,
        "user_id": user.id,
        "remaining_tokens": tokens_balance - tokens_used,
        "remaining_credits": credits_balance - credits_used,
        "xp_gained": xp_to_add,
        "current_xp": new_xp,
        "current_level": new_level,
        "leveled_up": new_level > current_level,
        "rakeback_added": rakeback_amount,
        "current_rank": rank_name,
        "rank_changed": rank_changed
    }

    now = datetime.datetime.now()
    rn = now.strftime("%X")
    print(f"{Back.CYAN}  {Style.DIM}{user.id}{Style.RESET_ALL}{Back.RESET}{Fore.CYAN}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}{tokens_used + credits_used} ({round((tokens_used + credits_used)*0.0212, 3)}$){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}process_bet{Fore.WHITE}")

    # Add debug log for rakeback
    if rakeback_amount > 0:
        print(f"{Back.YELLOW}  {Style.DIM}{user.id}{Style.RESET_ALL}{Back.RESET}{Fore.YELLOW}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}+{rakeback_amount:.2f} ({rank_name} {rakeback_percentage}%){Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}rakeback{Fore.WHITE}")

    # Add debug log for rank change only if rank actually changed
    if rank_changed and new_rank != current_rank:
        print(f"{Back.MAGENTA}  {Style.DIM}{user.id}{Style.RESET_ALL}{Back.RESET}{Fore.MAGENTA}{Fore.WHITE}    {Fore.LIGHTWHITE_EX}{rn}{Fore.WHITE}    {Style.BRIGHT}{Fore.GREEN}RANK UP: {rank_name}{Fore.WHITE}{Style.RESET_ALL}  {Fore.MAGENTA}rank_change{Fore.WHITE}")

    # Update loading message if provided
    async def update_loading(content):
        if loading_message:
            try:
                await loading_message.edit(embed=discord.Embed(
                    title="Processing bet...",
                    description=content,
                    color=0x00FFAE
                ))
            except:
                pass

    await update_loading(f"{user.mention}'s Bet:  {f'**{tokens_used:.2f} tokens** and **{credits_used:.2f} credits**' if tokens_used > 0 and credits_used > 0 else f'**{tokens_used:.2f} tokens**' if tokens_used > 0 else f'**{credits_used:.2f} credits**'}")

    return True, bet_info, None