import os
import random
from dotenv import load_dotenv
from typing import List, Optional
from app.models import Card, Player, Game

# Load environment variables
load_dotenv()

# API URLs
API_BASE_URL = "http://192.168.43.238:8000"  # Updated to use the dealer API
PING_URL = f"{API_BASE_URL}/ping"
SHOW_CARDS_URL = f"{API_BASE_URL}/show-cards"
SHOW_POT_URL = f"{API_BASE_URL}/show-pot"
PLAYER_ACTION_URL = f"{API_BASE_URL}/player-action"

# Initialize a global game variable
_game = None

# Define DEALER_API_URL
DEALER_API_URL = "http://192.168.43.238:8000"  # Updated to use the dealer API

def get_game():
    """Get the current active game or create a new one if none exists"""
    global _game
    if _game is None or not getattr(_game, 'is_active', False):
        _game = Game()
        _game.is_active = False
        _game.players = []
        _game.pot = 0
        _game.current_bet = 0
        _game.side_pots = []
        _game.community_cards = []
        _game.current_turn_index = 0
        _game.current_turn_order = []
    return _game

def initialize_game(num_players: int):
    """Initialize a new game with the specified number of players"""
    global _game
    
    # Create new game
    _game = Game()
    _game.is_active = True
    _game.pot = 0
    _game.current_turn_index = 0
    _game.current_turn_order = []
    _game.current_stage = "pre_flop"
    _game.current_bet = 0
    _game.community_cards = []
    _game.players = []
    
    # Initialize players only if num_players > 0
    if num_players > 0:
        for i in range(num_players):
            player = Player(
                name=f"Player {i+1}",
                balance=1000.0
            )
            # Set attributes after initialization
            player.is_active = True
            player.current_bet = 0.0
            player.is_all_in = False
            player.has_acted = False
            player.cards = []
            _game.players.append(player)
            _game.current_turn_order.append(player.name)
    
    # Initialize deck and deal cards
    initialize_deck()
    
    return _game

def initialize_deck():
    """Initialize a standard 52-card deck"""
    game = get_game()
    
    # Card ranks and suits
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
    
    # Create deck
    game.deck = []
    for suit in suits:
        for rank in ranks:
            card = Card(rank=rank, suit=suit, name=f"{rank} of {suit}")
            game.deck.append(card)
    
    # Shuffle deck
    random.shuffle(game.deck)

def deal_cards():
    """Deal cards to players (2 cards per player in Texas Hold'em)"""
    game = get_game()
    
    # Deal 2 cards to each player
    for player in game.players:
        player.cards = []
        for _ in range(2):
            if game.deck:
                card = game.deck.pop(0)
                player.cards.append(card)

def find_player_by_name(name: str) -> Optional[Player]:
    """Find a player by name"""
    game = get_game()
    for player in game.players:
        if player.name == name:
            return player
    return None

def get_game_status():
    """Get the current game status"""
    game = get_game()
    current_turn = None
    if game.is_active and game.current_turn_order:
        current_turn = game.current_turn_order[game.current_turn_index]
    
    players_info = []
    for player in game.players:
        players_info.append({
            "name": player.name,
            "balance": player.balance,
            "is_active": player.is_active,
            "current_bet": player.current_bet,
            "is_all_in": getattr(player, "is_all_in", False),
            "has_acted": getattr(player, "has_acted", False)
        })
    
    # Get side pots information
    side_pots_info = []
    if hasattr(game, "side_pots"):
        side_pots_info = game.side_pots
    
    return {
        "is_active": game.is_active,
        "pot": game.pot,
        "current_turn": current_turn,
        "current_stage": getattr(game, "current_stage", "pre_flop"),
        "current_bet": getattr(game, "current_bet", 0),
        "community_cards": [{"rank": card.rank, "suit": card.suit, "name": card.name} 
                           for card in getattr(game, "community_cards", [])],
        "players": players_info,
        "side_pots": side_pots_info
    }

def end_current_game():
    """End the current game and reset the state"""
    global _game
    if _game:
        # Set game as inactive
        _game.is_active = False
        
        # Reset game state properties
        _game.pot = 0.0
        _game.current_turn_order = []
        _game.current_turn_index = 0
        
        # Reset additional properties that might be added during gameplay
        if hasattr(_game, "current_bet"):
            _game.current_bet = 0
        if hasattr(_game, "community_cards"):
            _game.community_cards = []
        if hasattr(_game, "side_pots"):
            _game.side_pots = []
        if hasattr(_game, "current_stage"):
            delattr(_game, "current_stage")
            
    return {"message": "Game ended and state reset"}

if __name__ == "__main__":
    # Initialize a game when this script is run directly
    game = initialize_game(2)
    print(f"Game initialized with {len(game.players)} players")