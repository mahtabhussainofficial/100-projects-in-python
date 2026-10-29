import random

def deal_card():
    """Returns a random card from the deck."""
    cards = [11, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10]
    return random.choice(cards)

def calculate_score(cards):
    """Calculates score and handles Blackjack (0) and Ace conversions."""
    if sum(cards) == 21 and len(cards) == 2:
        return 0

    while 11 in cards and sum(cards) > 21:
        cards.remove(11)
        cards.append(1)

    return sum(cards)

def compare(u_score, com_score):
    if u_score == com_score:
        return "Draw!"
    elif com_score == 0:
        return "You lose! Dealer got Blackjack."
    elif u_score == 0:
        return "You win with a Blackjack!"
    elif u_score > 21:
        return "You went over 21. You lose!"
    elif com_score > 21:
        return "Dealer went over 21. You win!"
    elif u_score > com_score:
        return "You win!"
    else:
        return "You lose!"

def play_game():
    user_card = []
    computer_card = []
    is_game_over = False

    for _ in range(2):
        user_card.append(deal_card())
        computer_card.append(deal_card())

    while not is_game_over:
        user_score = calculate_score(user_card)
        computer_score = calculate_score(computer_card)
        print(f"Your cards: {user_card}, current score: {user_score}")
        print(f"Computer's first card: {computer_card[0]}")

        if user_score == 0 or computer_score == 0 or user_score > 21:
            is_game_over = True
        else:
            choice = input("Type 'y' to get another card, 'n' to pass: ").strip().lower()
            if choice == "y":
                user_card.append(deal_card())
            else:
                is_game_over = True

    # Dealer draws until at least 17, unless player already busted or dealer has blackjack
    if user_score <= 21:
        while computer_score != 0 and computer_score < 17:
            computer_card.append(deal_card())
            computer_score = calculate_score(computer_card)

    print(f"\nYour final hand: {user_card}, final score: {user_score}")
    print(f"Computer's final hand: {computer_card}, final score: {computer_score}")
    print(compare(user_score, computer_score))

while input("Do you want to play a game of Blackjack? Type 'y' or 'n': ").strip().lower() == "y":
    print("\n" * 20)
    play_game()