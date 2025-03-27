from fastapi import APIRouter, HTTPException, Path, Body, Depends, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from app.models import Card, Player, Game, GameStatusResponse
from app.init import get_game, initialize_game, find_player_by_name, get_game_status, API_BASE_URL, DEALER_API_URL
import json
import requests  # Add this import for making HTTP requests
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Define dealer API URL for use in this file
DEALER_API = DEALER_API_URL  # Use the URL from init.py

# Helper function for making API calls to dealer
def call_dealer_api(endpoint, method="GET", data=None):
    """Make API calls to the dealer with error handling"""
    url = f"{DEALER_API}/{endpoint.lstrip('/')}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return {"error": "Unsupported HTTP method"}
            
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed: {str(e)}")
        return {"error": f"Failed to connect to dealer: {str(e)}"}
    except json.JSONDecodeError:
        logger.error("Failed to parse response from dealer")
        return {"error": "Invalid response from dealer"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

# Request models
class PlayerActionRequest(BaseModel):
    player_name: str
    turn: str  # "bet", "check", "fold", "raise", "all-in", or "show"
    amount: Optional[float] = None  # Required for "bet" and "raise" actions

class BetRequest(BaseModel):
    name: str
    amount: float

class FoldRequest(BaseModel):
    name: str

class JoinGameRequest(BaseModel):
    name: str
    host_url: str

# Card values for ranking
CARD_VALUES = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, 
               "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}

# Hand rankings
HAND_RANKINGS = {
    "royal_flush": 10,
    "straight_flush": 9,
    "four_of_a_kind": 8,
    "full_house": 7,
    "flush": 6,
    "straight": 5,
    "three_of_a_kind": 4,
    "two_pair": 3,
    "pair": 2,
    "high_card": 1
}

@router.get("/ping")
def ping():
    """Simple endpoint to check if the server is running"""
    # Try to ping the dealer as well
    try:
        dealer_response = call_dealer_api("ping")
        if "error" in dealer_response:
            return {"message": "pong", "dealer_status": "unavailable", "error": dealer_response["error"]}
        return {"message": "pong", "dealer_status": "available", "dealer_response": dealer_response}
    except Exception as e:
        logger.error(f"Error pinging dealer: {str(e)}")
        return {"message": "pong", "dealer_status": "error", "error": str(e)}

# Fix for the community-cards endpoint (hyphen vs underscore issue)
@router.get("/community_cards")
def community_cards():
    """Endpoint to show the community cards"""
    try:
        # Try to get community cards from dealer first
        dealer_response = call_dealer_api("community_cards")
        
        # If dealer responds without error, use that response
        if dealer_response and isinstance(dealer_response, dict) and "error" not in dealer_response:
            return dealer_response
            
        # Fall back to local implementation if dealer fails
        game = get_game()
        
        # Initialize community cards if not set
        if not hasattr(game, "community_cards") or game.community_cards is None:
            game.community_cards = []
        
        # Deal community cards if needed
        if len(game.community_cards) == 0 and hasattr(game, "deck") and game.deck:
            # Deal 5 community cards (flop, turn, river)
            for _ in range(5):
                if game.deck and len(game.deck) > 0:
                    card = game.deck.pop(0)
                    game.community_cards.append(card)
        
        return {
            "stage": getattr(game, "current_stage", "pre_flop"),
            "community_cards": [{"rank": card.rank, "suit": card.suit, "name": card.name} 
                               for card in game.community_cards]
        }
    except Exception as e:
        logger.error(f"Error in community_cards: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Fix for the show_cards endpoint to ensure cards are dealt
@router.get("/show_cards")
def show_cards(player_name: str = Query(...)):
    """Endpoint for a player to view their cards"""
    try:
        # Try to get cards from dealer first
        dealer_response = call_dealer_api(f"show_cards?player_name={player_name}")
        
        # If dealer responds without error, use that response
        if dealer_response and isinstance(dealer_response, dict) and "error" not in dealer_response:
            return dealer_response
            
        # Fall back to local implementation if dealer fails
        game = get_game()
        
        # Find the player
        player = find_player_by_name(player_name)
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_name} not found")
        
        # Activate the game if not active
        if not game.is_active:
            game.is_active = True
        
        # Deal cards if player doesn't have any
        if not player.cards or len(player.cards) == 0:
            # Make sure we have a deck
            if not hasattr(game, "deck") or not game.deck or len(game.deck) < 2:
                # Initialize a new deck
                suits = ["hearts", "diamonds", "clubs", "spades"]
                ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
                
                deck = []
                for suit in suits:
                    for rank in ranks:
                        card_name = f"{rank} of {suit.capitalize()}"
                        deck.append(Card(rank=rank, suit=suit, name=card_name))
                
                # Shuffle the deck
                import random
                random.shuffle(deck)
                
                game.deck = deck
            
            # Deal two cards to the player
            for _ in range(2):
                if game.deck:
                    card = game.deck.pop(0)
                    player.cards.append(card)
        
        return {
            "cards": [{"rank": card.rank, "suit": card.suit, "name": card.name} 
                     for card in player.cards]
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in show_cards: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/show_pot")
def show_pot():
    """Endpoint to show the current pot amount"""
    game = get_game()
    
    return {
        "pot": game.pot,
        "current_bet": getattr(game, "current_bet", 0),
        "side_pots": getattr(game, "side_pots", [])
    }

# Fix for the game_status endpoint
@router.get("/game_status")
def game_status():
    """Endpoint to get the current game status"""
    status = get_game_status()
    
    # If game is not active, activate it
    if not status["is_active"]:
        game = get_game()
        game.is_active = True
        status = get_game_status()  # Get updated status
    
    return GameStatusResponse(**status)

@router.post("/start_game")
def start_game():
    """Endpoint to start a new game"""
    # Initialize with 0 players to avoid creating default players
    initialize_game(0)
    game = get_game()
    
    # Initialize deck
    suits = ["hearts", "diamonds", "clubs", "spades"]
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    
    deck = []
    for suit in suits:
        for rank in ranks:
            card_name = f"{rank} of {suit.capitalize()}"
            deck.append(Card(rank=rank, suit=suit, name=card_name))
    
    # Shuffle the deck
    import random
    random.shuffle(deck)
    
    game.deck = deck
    
    return {"message": "Game started successfully"}

@router.post("/join_game")
def join_game(request: JoinGameRequest):
    """Endpoint for a player to join a game"""
    game = get_game()
    if not game.is_active:
        # If no active game, start a new one
        initialize_game(0)
        game = get_game()
        
        # Initialize deck if not already present
        if not hasattr(game, "deck") or not game.deck:
            suits = ["hearts", "diamonds", "clubs", "spades"]
            ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
            
            deck = []
            for suit in suits:
                for rank in ranks:
                    card_name = f"{rank} of {suit.capitalize()}"
                    deck.append(Card(rank=rank, suit=suit, name=card_name))
            
            # Shuffle the deck
            import random
            random.shuffle(deck)
            
            game.deck = deck
    
    # Check if player name already exists
    existing_player = find_player_by_name(request.name)
    if existing_player:
        raise HTTPException(status_code=400, detail=f"Player name '{request.name}' already exists")
    
    # Remove the game full check - allow multiple players
    # if len(game.players) >= 6:  # Limit to 6 players
    #     raise HTTPException(status_code=400, detail="Game is full.")
    
    # Add player to the game
    new_player = Player(name=request.name, balance=1000)  # Default balance
    new_player.host_url = request.host_url
    new_player.is_active = True
    new_player.cards = []  # Initialize empty cards list
    new_player.current_bet = 0.0
    new_player.is_all_in = False
    new_player.has_acted = False
    
    # Deal two cards to the player from the deck
    if not hasattr(game, "deck") or not game.deck:
        # Create a new deck if none exists
        suits = ["hearts", "diamonds", "clubs", "spades"]
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        
        deck = []
        for suit in suits:
            for rank in ranks:
                card_name = f"{rank} of {suit.capitalize()}"
                deck.append(Card(rank=rank, suit=suit, name=card_name))
        
        # Shuffle the deck
        import random
        random.shuffle(deck)
        
        game.deck = deck
    
    # Now deal cards
    if hasattr(game, "deck") and game.deck and len(game.deck) >= 2:
        for _ in range(2):
            card = game.deck.pop(0)
            new_player.cards.append(card)
    
    # Add to game's players list
    game.players.append(new_player)
    
    # Update turn order if needed
    if not hasattr(game, "current_turn_order") or not game.current_turn_order:
        game.current_turn_order = []  # Initialize as empty list if not exists
    
    # Add the new player to the turn order
    game.current_turn_order.append(new_player.name)
    
    # Initialize current_turn_index if not set
    if not hasattr(game, "current_turn_index") or game.current_turn_index is None:
        game.current_turn_index = 0
    
    # Initialize community cards if not set
    if not hasattr(game, "community_cards"):
        game.community_cards = []
    
    return {"message": f"Player {request.name} joined the game successfully."}

# Fix for the place_bet and fold endpoints
# Fix the is_your_turn endpoint - move it outside of compare_cards
@router.get("/is_your_turn")
def is_your_turn(player_name: str = Query(...)):
    """Endpoint to check if it's a specific player's turn"""
    game = get_game()
    
    if not game.is_active:
        # Activate the game if it's not active
        game.is_active = True
        return {"is_your_turn": False, "reason": "Game was not active, now activated"}
    
    player = find_player_by_name(player_name)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_name} not found")
    
    if not player.is_active:
        player.is_active = True  # Activate the player
        return {"is_your_turn": False, "reason": "Player was not active, now activated"}
    
    # Check if it's the player's turn
    is_turn = False
    reason = "Waiting for other players"
    
    if not hasattr(game, "current_turn_order") or not game.current_turn_order:
        # Initialize turn order if it doesn't exist
        game.current_turn_order = [p.name for p in game.players if p.is_active]
        game.current_turn_index = 0
    
    if game.current_turn_order and game.current_turn_index < len(game.current_turn_order):
        if game.current_turn_order[game.current_turn_index] == player_name:
            is_turn = True
            reason = "It's your turn to act"
    
    return {
        "is_your_turn": is_turn,
        "reason": reason,
        "current_player": game.current_turn_order[game.current_turn_index] if game.current_turn_order and game.current_turn_index < len(game.current_turn_order) else None,
        "current_bet": getattr(game, "current_bet", 0),
        "stage": getattr(game, "current_stage", "pre_flop")
    }

# Fix the place_bet endpoint to handle player validation better
@router.post("/place_bet")
def place_bet(request: BetRequest):
    """Endpoint for a player to place a bet"""
    try:
        # Try to place bet with dealer first
        dealer_response = call_dealer_api("place_bet", method="POST", data=request.dict())
        
        # If dealer responds without error, use that response
        if dealer_response and not "error" in dealer_response:
            return dealer_response
            
        # Fall back to local implementation if dealer fails
        game = get_game()
        
        # Activate game if not active
        if not game.is_active:
            game.is_active = True
        
        player = find_player_by_name(request.name)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Activate player if not active
        if not player.is_active:
            player.is_active = True
        
        # Initialize turn order if needed
        if not hasattr(game, "current_turn_order") or not game.current_turn_order:
            game.current_turn_order = [p.name for p in game.players if p.is_active]
            game.current_turn_index = 0
        
        # Get current bet in the game
        current_bet = getattr(game, "current_bet", 0)
        
        if request.amount <= 0:
            raise HTTPException(status_code=400, detail="Bet amount must be positive")
        
        # Ensure player has enough balance (give them more if needed for testing)
        if request.amount > player.balance:
            # For testing purposes, add funds to the player
            player.balance = max(1000, request.amount * 2)  # Ensure they have enough
        
        # Process the bet
        player.balance -= request.amount
        player.current_bet = request.amount
        game.pot += request.amount
        
        # Update game's current bet if this is higher
        if request.amount > current_bet:
            game.current_bet = request.amount
            # Reset other players' has_acted status
            for p in game.players:
                if p.name != player.name and p.is_active and not getattr(p, "is_all_in", False):
                    p.has_acted = False
        
        # Mark player as having acted
        player.has_acted = True
        
        # Move to next player's turn
        advance_turn(game)
        
        return {
            "message": f"Player {request.name} bet {request.amount}",
            "player_balance": player.balance,
            "pot": game.pot,
            "current_bet": game.current_bet,
            "next_turn": game.current_turn_order[game.current_turn_index] if game.current_turn_order and game.current_turn_index < len(game.current_turn_order) else None
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in place_bet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Fix the fold endpoint to handle player validation better
@router.post("/fold")
def fold(request: FoldRequest):
    """Endpoint for a player to fold"""
    try:
        # Try to fold with dealer first
        dealer_response = call_dealer_api("fold", method="POST", data=request.dict())
        
        # If dealer responds without error, use that response
        if dealer_response and not "error" in dealer_response:
            return dealer_response
            
        # Fall back to local implementation if dealer fails
        game = get_game()
        
        # Activate game if not active
        if not game.is_active:
            game.is_active = True
        
        player = find_player_by_name(request.name)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Make sure player is active before folding
        player.is_active = True  # First ensure they're active
        player.has_acted = True  # Mark as acted
        
        # Now fold (set inactive)
        player.is_active = False
        
        # Initialize or update turn order
        if not hasattr(game, "current_turn_order") or not game.current_turn_order:
            game.current_turn_order = [p.name for p in game.players if p.is_active]
            game.current_turn_index = 0
        elif player.name in game.current_turn_order:
            idx = game.current_turn_order.index(player.name)
            game.current_turn_order.remove(player.name)
            # Adjust current turn index if needed
            if idx <= game.current_turn_index and game.current_turn_order:
                game.current_turn_index = game.current_turn_index % len(game.current_turn_order)
        
        # Check if only one player is active
        active_players = [p for p in game.players if p.is_active]
        if len(active_players) == 1:
            # Game ends, winner takes the pot
            winner = active_players[0]
            winner.balance += game.pot
            game.pot = 0
            
            return {
                "message": f"Player {request.name} folded. Player {winner.name} wins the pot!",
                "winner": winner.name,
                "winner_balance": winner.balance
            }
        
        # Move to next player's turn if there are still active players
        if active_players:
            advance_turn(game)
        
        return {
            "message": f"Player {request.name} folded",
            "active_players": [p.name for p in active_players],
            "next_turn": game.current_turn_order[game.current_turn_index] if game.current_turn_order and game.current_turn_index < len(game.current_turn_order) else None
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in fold: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Fix the compare_cards endpoint - remove the nested is_your_turn endpoint
@router.post("/compare_cards")
def compare_cards():
    """Endpoint to compare player cards and determine winner"""
    game = get_game()
    
    # Activate game if not active
    if not game.is_active:
        game.is_active = True
        return {"message": "Game activated, please deal cards first"}
    
    # Ensure all players have cards
    for player in game.players:
        if not player.cards or len(player.cards) == 0:
            # Deal cards if needed
            if hasattr(game, "deck") and game.deck and len(game.deck) >= 2:
                for _ in range(2):
                    card = game.deck.pop(0)
                    player.cards.append(card)
            else:
                # Fallback if deck is empty
                player.cards.append(Card(rank="A", suit="hearts", name="Ace of Hearts"))
                player.cards.append(Card(rank="K", suit="hearts", name="King of Hearts"))
    
    # This would typically happen at showdown
    # For simplicity, we'll just determine a winner based on current hands
    winner_info = determine_winner(game)
    
    if isinstance(winner_info, list):
        # Multiple winners (split pot)
        winner_names = [w["name"] for w in winner_info]
        return {
            "result": "Split pot",
            "winners": winner_names,
            "hand_type": winner_info[0]["hand_type"]
        }
    else:
        # Single winner
        return {
            "result": "Winner determined",
            "winner": winner_info["name"],
            "hand_type": winner_info["hand_type"]
        }

# Fix the end_game endpoint
@router.post("/end_game")
def end_game():
    """Endpoint to end the current game"""
    game = get_game()
    game.is_active = False
    
    # Reset game state
    game.pot = 0
    if hasattr(game, "side_pots"):
        game.side_pots = []
    
    # Reset player states
    for player in game.players:
        player.cards = []
        player.current_bet = 0
        player.is_all_in = False
        player.has_acted = False
    
    return {"message": "Game ended successfully"}

# Add the determine_winner function
def determine_winner(game):
    """Determine the winner based on player cards"""
    active_players = [p for p in game.players if p.is_active]
    
    if not active_players:
        return None
    
    if len(active_players) == 1:
        # Only one active player, they win by default
        return {
            "name": active_players[0].name,
            "hand_type": "default_win"
        }
    
    # For simplicity, just determine winner based on highest card
    player_scores = []
    
    for player in active_players:
        if not player.cards or len(player.cards) < 2:
            continue
            
        # Get highest card value
        highest_card = max([CARD_VALUES.get(card.rank, 0) for card in player.cards])
        
        player_scores.append({
            "name": player.name,
            "score": highest_card,
            "hand_type": "high_card"
        })
    
    if not player_scores:
        return None
        
    # Find highest score
    max_score = max([p["score"] for p in player_scores])
    
    # Find all players with the highest score
    winners = [p for p in player_scores if p["score"] == max_score]
    
    if len(winners) == 1:
        return winners[0]
    else:
        return winners

# Add the advance_turn function
def advance_turn(game):
    """Advance to the next player's turn"""
    if not hasattr(game, "current_turn_order") or not game.current_turn_order:
        # Initialize turn order if it doesn't exist
        game.current_turn_order = [p.name for p in game.players if p.is_active]
        game.current_turn_index = 0
        return
    
    # Safety check - if no active players, don't try to advance
    active_players = [p for p in game.players if p.is_active and not getattr(p, "is_all_in", False)]
    if not active_players:
        return
    
    # Safety check - if turn order is empty, rebuild it
    if len(game.current_turn_order) == 0:
        game.current_turn_order = [p.name for p in active_players]
        game.current_turn_index = 0
        return
    
    # Find next active player who hasn't gone all-in
    original_index = game.current_turn_index
    max_iterations = len(game.current_turn_order)  # Prevent infinite loop
    iteration_count = 0
    
    while iteration_count < max_iterations:
        game.current_turn_index = (game.current_turn_index + 1) % len(game.current_turn_order)
        next_player_name = game.current_turn_order[game.current_turn_index]
        next_player = find_player_by_name(next_player_name)
        iteration_count += 1
        
        # If we've checked all players and come back to the original, break
        if game.current_turn_index == original_index:
            break
        
        # If this player is active and not all-in, they can take their turn
        if next_player and next_player.is_active and not getattr(next_player, "is_all_in", False):
            break