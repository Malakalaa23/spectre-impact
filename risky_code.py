# risky_code.py – Has real bugs for the AI to find

def process_payment(amount, user):
    if not user:
        raise ValueError("User cannot be None")
    # BUG: Doesn't update the user's balance
    return user.balance - amount

def calculate_discount(amount, percentage):
    # BUG: No validation for percentage range
    return amount * (percentage / 100)

def refund(amount, user):
    # BUG: No validation for amount
    user.balance += amount
