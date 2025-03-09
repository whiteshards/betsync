import random
from collections import defaultdict

# Game difficulties: (hit_chance, multiplier_increment)
DIFFICULTIES = {
    "easy": (0.16, 1.10),
    "medium": (0.25, 1.30),
    "hard": (0.37, 1.50),
    "extreme": (0.47, 1.70)
}

STRATEGIES = {
    "Exit Early": 5,    # Cash out after 5 lanes
    "Exit Middle": 12,  # Cash out after 12 lanes
    "Go All the Way": 25  # Continue until hit or reach 25 lanes
}

NUM_SIMULATIONS = 1000  # Reduced for demonstration; increase as needed
MAX_LANES = 25
BET_AMOUNT = 1.0

def simulate_game(hit_chance, increment, target_lanes, strategy_name):
    """
    Simulate a single game based on the strategy.
    Returns (payout, lanes_crossed).
    """
    current_multiplier = 1.0
    lanes_crossed = 0
    
    # For "Go All the Way", keep going until hit or max lanes
    max_attempts = MAX_LANES if strategy_name == "Go All the Way" else target_lanes
    
    for lane in range(max_attempts):
        if random.random() < hit_chance:
            # Hit a car, game over
            return (0.0, lanes_crossed)
        # Successfully crossed the lane
        current_multiplier *= increment
        lanes_crossed += 1
        
        # Check cashout condition
        if strategy_name != "Go All the Way" and lanes_crossed == target_lanes:
            return (round(current_multiplier * BET_AMOUNT, 2), lanes_crossed)
        elif strategy_name == "Go All the Way" and lanes_crossed == MAX_LANES:
            return (round(current_multiplier * BET_AMOUNT, 2), lanes_crossed)
    
    # Should only reach here for "Go All the Way" if max lanes hit
    return (round(current_multiplier * BET_AMOUNT, 2), lanes_crossed)

def run_simulations():
    results = {}
    
    for difficulty, (hit_chance, increment) in DIFFICULTIES.items():
        results[difficulty] = {}
        for strategy_name, target_lanes in STRATEGIES.items():
            total_payout = 0.0
            simulation_outcomes = []
            
            for sim in range(NUM_SIMULATIONS):
                payout, lanes = simulate_game(hit_chance, increment, target_lanes, strategy_name)
                simulation_outcomes.append((payout, lanes))
                total_payout += payout
            
            # Store results
            results[difficulty][strategy_name] = {
                "outcomes": simulation_outcomes,
                "total_payout": total_payout,
                "average_payout": total_payout / NUM_SIMULATIONS,
                "house_edge": 1.0 - (total_payout / NUM_SIMULATIONS)
            }
    
    return results

def display_results(results):
    for difficulty in results:
        print(f"\nDifficulty: {difficulty.capitalize()}")
        print("-" * 40)
        for strategy in results[difficulty]:
            data = results[difficulty][strategy]
            print(f"Strategy: {strategy}")
            # Show a sample of individual outcomes (first 5 for brevity)
            print("Sample Outcomes (payout, lanes crossed):")
            for i, (payout, lanes) in enumerate(data["outcomes"][:5], 1):
                print(f"  Game {i}: Payout = {payout}, Lanes = {lanes}")
            print(f"Total Payout over {NUM_SIMULATIONS} games: {data['total_payout']:.2f}")
            print(f"Average Payout: {data['average_payout']:.2f}")
            house_edge_pct = data['house_edge'] * 100
            print(f"House Edge: {house_edge_pct:.2f}%")
            print("-" * 40)

# Run and display
if __name__ == "__main__":
    simulation_results = run_simulations()
    display_results(simulation_results)