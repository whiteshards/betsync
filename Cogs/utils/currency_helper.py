import discord
from Cogs.utils.mongo import Users

async def process_bet_amount(ctx, bet_amount, currency_type=None, loading_message=None, user=None):
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
    target_user = user if user else ctx.author
    db = Users()
    user_data = db.fetch_user(target_user.id)

    if not user_data:
        error_embed = discord.Embed(
            title="<:no:1344252518305234987> | Account Required",
            description=f"{target_user.mention} needs an account to place bets. Use a command to create one.",
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
                    bet_amount_value = tokens_balance
                    currency_specified = "tokens"
                elif currency_type.lower() in ["credits", "c"]:
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
                description=f"{target_user.mention} doesn't have enough tokens. Your balance: **{tokens_balance:.2f} tokens**",
                color=0xFF0000
            )
            return False, None, error_embed
    elif currency_specified == "credits":
        if bet_amount_value <= credits_balance:
            credits_used = bet_amount_value
        else:
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Credits",
                description=f"{target_user.mention} doesn't have enough credits. Your balance: **{credits_balance:.2f} credits**",
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
                description=f"{target_user.mention} doesn't have enough balance. They have **{tokens_balance:.2f} tokens** and **{credits_balance:.2f} credits**",
                color=0xFF0000
            )
            return False, None, error_embed

    # Apply the deductions to the user's balance
    if tokens_used > 0:
        db.update_balance(target_user.id, -tokens_used, "tokens", "$inc")

    if credits_used > 0:
        db.update_balance(target_user.id, -credits_used, "credits", "$inc")

    # Create a result dictionary with all relevant information
    bet_info = {
        "tokens_used": tokens_used,
        "credits_used": credits_used,
        "total_bet_amount": tokens_used + credits_used,
        "user_id": target_user.id,
        "remaining_tokens": tokens_balance - tokens_used,
        "remaining_credits": credits_balance - credits_used
    }

    # Update loading message if provided
    if loading_message:
        currency_text = ""
        if tokens_used > 0 and credits_used > 0:
            currency_text = f"**{tokens_used:.2f} tokens** and **{credits_used:.2f} credits**"
        elif tokens_used > 0:
            currency_text = f"**{tokens_used:.2f} tokens**"
        else:
            currency_text = f"**{credits_used:.2f} credits**"

        loading_embed = loading_message.embeds[0]
        loading_embed.description = f"{target_user.mention}'s Bet: {currency_text}"
        await loading_message.edit(embed=loading_embed)

    return True, bet_info, None