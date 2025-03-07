import random
from collections import Counter
from itertools import combinations

# Define the paytable with multipliers for each hand type
paytable = {
    "Royal Flush": 1000,
    "Straight Flush": 200,
    "Four of a Kind": 60,
    "Full House": 25,
    "Flush": 20,
    "Straight": 15,
    "Three of a Kind": 9,
    "Two Pair": 4,
    "One Pair": 1,
    "High Card": 0
}

# Function to check if ranks form a straight
def is_straight(ranks):
    sorted_ranks = sorted(ranks)
    if len(set(sorted_ranks)) != 5:  # Ensure all ranks are unique
        return False
    if max(sorted_ranks) - min(sorted_ranks) == 4:  # Consecutive ranks (e.g., 5,6,7,8,9)
        return True
    if sorted_ranks == [0, 1, 2, 3, 12]:  # Special case: A,2,3,4,5 (ranks 12,0,1,2,3)
        return True
    return False

# Function to evaluate a hand and return its type
def evaluate_hand(hand):
    ranks = [card[0] for card in hand]
    suits = [card[1] for card in hand]
    rank_counts = Counter(ranks)
    suit_counts = Counter(suits)
    sorted_ranks = sorted(ranks)
    is_flush = len(suit_counts) == 1
    is_straight_hand = is_straight(ranks)
    
    if is_flush and sorted_ranks == [8, 9, 10, 11, 12]:  # 10,J,Q,K,A same suit
        return "Royal Flush"
    elif is_flush and is_straight_hand:
        return "Straight Flush"
    elif 4 in rank_counts.values():
        return "Four of a Kind"
    elif 3 in rank_counts.values() and 2 in rank_counts.values():
        return "Full House"
    elif is_flush:
        return "Flush"
    elif is_straight_hand:
        return "Straight"
    elif 3 in rank_counts.values():
        return "Three of a Kind"
    elif list(rank_counts.values()).count(2) == 2:
        return "Two Pair"
    elif 2 in rank_counts.values():
        return "One Pair"
    else:
        return "High Card"

# Strategy 1: Risky Holder - Always discards all cards
def risky_holder(hand):
    return []  # Hold no cards

# Strategy 2: Medium - Holds based on potential winning hands
def medium(hand):
    hand_type = evaluate_hand(hand)
    if hand_type in ["Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush", "Royal Flush"]:
        return [0, 1, 2, 3, 4]  # Hold all for strong hands
    rank_counts = Counter([card[0] for card in hand])
    
    # Hold three of a kind
    for rank, count in rank_counts.items():
        if count == 3:
            return [i for i, card in enumerate(hand) if card[0] == rank]
    
    # Hold two pairs
    pairs = [rank for rank, count in rank_counts.items() if count == 2]
    if len(pairs) == 2:
        return [i for i, card in enumerate(hand) if card[0] in pairs]
    
    # Hold one pair
    if len(pairs) == 1:
        return [i for i, card in enumerate(hand) if card[0] == pairs[0]]
    
    # Hold four to a flush
    suit_counts = Counter([card[1] for card in hand])
    for suit, count in suit_counts.items():
        if count >= 4:
            return [i for i, card in enumerate(hand) if card[1] == suit]
    
    # Hold four to a straight
    straight_sets = [set(range(i, i + 5)) for i in range(9)] + [set([12, 0, 1, 2, 3])]
    for comb in combinations(range(5), 4):
        four_ranks = set(hand[i][0] for i in comb)
        if any(len(four_ranks & straight_set) == 4 for straight_set in straight_sets):
            return list(comb)
    
    return []  # Discard all if no promising combination

# Strategy 3: Safe - Holds paying hands or two highest cards
def safe(hand):
    hand_type = evaluate_hand(hand)
    if hand_type in ["One Pair", "Two Pair", "Three of a Kind", "Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush", "Royal Flush"]:
        if hand_type == "One Pair":
            rank_counts = Counter([card[0] for card in hand])
            pair_rank = [rank for rank, count in rank_counts.items() if count == 2][0]
            return [i for i, card in enumerate(hand) if card[0] == pair_rank]
        elif hand_type == "Two Pair":
            rank_counts = Counter([card[0] for card in hand])
            pair_ranks = [rank for rank, count in rank_counts.items() if count == 2]
            return [i for i, card in enumerate(hand) if card[0] in pair_ranks]
        elif hand_type == "Three of a Kind":
            rank_counts = Counter([card[0] for card in hand])
            three_rank = [rank for rank, count in rank_counts.items() if count == 3][0]
            return [i for i, card in enumerate(hand) if card[0] == three_rank]
        else:
            return [0, 1, 2, 3, 4]  # Hold all for Straight or better
    else:
        # Hold two highest cards
        sorted_indices = sorted(range(5), key=lambda i: hand[i][0], reverse=True)
        return sorted_indices[:2]

# Function to simulate one game with a given strategy
def simulate_game(strategy_func):
    # Create and shuffle deck (ranks 0-12: 2-A, suits 0-3: spades, hearts, diamonds, clubs)
    deck = [(rank, suit) for suit in range(4) for rank in range(13)]
    random.shuffle(deck)
    hand = deck[:5]
    remaining_deck = deck[5:]
    
    # Decide which cards to hold
    hold_indices = strategy_func(hand)
    num_to_replace = 5 - len(hold_indices)
    new_cards = remaining_deck[:num_to_replace]
    
    # Form final hand
    final_hand = [hand[i] if i in hold_indices else new_cards.pop(0) for i in range(5)]
    
    # Evaluate and return payout
    hand_type = evaluate_hand(final_hand)
    return paytable[hand_type]

# Function to run simulations and calculate metrics
def run_simulations(strategy_func, strategy_name, num_simulations=100000):
    total_payout = 0
    for _ in range(num_simulations):
        payout = simulate_game(strategy_func)
        total_payout += payout
    average_multiplier = total_payout / num_simulations
    house_edge = 1 - average_multiplier
    print(f"{strategy_name}:")
    print(f"  Average Multiplier: {average_multiplier:.4f}")
    print(f"  House Edge: {house_edge:.4f}")
    print()
    return average_multiplier, house_edge

# Run simulations for all strategies
print("Simulation Results (100,000 games per strategy, $1 bet):")
print("-----------------------------------------------------")
strategies = [
    ("Risky Holder", risky_holder),
    ("Medium", medium),
    ("Safe", safe)
]
results = {}
for name, func in strategies:
    avg_mult, h_edge = run_simulations(func, name)
    results[name] = (avg_mult, h_edge)