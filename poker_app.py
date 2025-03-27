import streamlit as st
import requests
import json
import time
import random
from PIL import Image
import os
import base64
from io import BytesIO

# Set page configuration
st.set_page_config(
    page_title="Poker Player Client",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define API URLs
DEALER_API = "http://192.168.43.238:8000"  # Dealer API
PLAYER_API = "http://localhost:8000"  # Your backend API

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #0D1117;
        color: white;
    }
    .stButton>button {
        background-color: #2ea44f;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #2c974b;
    }
    .card {
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        margin: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .pot {
        font-size: 24px;
        font-weight: bold;
        color: gold;
        text-align: center;
        margin: 20px;
    }
    .player-info {
        background-color: #161b22;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .community-cards {
        display: flex;
        justify-content: center;
        margin: 20px 0;
    }
    .title {
        text-align: center;
        color: #58a6ff;
        font-size: 40px;
        margin-bottom: 30px;
    }
    .subtitle {
        color: #58a6ff;
        font-size: 24px;
        margin: 15px 0;
    }
    .dealer-status {
        background-color: #30363d;
        border-radius: 5px;
        padding: 10px;
        margin: 5px 0;
        font-size: 14px;
    }
    .player-turn {
        background-color: #238636;
        color: white;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
    }
    .waiting-turn {
        background-color: #30363d;
        color: #8b949e;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Card images (we'll generate these)
def get_card_image(card):
    """Generate a simple card image"""
    suits = {
        "hearts": "♥️",
        "diamonds": "♦️",
        "clubs": "♣️",
        "spades": "♠️"
    }
    
    suit_symbol = suits.get(card["suit"].lower(), "?")
    rank = card["rank"]
    
    # Create a simple card image
    img = Image.new('RGB', (100, 140), color='white')
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    # Draw border
    draw.rectangle([(0, 0), (99, 139)], outline='black', width=2)
    
    # Try to use a font, fall back to default if not available
    try:
        font = ImageFont.truetype("Arial", 36)
        small_font = ImageFont.truetype("Arial", 24)
    except IOError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Draw rank and suit
    draw.text((10, 10), rank, fill='black', font=font)
    
    # Color for hearts and diamonds is red
    suit_color = 'red' if card["suit"].lower() in ["hearts", "diamonds"] else 'black'
    draw.text((50, 60), suit_symbol, fill=suit_color, font=font)
    
    # Convert to base64 for display
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

# Initialize session state
if 'player_name' not in st.session_state:
    st.session_state.player_name = ""
if 'joined' not in st.session_state:
    st.session_state.joined = False
if 'cards' not in st.session_state:
    st.session_state.cards = []
if 'community_cards' not in st.session_state:
    st.session_state.community_cards = []
if 'pot' not in st.session_state:
    st.session_state.pot = 0
if 'balance' not in st.session_state:
    st.session_state.balance = 1000
if 'current_bet' not in st.session_state:
    st.session_state.current_bet = 0
if 'game_status' not in st.session_state:
    st.session_state.game_status = {}
if 'is_turn' not in st.session_state:
    st.session_state.is_turn = False
if 'message' not in st.session_state:
    st.session_state.message = ""
if 'error' not in st.session_state:
    st.session_state.error = ""
if 'dealer_status' not in st.session_state:
    st.session_state.dealer_status = "Unknown"
if 'player_api_status' not in st.session_state:
    st.session_state.player_api_status = "Unknown"

# Helper functions for API calls
def call_dealer_api(endpoint, method="GET", data=None):
    """Make API calls to the dealer with error handling"""
    url = f"{DEALER_API}/{endpoint.lstrip('/')}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return {"error": "Unsupported HTTP method"}
            
        response.raise_for_status()
        st.session_state.dealer_status = "Connected"
        return response.json()
    except requests.exceptions.RequestException as e:
        st.session_state.dealer_status = "Disconnected"
        st.session_state.error = f"Dealer API call failed: {str(e)}"
        return {"error": f"Failed to connect to dealer: {str(e)}"}
    except json.JSONDecodeError:
        st.session_state.dealer_status = "Error"
        st.session_state.error = "Failed to parse dealer response"
        return {"error": "Invalid response from dealer"}
    except Exception as e:
        st.session_state.dealer_status = "Error"
        st.session_state.error = f"Unexpected dealer error: {str(e)}"
        return {"error": f"Unexpected error: {str(e)}"}

def call_player_api(endpoint, method="GET", data=None):
    """Make API calls to your player backend with error handling"""
    url = f"{PLAYER_API}/{endpoint.lstrip('/')}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return {"error": "Unsupported HTTP method"}
            
        response.raise_for_status()
        st.session_state.player_api_status = "Connected"
        return response.json()
    except requests.exceptions.RequestException as e:
        st.session_state.player_api_status = "Disconnected"
        st.session_state.error = f"Player API call failed: {str(e)}"
        return {"error": f"Failed to connect to player API: {str(e)}"}
    except json.JSONDecodeError:
        st.session_state.player_api_status = "Error"
        st.session_state.error = "Failed to parse player API response"
        return {"error": "Invalid response from player API"}
    except Exception as e:
        st.session_state.player_api_status = "Error"
        st.session_state.error = f"Unexpected player API error: {str(e)}"
        return {"error": f"Unexpected error: {str(e)}"}

def call_api(endpoint, method="GET", data=None):
    """Try player API first, then fall back to dealer API if needed"""
    # Try player API first
    response = call_player_api(endpoint, method, data)
    
    # If player API fails, try dealer API
    if "error" in response:
        dealer_response = call_dealer_api(endpoint, method, data)
        if "error" not in dealer_response:
            return dealer_response
    else:
        return response
    
    # If both fail, return the player API error
    return response

def join_game():
    """Join the poker game"""
    if not st.session_state.player_name:
        st.session_state.error = "Please enter a player name"
        return
    
    response = call_api("join_game", method="POST", data={
        "name": st.session_state.player_name,
        "host_url": "streamlit_app"
    })
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    st.session_state.joined = True
    st.session_state.message = f"Welcome to the game, {st.session_state.player_name}!"
    
    # Get initial cards
    get_cards()

def get_cards():
    """Get player's cards"""
    if not st.session_state.player_name:
        return
    
    response = call_api(f"show_cards?player_name={st.session_state.player_name}")
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    if "cards" in response:
        st.session_state.cards = response["cards"]

def get_community_cards():
    """Get community cards"""
    response = call_api("community_cards")
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    if "community_cards" in response:
        st.session_state.community_cards = response["community_cards"]

def get_pot():
    """Get current pot amount"""
    response = call_api("show_pot")
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    if "pot" in response:
        st.session_state.pot = response["pot"]
    if "current_bet" in response:
        st.session_state.current_bet = response["current_bet"]

def check_turn():
    """Check if it's the player's turn"""
    if not st.session_state.player_name:
        return
    
    response = call_api(f"is_your_turn?player_name={st.session_state.player_name}")
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    st.session_state.is_turn = response.get("is_your_turn", False)
    return response

# Initialize game history in session state
if 'game_history' not in st.session_state:
    st.session_state.game_history = []

# Function to record game actions
def record_action(action, details):
    """Record an action in the game history"""
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.game_history.append({
        "time": timestamp,
        "action": action,
        "details": details
    })
    # Keep only the last 20 actions
    if len(st.session_state.game_history) > 20:
        st.session_state.game_history.pop(0)

# Update the place_bet function to record history
def place_bet(amount):
    """Place a bet"""
    if not st.session_state.player_name:
        st.session_state.error = "Please join the game first"
        return
    
    response = call_api("place_bet", method="POST", data={
        "name": st.session_state.player_name,
        "amount": amount
    })
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    st.session_state.message = f"You bet ${amount}"
    if "player_balance" in response:
        st.session_state.balance = response["player_balance"]
    
    # Record the action in history
    record_action("Bet", f"{st.session_state.player_name} bet ${amount}")
    
    # Update game state
    get_pot()
    check_turn()

# Update the fold function to record history
def fold():
    """Fold current hand"""
    if not st.session_state.player_name:
        st.session_state.error = "Please join the game first"
        return
    
    response = call_api("fold", method="POST", data={
        "name": st.session_state.player_name
    })
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    st.session_state.message = "You folded"
    
    # Record the action in history
    record_action("Fold", f"{st.session_state.player_name} folded")
    
    # Update game state
    check_turn()

# Add game history display to the main interface
if st.session_state.joined:
    # Display messages/errors
    if st.session_state.message:
        st.success(st.session_state.message)
    if st.session_state.error:
        st.error(st.session_state.error)
    
    # Middle section - Community cards
    st.markdown("<h2 class='subtitle'>Community Cards</h2>", unsafe_allow_html=True)
    
    if st.session_state.community_cards:
        cols = st.columns(5)
        for i, card in enumerate(st.session_state.community_cards[:5]):
            with cols[i]:
                card_img = get_card_image(card)
                st.markdown(f"<img src='{card_img}' style='width:100%;'>", unsafe_allow_html=True)
    else:
        st.info("No community cards yet")
    
    # Player section
    st.markdown("<h2 class='subtitle'>Your Hand</h2>", unsafe_allow_html=True)
    
    # Player info
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown(f"<div class='player-info'>Player: {st.session_state.player_name}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='player-info'>Balance: ${st.session_state.balance}</div>", unsafe_allow_html=True)
    with col3:
        turn_status = "Your Turn!" if st.session_state.is_turn else "Waiting..."
        st.markdown(f"<div class='player-info'>Status: {turn_status}</div>", unsafe_allow_html=True)
    
    # Player cards
    if st.session_state.cards:
        cols = st.columns(2)
        for i, card in enumerate(st.session_state.cards[:2]):
            with cols[i]:
                card_img = get_card_image(card)
                st.markdown(f"<img src='{card_img}' style='width:100%;'>", unsafe_allow_html=True)
    else:
        st.info("No cards dealt yet")
    
    # Action buttons
    st.markdown("<h2 class='subtitle'>Actions</h2>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("Check/Call", disabled=not st.session_state.is_turn):
            # Call the current bet or check if no bet
            current_bet = st.session_state.current_bet
            if current_bet > 0:
                place_bet(current_bet)
            else:
                place_bet(0)
                st.session_state.message = "You checked"
    
    with col2:
        bet_amount = st.number_input("Bet Amount", min_value=1, value=10, step=5)
    
    with col3:
        if st.button("Bet/Raise", disabled=not st.session_state.is_turn):
            place_bet(bet_amount)
    
    with col4:
        if st.button("Fold", disabled=not st.session_state.is_turn):
            fold()
    
    # Game status
    st.markdown("<h2 class='subtitle'>Game Status</h2>", unsafe_allow_html=True)
    
    if st.session_state.game_status:
        # Display active players
        if "players" in st.session_state.game_status:
            active_players = [p for p in st.session_state.game_status["players"] if p.get("is_active", False)]
            st.write(f"Active Players: {len(active_players)}")
            
            # Create a table of players
            player_data = []
            for p in st.session_state.game_status["players"]:
                player_data.append({
                    "Name": p.get("name", "Unknown"),
                    "Balance": f"${p.get('balance', 0)}",
                    "Status": "Active" if p.get("is_active", False) else "Folded",
                    "Current Bet": f"${p.get('current_bet', 0)}"
                })
            
            if player_data:
                st.table(player_data)
        
        # Show current stage
        if "current_stage" in st.session_state.game_status:
            st.write(f"Current Stage: {st.session_state.game_status['current_stage'].upper()}")
        
        # Show whose turn it is
        if "current_turn" in st.session_state.game_status:
            current_turn = st.session_state.game_status["current_turn"]
            if current_turn:
                st.write(f"Current Turn: {current_turn}")

# Auto-refresh game state every few seconds if joined
def refresh_game_state():
    """Refresh all game state"""
    get_cards()
    get_community_cards()
    get_pot()
    check_turn()
    get_game_status()
    
    # Clear any old messages
    if st.session_state.message:
        # Keep messages for a short time then clear them
        time.sleep(0.5)
        st.session_state.message = ""
    if st.session_state.error:
        time.sleep(1)
        st.session_state.error = ""

def get_game_status():
    """Get current game status"""
    response = call_api("game_status")
    
    if "error" in response:
        st.session_state.error = response["error"]
        return
    
    st.session_state.game_status = response

# Add hand rankings to sidebar
with st.sidebar:
    st.subheader("Hand Rankings")
    hand_rankings = {
        "Royal Flush": "A, K, Q, J, 10 of the same suit",
        "Straight Flush": "Five consecutive cards of the same suit",
        "Four of a Kind": "Four cards of the same rank",
        "Full House": "Three of a kind plus a pair",
        "Flush": "Five cards of the same suit",
        "Straight": "Five consecutive cards",
        "Three of a Kind": "Three cards of the same rank",
        "Two Pair": "Two different pairs",
        "Pair": "Two cards of the same rank",
        "High Card": "Highest card plays"
    }
    
    for hand, description in hand_rankings.items():
        st.markdown(f"**{hand}**: {description}")

# Main app layout
st.markdown("<h1 class='title'>♠️ Texas Hold'em Poker ♣️</h1>", unsafe_allow_html=True)

# Sidebar for API status
with st.sidebar:
    st.title("API Status")
    st.markdown(f"<div class='dealer-status'>Dealer API: {st.session_state.dealer_status}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='dealer-status'>Player API: {st.session_state.player_api_status}</div>", unsafe_allow_html=True)
    
    # Add API URL configuration
    st.subheader("API Configuration")
    new_dealer_api = st.text_input("Dealer API URL", DEALER_API)
    new_player_api = st.text_input("Player API URL", PLAYER_API)
    
    if st.button("Update API URLs"):
        DEALER_API = new_dealer_api
        PLAYER_API = new_player_api
        st.success("API URLs updated!")
        
    # Add a ping button to test connections
    if st.button("Test Connections"):
        dealer_response = call_dealer_api("ping")
        player_response = call_player_api("ping")
        
        if "error" not in dealer_response:
            st.success("Dealer API connection successful!")
        else:
            st.error(f"Dealer API connection failed: {dealer_response['error']}")
            
        if "error" not in player_response:
            st.success("Player API connection successful!")
        else:
            st.error(f"Player API connection failed: {player_response['error']}")

# Login/Join section - This part was missing
if not st.session_state.joined:
    st.markdown("<h2 class='subtitle'>Join the Game</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.session_state.player_name = st.text_input("Enter your name:", key="name_input")
    with col2:
        if st.button("Join Game"):
            join_game()
else:
    # Game interface
    # Top section - Game info and refresh
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Refresh Game"):
            refresh_game_state()
    with col2:
        st.markdown(f"<div class='pot'>Current Pot: ${st.session_state.pot}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("New Game"):
            call_api("start_game", method="POST")
            refresh_game_state()
    
    # Display messages/errors
    if st.session_state.message:
        st.success(st.session_state.message)
    if st.session_state.error:
        st.error(st.session_state.error)
    
    # Middle section - Community cards
    st.markdown("<h2 class='subtitle'>Community Cards</h2>", unsafe_allow_html=True)
    
    if st.session_state.community_cards:
        cols = st.columns(5)
        for i, card in enumerate(st.session_state.community_cards[:5]):
            with cols[i]:
                card_img = get_card_image(card)
                st.markdown(f"<img src='{card_img}' style='width:100%;'>", unsafe_allow_html=True)
    else:
        st.info("No community cards yet")
    
    # Player section
    st.markdown("<h2 class='subtitle'>Your Hand</h2>", unsafe_allow_html=True)
    
    # Player info
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown(f"<div class='player-info'>Player: {st.session_state.player_name}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='player-info'>Balance: ${st.session_state.balance}</div>", unsafe_allow_html=True)
    with col3:
        turn_status = "Your Turn!" if st.session_state.is_turn else "Waiting..."
        st.markdown(f"<div class='player-info'>Status: {turn_status}</div>", unsafe_allow_html=True)
    
    # Player cards
    if st.session_state.cards:
        cols = st.columns(2)
        for i, card in enumerate(st.session_state.cards[:2]):
            with cols[i]:
                card_img = get_card_image(card)
                st.markdown(f"<img src='{card_img}' style='width:100%;'>", unsafe_allow_html=True)
    else:
        st.info("No cards dealt yet")
    
    # Action buttons
    st.markdown("<h2 class='subtitle'>Actions</h2>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("Check/Call", disabled=not st.session_state.is_turn):
            # Call the current bet or check if no bet
            current_bet = st.session_state.current_bet
            if current_bet > 0:
                place_bet(current_bet)
            else:
                place_bet(0)
                st.session_state.message = "You checked"
    
    with col2:
        bet_amount = st.number_input("Bet Amount", min_value=1, value=10, step=5)
    
    with col3:
        if st.button("Bet/Raise", disabled=not st.session_state.is_turn):
            place_bet(bet_amount)
    
    with col4:
        if st.button("Fold", disabled=not st.session_state.is_turn):
            fold()
    
    # Game status
    st.markdown("<h2 class='subtitle'>Game Status</h2>", unsafe_allow_html=True)
    
    if st.session_state.game_status:
        # Display active players
        if "players" in st.session_state.game_status:
            active_players = [p for p in st.session_state.game_status["players"] if p.get("is_active", False)]
            st.write(f"Active Players: {len(active_players)}")
            
            # Create a table of players
            player_data = []
            for p in st.session_state.game_status["players"]:
                player_data.append({
                    "Name": p.get("name", "Unknown"),
                    "Balance": f"${p.get('balance', 0)}",
                    "Status": "Active" if p.get("is_active", False) else "Folded",
                    "Current Bet": f"${p.get('current_bet', 0)}"
                })
            
            if player_data:
                st.table(player_data)
        
        # Show current stage
        if "current_stage" in st.session_state.game_status:
            st.write(f"Current Stage: {st.session_state.game_status['current_stage'].upper()}")
        
        # Show whose turn it is
        if "current_turn" in st.session_state.game_status:
            current_turn = st.session_state.game_status["current_turn"]
            if current_turn:
                st.write(f"Current Turn: {current_turn}")
    
    # Game history
    st.markdown("<h2 class='subtitle'>Game History</h2>", unsafe_allow_html=True)
    
    if st.session_state.game_history:
        history_data = []
        for entry in reversed(st.session_state.game_history):
            history_data.append({
                "Time": entry["time"],
                "Action": entry["action"],
                "Details": entry["details"]
            })
        
        st.table(history_data)
    else:
        st.info("No game history yet")
    
    # Auto-refresh game state every few seconds
    placeholder = st.empty()
    with placeholder.container():
        refresh_game_state()