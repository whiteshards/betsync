import random
import numpy as np

# Payout table taken from your second PAYOUTS definition
payouts = {
    1: {1: 3.72},
    2: {1: 1, 2: 10},
    3: {1: 0.5, 2: 1.5, 3: 25},
    4: {1: 0.0, 2: 1.35, 3: 10.0, 4: 100},
    5: {1: 0.0, 2: 0.0, 3: 3, 4: 50.0, 5: 100.0},
    6: {1: 0.0, 2: 0.5, 3: 3.0, 4: 12.0, 5: 300.0},
    7: {1: 0.0, 2: 0.0, 3: 2.0, 4: 8.0, 5: 100.0},
    8: {1: 0.0, 2: 0.0, 3: 1.5, 4: 5.0, 5: 50.0},
    9: {1: 0.0, 2: 0.0, 3: 1.0, 4: 3.0, 5: 30.0},
    10: {1: 0.0, 2: 0.0, 3: 0.5, 4: 2.0, 5: 20.0}
}

def simulate_keno(selection_count, iterations=10000, bet=1):
    """
    Simulate the Keno game for a given number of selections.
    
    For each simulation:
      - Randomly choose 'selection_count' distinct numbers from 1 to 20.
      - Randomly draw 5 winning numbers (without replacement) from 1 to 20.
      - Count the number of matches.
      - Look up the multiplier using the payout table.
      - Compute winnings as bet * multiplier.
    
    Returns a dictionary of statistics:
      - Average return per bet
      - House edge (1 - average return)
      - Win rate (fraction of bets with a nonzero payout)
      - Standard deviation of winnings
      - Frequency distribution of match counts.
    """
    total_winnings = 0
    winnings_list = []
    # Possible matches range from 0 up to the number of selections (though the game draws only 5 numbers)
    match_frequency = {i: 0 for i in range(selection_count + 1)}
    win_count = 0
    
    for _ in range(iterations):
        player_nums = random.sample(range(1, 21), selection_count)
        winning_nums = random.sample(range(1, 21), 5)
        matches = len(set(player_nums) & set(winning_nums))
        multiplier = payouts.get(selection_count, {}).get(matches, 0)
        win_amount = bet * multiplier
        total_winnings += win_amount
        winnings_list.append(win_amount)
        match_frequency[matches] += 1
        if win_amount > 0:
            win_count += 1
    
    avg_return = total_winnings / iterations   # average payout for a bet of 1 unit
    house_edge = 1 - avg_return                  # house edge as a fraction of the bet
    win_rate = win_count / iterations
    std_dev = np.std(winnings_list)
    
    return {
        "selection_count": selection_count,
        "iterations": iterations,
        "total_winnings": total_winnings,
        "avg_return": avg_return,
        "house_edge": house_edge,
        "win_rate": win_rate,
        "std_dev": std_dev,
        "match_frequency": match_frequency
    }

# Run simulations for each selection count from 1 to 10
results = {}
for n in range(1, 11):
    results[n] = simulate_keno(n, iterations=10000, bet=1)

# Print results
for n in range(1, 11):
    res = results[n]
    print(f"Selection Count: {res['selection_count']}")
    print(f"Iterations: {res['iterations']}")
    print(f"Total Winnings: {res['total_winnings']:.2f}")
    print(f"Average Return per Bet: {res['avg_return']:.4f}")
    print(f"House Edge: {res['house_edge']*100:.2f}%")
    print(f"Win Rate: {res['win_rate']*100:.2f}%")
    print(f"Std Dev of Winnings: {res['std_dev']:.4f}")
    print("Match Frequency:")
    for matches, freq in sorted(res["match_frequency"].items()):
        print(f"  {matches} match(es): {freq} times")
    print("-"*50)
    